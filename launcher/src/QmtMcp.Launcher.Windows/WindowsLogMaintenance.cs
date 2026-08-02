namespace QmtMcp.Launcher.Windows;

public static class WindowsLogMaintenance
{
    public const long MaximumLogBytes = 5 * 1024 * 1024;
    public const int BackupCount = 3;

    public static void RotateDirectory(string rootDirectory)
    {
        if (!Directory.Exists(rootDirectory))
        {
            return;
        }

        try
        {
            foreach (var path in Directory.EnumerateFiles(rootDirectory, "*", SearchOption.AllDirectories)
                         .Where(IsActiveLog))
            {
                RotateFileIfNeeded(path);
            }
        }
        catch (Exception exception) when (exception is UnauthorizedAccessException or IOException)
        {
            // A child may be creating a log directory while maintenance scans it.
        }
    }

    public static void RotateFileIfNeeded(string logPath)
    {
        if (!File.Exists(logPath) || new FileInfo(logPath).Length < MaximumLogBytes)
        {
            return;
        }

        var oldest = $"{logPath}.{BackupCount}";
        if (File.Exists(oldest))
        {
            File.Delete(oldest);
        }

        for (var index = BackupCount - 1; index >= 1; index--)
        {
            var source = $"{logPath}.{index}";
            if (File.Exists(source))
            {
                File.Move(source, $"{logPath}.{index + 1}");
            }
        }

        File.Move(logPath, $"{logPath}.1");
    }

    private static bool IsActiveLog(string path) =>
        Path.GetExtension(path).Equals(".jsonl", StringComparison.OrdinalIgnoreCase);
}
