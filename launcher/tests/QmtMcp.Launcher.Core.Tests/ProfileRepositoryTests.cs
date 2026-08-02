using QmtMcp.Launcher.Core;

namespace QmtMcp.Launcher.Core.Tests;

public sealed class ProfileRepositoryTests
{
    [Fact]
    public async Task ProfilesRoundTripWithoutTokenPlaintext()
    {
        var directory = Path.Combine(Path.GetTempPath(), $"qmt-launcher-test-{Guid.NewGuid():N}");
        var path = Path.Combine(directory, "profiles.json");

        try
        {
            var repository = new ProfileRepository(path);
            var profile = ProfileFixture.Create();
            await repository.SaveAsync(new ProfileDocument
            {
                ActiveProfileId = profile.Id,
                Profiles = [profile],
            }, TestContext.Current.CancellationToken);

            var loaded = await repository.LoadAsync(TestContext.Current.CancellationToken);
            var json = await File.ReadAllTextAsync(path, TestContext.Current.CancellationToken);

            Assert.Equal(profile, Assert.Single(loaded.Profiles));
            Assert.DoesNotContain("plaintext-token", json, StringComparison.Ordinal);
            Assert.Contains("secret_test", json, StringComparison.Ordinal);
        }
        finally
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, true);
            }
        }
    }

    [Fact]
    public async Task UnknownActiveProfileFailsClosed()
    {
        var path = Path.Combine(Path.GetTempPath(), $"qmt-launcher-test-{Guid.NewGuid():N}", "profiles.json");
        var repository = new ProfileRepository(path);

        await Assert.ThrowsAsync<InvalidDataException>(() => repository.SaveAsync(
            new ProfileDocument
            {
                ActiveProfileId = "missing",
                Profiles = [ProfileFixture.Create()],
            },
            TestContext.Current.CancellationToken));
    }
}
