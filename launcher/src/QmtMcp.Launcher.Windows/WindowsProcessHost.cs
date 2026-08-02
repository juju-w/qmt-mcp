using System.Diagnostics;
using System.Runtime.Versioning;
using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Windows;

[SupportedOSPlatform("windows")]
public sealed class WindowsProcessHost(string logDirectory) : IProcessHost, IDisposable
{
    private static readonly string[] ClientProcessNames = ["XtItClient", "XtMiniQmt", "XtMiniQMT"];
    private readonly SemaphoreSlim logWriteLock = new(1, 1);

    public Task<IReadOnlyList<string>> GetRunningClientPathsAsync(CancellationToken cancellationToken)
    {
        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var processName in ClientProcessNames)
        {
            foreach (var process in Process.GetProcessesByName(processName))
            {
                using (process)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    try
                    {
                        var path = process.MainModule?.FileName;
                        if (!string.IsNullOrWhiteSpace(path))
                        {
                            paths.Add(path);
                        }
                    }
                    catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
                    {
                        // Another user's or elevated process may not expose MainModule.
                    }
                }
            }
        }

        return Task.FromResult<IReadOnlyList<string>>(paths.ToArray());
    }

    public async Task<IManagedProcess?> FindByExecutablePathAsync(
        string executablePath,
        CancellationToken cancellationToken)
    {
        var processName = Path.GetFileNameWithoutExtension(executablePath);
        foreach (var process in Process.GetProcessesByName(processName))
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                var path = process.MainModule?.FileName;
                if (path is not null && WindowsPath.EqualsNormalized(path, executablePath))
                {
                    return new WindowsManagedProcess(process, false);
                }
            }
            catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
            {
                // Continue past inaccessible candidates and require explicit startup if none match.
            }

            process.Dispose();
        }

        return await Task.FromResult<IManagedProcess?>(null);
    }

    public Task<IManagedProcess> StartAsync(
        LaunchCommand command,
        SecretRedactor redactor,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        Directory.CreateDirectory(command.WorkingDirectory);
        var startInfo = new ProcessStartInfo(command.Executable)
        {
            WorkingDirectory = command.WorkingDirectory,
            UseShellExecute = command.UseShellExecute,
            CreateNoWindow = !command.UseShellExecute,
            RedirectStandardOutput = command.RedirectOutput,
            RedirectStandardError = command.RedirectOutput,
        };
        foreach (var argument in command.Arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        if (!command.UseShellExecute)
        {
            foreach (var pair in command.Environment)
            {
                startInfo.Environment[pair.Key] = pair.Value;
            }
        }

        var process = Process.Start(startInfo)
            ?? throw new InvalidOperationException($"Failed to start {Path.GetFileName(command.Executable)}.");
        if (command.RedirectOutput)
        {
            Directory.CreateDirectory(logDirectory);
            var logPath = Path.Combine(logDirectory, "mcp-server.log");
            _ = PumpAsync(process.StandardOutput, logPath, redactor, cancellationToken);
            _ = PumpAsync(process.StandardError, logPath, redactor, cancellationToken);
        }

        return Task.FromResult<IManagedProcess>(new WindowsManagedProcess(process, true));
    }

    public void Dispose() => logWriteLock.Dispose();

    private async Task PumpAsync(
        StreamReader reader,
        string logPath,
        SecretRedactor redactor,
        CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                var line = await reader.ReadLineAsync(cancellationToken);
                if (line is null)
                {
                    break;
                }

                await logWriteLock.WaitAsync(cancellationToken);
                try
                {
                    WindowsLogMaintenance.RotateFileIfNeeded(logPath);
                    await File.AppendAllTextAsync(
                        logPath,
                        $"{DateTimeOffset.UtcNow:O} {redactor.Redact(line)}{Environment.NewLine}",
                        cancellationToken);
                }
                finally
                {
                    logWriteLock.Release();
                }
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // Process supervision owns cancellation; no extra failure is needed.
        }
    }

    private sealed class WindowsManagedProcess(Process process, bool owned) : IManagedProcess
    {
        public int Id => process.Id;
        public bool HasExited => process.HasExited;
        public bool IsOwned => owned;

        public async Task<int> WaitForExitAsync(CancellationToken cancellationToken)
        {
            await process.WaitForExitAsync(cancellationToken);
            return process.ExitCode;
        }

        public async Task StopAsync(CancellationToken cancellationToken)
        {
            if (!owned || process.HasExited)
            {
                return;
            }

            process.Kill(true);
            await process.WaitForExitAsync(cancellationToken);
        }

        public ValueTask DisposeAsync()
        {
            process.Dispose();
            return ValueTask.CompletedTask;
        }
    }
}
