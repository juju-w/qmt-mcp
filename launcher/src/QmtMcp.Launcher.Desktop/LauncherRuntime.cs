using System.Diagnostics;
using System.IO.Compression;
using System.Runtime.Versioning;
using QmtMcp.Launcher.Core;
using QmtMcp.Launcher.Windows;

namespace QmtMcp.Launcher.Desktop;

internal sealed class LauncherRuntime : IAsyncDisposable
{
    private readonly IDisposable? disposableProcessHost;

    private LauncherRuntime(
        string localDataRoot,
        string logsRoot,
        ProfileRepository profiles,
        BrokerResolver resolver,
        BrokerDiscovery discovery,
        IReadOnlyList<string> discoveryRoots,
        ISecretStore secrets,
        LauncherOrchestrator orchestrator,
        IDisposable? disposableProcessHost)
    {
        LocalDataRoot = localDataRoot;
        LogsRoot = logsRoot;
        Profiles = profiles;
        Resolver = resolver;
        Discovery = discovery;
        DiscoveryRoots = discoveryRoots;
        Secrets = secrets;
        Orchestrator = orchestrator;
        this.disposableProcessHost = disposableProcessHost;
    }

    public string LocalDataRoot { get; }
    public string LogsRoot { get; }
    public ProfileRepository Profiles { get; }
    public BrokerResolver Resolver { get; }
    public BrokerDiscovery Discovery { get; }
    public IReadOnlyList<string> DiscoveryRoots { get; }
    public ISecretStore Secrets { get; }
    public LauncherOrchestrator Orchestrator { get; }

    public async Task<IReadOnlyList<DiscoveryCandidate>> DiscoverBrokersAsync(
        CancellationToken cancellationToken)
    {
        var document = await Profiles.LoadAsync(cancellationToken);
        return await Discovery.DiscoverAsync(
            document.Profiles.Select(item => item.ClientPath),
            DiscoveryRoots,
            cancellationToken);
    }

    public static bool IsAutoStartEnabled() =>
        OperatingSystem.IsWindows() && WindowsShellIntegration.IsAutoStartEnabled();

    public static void SetAutoStart(bool enabled)
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        var executablePath = Environment.ProcessPath
            ?? throw new InvalidOperationException("Unable to identify the launcher executable.");
        WindowsShellIntegration.SetAutoStart(enabled, executablePath);
    }

    public static LauncherRuntime Create()
    {
        if (OperatingSystem.IsWindows())
        {
            return CreateWindows();
        }

        if (!string.Equals(Environment.GetEnvironmentVariable("QMT_LAUNCHER_DEMO"), "1", StringComparison.Ordinal))
        {
            throw new PlatformNotSupportedException("Run with QMT_LAUNCHER_DEMO=1 outside Windows.");
        }

        return CreateDemo();
    }

    public async Task<string> ExportDiagnosticsAsync(
        LauncherProfile? profile,
        string? token,
        CancellationToken cancellationToken)
    {
        var diagnosticsRoot = Path.Combine(LocalDataRoot, "diagnostics");
        Directory.CreateDirectory(diagnosticsRoot);
        var archivePath = Path.Combine(diagnosticsRoot, $"qmt-mcp-diagnostics-{DateTimeOffset.UtcNow:yyyyMMdd-HHmmss}.zip");
        var staging = Path.Combine(diagnosticsRoot, $"stage-{Guid.NewGuid():N}");
        Directory.CreateDirectory(staging);
        var redactor = new SecretRedactor(token is null ? [] : [token]);

        try
        {
            var summary = $"version={ThisAssembly.Version}\nstate={Orchestrator.Snapshot.State}\n"
                + $"profile={profile?.Id ?? "none"}\nclient={profile?.ClientPath ?? "none"}\n"
                + $"mcp=http://127.0.0.1:{profile?.McpPort ?? 0}/mcp\n";
            await File.WriteAllTextAsync(
                Path.Combine(staging, "summary.txt"),
                redactor.Redact(summary),
                cancellationToken);

            if (Directory.Exists(LogsRoot))
            {
                var destination = Path.Combine(staging, "logs");
                Directory.CreateDirectory(destination);
                foreach (var log in Directory.EnumerateFiles(LogsRoot, "*", SearchOption.AllDirectories)
                             .Where(IsDiagnosticLog)
                             .Take(12))
                {
                    var content = await File.ReadAllTextAsync(log, cancellationToken);
                    await File.WriteAllTextAsync(
                        Path.Combine(destination, Path.GetFileName(log)),
                        redactor.Redact(content),
                        cancellationToken);
                }
            }

            ZipFile.CreateFromDirectory(staging, archivePath, CompressionLevel.Optimal, false);
            return archivePath;
        }
        finally
        {
            if (Directory.Exists(staging))
            {
                Directory.Delete(staging, true);
            }
        }
    }

    public void OpenLogs()
    {
        Directory.CreateDirectory(LogsRoot);
        Process.Start(new ProcessStartInfo(LogsRoot) { UseShellExecute = true });
    }

    public async ValueTask DisposeAsync()
    {
        await Orchestrator.DisposeAsync();
        disposableProcessHost?.Dispose();
    }

    [SupportedOSPlatform("windows")]
    private static LauncherRuntime CreateWindows()
    {
        var paths = LauncherPaths.ForCurrentUser();
        paths.EnsureCreated();
        var fileSystem = new SystemLauncherFileSystem();
        var processHost = new WindowsProcessHost(paths.LogsRoot);
        var orchestrator = new LauncherOrchestrator(
            new CommandFactory(paths.InstallRoot, paths.LocalDataRoot),
            processHost,
            new HttpHealthProbe(new HttpClient { Timeout = TimeSpan.FromSeconds(2) }));
        orchestrator.SnapshotChanged += (_, _) => WindowsLogMaintenance.RotateDirectory(paths.LogsRoot);
        return new LauncherRuntime(
            paths.LocalDataRoot,
            paths.LogsRoot,
            new ProfileRepository(paths.ProfilesPath),
            new BrokerResolver(fileSystem, GetWindowsXtquantSearchRoots(paths)),
            new BrokerDiscovery(fileSystem, processHost),
            GetWindowsDiscoveryRoots(),
            new DpapiSecretStore(paths.SecretsRoot),
            orchestrator,
            processHost);
    }

    private static LauncherRuntime CreateDemo()
    {
        var localDataRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "QMT-MCP-Demo");
        var logsRoot = Path.Combine(localDataRoot, "logs");
        Directory.CreateDirectory(logsRoot);
        var fileSystem = new DemoFileSystem();
        var processHost = new DemoProcessHost();
        var orchestrator = new LauncherOrchestrator(
            new CommandFactory(@"C:\QMT-MCP", @"C:\Users\demo\AppData\Local\QMT-MCP"),
            processHost,
            new DemoHealthProbe(),
            pollInterval: TimeSpan.FromMilliseconds(500));
        return new LauncherRuntime(
            localDataRoot,
            logsRoot,
            new ProfileRepository(Path.Combine(localDataRoot, "profiles.json")),
            new BrokerResolver(fileSystem),
            new BrokerDiscovery(fileSystem, processHost),
            [],
            new DemoFileSecretStore(Path.Combine(localDataRoot, "demo-secrets")),
            orchestrator,
            null);
    }

    [SupportedOSPlatform("windows")]
    private static string[] GetWindowsDiscoveryRoots()
    {
        var roots = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        AddEnvironmentRoot(roots, Environment.SpecialFolder.ProgramFiles);
        AddEnvironmentRoot(roots, Environment.SpecialFolder.ProgramFilesX86);
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (!string.IsNullOrWhiteSpace(local))
        {
            roots.Add(Path.Combine(local, "Programs"));
        }

        foreach (var drive in DriveInfo.GetDrives().Where(item => item.DriveType == DriveType.Fixed && item.IsReady))
        {
            roots.Add(Path.Combine(drive.RootDirectory.FullName, "QMT"));
            roots.Add(Path.Combine(drive.RootDirectory.FullName, "MiniQMT"));
            try
            {
                foreach (var directory in Directory.EnumerateDirectories(drive.RootDirectory.FullName)
                             .Where(item => Path.GetFileName(item).Contains("qmt", StringComparison.OrdinalIgnoreCase))
                             .Take(16))
                {
                    roots.Add(directory);
                }
            }
            catch (Exception exception) when (exception is UnauthorizedAccessException or IOException)
            {
                // Explicit selection remains available when a drive root cannot be inspected.
            }
        }

        return roots.Where(Directory.Exists).Take(32).ToArray();
    }

    [SupportedOSPlatform("windows")]
    private static string[] GetWindowsXtquantSearchRoots(LauncherPaths paths)
    {
        var roots = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            Path.Combine(paths.LocalDataRoot, "sdk"),
        };
        var configured = Environment.GetEnvironmentVariable("QMT_XTQUANT_DIR_WIN");
        if (!string.IsNullOrWhiteSpace(configured) && Path.IsPathFullyQualified(configured))
        {
            roots.Add(configured);
        }

        return roots.ToArray();
    }

    private static void AddEnvironmentRoot(HashSet<string> roots, Environment.SpecialFolder folder)
    {
        var path = Environment.GetFolderPath(folder);
        if (!string.IsNullOrWhiteSpace(path))
        {
            roots.Add(path);
        }
    }

    private static bool IsDiagnosticLog(string path)
    {
        var fileName = Path.GetFileName(path);
        return fileName.Contains(".log", StringComparison.OrdinalIgnoreCase)
            || fileName.Contains(".jsonl", StringComparison.OrdinalIgnoreCase);
    }

    private static class ThisAssembly
    {
        public static string Version =>
            typeof(LauncherRuntime).Assembly.GetName().Version?.ToString() ?? "dev";
    }

    private sealed class DemoFileSystem : ILauncherFileSystem
    {
        private static readonly HashSet<string> Files = new(StringComparer.OrdinalIgnoreCase)
        {
            @"D:\QMT\bin.x64\XtItClient.exe",
            @"D:\QMT\xtquant\__init__.py",
        };

        public bool FileExists(string path) => Files.Contains(WindowsPath.Normalize(path));
        public bool DirectoryExists(string path) => WindowsPath.Normalize(path) is @"D:\QMT" or @"D:\QMT\bin.x64" or @"D:\QMT\userdata_mini";
        public void EnsureDirectory(string path) { }
        public IReadOnlyList<string> FindFiles(string root, IReadOnlySet<string> fileNames, int maxDepth, int maxResults, CancellationToken cancellationToken) =>
            Files.Where(path => fileNames.Contains(WindowsPath.GetFileName(path))).Take(maxResults).ToArray();
    }

    private sealed class DemoFileSecretStore(string rootDirectory) : ISecretStore
    {
        public async Task SaveAsync(string id, string value, CancellationToken cancellationToken = default)
        {
            Directory.CreateDirectory(rootDirectory);
            await File.WriteAllTextAsync(Path.Combine(rootDirectory, id), value, cancellationToken);
        }

        public Task<string> GetAsync(string id, CancellationToken cancellationToken = default) =>
            File.ReadAllTextAsync(Path.Combine(rootDirectory, id), cancellationToken);

        public Task DeleteAsync(string id, CancellationToken cancellationToken = default)
        {
            cancellationToken.ThrowIfCancellationRequested();
            File.Delete(Path.Combine(rootDirectory, id));
            return Task.CompletedTask;
        }
    }

    private sealed class DemoProcessHost : IProcessHost
    {
        private int nextId = 1000;
        public Task<IReadOnlyList<string>> GetRunningClientPathsAsync(CancellationToken cancellationToken) =>
            Task.FromResult<IReadOnlyList<string>>([]);
        public Task<IManagedProcess?> FindByExecutablePathAsync(string executablePath, CancellationToken cancellationToken) =>
            Task.FromResult<IManagedProcess?>(null);
        public Task<IManagedProcess> StartAsync(LaunchCommand command, SecretRedactor redactor, CancellationToken cancellationToken) =>
            Task.FromResult<IManagedProcess>(new DemoProcess(nextId++));
    }

    private sealed class DemoProcess(int id) : IManagedProcess
    {
        public int Id { get; } = id;
        public bool HasExited { get; private set; }
        public bool IsOwned => true;
        public Task<int> WaitForExitAsync(CancellationToken cancellationToken) => Task.FromResult(0);
        public Task StopAsync(CancellationToken cancellationToken)
        {
            HasExited = true;
            return Task.CompletedTask;
        }
        public ValueTask DisposeAsync() => ValueTask.CompletedTask;
    }

    private sealed class DemoHealthProbe : IHealthProbe
    {
        private int attempts;
        public Task<HealthObservation> ProbeAsync(LauncherProfile profile, string token, CancellationToken cancellationToken)
        {
            attempts++;
            return Task.FromResult(attempts < 3
                ? new HealthObservation(true, "degraded", "disabled", "Waiting for QMT login")
                : new HealthObservation(true, "ready", "disabled", "Market data ready"));
        }
    }
}
