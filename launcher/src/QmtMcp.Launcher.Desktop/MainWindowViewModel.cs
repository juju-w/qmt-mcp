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
    private readonly LocalizationManager localization;
    private readonly IReadOnlyList<LanguageOption> languages;
    private readonly Action<Action> dispatch;
    private LauncherProfile? profile;
    private ResolvedBroker? resolvedBroker;
    private string profileName = "QMT";
    private string clientPath = string.Empty;
    private string xtquantRoot = string.Empty;
    private string userdataPath = string.Empty;
    private int mcpPort = 18765;
    private LocalizedText stateLabelText = LocalizedText.Key("StateStopped");
    private LocalizedText stateDetailText = LocalizedText.Key("DetailSelectClient");
    private LocalizedText qmtStatusText = LocalizedText.Key("StatusNotConfigured");
    private LocalizedText mcpStatusText = LocalizedText.Key("StatusStopped");
    private LocalizedText xtdataStatusText = LocalizedText.Key("StatusUnknown");
    private LocalizedText xttradeStatusText = LocalizedText.Key("StatusDisabled");
    private LocalizedText resolutionStatusText = LocalizedText.Key("ResolutionNoClient");
    private LocalizedText lastDiagnosticPathText = LocalizedText.Key("NoDiagnosticArchive");
    private bool autoStartLauncher;
    private bool busy;

    public MainWindowViewModel(
        LauncherRuntime runtime,
        LocalizationManager localization,
        Action<Action> dispatch)
    {
        this.runtime = runtime;
        this.localization = localization;
        languages = LocalizationManager.Languages;
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
        localization.LanguageChanged += OnLanguageChanged;
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand SaveCommand { get; }
    public ICommand StartCommand { get; }
    public ICommand StopCommand { get; }
    public ICommand ResolveCommand { get; }
    public ICommand DiscoverCommand { get; }
    public ICommand ExportDiagnosticsCommand { get; }
    public ICommand OpenLogsCommand { get; }

    public IReadOnlyList<LanguageOption> Languages => languages;
    public LanguageOption SelectedLanguage
    {
        get => Languages.First(item => item.Code == localization.CurrentLanguage);
        set
        {
            if (value is not null)
            {
                localization.SetLanguage(value.Code);
            }
        }
    }

    public string ProfileName { get => profileName; set => Set(ref profileName, value); }
    public string ClientPath { get => clientPath; set => Set(ref clientPath, value); }
    public string XtquantRoot { get => xtquantRoot; set => Set(ref xtquantRoot, value); }
    public string UserdataPath { get => userdataPath; set => Set(ref userdataPath, value); }
    public int McpPort { get => mcpPort; set { if (Set(ref mcpPort, value)) OnPropertyChanged(nameof(McpUrl)); } }
    public string McpUrl => $"http://127.0.0.1:{McpPort}/mcp";
    public string StateLabel => stateLabelText.Resolve(localization);
    public string StateDetail => stateDetailText.Resolve(localization);
    public string QmtStatus => qmtStatusText.Resolve(localization);
    public string McpStatus => mcpStatusText.Resolve(localization);
    public string XtdataStatus => xtdataStatusText.Resolve(localization);
    public string XttradeStatus => xttradeStatusText.Resolve(localization);
    public string ResolutionStatus => resolutionStatusText.Resolve(localization);
    public string LastDiagnosticPath => lastDiagnosticPathText.Resolve(localization);
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
            SetResolutionFailure(result.Failure);
            SetLocalized(ref qmtStatusText, nameof(QmtStatus), "StatusConfigurationIncomplete");
            return;
        }

        resolvedBroker = result.Broker;
        ClientPath = resolvedBroker!.ClientPath;
        XtquantRoot = resolvedBroker.XtquantRoot;
        UserdataPath = resolvedBroker.UserdataPath;
        SetLocalized(ref resolutionStatusText, nameof(ResolutionStatus), "ResolutionValidated");
        SetLocalized(ref qmtStatusText, nameof(QmtStatus), "StatusConfigured");
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
                SetLocalized(ref resolutionStatusText, nameof(ResolutionStatus), "ResolutionNoClientFound");
                return;
            }

            var selected = candidates[0];
            ClientPath = selected.ClientPath;
            XtquantRoot = string.Empty;
            UserdataPath = string.Empty;
            await ResolveAsync();
            if (resolvedBroker is not null)
            {
                SetLocalized(
                    ref resolutionStatusText,
                    nameof(ResolutionStatus),
                    "ResolutionDetected",
                    selected.Source);
            }
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
            throw new InvalidOperationException(localization["ErrorSaveProfileBeforeCopy"]);
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

        SetLiteral(
            ref lastDiagnosticPathText,
            nameof(LastDiagnosticPath),
            await runtime.ExportDiagnosticsAsync(profile, token, CancellationToken.None));
    }

    private void OnSnapshotChanged(object? sender, LauncherSnapshot snapshot) => dispatch(() =>
    {
        SetLocalized(ref stateLabelText, nameof(StateLabel), StateLabelKey(snapshot.State));
        SetSnapshotDetail(snapshot);
        if (snapshot.TerminalPid is null)
        {
            SetLocalized(ref qmtStatusText, nameof(QmtStatus), "StatusStopped");
        }
        else
        {
            SetLocalized(ref qmtStatusText, nameof(QmtStatus), "StatusRunningPid", snapshot.TerminalPid);
        }

        if (snapshot.McpPid is null)
        {
            SetLocalized(ref mcpStatusText, nameof(McpStatus), "StatusStopped");
        }
        else
        {
            SetLocalized(
                ref mcpStatusText,
                nameof(McpStatus),
                snapshot.McpLive ? "StatusLivePid" : "StatusStartingPid",
                snapshot.McpPid);
        }

        SetLocalized(ref xtdataStatusText, nameof(XtdataStatus), ComponentStateKey(snapshot.XtdataState));
        SetLocalized(ref xttradeStatusText, nameof(XttradeStatus), ComponentStateKey(snapshot.XttradeState));
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
        SetLocalized(ref stateLabelText, nameof(StateLabel), "StateActionRequired");
        SetLiteral(ref stateDetailText, nameof(StateDetail), new SecretRedactor().Redact(exception.Message));
    }

    internal string Localize(string key) => localization[key];

    private void OnLanguageChanged(object? sender, EventArgs eventArgs)
    {
        foreach (var propertyName in new[]
                 {
                     nameof(SelectedLanguage),
                     nameof(StateLabel),
                     nameof(StateDetail),
                     nameof(QmtStatus),
                     nameof(McpStatus),
                     nameof(XtdataStatus),
                     nameof(XttradeStatus),
                     nameof(ResolutionStatus),
                     nameof(LastDiagnosticPath),
                 })
        {
            OnPropertyChanged(propertyName);
        }
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
        SetLocalized(ref stateDetailText, nameof(StateDetail), "ResolutionProfileSaved");
    }

    private void SetResolutionFailure(ResolutionFailure? failure)
    {
        var key = failure?.Code switch
        {
            "path_not_absolute" => "ResolutionPathNotAbsolute",
            "client_missing" => "ResolutionClientMissing",
            "client_unsupported" => "ResolutionClientUnsupported",
            "xtquant_missing" => "ResolutionXtquantMissing",
            "xtquant_ambiguous" => "ResolutionXtquantAmbiguous",
            "userdata_missing" => "ResolutionUserdataMissing",
            _ => "ResolutionUnable",
        };
        SetLocalized(ref resolutionStatusText, nameof(ResolutionStatus), key);
    }

    private void SetSnapshotDetail(LauncherSnapshot snapshot)
    {
        if (snapshot.State == LauncherState.Faulted)
        {
            var errorKey = snapshot.LastError?.Code switch
            {
                "profile_invalid" => "DetailProfileInvalid",
                "startup_failed" => "DetailStartupFailed",
                "mcp_restart_exhausted" => "DetailRestartExhausted",
                _ => null,
            };
            if (errorKey is not null)
            {
                SetLocalized(ref stateDetailText, nameof(StateDetail), errorKey);
            }
            else
            {
                SetLiteral(ref stateDetailText, nameof(StateDetail), snapshot.Summary);
            }

            return;
        }

        var key = snapshot.State switch
        {
            LauncherState.Validating => "DetailValidating",
            LauncherState.StartingMcp => "DetailStartingMcp",
            LauncherState.StartingTerminal when snapshot.TerminalOwnership == TerminalOwnership.Attached => "DetailAttachedQmt",
            LauncherState.StartingTerminal => "DetailStartingQmt",
            LauncherState.WaitingForLogin => snapshot.Summary == "MCP server stopped"
                ? "DetailMcpStopped"
                : "DetailWaitingForLogin",
            LauncherState.Ready => "DetailReady",
            LauncherState.Degraded when snapshot.Summary == "QMT terminal stopped" => "DetailQmtStopped",
            LauncherState.Degraded when snapshot.Summary == "MCP server stopped" => "DetailMcpStopped",
            LauncherState.Degraded => "DetailDegraded",
            LauncherState.Stopping => "DetailStopping",
            LauncherState.Stopped => "DetailStopped",
            _ => "DetailStartingMcp",
        };
        SetLocalized(ref stateDetailText, nameof(StateDetail), key);
    }

    private static string StateLabelKey(LauncherState state) => state switch
    {
        LauncherState.Ready => "StateReady",
        LauncherState.WaitingForLogin => "StateWaitingForLogin",
        LauncherState.Degraded => "StateDegraded",
        LauncherState.Faulted => "StateActionRequired",
        LauncherState.Stopped => "StateStopped",
        LauncherState.Stopping => "StateStopping",
        _ => "StateStarting",
    };

    private static string ComponentStateKey(string state) => state.ToLowerInvariant() switch
    {
        "ready" => "ComponentReady",
        "degraded" => "ComponentDegraded",
        "disabled" => "ComponentDisabled",
        "login_required" => "ComponentLoginRequired",
        "error" => "ComponentError",
        _ => "ComponentUnknown",
    };

    private void SetLocalized(
        ref LocalizedText target,
        string propertyName,
        string key,
        params object?[] arguments)
    {
        target = LocalizedText.Key(key, arguments);
        OnPropertyChanged(propertyName);
    }

    private void SetLiteral(ref LocalizedText target, string propertyName, string value)
    {
        target = LocalizedText.Literal(value);
        OnPropertyChanged(propertyName);
    }

    private sealed record LocalizedText(string? ResourceKey, string? LiteralValue, object?[] Arguments)
    {
        public static LocalizedText Key(string key, params object?[] arguments) => new(key, null, arguments);
        public static LocalizedText Literal(string value) => new(null, value, []);

        public string Resolve(LocalizationManager localization) =>
            ResourceKey is null ? LiteralValue ?? string.Empty : localization.Format(ResourceKey, Arguments);
    }
}
