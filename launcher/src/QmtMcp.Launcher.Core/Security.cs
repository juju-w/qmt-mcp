using System.Security.Cryptography;
using System.Text.RegularExpressions;

namespace QmtMcp.Launcher.Core;

public interface ISecretStore
{
    Task SaveAsync(string id, string value, CancellationToken cancellationToken = default);
    Task<string> GetAsync(string id, CancellationToken cancellationToken = default);
    Task DeleteAsync(string id, CancellationToken cancellationToken = default);
}

public static class TokenGenerator
{
    public static string Generate()
    {
        Span<byte> bytes = stackalloc byte[32];
        RandomNumberGenerator.Fill(bytes);
        return Convert.ToHexStringLower(bytes);
    }
}

public sealed partial class SecretRedactor(IEnumerable<string>? secrets = null)
{
    private readonly string[] values = secrets?
        .Where(value => !string.IsNullOrWhiteSpace(value))
        .Distinct(StringComparer.Ordinal)
        .OrderByDescending(value => value.Length)
        .ToArray() ?? [];

    public string Redact(string? input)
    {
        if (string.IsNullOrEmpty(input))
        {
            return input ?? string.Empty;
        }

        var output = BearerPattern().Replace(input, "Bearer <redacted>");
        foreach (var value in values)
        {
            output = output.Replace(value, "<redacted>", StringComparison.Ordinal);
        }

        return AccountIdPattern().Replace(output, "<redacted-id>");
    }

    [GeneratedRegex("Bearer\\s+[^\\s,;]+", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex BearerPattern();

    [GeneratedRegex("(?<!\\d)\\d{8,18}(?!\\d)", RegexOptions.CultureInvariant)]
    private static partial Regex AccountIdPattern();
}
