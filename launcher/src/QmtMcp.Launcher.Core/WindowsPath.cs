namespace QmtMcp.Launcher.Core;

public static class WindowsPath
{
    public static bool IsAbsolute(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return false;
        }

        var value = path.Trim();
        return value.Length >= 3 && char.IsAsciiLetter(value[0]) && value[1] == ':' && IsSeparator(value[2])
            || value.Length >= 3 && IsSeparator(value[0]) && IsSeparator(value[1]);
    }

    public static string Normalize(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        var normalized = path.Trim().Replace('/', '\\');
        while (normalized.Length > 3 && normalized.EndsWith('\\'))
        {
            normalized = normalized[..^1];
        }

        return normalized;
    }

    public static string NormalizeForComparison(string path) => Normalize(path).ToUpperInvariant();

    public static bool EqualsNormalized(string left, string right) =>
        string.Equals(NormalizeForComparison(left), NormalizeForComparison(right), StringComparison.Ordinal);

    public static string GetFileName(string path)
    {
        var normalized = Normalize(path);
        var index = normalized.LastIndexOf('\\');
        return index < 0 ? normalized : normalized[(index + 1)..];
    }

    public static string GetDirectoryName(string path)
    {
        var normalized = Normalize(path);
        var index = normalized.LastIndexOf('\\');
        if (index < 0)
        {
            return string.Empty;
        }

        if (index == 2 && normalized.Length >= 3 && normalized[1] == ':')
        {
            return normalized[..3];
        }

        return normalized[..index];
    }

    public static string Combine(params string[] parts)
    {
        if (parts.Length == 0)
        {
            return string.Empty;
        }

        var result = Normalize(parts[0]);
        foreach (var part in parts.Skip(1))
        {
            if (string.IsNullOrWhiteSpace(part))
            {
                continue;
            }

            result = $"{result.TrimEnd('\\')}\\{part.Trim().Replace('/', '\\').Trim('\\')}";
        }

        return result;
    }

    public static string Parent(string path) => GetDirectoryName(path);

    private static bool IsSeparator(char value) => value is '\\' or '/';
}
