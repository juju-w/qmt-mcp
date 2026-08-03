using System.Globalization;
using System.Text.Json;

namespace QmtMcp.Launcher.Desktop;

internal sealed record LanguageOption(string Code, string DisplayName);

internal sealed class LocalizationManager
{
    public const string English = "en-US";
    public const string SimplifiedChinese = "zh-CN";

    private static readonly IReadOnlyDictionary<string, string> EnglishStrings = new Dictionary<string, string>
    {
        ["TrayOpen"] = "Open QMT-MCP",
        ["TrayExit"] = "Exit",
        ["Language"] = "Language",
        ["ActionStart"] = "Start",
        ["ActionStop"] = "Stop",
        ["TabStatus"] = "Status",
        ["TabSetup"] = "Setup",
        ["TabDiagnostics"] = "Diagnostics",
        ["SectionRuntime"] = "Runtime",
        ["LabelQmtTerminal"] = "QMT terminal",
        ["LabelMcpServer"] = "MCP server",
        ["LabelMarketData"] = "Market data",
        ["LabelAccountQuery"] = "Account query",
        ["SectionEndpoint"] = "Local MCP endpoint",
        ["ActionCopyConnection"] = "Copy connection",
        ["SectionActiveProfile"] = "Active profile",
        ["LabelName"] = "Name",
        ["LabelValidation"] = "Validation",
        ["LabelSecurity"] = "Security",
        ["SecurityLoopback"] = "Loopback only",
        ["SecurityToken"] = "Bearer token protected for current user",
        ["LabelProfileName"] = "Profile name",
        ["LabelQmtClient"] = "QMT client",
        ["LabelXtquantRoot"] = "xtquant root",
        ["LabelUserdata"] = "Userdata",
        ["LabelMcpPort"] = "MCP port",
        ["LabelStartup"] = "Startup",
        ["StartupAfterSignIn"] = "Start QMT-MCP after Windows sign-in",
        ["ActionBrowse"] = "Browse",
        ["ActionDetectClient"] = "Detect client",
        ["ActionValidatePaths"] = "Validate paths",
        ["ActionSaveProfile"] = "Save profile",
        ["PlaceholderXtquant"] = "Folder containing the xtquant subfolder",
        ["PlaceholderUserdata"] = "userdata_mini directory",
        ["SectionRuntimeLogs"] = "Runtime logs",
        ["RuntimeLogsDescription"] = "Launcher and MCP server output",
        ["ActionOpenLogs"] = "Open logs",
        ["SectionDiagnosticArchive"] = "Diagnostic archive",
        ["ActionExportDiagnostics"] = "Export diagnostics",
        ["PickerQmtClient"] = "Select QMT client",
        ["PickerWindowsExecutable"] = "Windows executable",
        ["PickerXtquant"] = "Select the folder containing the xtquant subfolder",
        ["PickerUserdata"] = "Select userdata_mini directory",
        ["StateStopped"] = "Stopped",
        ["StateReady"] = "Ready",
        ["StateWaitingForLogin"] = "Waiting for login",
        ["StateDegraded"] = "Degraded",
        ["StateActionRequired"] = "Action required",
        ["StateStarting"] = "Starting",
        ["StateStopping"] = "Stopping",
        ["DetailSelectClient"] = "Select a QMT client to create a local profile.",
        ["DetailValidating"] = "Validating profile",
        ["DetailStartingMcp"] = "Starting MCP server",
        ["DetailAttachedQmt"] = "Attached to the running QMT terminal",
        ["DetailStartingQmt"] = "Starting QMT terminal",
        ["DetailWaitingForLogin"] = "Waiting for QMT login and market data readiness",
        ["DetailReady"] = "Market data is ready",
        ["DetailDegraded"] = "One or more runtime components are degraded",
        ["DetailStopping"] = "Stopping MCP server",
        ["DetailStopped"] = "QMT-MCP is stopped",
        ["DetailMcpStopped"] = "MCP server stopped and will be restarted when allowed",
        ["DetailQmtStopped"] = "QMT terminal stopped",
        ["DetailProfileInvalid"] = "Profile validation failed",
        ["DetailStartupFailed"] = "Unable to start QMT-MCP",
        ["DetailRestartExhausted"] = "MCP server restart limit reached",
        ["StatusNotConfigured"] = "Not configured",
        ["StatusStopped"] = "Stopped",
        ["StatusUnknown"] = "Unknown",
        ["StatusDisabled"] = "Disabled",
        ["StatusConfigurationIncomplete"] = "Configuration incomplete",
        ["StatusConfigured"] = "Configured",
        ["StatusRunningPid"] = "Running (PID {0})",
        ["StatusLivePid"] = "Live (PID {0})",
        ["StatusStartingPid"] = "Starting (PID {0})",
        ["ComponentReady"] = "Ready",
        ["ComponentDegraded"] = "Degraded",
        ["ComponentDisabled"] = "Disabled",
        ["ComponentUnknown"] = "Unknown",
        ["ComponentLoginRequired"] = "Login required",
        ["ComponentError"] = "Error",
        ["ResolutionNoClient"] = "No client selected",
        ["ResolutionUnable"] = "Unable to resolve QMT paths.",
        ["ResolutionValidated"] = "Client, xtquant, and userdata paths validated",
        ["ResolutionNoClientFound"] = "No QMT client found. Select the executable manually.",
        ["ResolutionDetected"] = "Detected from {0}; paths validated",
        ["ResolutionProfileSaved"] = "Profile saved locally",
        ["ResolutionPathNotAbsolute"] = "The selected path must be an absolute Windows path.",
        ["ResolutionClientMissing"] = "The selected QMT client executable does not exist.",
        ["ResolutionClientUnsupported"] = "The selected QMT client must be a Windows executable.",
        ["ResolutionXtquantMissing"] = "No xtquant was found in this QMT installation. Download/install its Python SDK in the broker client, or browse to the extracted SDK import root.",
        ["ResolutionXtquantAmbiguous"] = "Multiple xtquant packages were found. Select the matching import root.",
        ["ResolutionUserdataMissing"] = "The userdata directory or its parent does not exist.",
        ["NoDiagnosticArchive"] = "No diagnostic archive exported",
        ["ErrorSaveProfileBeforeCopy"] = "Save a valid profile before copying the connection.",
    };

    private static readonly IReadOnlyDictionary<string, string> ChineseStrings = new Dictionary<string, string>
    {
        ["TrayOpen"] = "打开 QMT-MCP",
        ["TrayExit"] = "退出",
        ["Language"] = "语言",
        ["ActionStart"] = "启动",
        ["ActionStop"] = "停止",
        ["TabStatus"] = "状态",
        ["TabSetup"] = "设置",
        ["TabDiagnostics"] = "诊断",
        ["SectionRuntime"] = "运行状态",
        ["LabelQmtTerminal"] = "QMT 终端",
        ["LabelMcpServer"] = "MCP 服务",
        ["LabelMarketData"] = "行情数据",
        ["LabelAccountQuery"] = "账户查询",
        ["SectionEndpoint"] = "本地 MCP 地址",
        ["ActionCopyConnection"] = "复制连接配置",
        ["SectionActiveProfile"] = "当前配置",
        ["LabelName"] = "名称",
        ["LabelValidation"] = "校验结果",
        ["LabelSecurity"] = "安全",
        ["SecurityLoopback"] = "仅允许本机访问",
        ["SecurityToken"] = "访问令牌已使用当前 Windows 用户身份保护",
        ["LabelProfileName"] = "配置名称",
        ["LabelQmtClient"] = "QMT 客户端",
        ["LabelXtquantRoot"] = "xtquant 根目录",
        ["LabelUserdata"] = "用户数据目录",
        ["LabelMcpPort"] = "MCP 端口",
        ["LabelStartup"] = "开机启动",
        ["StartupAfterSignIn"] = "登录 Windows 后启动 QMT-MCP",
        ["ActionBrowse"] = "浏览",
        ["ActionDetectClient"] = "自动查找客户端",
        ["ActionValidatePaths"] = "校验路径",
        ["ActionSaveProfile"] = "保存配置",
        ["PlaceholderXtquant"] = "包含 xtquant 子目录的文件夹",
        ["PlaceholderUserdata"] = "userdata_mini 目录",
        ["SectionRuntimeLogs"] = "运行日志",
        ["RuntimeLogsDescription"] = "启动器与 MCP 服务输出",
        ["ActionOpenLogs"] = "打开日志",
        ["SectionDiagnosticArchive"] = "诊断包",
        ["ActionExportDiagnostics"] = "导出诊断包",
        ["PickerQmtClient"] = "选择 QMT 客户端",
        ["PickerWindowsExecutable"] = "Windows 可执行文件",
        ["PickerXtquant"] = "选择包含 xtquant 子目录的文件夹",
        ["PickerUserdata"] = "选择 userdata_mini 目录",
        ["StateStopped"] = "已停止",
        ["StateReady"] = "已就绪",
        ["StateWaitingForLogin"] = "等待登录",
        ["StateDegraded"] = "部分功能不可用",
        ["StateActionRequired"] = "需要处理",
        ["StateStarting"] = "正在启动",
        ["StateStopping"] = "正在停止",
        ["DetailSelectClient"] = "请选择 QMT 客户端并创建本地配置。",
        ["DetailValidating"] = "正在校验配置",
        ["DetailStartingMcp"] = "正在启动 MCP 服务",
        ["DetailAttachedQmt"] = "已连接到正在运行的 QMT 终端",
        ["DetailStartingQmt"] = "正在启动 QMT 终端",
        ["DetailWaitingForLogin"] = "正在等待 QMT 登录和行情数据就绪",
        ["DetailReady"] = "行情数据已就绪",
        ["DetailDegraded"] = "一个或多个运行组件当前不可用",
        ["DetailStopping"] = "正在停止 MCP 服务",
        ["DetailStopped"] = "QMT-MCP 已停止",
        ["DetailMcpStopped"] = "MCP 服务已停止，将按策略尝试恢复",
        ["DetailQmtStopped"] = "QMT 终端已停止",
        ["DetailProfileInvalid"] = "配置校验失败",
        ["DetailStartupFailed"] = "无法启动 QMT-MCP",
        ["DetailRestartExhausted"] = "MCP 服务已达到重启次数上限",
        ["StatusNotConfigured"] = "尚未配置",
        ["StatusStopped"] = "已停止",
        ["StatusUnknown"] = "未知",
        ["StatusDisabled"] = "未启用",
        ["StatusConfigurationIncomplete"] = "配置不完整",
        ["StatusConfigured"] = "已配置",
        ["StatusRunningPid"] = "运行中（PID {0}）",
        ["StatusLivePid"] = "服务正常（PID {0}）",
        ["StatusStartingPid"] = "启动中（PID {0}）",
        ["ComponentReady"] = "已就绪",
        ["ComponentDegraded"] = "不可用",
        ["ComponentDisabled"] = "未启用",
        ["ComponentUnknown"] = "未知",
        ["ComponentLoginRequired"] = "需要登录",
        ["ComponentError"] = "错误",
        ["ResolutionNoClient"] = "尚未选择客户端",
        ["ResolutionUnable"] = "无法解析 QMT 路径。",
        ["ResolutionValidated"] = "客户端、xtquant 和用户数据目录均已校验",
        ["ResolutionNoClientFound"] = "未找到 QMT 客户端，请手动选择可执行文件。",
        ["ResolutionDetected"] = "已从 {0} 找到客户端并完成路径校验",
        ["ResolutionProfileSaved"] = "配置已保存在本机",
        ["ResolutionPathNotAbsolute"] = "所选路径必须是 Windows 绝对路径。",
        ["ResolutionClientMissing"] = "所选 QMT 客户端不存在。",
        ["ResolutionClientUnsupported"] = "所选 QMT 客户端必须是 Windows 可执行文件。",
        ["ResolutionXtquantMissing"] = "此 QMT 安装中未找到 xtquant。请先在券商 QMT 客户端下载/安装 Python SDK，或解压 SDK 包后浏览选择其导入根目录。",
        ["ResolutionXtquantAmbiguous"] = "找到多个 xtquant，请手动选择正确的导入根目录。",
        ["ResolutionUserdataMissing"] = "用户数据目录及其父目录均不存在。",
        ["NoDiagnosticArchive"] = "尚未导出诊断包",
        ["ErrorSaveProfileBeforeCopy"] = "请先保存有效配置，再复制连接信息。",
    };

    private static readonly IReadOnlyList<LanguageOption> SupportedLanguages =
    [
        new(SimplifiedChinese, "中文（简体）"),
        new(English, "English"),
    ];

    private readonly string settingsPath;
    private string currentLanguage;

    public LocalizationManager(string localDataRoot, CultureInfo? systemCulture = null)
    {
        ValidateCatalogs();
        settingsPath = Path.Combine(localDataRoot, "ui-settings.json");
        currentLanguage = LoadLanguage()
            ?? GetDefaultLanguage(systemCulture ?? CultureInfo.CurrentUICulture);
        ApplyCulture(currentLanguage);
    }

    public event EventHandler? LanguageChanged;

    public static IReadOnlyList<LanguageOption> Languages => SupportedLanguages;
    public string CurrentLanguage => currentLanguage;
    public IReadOnlyDictionary<string, string> CurrentStrings => GetCatalog(currentLanguage);

    public string this[string key] => CurrentStrings.TryGetValue(key, out var value)
        ? value
        : EnglishStrings.TryGetValue(key, out var fallback) ? fallback : key;

    public string Format(string key, params object?[] arguments) =>
        string.Format(CultureInfo.CurrentCulture, this[key], arguments);

    public void SetLanguage(string language)
    {
        var normalized = NormalizeLanguage(language);
        if (string.Equals(currentLanguage, normalized, StringComparison.Ordinal))
        {
            return;
        }

        currentLanguage = normalized;
        ApplyCulture(currentLanguage);
        SaveLanguage();
        LanguageChanged?.Invoke(this, EventArgs.Empty);
    }

    private static string GetDefaultLanguage(CultureInfo culture) =>
        culture.Name.StartsWith("zh", StringComparison.OrdinalIgnoreCase)
            ? SimplifiedChinese
            : English;

    private static string NormalizeLanguage(string language) =>
        string.Equals(language, SimplifiedChinese, StringComparison.OrdinalIgnoreCase)
            ? SimplifiedChinese
            : English;

    private static IReadOnlyDictionary<string, string> GetCatalog(string language) =>
        string.Equals(language, SimplifiedChinese, StringComparison.Ordinal)
            ? ChineseStrings
            : EnglishStrings;

    private static void ApplyCulture(string language)
    {
        var culture = CultureInfo.GetCultureInfo(language);
        CultureInfo.CurrentCulture = culture;
        CultureInfo.CurrentUICulture = culture;
    }

    private string? LoadLanguage()
    {
        try
        {
            if (!File.Exists(settingsPath))
            {
                return null;
            }

            var settings = JsonSerializer.Deserialize<UiSettings>(File.ReadAllText(settingsPath));
            return settings?.SchemaVersion == 1 ? NormalizeLanguage(settings.Language) : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    private void SaveLanguage()
    {
        try
        {
            var directory = Path.GetDirectoryName(settingsPath)!;
            Directory.CreateDirectory(directory);
            var temporaryPath = $"{settingsPath}.{Guid.NewGuid():N}.tmp";
            File.WriteAllText(
                temporaryPath,
                JsonSerializer.Serialize(new UiSettings { Language = currentLanguage }));
            File.Move(temporaryPath, settingsPath, true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // The selected language still applies for the current process.
        }
    }

    private static void ValidateCatalogs()
    {
        var missingChinese = EnglishStrings.Keys.Except(ChineseStrings.Keys, StringComparer.Ordinal).ToArray();
        var extraChinese = ChineseStrings.Keys.Except(EnglishStrings.Keys, StringComparer.Ordinal).ToArray();
        if (missingChinese.Length > 0 || extraChinese.Length > 0)
        {
            throw new InvalidOperationException("Localization catalogs must contain identical keys.");
        }
    }

    private sealed record UiSettings
    {
        public int SchemaVersion { get; init; } = 1;
        public required string Language { get; init; }
    }
}
