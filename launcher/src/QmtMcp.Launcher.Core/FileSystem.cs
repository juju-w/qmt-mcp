namespace QmtMcp.Launcher.Core;

public interface ILauncherFileSystem
{
    bool FileExists(string path);
    bool DirectoryExists(string path);
    void EnsureDirectory(string path);
    IReadOnlyList<string> FindFiles(
        string root,
        IReadOnlySet<string> fileNames,
        int maxDepth,
        int maxResults,
        CancellationToken cancellationToken);
}

public sealed class SystemLauncherFileSystem : ILauncherFileSystem
{
    public bool FileExists(string path) => File.Exists(path);

    public bool DirectoryExists(string path) => Directory.Exists(path);

    public void EnsureDirectory(string path) => Directory.CreateDirectory(path);

    public IReadOnlyList<string> FindFiles(
        string root,
        IReadOnlySet<string> fileNames,
        int maxDepth,
        int maxResults,
        CancellationToken cancellationToken)
    {
        if (maxDepth < 0 || maxResults <= 0 || !Directory.Exists(root))
        {
            return [];
        }

        var matches = new List<string>();
        var pending = new Stack<(string Path, int Depth)>();
        pending.Push((root, 0));
        var visited = 0;

        while (pending.Count > 0 && matches.Count < maxResults && visited < 20_000)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var current = pending.Pop();
            visited++;

            try
            {
                foreach (var file in Directory.EnumerateFiles(current.Path))
                {
                    if (fileNames.Contains(Path.GetFileName(file)))
                    {
                        matches.Add(file);
                        if (matches.Count >= maxResults)
                        {
                            break;
                        }
                    }
                }

                if (current.Depth >= maxDepth)
                {
                    continue;
                }

                foreach (var directory in Directory.EnumerateDirectories(current.Path))
                {
                    pending.Push((directory, current.Depth + 1));
                }
            }
            catch (Exception exception) when (exception is UnauthorizedAccessException or IOException)
            {
                // Broker trees often contain protected update/cache directories.
            }
        }

        return matches;
    }
}

public interface IBrokerProcessInspector
{
    Task<IReadOnlyList<string>> GetRunningClientPathsAsync(CancellationToken cancellationToken);
}
