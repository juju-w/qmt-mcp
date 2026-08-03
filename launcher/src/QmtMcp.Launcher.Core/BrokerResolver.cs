namespace QmtMcp.Launcher.Core;

public sealed class BrokerResolver(
    ILauncherFileSystem fileSystem,
    IReadOnlyList<string>? xtquantSearchRoots = null)
{
    private static readonly HashSet<string> XtquantMarker = new(StringComparer.OrdinalIgnoreCase)
    {
        "__init__.py",
    };
    private readonly IReadOnlyList<string> externalXtquantSearchRoots = (xtquantSearchRoots ?? [])
        .Where(WindowsPath.IsAbsolute)
        .Select(WindowsPath.Normalize)
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToArray();

    public ResolutionResult Resolve(BrokerSelection selection, CancellationToken cancellationToken = default)
    {
        if (!WindowsPath.IsAbsolute(selection.ClientPath))
        {
            return ResolutionResult.Fail("path_not_absolute", "QMT client path must be an absolute Windows path.");
        }

        var clientPath = WindowsPath.Normalize(selection.ClientPath);
        if (!fileSystem.FileExists(clientPath))
        {
            return ResolutionResult.Fail("client_missing", "The selected QMT client executable does not exist.");
        }

        if (!string.Equals(Path.GetExtension(WindowsPath.GetFileName(clientPath)), ".exe", StringComparison.OrdinalIgnoreCase))
        {
            return ResolutionResult.Fail("client_unsupported", "The selected QMT client must be a Windows executable.");
        }

        var workingDirectory = WindowsPath.GetDirectoryName(clientPath);
        var qmtRoot = string.Equals(WindowsPath.GetFileName(workingDirectory), "bin.x64", StringComparison.OrdinalIgnoreCase)
            ? WindowsPath.Parent(workingDirectory)
            : workingDirectory;
        var evidence = new List<string> { $"client:{clientPath}", $"qmt-root:{qmtRoot}" };

        var xtquant = ResolveXtquant(selection.XtquantRoot, qmtRoot, evidence, cancellationToken);
        if (!xtquant.IsSuccess)
        {
            return xtquant;
        }

        var userdata = ResolveUserdata(selection.UserdataPath, qmtRoot, evidence);
        if (!userdata.IsSuccess)
        {
            return userdata;
        }

        return ResolutionResult.Success(
            new ResolvedBroker(
                clientPath,
                workingDirectory,
                qmtRoot,
                xtquant.Broker!.XtquantRoot,
                userdata.Broker!.UserdataPath,
                evidence));
    }

    private ResolutionResult ResolveXtquant(
        string? explicitRoot,
        string qmtRoot,
        List<string> evidence,
        CancellationToken cancellationToken)
    {
        if (!string.IsNullOrWhiteSpace(explicitRoot))
        {
            if (!WindowsPath.IsAbsolute(explicitRoot))
            {
                return ResolutionResult.Fail("path_not_absolute", "xtquant root must be an absolute Windows path.");
            }

            var root = WindowsPath.Normalize(explicitRoot);
            if (!fileSystem.FileExists(WindowsPath.Combine(root, "xtquant", "__init__.py")))
            {
                return ResolutionResult.Fail("xtquant_missing", "The selected directory does not contain xtquant/__init__.py.");
            }

            evidence.Add($"xtquant:explicit:{root}");
            return PartialBroker(xtquantRoot: root);
        }

        var directMarker = WindowsPath.Combine(qmtRoot, "xtquant", "__init__.py");
        if (fileSystem.FileExists(directMarker))
        {
            evidence.Add($"xtquant:beside-client:{qmtRoot}");
            return PartialBroker(xtquantRoot: qmtRoot);
        }

        var markers = FindXtquantRoots(qmtRoot, 5, 16, cancellationToken);

        if (markers.Length == 1)
        {
            evidence.Add($"xtquant:detected:{markers[0]}");
            return PartialBroker(xtquantRoot: markers[0]);
        }

        if (markers.Length > 1)
        {
            return ResolutionResult.Fail(
                "xtquant_ambiguous",
                "Multiple xtquant packages were found. Select the matching import root explicitly.",
                markers);
        }

        var externalMarkers = externalXtquantSearchRoots
            .SelectMany(root => FindXtquantRoots(root, 4, 16, cancellationToken))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        if (externalMarkers.Length == 1)
        {
            evidence.Add($"xtquant:external:{externalMarkers[0]}");
            return PartialBroker(xtquantRoot: externalMarkers[0]);
        }

        if (externalMarkers.Length > 1)
        {
            return ResolutionResult.Fail(
                "xtquant_ambiguous",
                "Multiple xtquant packages were found in the local SDK roots. Select the matching import root explicitly.",
                externalMarkers);
        }

        return ResolutionResult.Fail(
            "xtquant_missing",
            "No xtquant package was found under the selected QMT tree or local SDK roots.");
    }

    private string[] FindXtquantRoots(
        string searchRoot,
        int maxDepth,
        int maxResults,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var normalizedRoot = WindowsPath.Normalize(searchRoot);
        var roots = new List<string>();
        if (fileSystem.FileExists(WindowsPath.Combine(normalizedRoot, "xtquant", "__init__.py")))
        {
            roots.Add(normalizedRoot);
        }

        roots.AddRange(
            fileSystem.FindFiles(normalizedRoot, XtquantMarker, maxDepth, maxResults, cancellationToken)
                .Where(path => string.Equals(
                    WindowsPath.GetFileName(WindowsPath.GetDirectoryName(path)),
                    "xtquant",
                    StringComparison.OrdinalIgnoreCase))
                .Select(path => WindowsPath.Parent(WindowsPath.GetDirectoryName(path))));
        return roots.Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
    }

    private ResolutionResult ResolveUserdata(string? explicitPath, string qmtRoot, List<string> evidence)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            if (!WindowsPath.IsAbsolute(explicitPath))
            {
                return ResolutionResult.Fail("path_not_absolute", "Userdata path must be an absolute Windows path.");
            }

            var path = WindowsPath.Normalize(explicitPath);
            if (!fileSystem.DirectoryExists(path) && !fileSystem.DirectoryExists(WindowsPath.Parent(path)))
            {
                return ResolutionResult.Fail("userdata_missing", "The userdata path and its parent directory do not exist.");
            }

            evidence.Add($"userdata:explicit:{path}");
            return PartialBroker(userdataPath: path);
        }

        foreach (var name in new[] { "userdata_mini", "userdata" })
        {
            var candidate = WindowsPath.Combine(qmtRoot, name);
            if (fileSystem.DirectoryExists(candidate))
            {
                evidence.Add($"userdata:detected:{candidate}");
                return PartialBroker(userdataPath: candidate);
            }
        }

        var defaultPath = WindowsPath.Combine(qmtRoot, "userdata_mini");
        evidence.Add($"userdata:default:{defaultPath}");
        return PartialBroker(userdataPath: defaultPath);
    }

    private static ResolutionResult PartialBroker(string xtquantRoot = "", string userdataPath = "") =>
        ResolutionResult.Success(new ResolvedBroker("", "", "", xtquantRoot, userdataPath, []));
}
