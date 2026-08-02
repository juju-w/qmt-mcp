using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace QmtMcp.Launcher.Core;

public static partial class ProfileValidator
{
    public static IReadOnlyList<string> Validate(LauncherProfile profile)
    {
        var errors = new List<string>();
        if (profile.SchemaVersion != 1)
        {
            errors.Add("Only profile schema version 1 is supported.");
        }

        if (!ProfileIdPattern().IsMatch(profile.Id))
        {
            errors.Add("Profile ID must contain only lowercase letters, digits, dots, underscores, or hyphens.");
        }

        if (string.IsNullOrWhiteSpace(profile.DisplayName))
        {
            errors.Add("Display name is required.");
        }

        foreach (var (label, path) in new[]
                 {
                     ("Client", profile.ClientPath),
                     ("Working directory", profile.WorkingDirectory),
                     ("xtquant root", profile.XtquantRoot),
                     ("Userdata", profile.UserdataPath),
                 })
        {
            if (!WindowsPath.IsAbsolute(path))
            {
                errors.Add($"{label} path must be absolute.");
            }
        }

        if (!string.Equals(profile.McpHost, "127.0.0.1", StringComparison.Ordinal))
        {
            errors.Add("Schema version 1 permits only the 127.0.0.1 MCP host.");
        }

        if (profile.McpPort is < 1024 or > 65535)
        {
            errors.Add("MCP port must be between 1024 and 65535.");
        }

        if (string.IsNullOrWhiteSpace(profile.TokenSecretId))
        {
            errors.Add("Token secret reference is required.");
        }

        return errors;
    }

    [GeneratedRegex("^[a-z0-9][a-z0-9._-]{0,63}$", RegexOptions.CultureInvariant)]
    private static partial Regex ProfileIdPattern();
}

public sealed class ProfileRepository(string documentPath)
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public async Task<ProfileDocument> LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(documentPath))
        {
            return new ProfileDocument();
        }

        await using var stream = File.OpenRead(documentPath);
        var document = await JsonSerializer.DeserializeAsync<ProfileDocument>(stream, JsonOptions, cancellationToken)
            ?? throw new InvalidDataException("Profile document is empty.");
        ValidateDocument(document);
        return document;
    }

    public async Task SaveAsync(ProfileDocument document, CancellationToken cancellationToken = default)
    {
        ValidateDocument(document);
        var directory = Path.GetDirectoryName(documentPath)
            ?? throw new InvalidOperationException("Profile document path has no parent directory.");
        Directory.CreateDirectory(directory);
        var temporaryPath = $"{documentPath}.{Guid.NewGuid():N}.tmp";

        try
        {
            await using (var stream = File.Create(temporaryPath))
            {
                await JsonSerializer.SerializeAsync(stream, document, JsonOptions, cancellationToken);
            }

            File.Move(temporaryPath, documentPath, true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    private static void ValidateDocument(ProfileDocument document)
    {
        if (document.SchemaVersion != 1)
        {
            throw new InvalidDataException("Unsupported profile document schema version.");
        }

        var duplicate = document.Profiles
            .GroupBy(profile => profile.Id, StringComparer.Ordinal)
            .FirstOrDefault(group => group.Count() > 1);
        if (duplicate is not null)
        {
            throw new InvalidDataException($"Duplicate profile ID: {duplicate.Key}");
        }

        foreach (var profile in document.Profiles)
        {
            var errors = ProfileValidator.Validate(profile);
            if (errors.Count > 0)
            {
                throw new InvalidDataException(string.Join(" ", errors));
            }
        }

        if (document.ActiveProfileId is not null
            && !document.Profiles.Any(profile => profile.Id == document.ActiveProfileId))
        {
            throw new InvalidDataException("Active profile does not exist.");
        }
    }
}
