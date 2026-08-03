using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Core.Tests;

public sealed class CommandFactoryTests
{
    [Fact]
    public void McpTokenExistsOnlyInChildEnvironment()
    {
        const string token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        var command = new CommandFactory(
            @"C:\Users\user\AppData\Local\Programs\QMT-MCP",
            @"C:\Users\user\AppData\Local\QMT-MCP")
            .CreateMcp(ProfileFixture.Create(), ProfileFixture.Broker(), token, "1.2.3");

        Assert.Equal(
            @"C:\Users\user\AppData\Local\Programs\QMT-MCP\runtime\python\python.exe",
            command.Executable);
        Assert.DoesNotContain(command.Arguments, argument => argument.Contains(token, StringComparison.Ordinal));
        Assert.Equal(token, command.Environment["QMT_MCP_TOKEN"]);
        Assert.Equal("127.0.0.1", command.Environment["MCP_HOST"]);
        Assert.Equal(
            @"C:\Users\user\AppData\Local\Programs\QMT-MCP\server;D:\QMT",
            command.Environment["PYTHONPATH"]);
        Assert.True(command.RedirectOutput);
        Assert.False(command.UseShellExecute);
    }

    [Fact]
    public void TerminalCommandHasNoCredentialArguments()
    {
        var command = CommandFactory.CreateTerminal(ProfileFixture.Broker());

        Assert.Empty(command.Arguments);
        Assert.Equal(@"D:\QMT\bin.x64", command.WorkingDirectory);
        Assert.True(command.UseShellExecute);
        Assert.False(command.RedirectOutput);
    }
}
