using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Core.Tests;

public sealed class BrokerDiscoveryTests
{
    [Fact]
    public async Task SavedAndRunningCandidatesOutrankBoundedSearch()
    {
        var saved = @"D:\QMT\bin.x64\XtItClient.exe";
        var running = @"E:\Broker\bin.x64\XtMiniQmt.exe";
        var scanned = @"C:\Apps\QMT\bin.x64\XtItClient.exe";
        var fileSystem = new FakeFileSystem()
            .AddFile(saved)
            .AddFile(running)
            .AddFile(scanned)
            .AddDirectory(@"C:\Apps");
        var discovery = new BrokerDiscovery(fileSystem, new FakeProcessInspector(running, saved));

        var candidates = await discovery.DiscoverAsync(
            [saved],
            [@"C:\Apps"],
            TestContext.Current.CancellationToken);

        Assert.Equal(3, candidates.Count);
        Assert.Equal(saved, candidates[0].ClientPath);
        Assert.Equal("saved-profile", candidates[0].Source);
        Assert.Equal(running, candidates[1].ClientPath);
        Assert.Equal("running-process", candidates[1].Source);
        Assert.Equal(5, fileSystem.LastMaxDepth);
        Assert.Equal(32, fileSystem.LastMaxResults);
    }
}
