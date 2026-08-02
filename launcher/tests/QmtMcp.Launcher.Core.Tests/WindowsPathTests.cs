using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Core.Tests;

public sealed class WindowsPathTests
{
    [Theory]
    [InlineData(@"D:\QMT\XtItClient.exe")]
    [InlineData("d:/QMT/XtItClient.exe")]
    [InlineData(@"\\server\share\QMT")]
    public void AbsoluteWindowsPathsAreRecognizedOnAnyHost(string path)
    {
        Assert.True(WindowsPath.IsAbsolute(path));
    }

    [Theory]
    [InlineData("QMT/XtItClient.exe")]
    [InlineData("/Applications/QMT")]
    [InlineData("")]
    public void RelativeOrPosixPathsAreRejected(string path)
    {
        Assert.False(WindowsPath.IsAbsolute(path));
    }

    [Fact]
    public void PathOperationsUseWindowsSemanticsOnMac()
    {
        var client = WindowsPath.Normalize("d:/QMT/bin.x64/XtItClient.exe");

        Assert.Equal(@"d:\QMT\bin.x64\XtItClient.exe", client);
        Assert.Equal("XtItClient.exe", WindowsPath.GetFileName(client));
        Assert.Equal(@"d:\QMT\bin.x64", WindowsPath.GetDirectoryName(client));
        Assert.Equal(@"d:\QMT", WindowsPath.Parent(WindowsPath.GetDirectoryName(client)));
        Assert.True(WindowsPath.EqualsNormalized(client, @"D:\qmt\BIN.X64\XtItClient.exe"));
    }
}
