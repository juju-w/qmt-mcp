using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Core.Tests;

public sealed class BrokerResolverTests
{
    [Fact]
    public void StandardQmtTreeResolvesWithoutOverrides()
    {
        var fileSystem = new FakeFileSystem()
            .AddFile(@"D:\QMT\bin.x64\XtItClient.exe")
            .AddFile(@"D:\QMT\xtquant\__init__.py")
            .AddDirectory(@"D:\QMT\userdata_mini");

        var result = new BrokerResolver(fileSystem).Resolve(
            new BrokerSelection(@"D:\QMT\bin.x64\XtItClient.exe"),
            TestContext.Current.CancellationToken);

        Assert.True(result.IsSuccess);
        Assert.Equal(@"D:\QMT", result.Broker!.QmtRoot);
        Assert.Equal(@"D:\QMT", result.Broker.XtquantRoot);
        Assert.Equal(@"D:\QMT\userdata_mini", result.Broker.UserdataPath);
        Assert.Contains("xtquant:beside-client:D:\\QMT", result.Broker.Evidence);
    }

    [Fact]
    public void GuangdaNestedSdkTreeResolvesWithoutOverrides()
    {
        var fileSystem = new FakeFileSystem()
            .AddFile(@"C:\Program Files\guangda_qmt\bin.x64\XtMiniQmt.exe")
            .AddFile(@"C:\Program Files\guangda_qmt\bin.x64\Lib\site-packages\xtquant\__init__.py")
            .AddDirectory(@"C:\Program Files\guangda_qmt\userdata_mini");

        var result = new BrokerResolver(fileSystem).Resolve(
            new BrokerSelection(@"C:\Program Files\guangda_qmt\bin.x64\XtMiniQmt.exe"),
            TestContext.Current.CancellationToken);

        Assert.True(result.IsSuccess);
        Assert.Equal(@"C:\Program Files\guangda_qmt", result.Broker!.QmtRoot);
        Assert.Equal(
            @"C:\Program Files\guangda_qmt\bin.x64\Lib\site-packages",
            result.Broker.XtquantRoot);
        Assert.Equal(
            @"C:\Program Files\guangda_qmt\userdata_mini",
            result.Broker.UserdataPath);
    }

    [Fact]
    public void MissingClientFailsBeforeGuessing()
    {
        var result = new BrokerResolver(new FakeFileSystem()).Resolve(
            new BrokerSelection(@"D:\Missing\XtItClient.exe"),
            TestContext.Current.CancellationToken);

        Assert.False(result.IsSuccess);
        Assert.Equal("client_missing", result.Failure!.Code);
    }

    [Fact]
    public void ExplicitXtquantRootWins()
    {
        var fileSystem = new FakeFileSystem()
            .AddFile(@"D:\QMT\bin.x64\XtItClient.exe")
            .AddFile(@"E:\SDK\xtquant\__init__.py")
            .AddDirectory(@"D:\QMT\userdata_mini");

        var result = new BrokerResolver(fileSystem).Resolve(
            new BrokerSelection(
                @"D:\QMT\bin.x64\XtItClient.exe",
                @"E:\SDK"),
            TestContext.Current.CancellationToken);

        Assert.True(result.IsSuccess);
        Assert.Equal(@"E:\SDK", result.Broker!.XtquantRoot);
        Assert.Contains("xtquant:explicit:E:\\SDK", result.Broker.Evidence);
    }

    [Fact]
    public void MultipleNestedXtquantPackagesRequireAChoice()
    {
        var fileSystem = new FakeFileSystem()
            .AddFile(@"D:\QMT\bin.x64\XtItClient.exe")
            .AddFile(@"D:\QMT\sdk-a\xtquant\__init__.py")
            .AddFile(@"D:\QMT\sdk-b\xtquant\__init__.py")
            .AddDirectory(@"D:\QMT");

        var result = new BrokerResolver(fileSystem).Resolve(
            new BrokerSelection(@"D:\QMT\bin.x64\XtItClient.exe"),
            TestContext.Current.CancellationToken);

        Assert.False(result.IsSuccess);
        Assert.Equal("xtquant_ambiguous", result.Failure!.Code);
        Assert.Equal(2, result.Failure.Candidates.Count);
        Assert.Equal(5, fileSystem.LastMaxDepth);
        Assert.Equal(16, fileSystem.LastMaxResults);
    }

    [Fact]
    public void XtquantOutsideQmtTreeIsNotGuessedWithoutExplicitSelection()
    {
        var fileSystem = new FakeFileSystem()
            .AddFile(@"G:\BrokerQmt\bin.x64\XtMiniQmt.exe")
            .AddFile(@"C:\Users\Example\AppData\Local\QMT-MCP\sdk\guangda\xtquant\__init__.py")
            .AddDirectory(@"G:\BrokerQmt\userdata_mini");

        var result = new BrokerResolver(fileSystem).Resolve(
            new BrokerSelection(@"G:\BrokerQmt\bin.x64\XtMiniQmt.exe"),
            TestContext.Current.CancellationToken);

        Assert.False(result.IsSuccess);
        Assert.Equal("xtquant_missing", result.Failure!.Code);
    }
}
