using System.Net.Http.Headers;
using System.Text.Json;

namespace QmtMcp.Launcher.Core;

public interface IManagedProcess : IAsyncDisposable
{
    int Id { get; }
    bool HasExited { get; }
    bool IsOwned { get; }
    Task<int> WaitForExitAsync(CancellationToken cancellationToken);
    Task StopAsync(CancellationToken cancellationToken);
}

public interface IProcessHost : IBrokerProcessInspector
{
    Task<IManagedProcess?> FindByExecutablePathAsync(string executablePath, CancellationToken cancellationToken);
    Task<IManagedProcess> StartAsync(LaunchCommand command, SecretRedactor redactor, CancellationToken cancellationToken);
}

public interface IHealthProbe
{
    Task<HealthObservation> ProbeAsync(LauncherProfile profile, string token, CancellationToken cancellationToken);
}

public sealed class HttpHealthProbe(HttpClient httpClient) : IHealthProbe
{
    public async Task<HealthObservation> ProbeAsync(
        LauncherProfile profile,
        string token,
        CancellationToken cancellationToken)
    {
        var baseUri = new Uri($"http://{profile.McpHost}:{profile.McpPort}", UriKind.Absolute);
        try
        {
            using var liveResponse = await httpClient.GetAsync(new Uri(baseUri, "/livez"), cancellationToken);
            if (!liveResponse.IsSuccessStatusCode)
            {
                return new HealthObservation(false, "unknown", "unknown", "MCP server is starting");
            }

            using var request = new HttpRequestMessage(HttpMethod.Get, new Uri(baseUri, "/healthz"));
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var healthResponse = await httpClient.SendAsync(request, cancellationToken);
            if (!healthResponse.IsSuccessStatusCode)
            {
                return new HealthObservation(true, "unknown", "unknown", "MCP health authorization failed");
            }

            await using var stream = await healthResponse.Content.ReadAsStreamAsync(cancellationToken);
            using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
            var root = document.RootElement;
            var xtdata = ReadString(root, "xtdata", "unknown");
            var xttrade = ReadString(root, "xttrade", "disabled");
            var summary = string.Equals(xtdata, "ready", StringComparison.OrdinalIgnoreCase)
                ? "Market data ready"
                : "Waiting for QMT login";
            return new HealthObservation(true, xtdata, xttrade, summary);
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException or JsonException)
        {
            return new HealthObservation(false, "unknown", "unknown", "MCP server is starting");
        }
    }

    private static string ReadString(JsonElement root, string propertyName, string fallback) =>
        root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? fallback
            : fallback;
}

public sealed class LauncherOrchestrator : IAsyncDisposable
{
    private readonly CommandFactory commandFactory;
    private readonly IProcessHost processHost;
    private readonly IHealthProbe healthProbe;
    private readonly RestartPolicy restartPolicy;
    private readonly TimeSpan pollInterval;
    private readonly SemaphoreSlim lifecycle = new(1, 1);
    private readonly LauncherStateMachine stateMachine = new();
    private CancellationTokenSource? monitorCancellation;
    private Task? monitorTask;
    private IManagedProcess? mcpProcess;
    private IManagedProcess? terminalProcess;

    public LauncherOrchestrator(
        CommandFactory commandFactory,
        IProcessHost processHost,
        IHealthProbe healthProbe,
        RestartPolicy? restartPolicy = null,
        TimeSpan? pollInterval = null)
    {
        this.commandFactory = commandFactory;
        this.processHost = processHost;
        this.healthProbe = healthProbe;
        this.restartPolicy = restartPolicy ?? new RestartPolicy();
        this.pollInterval = pollInterval ?? TimeSpan.FromSeconds(2);
    }

    public event EventHandler<LauncherSnapshot>? SnapshotChanged;

    public LauncherSnapshot Snapshot => stateMachine.Snapshot;

    public async Task StartAsync(
        LauncherProfile profile,
        ResolvedBroker broker,
        string token,
        string version,
        CancellationToken cancellationToken = default)
    {
        await lifecycle.WaitAsync(cancellationToken);
        try
        {
            if (monitorTask is not null)
            {
                throw new InvalidOperationException("A launcher profile is already active.");
            }

            Publish(stateMachine.BeginStart(profile.Id));
            var validationErrors = ProfileValidator.Validate(profile);
            if (validationErrors.Count > 0)
            {
                Publish(stateMachine.Fail(
                    "profile_invalid",
                    "profile",
                    "Profile validation failed",
                    string.Join(" ", validationErrors),
                    true));
                return;
            }

            var mcpCommand = commandFactory.CreateMcp(profile, broker, token, version);
            var redactor = new SecretRedactor([token]);
            mcpProcess = await processHost.StartAsync(mcpCommand, redactor, cancellationToken);
            Publish(stateMachine.McpStarted(mcpProcess.Id));

            terminalProcess = await processHost.FindByExecutablePathAsync(broker.ClientPath, cancellationToken);
            var ownership = TerminalOwnership.Attached;
            if (terminalProcess is null)
            {
                terminalProcess = await processHost.StartAsync(
                    CommandFactory.CreateTerminal(broker),
                    redactor,
                    cancellationToken);
                ownership = TerminalOwnership.Launched;
            }

            Publish(stateMachine.TerminalObserved(terminalProcess.Id, ownership));
            monitorCancellation = new CancellationTokenSource();
            monitorTask = MonitorAsync(profile, token, mcpCommand, redactor, monitorCancellation.Token);
        }
        catch (Exception exception)
        {
            Publish(stateMachine.Fail(
                "startup_failed",
                "launcher",
                "Unable to start QMT-MCP",
                new SecretRedactor([token]).Redact(exception.Message),
                true));
            await StopProcessesAsync(CancellationToken.None);
        }
        finally
        {
            lifecycle.Release();
        }
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        await lifecycle.WaitAsync(cancellationToken);
        try
        {
            if (monitorTask is null && mcpProcess is null)
            {
                Publish(stateMachine.CompleteStop());
                return;
            }

            Publish(stateMachine.BeginStop());
            if (monitorCancellation is not null)
            {
                await monitorCancellation.CancelAsync();
            }

            if (monitorTask is not null)
            {
                try
                {
                    await monitorTask.WaitAsync(cancellationToken);
                }
                catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                {
                    throw;
                }
                catch (OperationCanceledException)
                {
                    // Expected when the monitor's private token is cancelled.
                }
            }

            await StopProcessesAsync(cancellationToken);
            monitorTask = null;
            monitorCancellation?.Dispose();
            monitorCancellation = null;
            Publish(stateMachine.CompleteStop());
        }
        finally
        {
            lifecycle.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync();
        lifecycle.Dispose();
    }

    private async Task MonitorAsync(
        LauncherProfile profile,
        string token,
        LaunchCommand mcpCommand,
        SecretRedactor redactor,
        CancellationToken cancellationToken)
    {
        var restartAttempts = 0;
        while (!cancellationToken.IsCancellationRequested)
        {
            if (mcpProcess is null || mcpProcess.HasExited)
            {
                Publish(stateMachine.ApplyHealth(
                    new HealthObservation(false, "unknown", "unknown", "MCP server stopped")));
                var delay = restartPolicy.GetDelay(restartAttempts++);
                if (delay is null)
                {
                    Publish(stateMachine.Fail(
                        "mcp_restart_exhausted",
                        "mcp",
                        "MCP server restart limit reached",
                        null,
                        true));
                    return;
                }

                await Task.Delay(delay.Value, cancellationToken);
                if (mcpProcess is not null)
                {
                    await mcpProcess.DisposeAsync();
                }

                mcpProcess = await processHost.StartAsync(mcpCommand, redactor, cancellationToken);
                Publish(stateMachine.McpStarted(mcpProcess.Id));
            }

            var observation = await healthProbe.ProbeAsync(profile, token, cancellationToken);
            Publish(stateMachine.ApplyHealth(observation));
            if (observation.McpLive)
            {
                restartAttempts = 0;
            }

            if (terminalProcess is not null && terminalProcess.HasExited)
            {
                Publish(stateMachine.ApplyHealth(
                    observation with { XtdataState = "degraded", Summary = "QMT terminal stopped" }));
            }

            await Task.Delay(pollInterval, cancellationToken);
        }
    }

    private async Task StopProcessesAsync(CancellationToken cancellationToken)
    {
        if (mcpProcess is not null)
        {
            await mcpProcess.StopAsync(cancellationToken);
            await mcpProcess.DisposeAsync();
            mcpProcess = null;
        }

        if (terminalProcess is not null)
        {
            await terminalProcess.DisposeAsync();
            terminalProcess = null;
        }
    }

    private void Publish(LauncherSnapshot snapshot) => SnapshotChanged?.Invoke(this, snapshot);
}
