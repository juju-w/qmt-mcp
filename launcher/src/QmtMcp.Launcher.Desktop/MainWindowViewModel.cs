using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Windows.Input;
using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Desktop;

internal sealed class MainWindowViewModel : INotifyPropertyChanged
{
    private static readonly JsonSerializerOptions ConnectionJsonOptions = new()
    {
        WriteIndented = true,
    };

    private readonly LauncherRuntime runtime;
    private readonly Action<Action> dispatch;
    private LauncherProfile? profile;
    private ResolvedBroker? resolvedBroker;
    private string profileName = "QMT";
    private string clientPath = string.Empty;
    private string xtquantRoot = string.Empty;
    private string userdataPath = string.Empty;
    private int mcpPort = 18765;
    private string stateLabel = "Stopped";
    private string stateDetail = "Select a QMT client to create a local profile.";
    private string qmtStatus = "Not configured";
    private string mcpStatus = "Stopped";
    private string xtdataStatus = "Unknown";
    private string xttradeStatus = "Disabled";
    private string resolutionStatus = "No client selected";
    private string lastDiagnosticPath = "No diagnostic archive exported";
    private bool autoStartLauncher;
    private bool busy;

    public MainWindowViewModel(LauncherRuntime runtime, Action<Action> dispatch)
    {
        this.runtime = runtime;
        this.dispatch = dispatch;
        SaveCommand = new AsyncCommand(SaveAsync, () => !Busy, ShowError);
        StartCommand = new AsyncCommand(StartAsync, () => !Busy, ShowError);
        StopCommand = new AsyncCommand(StopAsync, () => !Busy, ShowError);
        ResolveCommand = new AsyncCommand(ResolveAsync, () => !Busy, ShowError);
        DiscoverCommand = new AsyncCommand(DiscoverAsync, () => !Busy, ShowError);
        ExportDiagnosticsCommand = new AsyncCommand(ExportDiagnosticsAsync, () => !Busy, ShowError);
        OpenLogsCommand = new AsyncCommand(() =>
        {
            runtime.OpenLogs();
            return Task.CompletedTask;
        }, () => !Busy, ShowError);
        runtime.Orchestrator.SnapshotChanged += OnSnapshotChanged;
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand SaveCommand { get; }
    public ICommand StartCommand { get; }
    public ICommand StopCommand { get; }
    public ICommand ResolveCommand { get; }
    public ICommand DiscoverCommand { get; }
    public ICommand ExportDiagnosticsCommand { get; }
    public ICommand OpenLogsCommand { get; }

    public string ProfileName { get => profileName; set => Set(ref profileName, value); }
    public string ClientPath { get => clientPath; set => Set(ref clientPath, value); }
    public string XtquantRoot { get => xtquantRoot; set => Set(ref xtquantRoot, value); }
    public string UserdataPath { get => userdataPath; set => Set(ref userdataPath, value); }
    public int McpPort { get => mcpPort; set { if (Set(ref mcpPort, value)) OnPropertyChanged(nameof(McpUrl)); } }
    public string McpUrl => $"http://127.0.0.1:{McpPort}/mcp";
    public string StateLabel { get => stateLabel; private set => Set(ref stateLabel, value); }
    public string StateDetail { get => stateDetail; private set => Set(ref stateDetail, value); }
    public string QmtStatus { get => qmtStatus; private set => Set(ref qmtStatus, value); }
    public string McpStatus { get => mcpStatus; private set => Set(ref mcpStatus, value); }
    public string XtdataStatus { get => xtdataStatus; private set => Set(ref xtdataStatus, value); }
    public string XttradeStatus { get => xttradeStatus; private set => Set(ref xttradeStatus, value); }
    public string ResolutionStatus { get => resolutionStatus; private set => Set(ref resolutionStatus, value); }
    public string LastDiagnosticPath { get => lastDiagnosticPath; private set => Set(ref lastDiagnosticPath, value); }
    public bool AutoStartLauncher { get => autoStartLauncher; set => Set(ref autoStartLauncher, value); }
    public bool Busy { get => busy; private set { if (Set(ref busy, value)) RefreshCommands(); } }
    public bool IsRunning => runtime.Orchestrator.Snapshot.State is not LauncherState.Stopped and not LauncherState.Faulted;

    public async Task InitializeAsync()
    {
        Busy = true;
        try
        {
            var document = await runtime.Profiles.LoadAsync();
            profile = document.Profiles.FirstOrDefault(item => item.Id == document.ActiveProfileId)
                ?? (document.Profiles.Count > 0 ? document.Profiles[0] : null);
            if (profile is null)
            {
                if (!OperatingSystem.IsWindows())
                {
                    ClientPath = @"D:\QMT\bin.x64\XtItClient.exe";
                    XtquantRoot = @"D:\QMT";
                    UserdataPath = @"D:\QMT\userdata_mini";
                    await ResolveAsync();
                }

                return;
            }

            ApplyProfile(profile);
            await ResolveAsync();
        }
        catch (InvalidDataException exception)
        {
            ShowError(exception);
        }
        finally
        {
            Busy = false;
        }
    }

    public async Task ResolveAsync()
    {
        await Task.Yield();
        var result = runtime.Resolver.Resolve(
            new BrokerSelection(ClientPath, EmptyToNull(XtquantRoot), EmptyToNull(UserdataPath)));
        if (!result.IsSuccess)
        {
            resolvedBroker = null;
            ResolutionStatus = result.Failure?.Message ?? "Unable to resolve QMT paths.";
            QmtStatus = "Configuration incomplete";
            return;
        }

        resolvedBroker = result.Broker;
        ClientPath = resolvedBroker!.ClientPath;
        XtquantRoot = resolvedBroker.XtquantRoot;
        UserdataPath = resolvedBroker.UserdataPath;
        ResolutionStatus = "Client, xtquant, and userdata paths validated";
        QmtStatus = "Configured";
    }

    public async Task SaveAsync()
    {
        Busy = true;
        try
        {
            await SaveProfileAsync();
        }
        finally
        {
            Busy = false;
        }
    }

    public async Task StartAsync()
    {
        Busy = true;
        try
        {
            if (runtime.Orchestrator.Snapshot.State != LauncherState.Stopped)
            {
                await runtime.Orchestrator.StopAsync();
            }

            await SaveProfileAsync();
            if (profile is null || resolvedBroker is null)
            {
                return;
            }

            var token = await runtime.Secrets.GetAsync(profile.TokenSecretId);
            var version = typeof(MainWindowViewModel).Assembly.GetName().Version?.ToString() ?? "dev";
            await runtime.Orchestrator.StartAsync(profile, resolvedBroker, token, version);
        }
        finally
        {
            Busy = false;
        }
    }

    public async Task StopAsync()
    {
        Busy = true;
        try
        {
            await runtime.Orchestrator.StopAsync();
        }
        finally
        {
            Busy = false;
        }
    }

    public async Task DiscoverAsync()
    {
        Busy = true;
        try
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            var candidates = await runtime.DiscoverBrokersAsync(timeout.Token);
            if (candidates.Count == 0)
            {
                ResolutionStatus = "No QMT client found. Select the executable manually.";
                return;
            }

            var selected = candidates[0];
            ClientPath = selected.ClientPath;
            XtquantRoot = string.Empty;
            UserdataPath = string.Empty;
            await ResolveAsync();
            ResolutionStatus = resolvedBroker is null
                ? ResolutionStatus
                : $"Detected from {selected.Source}; paths validated";
        }
        finally
        {
            Busy = false;
        }
    }

    public async Task<string> GetConnectionSnippetAsync()
    {
        if (profile is null)
        {
            await SaveAsync();
        }

        if (profile is null)
        {
            throw new InvalidOperationException("Save a valid profile before copying the connection.");
        }

        var token = await runtime.Secrets.GetAsync(profile.TokenSecretId);
        return JsonSerializer.Serialize(
            new
            {
                mcpServers = new Dictionary<string, object>
                {
                    ["qmt"] = new
                    {
                        url = McpUrl,
                        headers = new Dictionary<string, string>
                        {
                            ["Authorization"] = $"Bearer {token}",
                        },
                    },
                },
            },
            ConnectionJsonOptions);
    }

    private async Task ExportDiagnosticsAsync()
    {
        string? token = null;
        if (profile is not null)
        {
            token = await runtime.Secrets.GetAsync(profile.TokenSecretId);
        }

        LastDiagnosticPath = await runtime.ExportDiagnosticsAsync(profile, token, CancellationToken.None);
    }

    private void OnSnapshotChanged(object? sender, LauncherSnapshot snapshot) => dispatch(() =>
    {
        StateLabel = snapshot.State switch
        {
            LauncherState.Ready => "Ready",
            LauncherState.WaitingForLogin => "Waiting for login",
            LauncherState.Degraded => "Degraded",
            LauncherState.Faulted => "Action required",
            LauncherState.Stopped => "Stopped",
            _ => "Starting",
        };
        StateDetail = snapshot.Summary;
        QmtStatus = snapshot.TerminalPid is null
            ? "Stopped"
            : $"Running (PID {snapshot.TerminalPid})";
        McpStatus = snapshot.McpPid is null
            ? "Stopped"
            : snapshot.McpLive ? $"Live (PID {snapshot.McpPid})" : $"Starting (PID {snapshot.McpPid})";
        XtdataStatus = Capitalize(snapshot.XtdataState);
        XttradeStatus = Capitalize(snapshot.XttradeState);
        OnPropertyChanged(nameof(IsRunning));
        RefreshCommands();
    });

    private void ApplyProfile(LauncherProfile value)
    {
        ProfileName = value.DisplayName;
        ClientPath = value.ClientPath;
        XtquantRoot = value.XtquantRoot;
        UserdataPath = value.UserdataPath;
        McpPort = value.McpPort;
        AutoStartLauncher = value.AutoStartLauncher || LauncherRuntime.IsAutoStartEnabled();
    }

    private void ShowError(Exception exception)
    {
        StateLabel = "Action required";
        StateDetail = new SecretRedactor().Redact(exception.Message);
    }

    private void RefreshCommands()
    {
        foreach (var command in new[] { SaveCommand, StartCommand, StopCommand, ResolveCommand, DiscoverCommand, ExportDiagnosticsCommand, OpenLogsCommand })
        {
            (command as AsyncCommand)?.NotifyCanExecuteChanged();
        }
    }

    private bool Set<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
        {
            return false;
        }

        field = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));

    private static string? EmptyToNull(string value) => string.IsNullOrWhiteSpace(value) ? null : value;
    private static string Capitalize(string value) => string.IsNullOrEmpty(value) ? "Unknown" : char.ToUpperInvariant(value[0]) + value[1..];

    private async Task SaveProfileAsync()
    {
        await ResolveAsync();
        if (resolvedBroker is null)
        {
            return;
        }

        var now = DateTimeOffset.UtcNow;
        var secretId = profile?.TokenSecretId ?? $"secret_{Guid.NewGuid():N}";
        if (profile is null)
        {
            await runtime.Secrets.SaveAsync(secretId, TokenGenerator.Generate());
        }
        else
        {
            try
            {
                _ = await runtime.Secrets.GetAsync(secretId);
            }
            catch (FileNotFoundException)
            {
                await runtime.Secrets.SaveAsync(secretId, TokenGenerator.Generate());
            }
        }

        var updated = new LauncherProfile
        {
            Id = profile?.Id ?? $"profile-{Guid.NewGuid():N}"[..16],
            DisplayName = string.IsNullOrWhiteSpace(ProfileName) ? "QMT" : ProfileName.Trim(),
            ClientPath = resolvedBroker.ClientPath,
            WorkingDirectory = resolvedBroker.WorkingDirectory,
            XtquantRoot = resolvedBroker.XtquantRoot,
            UserdataPath = resolvedBroker.UserdataPath,
            McpPort = McpPort,
            TokenSecretId = secretId,
            AutoStartLauncher = AutoStartLauncher,
            RestartTerminal = profile?.RestartTerminal ?? false,
            CreatedAt = profile?.CreatedAt ?? now,
            UpdatedAt = now,
        };
        var document = await runtime.Profiles.LoadAsync();
        var profiles = document.Profiles.Where(item => item.Id != updated.Id).Append(updated).ToArray();
        await runtime.Profiles.SaveAsync(new ProfileDocument
        {
            ActiveProfileId = updated.Id,
            Profiles = profiles,
        });
        LauncherRuntime.SetAutoStart(AutoStartLauncher);
        profile = updated;
        StateDetail = "Profile saved locally";
    }
}
