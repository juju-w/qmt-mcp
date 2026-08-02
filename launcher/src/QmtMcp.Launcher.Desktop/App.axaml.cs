using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Interactivity;
using Avalonia.Markup.Xaml;
using QmtMcp.Launcher.Windows;

namespace QmtMcp.Launcher.Desktop;

public sealed partial class App : Application
{
    private const string WindowsActivationName = @"Local\QMT-MCP-Launcher-Activate";
    private MainWindow? mainWindow;
    private LauncherRuntime? runtime;
    private LocalizationManager? localization;
    private SingleInstanceLock? instanceLock;
    private SingleInstanceActivation? instanceActivation;

    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            runtime = LauncherRuntime.Create();
            localization = new LocalizationManager(runtime.LocalDataRoot);
            localization.LanguageChanged += OnLanguageChanged;
            ApplyLocalization();
            instanceLock = SingleInstanceLock.TryAcquire(Path.Combine(runtime.LocalDataRoot, "launcher.lock"));
            if (instanceLock is null)
            {
                if (OperatingSystem.IsWindows())
                {
                    SingleInstanceActivation.SignalExisting(WindowsActivationName);
                }

                runtime.DisposeAsync().AsTask().GetAwaiter().GetResult();
                runtime = null;
                desktop.Shutdown();
                return;
            }

            var startHidden = desktop.Args?.Contains("--background", StringComparer.OrdinalIgnoreCase) == true;
            var viewModel = new MainWindowViewModel(
                runtime,
                localization,
                action => Avalonia.Threading.Dispatcher.UIThread.Post(action));
            mainWindow = new MainWindow(viewModel, startHidden);
            if (OperatingSystem.IsWindows())
            {
                instanceActivation = SingleInstanceActivation.Start(
                    WindowsActivationName,
                    () => Avalonia.Threading.Dispatcher.UIThread.Post(ShowMainWindow));
            }

            desktop.MainWindow = mainWindow;
            desktop.Exit += OnDesktopExit;
            _ = InitializeAsync(viewModel, startHidden);
        }

        base.OnFrameworkInitializationCompleted();
    }

    private void OpenFromTray(object? sender, EventArgs eventArgs)
    {
        ShowMainWindow();
    }

    private void ShowMainWindow()
    {
        if (mainWindow is null)
        {
            return;
        }

        mainWindow.Show();
        mainWindow.ShowInTaskbar = true;
        mainWindow.WindowState = WindowState.Normal;
        mainWindow.Activate();
    }

    private async void ExitFromTray(object? sender, EventArgs eventArgs)
    {
        if (mainWindow is not null)
        {
            mainWindow.AllowClose = true;
            await mainWindow.ViewModel.StopAsync();
        }

        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            desktop.Shutdown();
        }
    }

    private void OnDesktopExit(object? sender, ControlledApplicationLifetimeExitEventArgs eventArgs)
    {
        if (localization is not null)
        {
            localization.LanguageChanged -= OnLanguageChanged;
        }

        if (runtime is not null)
        {
            runtime.DisposeAsync().AsTask().GetAwaiter().GetResult();
        }

        instanceActivation?.Dispose();
        instanceLock?.Dispose();
    }

    private void OnLanguageChanged(object? sender, EventArgs eventArgs) => ApplyLocalization();

    private void ApplyLocalization()
    {
        if (localization is null)
        {
            return;
        }

        foreach (var resource in localization.CurrentStrings)
        {
            Resources[resource.Key] = resource.Value;
        }

        var trayIcons = TrayIcon.GetIcons(this);
        var menu = trayIcons is { Count: > 0 } ? trayIcons[0].Menu : null;
        if (menu?.Items is { Count: >= 3 } items)
        {
            ((NativeMenuItem)items[0]).Header = localization["TrayOpen"];
            ((NativeMenuItem)items[2]).Header = localization["TrayExit"];
        }
    }

    private static async Task InitializeAsync(MainWindowViewModel viewModel, bool startHidden)
    {
        await viewModel.InitializeAsync();
        if (startHidden && viewModel.AutoStartLauncher)
        {
            await viewModel.StartAsync();
        }
    }
}
