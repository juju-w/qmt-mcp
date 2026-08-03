namespace QmtMcp.Launcher.Core;

public sealed class BrokerDiscovery(
    ILauncherFileSystem fileSystem,
    IBrokerProcessInspector processInspector)
{
    private static readonly HashSet<string> ClientNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "XtItClient.exe",
        "XtMiniQmt.exe",
        "XtMiniQMT.exe",
    };

    public async Task<IReadOnlyList<DiscoveryCandidate>> DiscoverAsync(
        IEnumerable<string> savedClientPaths,
        IEnumerable<string> searchRoots,
        CancellationToken cancellationToken)
    {
        var candidates = new Dictionary<string, DiscoveryCandidate>(StringComparer.OrdinalIgnoreCase);

        foreach (var path in savedClientPaths.Where(fileSystem.FileExists))
        {
            Add(candidates, new DiscoveryCandidate(WindowsPath.Normalize(path), "saved-profile", 100));
        }

        foreach (var path in await processInspector.GetRunningClientPathsAsync(cancellationToken))
        {
            if (fileSystem.FileExists(path) && ClientNames.Contains(WindowsPath.GetFileName(path)))
            {
                Add(candidates, new DiscoveryCandidate(WindowsPath.Normalize(path), "running-process", 90));
            }
        }

        foreach (var root in searchRoots.Where(fileSystem.DirectoryExists).Distinct(StringComparer.OrdinalIgnoreCase))
        {
            cancellationToken.ThrowIfCancellationRequested();
            foreach (var path in fileSystem.FindFiles(root, ClientNames, 5, 32, cancellationToken))
            {
                Add(candidates, new DiscoveryCandidate(WindowsPath.Normalize(path), "bounded-search", 50));
            }
        }

        return candidates.Values
            .OrderByDescending(candidate => candidate.Confidence)
            .ThenBy(candidate => candidate.ClientPath, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static void Add(Dictionary<string, DiscoveryCandidate> candidates, DiscoveryCandidate candidate)
    {
        var key = WindowsPath.NormalizeForComparison(candidate.ClientPath);
        if (!candidates.TryGetValue(key, out var existing) || candidate.Confidence > existing.Confidence)
        {
            candidates[key] = candidate;
        }
    }
}
