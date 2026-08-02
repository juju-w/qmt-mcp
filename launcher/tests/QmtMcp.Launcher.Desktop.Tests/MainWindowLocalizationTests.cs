using Avalonia;
using Avalonia.Controls;
using Avalonia.Headless;
using Avalonia.Headless.XUnit;
using Avalonia.Media.Imaging;
using Avalonia.Threading;
using Avalonia.VisualTree;

namespace QmtMcp.Launcher.Desktop.Tests;

public sealed class MainWindowLocalizationTests
{
    [AvaloniaFact]
    public async Task RendersChineseAndEnglishWithoutOverlappingHeaderControls()
    {
        var previousDemoValue = Environment.GetEnvironmentVariable("QMT_LAUNCHER_DEMO");
        var localizationRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "QMT-MCP-Tests",
            Guid.NewGuid().ToString("N"));
        try
        {
            Environment.SetEnvironmentVariable("QMT_LAUNCHER_DEMO", "1");
            await using var runtime = LauncherRuntime.Create();
            var localization = new LocalizationManager(localizationRoot);
            localization.SetLanguage(LocalizationManager.SimplifiedChinese);
            ApplyResources(localization);
            localization.LanguageChanged += (_, _) => ApplyResources(localization);
            var viewModel = new MainWindowViewModel(runtime, localization, action => action());
            await viewModel.InitializeAsync();

            var window = new MainWindow(viewModel, false)
            {
                Width = 940,
                Height = 680,
            };
            window.Show();

            AssertHeaderLayout(window);
            SaveFrame(window, "ui-zh-CN.png");

            window.Width = 760;
            window.Height = 600;
            window.GetVisualDescendants().OfType<TabControl>().Single().SelectedIndex = 1;
            SaveFrame(window, "ui-zh-CN-setup-760.png");

            localization.SetLanguage(LocalizationManager.English);
            window.Width = 940;
            window.Height = 680;
            window.GetVisualDescendants().OfType<TabControl>().Single().SelectedIndex = 0;
            AssertHeaderLayout(window);
            SaveFrame(window, "ui-en-US.png");

            window.Close();
        }
        finally
        {
            Environment.SetEnvironmentVariable("QMT_LAUNCHER_DEMO", previousDemoValue);
            if (Directory.Exists(localizationRoot))
            {
                Directory.Delete(localizationRoot, true);
            }
        }
    }

    private static void ApplyResources(LocalizationManager localization)
    {
        var resources = Application.Current!.Resources;
        foreach (var resource in localization.CurrentStrings)
        {
            resources[resource.Key] = resource.Value;
        }
    }

    private static void AssertHeaderLayout(Window window)
    {
        var headerControls = window.GetVisualDescendants()
            .OfType<Control>()
            .Where(control => control is ComboBox || control is Button button
                && button.Command is not null
                && button.Parent is StackPanel panel
                && panel.Orientation == Avalonia.Layout.Orientation.Horizontal)
            .ToArray();

        Assert.Equal(3, headerControls.Length);
        foreach (var control in headerControls)
        {
            Assert.True(control.Bounds.Width > 0);
            Assert.True(control.Bounds.Right <= window.ClientSize.Width);
        }

        for (var index = 1; index < headerControls.Length; index++)
        {
            Assert.True(headerControls[index - 1].Bounds.Right <= headerControls[index].Bounds.Left);
        }
    }

    private static void SaveFrame(Window window, string fileName)
    {
        Dispatcher.UIThread.RunJobs();
        AvaloniaHeadlessPlatform.ForceRenderTimerTick();
        using var frame = window.CaptureRenderedFrame();
        Assert.NotNull(frame);
        var artifacts = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../../artifacts"));
        Directory.CreateDirectory(artifacts);
        frame.Save(Path.Combine(artifacts, fileName), PngBitmapEncoderOptions.Default);
    }
}
