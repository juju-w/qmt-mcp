using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Core.Tests;

public sealed class SupervisionTests
{
    [Fact]
    public async Task ExistingTerminalIsAttachedAndLeftRunning()
    {
        var terminal = new FakeManagedProcess(42, false);
        var processHost = new FakeProcessHost(terminal);
        var probe = new SequenceHealthProbe(
            new HealthObservation(true, "degraded", "disabled", "Waiting for QMT login"),
            new HealthObservation(true, "ready", "disabled", "Market data ready"));
        await using var orchestrator = CreateOrchestrator(processHost, probe);

        await orchestrator.StartAsync(
            ProfileFixture.Create(),
            ProfileFixture.Broker(),
            TokenGenerator.Generate(),
            "test",
            TestContext.Current.CancellationToken);
        await WaitUntilAsync(
            () => orchestrator.Snapshot.State == LauncherState.Ready,
            TestContext.Current.CancellationToken);

        Assert.Equal(TerminalOwnership.Attached, orchestrator.Snapshot.TerminalOwnership);
        Assert.Single(processHost.Commands);

        await orchestrator.StopAsync(TestContext.Current.CancellationToken);

        Assert.False(terminal.StopCalled);
        Assert.True(processHost.Started[0].StopCalled);
        Assert.Equal(LauncherState.Stopped, orchestrator.Snapshot.State);
    }

    [Fact]
    public async Task MissingTerminalIsStartedOnce()
    {
        var processHost = new FakeProcessHost();
        var probe = new SequenceHealthProbe(
            new HealthObservation(true, "ready", "disabled", "Market data ready"));
        await using var orchestrator = CreateOrchestrator(processHost, probe);

        await orchestrator.StartAsync(
            ProfileFixture.Create(),
            ProfileFixture.Broker(),
            TokenGenerator.Generate(),
            "test",
            TestContext.Current.CancellationToken);
        await WaitUntilAsync(
            () => orchestrator.Snapshot.State == LauncherState.Ready,
            TestContext.Current.CancellationToken);

        Assert.Equal(2, processHost.Commands.Count);
        Assert.Equal(@"D:\QMT\bin.x64\XtItClient.exe", processHost.Commands[1].Executable);
        Assert.Equal(TerminalOwnership.Launched, orchestrator.Snapshot.TerminalOwnership);
    }

    [Fact]
    public async Task ExitedMcpChildIsRestartedWithoutDuplicatingTerminal()
    {
        var terminal = new FakeManagedProcess(42, false);
        var processHost = new FakeProcessHost(terminal);
        var probe = new SequenceHealthProbe(
            new HealthObservation(true, "ready", "disabled", "Market data ready"));
        await using var orchestrator = CreateOrchestrator(processHost, probe);

        await orchestrator.StartAsync(
            ProfileFixture.Create(),
            ProfileFixture.Broker(),
            TokenGenerator.Generate(),
            "test",
            TestContext.Current.CancellationToken);
        await WaitUntilAsync(
            () => orchestrator.Snapshot.State == LauncherState.Ready,
            TestContext.Current.CancellationToken);
        processHost.Started[0].Exit();

        await WaitUntilAsync(
            () => processHost.Started.Count == 2 && orchestrator.Snapshot.State == LauncherState.Ready,
            TestContext.Current.CancellationToken);

        Assert.Equal(2, processHost.Commands.Count);
        Assert.All(processHost.Commands, command => Assert.EndsWith("python.exe", command.Executable, StringComparison.Ordinal));
        Assert.Equal(42, orchestrator.Snapshot.TerminalPid);
    }

    private static LauncherOrchestrator CreateOrchestrator(FakeProcessHost host, IHealthProbe probe) =>
        new(
            new CommandFactory(@"C:\QMT-MCP", @"C:\Users\test\AppData\Local\QMT-MCP"),
            host,
            probe,
            new RestartPolicy(3, TimeSpan.FromMilliseconds(5), TimeSpan.FromMilliseconds(10)),
            TimeSpan.FromMilliseconds(5));

    private static async Task WaitUntilAsync(Func<bool> predicate, CancellationToken cancellationToken)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(2);
        while (!predicate())
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (DateTimeOffset.UtcNow >= deadline)
            {
                throw new TimeoutException("Launcher state did not converge in time.");
            }

            await Task.Delay(5, cancellationToken);
        }
    }
}
