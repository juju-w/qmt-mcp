using Avalonia.Controls;
using Avalonia.Input.Platform;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;

namespace QmtMcp.Launcher.Desktop;

internal sealed partial class MainWindow : Window
{
    public MainWindow(MainWindowViewModel viewModel, bool startHidden)
    {
        InitializeComponent();
        ViewModel = viewModel;
        DataContext = viewModel;
        Closing += OnClosing;
        if (startHidden)
        {
            ShowInTaskbar = false;
            Opened += (_, _) => Hide();
        }
    }

    public MainWindowViewModel ViewModel { get; }
    public bool AllowClose { get; set; }

    private void OnClosing(object? sender, WindowClosingEventArgs eventArgs)
    {
        if (!AllowClose && ViewModel.IsRunning)
        {
            eventArgs.Cancel = true;
            ShowInTaskbar = false;
            Hide();
        }
    }

    private async void BrowseClient_Click(object? sender, RoutedEventArgs eventArgs)
    {
        var files = await StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
        {
            Title = ViewModel.Localize("PickerQmtClient"),
            AllowMultiple = false,
            FileTypeFilter =
            [
                new FilePickerFileType(ViewModel.Localize("PickerWindowsExecutable")) { Patterns = ["*.exe"] },
            ],
        });
        var selected = files.Count > 0 ? files[0] : null;
        if (selected is not null)
        {
            ViewModel.ClientPath = selected.Path.LocalPath;
            await ViewModel.ResolveAsync();
        }
    }

    private async void BrowseXtquant_Click(object? sender, RoutedEventArgs eventArgs)
    {
        var selected = await PickFolderAsync(ViewModel.Localize("PickerXtquant"));
        if (selected is not null)
        {
            ViewModel.XtquantRoot = selected;
            await ViewModel.ResolveAsync();
        }
    }

    private async void BrowseUserdata_Click(object? sender, RoutedEventArgs eventArgs)
    {
        var selected = await PickFolderAsync(ViewModel.Localize("PickerUserdata"));
        if (selected is not null)
        {
            ViewModel.UserdataPath = selected;
            await ViewModel.ResolveAsync();
        }
    }

    private async void CopyConnection_Click(object? sender, RoutedEventArgs eventArgs)
    {
        var clipboard = GetTopLevel(this)?.Clipboard;
        if (clipboard is not null)
        {
            await clipboard.SetTextAsync(await ViewModel.GetConnectionSnippetAsync());
        }
    }

    private async Task<string?> PickFolderAsync(string title)
    {
        var folders = await StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = title,
            AllowMultiple = false,
        });
        return folders.Count > 0 ? folders[0].Path.LocalPath : null;
    }
}
