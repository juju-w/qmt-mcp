using System.Collections.ObjectModel;

namespace QmtMcp.Launcher.Core;

public sealed record LauncherProfile
{
    public int SchemaVersion { get; init; } = 1;
    public required string Id { get; init; }
    public required string DisplayName { get; init; }
    public required string ClientPath { get; init; }
    public required string WorkingDirectory { get; init; }
    public required string XtquantRoot { get; init; }
    public required string UserdataPath { get; init; }
    public string McpHost { get; init; } = "127.0.0.1";
    public int McpPort { get; init; } = 18765;
    public required string TokenSecretId { get; init; }
    public bool AutoStartLauncher { get; init; }
    public bool RestartTerminal { get; init; }
    public DateTimeOffset CreatedAt { get; init; }
    public DateTimeOffset UpdatedAt { get; init; }
}

public sealed record ProfileDocument
{
    public int SchemaVersion { get; init; } = 1;
    public string? ActiveProfileId { get; init; }
    public IReadOnlyList<LauncherProfile> Profiles { get; init; } = [];
}

public sealed record BrokerSelection(
    string ClientPath,
    string? XtquantRoot = null,
    string? UserdataPath = null);

public sealed record ResolvedBroker(
    string ClientPath,
    string WorkingDirectory,
    string QmtRoot,
    string XtquantRoot,
    string UserdataPath,
    IReadOnlyList<string> Evidence);

public sealed record ResolutionFailure(
    string Code,
    string Message,
    IReadOnlyList<string> Candidates);

public sealed record ResolutionResult
{
    private ResolutionResult(ResolvedBroker? broker, ResolutionFailure? failure)
    {
        Broker = broker;
        Failure = failure;
    }

    public bool IsSuccess => Broker is not null;
    public ResolvedBroker? Broker { get; }
    public ResolutionFailure? Failure { get; }

    public static ResolutionResult Success(ResolvedBroker broker) => new(broker, null);

    public static ResolutionResult Fail(string code, string message, IEnumerable<string>? candidates = null) =>
        new(null, new ResolutionFailure(code, message, candidates?.ToArray() ?? []));
}

public sealed record DiscoveryCandidate(string ClientPath, string Source, int Confidence);

public sealed record LaunchCommand
{
    public required string Executable { get; init; }
    public IReadOnlyList<string> Arguments { get; init; } = [];
    public required string WorkingDirectory { get; init; }
    public IReadOnlyDictionary<string, string> Environment { get; init; } =
        new ReadOnlyDictionary<string, string>(new Dictionary<string, string>());
    public bool UseShellExecute { get; init; }
    public bool RedirectOutput { get; init; }
}

public enum LauncherState
{
    Stopped,
    Validating,
    StartingMcp,
    StartingTerminal,
    WaitingForLogin,
    Ready,
    Degraded,
    Faulted,
    Stopping,
}

public enum TerminalOwnership
{
    None,
    Attached,
    Launched,
}

public sealed record LauncherError(
    string Code,
    string Component,
    string Message,
    string? Detail,
    bool Retryable,
    DateTimeOffset OccurredAt);

public sealed record LauncherSnapshot
{
    public LauncherState State { get; init; } = LauncherState.Stopped;
    public string? ProfileId { get; init; }
    public TerminalOwnership TerminalOwnership { get; init; }
    public int? TerminalPid { get; init; }
    public int? McpPid { get; init; }
    public bool McpLive { get; init; }
    public string XtdataState { get; init; } = "unknown";
    public string XttradeState { get; init; } = "disabled";
    public string Summary { get; init; } = "Stopped";
    public LauncherError? LastError { get; init; }
    public DateTimeOffset UpdatedAt { get; init; }
}

public sealed record HealthObservation(
    bool McpLive,
    string XtdataState,
    string XttradeState,
    string Summary);
