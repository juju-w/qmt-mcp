using System.Globalization;

namespace QmtMcp.Launcher.Desktop.Tests;

public sealed class LocalizationManagerTests : IDisposable
{
    private readonly string localDataRoot = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "QMT-MCP-Tests",
        Guid.NewGuid().ToString("N"));

    [Fact]
    public void DefaultsToSimplifiedChineseForChineseSystems()
    {
        var localization = new LocalizationManager(localDataRoot, CultureInfo.GetCultureInfo("zh-CN"));

        Assert.Equal(LocalizationManager.SimplifiedChinese, localization.CurrentLanguage);
        Assert.Equal("启动", localization["ActionStart"]);
        Assert.Equal("运行中（PID 42）", localization.Format("StatusRunningPid", 42));
    }

    [Fact]
    public void DefaultsToEnglishForOtherSystems()
    {
        var localization = new LocalizationManager(localDataRoot, CultureInfo.GetCultureInfo("fr-FR"));

        Assert.Equal(LocalizationManager.English, localization.CurrentLanguage);
        Assert.Equal("Start", localization["ActionStart"]);
    }

    [Fact]
    public void PersistsAnExplicitLanguageSelection()
    {
        var first = new LocalizationManager(localDataRoot, CultureInfo.GetCultureInfo("en-US"));
        var changes = 0;
        first.LanguageChanged += (_, _) => changes++;

        first.SetLanguage(LocalizationManager.SimplifiedChinese);
        var restored = new LocalizationManager(localDataRoot, CultureInfo.GetCultureInfo("en-US"));

        Assert.Equal(1, changes);
        Assert.Equal(LocalizationManager.SimplifiedChinese, restored.CurrentLanguage);
        Assert.Equal("诊断", restored["TabDiagnostics"]);
    }

    [Fact]
    public void UnsupportedSelectionsFallBackToEnglish()
    {
        var localization = new LocalizationManager(localDataRoot, CultureInfo.GetCultureInfo("zh-CN"));

        localization.SetLanguage("de-DE");

        Assert.Equal(LocalizationManager.English, localization.CurrentLanguage);
        Assert.Equal("Diagnostics", localization["TabDiagnostics"]);
    }

    public void Dispose()
    {
        if (Directory.Exists(localDataRoot))
        {
            Directory.Delete(localDataRoot, true);
        }
    }
}
