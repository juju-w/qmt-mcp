using QmtMcp.Launcher.Windows;

namespace QmtMcp.Launcher.Windows.Tests;

public sealed class WindowsAdapterTests
{
    [Fact]
    public void SingleInstanceLockRejectsDuplicateAndAllowsLaterAcquire()
    {
        using var directory = new TemporaryDirectory();
        var lockPath = Path.Combine(directory.Path, "launcher.lock");

        using (var first = SingleInstanceLock.TryAcquire(lockPath))
        {
            Assert.NotNull(first);
            Assert.Null(SingleInstanceLock.TryAcquire(lockPath));
        }

        using var reacquired = SingleInstanceLock.TryAcquire(lockPath);
        Assert.NotNull(reacquired);
    }

    [Fact]
    public void LogMaintenanceKeepsThreeBoundedBackups()
    {
        using var directory = new TemporaryDirectory();
        var logPath = Path.Combine(directory.Path, "mcp-audit.jsonl");

        for (var index = 0; index < 5; index++)
        {
            using (var stream = File.Create(logPath))
            {
                stream.SetLength(WindowsLogMaintenance.MaximumLogBytes);
            }

            WindowsLogMaintenance.RotateFileIfNeeded(logPath);
        }

        Assert.False(File.Exists(logPath));
        Assert.True(File.Exists($"{logPath}.1"));
        Assert.True(File.Exists($"{logPath}.2"));
        Assert.True(File.Exists($"{logPath}.3"));
        Assert.False(File.Exists($"{logPath}.4"));
    }

    [Fact]
    public async Task DpapiStoreRoundTripsForCurrentWindowsUser()
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        using var directory = new TemporaryDirectory();
        var store = new DpapiSecretStore(directory.Path);
        var cancellationToken = TestContext.Current.CancellationToken;
        await store.SaveAsync("test_secret", "sensitive-value", cancellationToken);

        Assert.Equal("sensitive-value", await store.GetAsync("test_secret", cancellationToken));
        Assert.DoesNotContain("sensitive-value", File.ReadAllText(Path.Combine(directory.Path, "test_secret.secret")));

        await store.DeleteAsync("test_secret", cancellationToken);
        Assert.False(File.Exists(Path.Combine(directory.Path, "test_secret.secret")));
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "QMT-MCP",
                "test-data",
                $"qmt-launcher-test-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose() => Directory.Delete(Path, true);
    }
}
