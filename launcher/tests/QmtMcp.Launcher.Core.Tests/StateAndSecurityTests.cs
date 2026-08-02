using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Core.Tests;

public sealed class StateAndSecurityTests
{
    [Fact]
    public void LoginWaitBecomesReadyWithoutMcpRestart()
    {
        var machine = new LauncherStateMachine();

        machine.BeginStart("qmt-test");
        machine.McpStarted(101);
        machine.TerminalObserved(202, TerminalOwnership.Launched);
        var waiting = machine.ApplyHealth(new HealthObservation(true, "degraded", "disabled", "Waiting for QMT login"));
        var ready = machine.ApplyHealth(new HealthObservation(true, "ready", "disabled", "Market data ready"));

        Assert.Equal(LauncherState.WaitingForLogin, waiting.State);
        Assert.Equal(LauncherState.Ready, ready.State);
        Assert.Equal(101, ready.McpPid);
        Assert.Equal(202, ready.TerminalPid);
    }

    [Fact]
    public void RestartPolicyIsBoundedAndExponential()
    {
        var policy = new RestartPolicy(3, TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(3));

        Assert.Equal(TimeSpan.FromSeconds(1), policy.GetDelay(0));
        Assert.Equal(TimeSpan.FromSeconds(2), policy.GetDelay(1));
        Assert.Equal(TimeSpan.FromSeconds(3), policy.GetDelay(2));
        Assert.Null(policy.GetDelay(3));
    }

    [Fact]
    public void RedactorRemovesBearerSecretAndLongAccountIds()
    {
        const string token = "secret-token-value";
        var redacted = new SecretRedactor([token]).Redact(
            $"Authorization: Bearer {token}; account=12345678901 token={token}");

        Assert.DoesNotContain(token, redacted, StringComparison.Ordinal);
        Assert.DoesNotContain("12345678901", redacted, StringComparison.Ordinal);
        Assert.Contains("Bearer <redacted>", redacted, StringComparison.Ordinal);
        Assert.Contains("<redacted-id>", redacted, StringComparison.Ordinal);
    }

    [Fact]
    public void GeneratedTokenHasAtLeast256Bits()
    {
        var first = TokenGenerator.Generate();
        var second = TokenGenerator.Generate();

        Assert.Equal(64, first.Length);
        Assert.NotEqual(first, second);
        Assert.Matches("^[0-9a-f]{64}$", first);
    }
}
