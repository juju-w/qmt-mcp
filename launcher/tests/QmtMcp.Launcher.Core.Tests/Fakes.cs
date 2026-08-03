using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Core.Tests;

internal sealed class FakeFileSystem : ILauncherFileSystem
{
    private readonly HashSet<string> files = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> directories = new(StringComparer.OrdinalIgnoreCase);

    public int? LastMaxDepth { get; private set; }
    public int? LastMaxResults { get; private set; }

    public FakeFileSystem AddFile(string path)
    {
        files.Add(WindowsPath.Normalize(path));
        AddDirectory(WindowsPath.GetDirectoryName(path));
        return this;
    }

    public FakeFileSystem AddDirectory(string path)
    {
        var current = WindowsPath.Normalize(path);
        while (!string.IsNullOrEmpty(current))
        {
            directories.Add(current);
            var parent = WindowsPath.Parent(current);
            if (string.IsNullOrEmpty(parent) || WindowsPath.EqualsNormalized(parent, current))
            {
                break;
            }

            current = parent;
        }

        return this;
    }

    public bool FileExists(string path) => files.Contains(WindowsPath.Normalize(path));

    public bool DirectoryExists(string path) => directories.Contains(WindowsPath.Normalize(path));

    public void EnsureDirectory(string path) => AddDirectory(path);

    public IReadOnlyList<string> FindFiles(
        string root,
        IReadOnlySet<string> fileNames,
        int maxDepth,
        int maxResults,
        CancellationToken cancellationToken)
    {
        LastMaxDepth = maxDepth;
        LastMaxResults = maxResults;
        var prefix = $"{WindowsPath.Normalize(root)}\\";
        return files
            .Where(path => path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            .Where(path => fileNames.Contains(WindowsPath.GetFileName(path)))
            .Take(maxResults)
            .ToArray();
    }
}

internal sealed class FakeProcessInspector(params string[] paths) : IBrokerProcessInspector
{
    public Task<IReadOnlyList<string>> GetRunningClientPathsAsync(CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<string>>(paths);
}

internal sealed class FakeManagedProcess(int id, bool owned) : IManagedProcess
{
    public int Id { get; } = id;
    public bool HasExited { get; private set; }
    public bool IsOwned { get; } = owned;
    public bool StopCalled { get; private set; }

    public void Exit() => HasExited = true;

    public Task<int> WaitForExitAsync(CancellationToken cancellationToken) => Task.FromResult(HasExited ? 1 : 0);

    public Task StopAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (IsOwned)
        {
            StopCalled = true;
            HasExited = true;
        }

        return Task.CompletedTask;
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}

internal sealed class FakeProcessHost(FakeManagedProcess? existingTerminal = null) : IProcessHost
{
    private int nextId = 100;
    public List<LaunchCommand> Commands { get; } = [];
    public List<FakeManagedProcess> Started { get; } = [];
    public FakeManagedProcess? ExistingTerminal { get; } = existingTerminal;

    public Task<IReadOnlyList<string>> GetRunningClientPathsAsync(CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<string>>([]);

    public Task<IManagedProcess?> FindByExecutablePathAsync(string executablePath, CancellationToken cancellationToken) =>
        Task.FromResult<IManagedProcess?>(ExistingTerminal);

    public Task<IManagedProcess> StartAsync(
        LaunchCommand command,
        SecretRedactor redactor,
        CancellationToken cancellationToken)
    {
        var process = new FakeManagedProcess(nextId++, true);
        Commands.Add(command);
        Started.Add(process);
        return Task.FromResult<IManagedProcess>(process);
    }
}

internal sealed class SequenceHealthProbe(params HealthObservation[] observations) : IHealthProbe
{
    private int index;

    public Task<HealthObservation> ProbeAsync(
        LauncherProfile profile,
        string token,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var current = observations.Length == 0
            ? new HealthObservation(false, "unknown", "unknown", "Starting")
            : observations[Math.Min(index++, observations.Length - 1)];
        return Task.FromResult(current);
    }
}

internal static class ProfileFixture
{
    public static LauncherProfile Create(string tokenSecretId = "secret_test") => new()
    {
        Id = "qmt-test",
        DisplayName = "QMT Test",
        ClientPath = @"D:\QMT\bin.x64\XtItClient.exe",
        WorkingDirectory = @"D:\QMT\bin.x64",
        XtquantRoot = @"D:\QMT",
        UserdataPath = @"D:\QMT\userdata_mini",
        TokenSecretId = tokenSecretId,
        CreatedAt = DateTimeOffset.Parse("2026-08-02T00:00:00Z", System.Globalization.CultureInfo.InvariantCulture),
        UpdatedAt = DateTimeOffset.Parse("2026-08-02T00:00:00Z", System.Globalization.CultureInfo.InvariantCulture),
    };

    public static ResolvedBroker Broker() => new(
        @"D:\QMT\bin.x64\XtItClient.exe",
        @"D:\QMT\bin.x64",
        @"D:\QMT",
        @"D:\QMT",
        @"D:\QMT\userdata_mini",
        []);
}
