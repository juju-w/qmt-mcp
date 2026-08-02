using System.Runtime.Versioning;
using Microsoft.Win32;

namespace QmtMcp.Launcher.Windows;

[SupportedOSPlatform("windows")]
public static class WindowsShellIntegration
{
    private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string ValueName = "QMT-MCP";

    public static bool IsAutoStartEnabled()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RunKey, false);
        return key?.GetValue(ValueName) is string;
    }

    public static void SetAutoStart(bool enabled, string executablePath)
    {
        using var key = Registry.CurrentUser.CreateSubKey(RunKey, true);
        if (enabled)
        {
            key.SetValue(ValueName, $"\"{executablePath}\" --background", RegistryValueKind.String);
        }
        else
        {
            key.DeleteValue(ValueName, false);
        }
    }
}

public sealed class SingleInstanceLock : IDisposable
{
    private readonly FileStream lockStream;

    private SingleInstanceLock(FileStream lockStream)
    {
        this.lockStream = lockStream;
    }

    public static SingleInstanceLock? TryAcquire(string lockPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(lockPath);
        Directory.CreateDirectory(Path.GetDirectoryName(lockPath)
            ?? throw new ArgumentException("Lock path requires a directory.", nameof(lockPath)));
        try
        {
            return new SingleInstanceLock(new FileStream(
                lockPath,
                FileMode.OpenOrCreate,
                FileAccess.ReadWrite,
                FileShare.None));
        }
        catch (IOException)
        {
            return null;
        }
    }

    public void Dispose() => lockStream.Dispose();
}

public sealed class SingleInstanceActivation : IDisposable
{
    private readonly EventWaitHandle signal;
    private readonly Thread listener;
    private readonly Action activate;
    private volatile bool stopping;

    private SingleInstanceActivation(EventWaitHandle signal, Action activate)
    {
        this.signal = signal;
        this.activate = activate;
        listener = new Thread(Listen)
        {
            IsBackground = true,
            Name = "QMT-MCP activation listener",
        };
        listener.Start();
    }

    [SupportedOSPlatform("windows")]
    public static SingleInstanceActivation Start(string name, Action activate)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        ArgumentNullException.ThrowIfNull(activate);
        return new SingleInstanceActivation(
            new EventWaitHandle(false, EventResetMode.AutoReset, name),
            activate);
    }

    [SupportedOSPlatform("windows")]
    public static void SignalExisting(string name)
    {
        if (EventWaitHandle.TryOpenExisting(name, out var existing))
        {
            using (existing)
            {
                existing.Set();
            }
        }
    }

    public void Dispose()
    {
        stopping = true;
        signal.Set();
        listener.Join(TimeSpan.FromSeconds(2));
        signal.Dispose();
    }

    private void Listen()
    {
        while (true)
        {
            signal.WaitOne();
            if (stopping)
            {
                return;
            }

            activate();
        }
    }
}
