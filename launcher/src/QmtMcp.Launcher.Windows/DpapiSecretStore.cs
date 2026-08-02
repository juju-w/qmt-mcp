using System.Runtime.Versioning;
using System.Security.Cryptography;
using System.Text;
using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Windows;

[SupportedOSPlatform("windows")]
public sealed class DpapiSecretStore(string rootDirectory) : ISecretStore
{
    private static readonly byte[] Entropy = "QMT-MCP launcher secret v1"u8.ToArray();

    public async Task SaveAsync(string id, string value, CancellationToken cancellationToken = default)
    {
        ValidateId(id);
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Directory.CreateDirectory(rootDirectory);
        var protectedValue = ProtectedData.Protect(
            Encoding.UTF8.GetBytes(value),
            Entropy,
            DataProtectionScope.CurrentUser);
        var path = Path.Combine(rootDirectory, $"{id}.secret");
        var temporaryPath = $"{path}.{Guid.NewGuid():N}.tmp";
        try
        {
            await File.WriteAllBytesAsync(temporaryPath, protectedValue, cancellationToken);
            File.Move(temporaryPath, path, true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    public async Task<string> GetAsync(string id, CancellationToken cancellationToken = default)
    {
        ValidateId(id);
        var protectedValue = await File.ReadAllBytesAsync(
            Path.Combine(rootDirectory, $"{id}.secret"),
            cancellationToken);
        var value = ProtectedData.Unprotect(protectedValue, Entropy, DataProtectionScope.CurrentUser);
        return Encoding.UTF8.GetString(value);
    }

    public Task DeleteAsync(string id, CancellationToken cancellationToken = default)
    {
        ValidateId(id);
        cancellationToken.ThrowIfCancellationRequested();
        var path = Path.Combine(rootDirectory, $"{id}.secret");
        if (File.Exists(path))
        {
            File.Delete(path);
        }

        return Task.CompletedTask;
    }

    private static void ValidateId(string id)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(id);
        if (id.Any(character => !(char.IsAsciiLetterOrDigit(character) || character is '_' or '-')))
        {
            throw new ArgumentException("Secret ID contains unsupported characters.", nameof(id));
        }
    }
}
