using System.Collections.ObjectModel;

namespace QmtMcp.Launcher.Core;

public sealed class CommandFactory(string installRoot, string localDataRoot)
{
    public LaunchCommand CreateMcp(LauncherProfile profile, ResolvedBroker broker, string token, string version)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(token);
        var serverRoot = WindowsPath.Combine(installRoot, "server");
        var logsRoot = WindowsPath.Combine(localDataRoot, "logs", profile.Id);
        var stateRoot = WindowsPath.Combine(localDataRoot, "state", profile.Id);
        var cacheRoot = WindowsPath.Combine(localDataRoot, "cache", profile.Id);
        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["PYTHONPATH"] = $"{serverRoot};{broker.XtquantRoot}",
            ["QMT_XTQUANT_DIR_WIN"] = broker.XtquantRoot,
            ["QMT_USERDATA_WIN"] = broker.UserdataPath,
            ["QMT_BROKER_ID"] = profile.Id,
            ["MCP_HOST"] = profile.McpHost,
            ["MCP_PORT"] = profile.McpPort.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["QMT_MCP_AUTH_MODE"] = "static",
            ["QMT_MCP_TOKEN"] = token,
            ["QMT_MCP_VERSION"] = version,
            ["QMT_MCP_AUDIT_PATH"] = WindowsPath.Combine(logsRoot, "mcp-audit.jsonl"),
            ["QMT_MCP_TASK_STORE"] = WindowsPath.Combine(stateRoot, "mcp-tasks-v1.sqlite3"),
            ["QMT_INSTRUMENT_CACHE_PATH"] = WindowsPath.Combine(cacheRoot, "instrument-search-v1.json"),
            ["QMT_QUOTE_SUBSCRIPTION_STORE"] = WindowsPath.Combine(cacheRoot, "quote-subscriptions-v1.json"),
        };

        return new LaunchCommand
        {
            Executable = WindowsPath.Combine(installRoot, "runtime", "python", "python.exe"),
            Arguments = ["-u", WindowsPath.Combine(serverRoot, "qmt_mcp.py")],
            WorkingDirectory = serverRoot,
            Environment = new ReadOnlyDictionary<string, string>(environment),
            UseShellExecute = false,
            RedirectOutput = true,
        };
    }

    public static LaunchCommand CreateTerminal(ResolvedBroker broker) => new()
    {
        Executable = broker.ClientPath,
        WorkingDirectory = broker.WorkingDirectory,
        UseShellExecute = true,
        RedirectOutput = false,
    };
}
