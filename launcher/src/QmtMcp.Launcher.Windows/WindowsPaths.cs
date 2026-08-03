using System.Runtime.Versioning;
using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Windows;

public sealed record LauncherPaths(
    string InstallRoot,
    string LocalDataRoot,
    string ProfilesPath,
    string SecretsRoot,
    string LogsRoot,
    string DiagnosticsRoot)
{
    [SupportedOSPlatform("windows")]
    public static LauncherPaths ForCurrentUser(string? installRoot = null)
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var dataRoot = Path.Combine(local, "QMT-MCP");
        return new LauncherPaths(
            installRoot ?? AppContext.BaseDirectory,
            dataRoot,
            Path.Combine(dataRoot, "profiles.json"),
            Path.Combine(dataRoot, "secrets"),
            Path.Combine(dataRoot, "logs"),
            Path.Combine(dataRoot, "diagnostics"));
    }

    public void EnsureCreated()
    {
        Directory.CreateDirectory(LocalDataRoot);
        Directory.CreateDirectory(SecretsRoot);
        Directory.CreateDirectory(LogsRoot);
        Directory.CreateDirectory(DiagnosticsRoot);
    }
}
