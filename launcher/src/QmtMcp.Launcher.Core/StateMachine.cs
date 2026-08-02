namespace QmtMcp.Launcher.Core;

public sealed class LauncherStateMachine(TimeProvider? timeProvider = null)
{
    private readonly TimeProvider clock = timeProvider ?? TimeProvider.System;

    public LauncherSnapshot Snapshot { get; private set; } = new()
    {
        UpdatedAt = DateTimeOffset.UnixEpoch,
    };

    public LauncherSnapshot BeginStart(string profileId)
    {
        RequireState(LauncherState.Stopped, LauncherState.Faulted);
        return Update(new LauncherSnapshot
        {
            State = LauncherState.Validating,
            ProfileId = profileId,
            Summary = "Validating profile",
            UpdatedAt = clock.GetUtcNow(),
        });
    }

    public LauncherSnapshot McpStarted(int pid)
    {
        RequireState(LauncherState.Validating, LauncherState.Degraded);
        return Update(Snapshot with
        {
            State = LauncherState.StartingMcp,
            McpPid = pid,
            McpLive = false,
            Summary = "Starting MCP server",
            LastError = null,
            UpdatedAt = clock.GetUtcNow(),
        });
    }

    public LauncherSnapshot TerminalObserved(int pid, TerminalOwnership ownership)
    {
        RequireState(LauncherState.StartingMcp, LauncherState.StartingTerminal);
        return Update(Snapshot with
        {
            State = LauncherState.StartingTerminal,
            TerminalPid = pid,
            TerminalOwnership = ownership,
            Summary = ownership == TerminalOwnership.Attached ? "Attached to QMT" : "Starting QMT",
            UpdatedAt = clock.GetUtcNow(),
        });
    }

    public LauncherSnapshot ApplyHealth(HealthObservation observation)
    {
        RequireActive();
        var ready = observation.McpLive
            && string.Equals(observation.XtdataState, "ready", StringComparison.OrdinalIgnoreCase);
        var state = ready
            ? LauncherState.Ready
            : observation.McpLive
                ? LauncherState.WaitingForLogin
                : LauncherState.Degraded;
        return Update(Snapshot with
        {
            State = state,
            McpLive = observation.McpLive,
            XtdataState = observation.XtdataState,
            XttradeState = observation.XttradeState,
            Summary = observation.Summary,
            UpdatedAt = clock.GetUtcNow(),
        });
    }

    public LauncherSnapshot Fail(string code, string component, string message, string? detail, bool retryable)
    {
        return Update(Snapshot with
        {
            State = LauncherState.Faulted,
            Summary = message,
            LastError = new LauncherError(code, component, message, detail, retryable, clock.GetUtcNow()),
            UpdatedAt = clock.GetUtcNow(),
        });
    }

    public LauncherSnapshot BeginStop()
    {
        if (Snapshot.State == LauncherState.Stopped)
        {
            return Snapshot;
        }

        return Update(Snapshot with
        {
            State = LauncherState.Stopping,
            Summary = "Stopping MCP server",
            UpdatedAt = clock.GetUtcNow(),
        });
    }

    public LauncherSnapshot CompleteStop() => Update(new LauncherSnapshot
    {
        State = LauncherState.Stopped,
        Summary = "Stopped",
        UpdatedAt = clock.GetUtcNow(),
    });

    private LauncherSnapshot Update(LauncherSnapshot snapshot)
    {
        Snapshot = snapshot;
        return Snapshot;
    }

    private void RequireState(params LauncherState[] allowed)
    {
        if (!allowed.Contains(Snapshot.State))
        {
            throw new InvalidOperationException($"Invalid launcher transition from {Snapshot.State}.");
        }
    }

    private void RequireActive()
    {
        if (Snapshot.State is LauncherState.Stopped or LauncherState.Stopping or LauncherState.Faulted)
        {
            throw new InvalidOperationException($"Cannot apply health in {Snapshot.State} state.");
        }
    }
}

public sealed class RestartPolicy(
    int maxAttempts = 5,
    TimeSpan? initialDelay = null,
    TimeSpan? maximumDelay = null)
{
    private readonly TimeSpan initial = initialDelay ?? TimeSpan.FromSeconds(1);
    private readonly TimeSpan maximum = maximumDelay ?? TimeSpan.FromSeconds(30);

    public TimeSpan? GetDelay(int completedAttempts)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(completedAttempts);

        if (completedAttempts >= maxAttempts)
        {
            return null;
        }

        var multiplier = Math.Pow(2, completedAttempts);
        return TimeSpan.FromMilliseconds(Math.Min(initial.TotalMilliseconds * multiplier, maximum.TotalMilliseconds));
    }
}
