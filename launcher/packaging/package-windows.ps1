[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string] $Version,

    [string] $OutputDirectory = (Join-Path $PSScriptRoot '..\artifacts'),

    [string] $DependencyPython = 'python',

    [string] $PythonArchivePath,

    [switch] $SkipInstaller
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$PythonVersion = '3.11.9'
$PythonSha256 = '009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b'
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"

$LauncherRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepositoryRoot = (Resolve-Path (Join-Path $LauncherRoot '..')).Path
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$StageDirectory = Join-Path $OutputDirectory 'stage'
$ZipName = "qmt-mcp-launcher_${Version}_windows_x64.zip"
$SetupName = "qmt-mcp-launcher_${Version}_setup.exe"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)] [string] $Command,
        [Parameter(Mandatory = $true)] [string[]] $CommandArguments
    )

    & $Command @CommandArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($CommandArguments -join ' ')"
    }
}

function Resolve-PythonArchive {
    if ($PythonArchivePath) {
        return (Resolve-Path $PythonArchivePath).Path
    }

    $CacheRoot = Join-Path $env:LOCALAPPDATA 'QMT-MCP\build-cache'
    New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
    $Archive = Join-Path $CacheRoot "python-$PythonVersion-embed-amd64.zip"
    if (-not (Test-Path $Archive)) {
        Invoke-WebRequest -Uri $PythonUrl -OutFile $Archive
    }
    return $Archive
}

function Find-InnoCompiler {
    $Command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $Candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) {
            return $Candidate
        }
    }
    throw 'Inno Setup 6 compiler (ISCC.exe) was not found.'
}

function Remove-PackagingOnlyFiles {
    param(
        [Parameter(Mandatory = $true)] [string] $StageRoot,
        [Parameter(Mandatory = $true)] [string] $SitePackagesRoot,
        [Parameter(Mandatory = $true)] [string] $PythonRoot
    )

    Get-ChildItem $StageRoot -File -Recurse -Filter '*.pdb' |
        Remove-Item -Force

    # Keep cryptography, cffi and pycparser together: MCP imports the crypto
    # bindings at startup and the Windows wheel loads _cffi_backend.
    @(
        'pythonwin'
        'win32com'
        'win32comext'
        'adodbapi'
        'isapi'
        'bin'
    ) | ForEach-Object {
        Get-ChildItem $SitePackagesRoot -Force -Filter $_ -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force
    }
    @('win32\Demos', 'win32\include', 'win32\libs', 'win32\scripts') |
        ForEach-Object {
            Remove-Item (Join-Path $SitePackagesRoot $_) `
                -Recurse -Force -ErrorAction SilentlyContinue
        }
    Remove-Item (Join-Path $SitePackagesRoot 'PyWin32.chm') -Force -ErrorAction SilentlyContinue

    @(Get-ChildItem $SitePackagesRoot -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @('test', 'tests') }) |
        Sort-Object { $_.FullName.Length } -Descending |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem $PythonRoot -Directory -Recurse -Filter '__pycache__' -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
    Get-ChildItem $PythonRoot -File -Recurse -Include '*.pyc', '*.pyo' -ErrorAction SilentlyContinue |
        Remove-Item -Force
}

if (-not $IsWindows) {
    throw 'Windows packaging must run on Windows x64.'
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Remove-Item -Recurse -Force $StageDirectory -ErrorAction SilentlyContinue
@($ZipName, $SetupName, 'LAUNCHER_SHA256SUMS') |
    ForEach-Object { Remove-Item -Force (Join-Path $OutputDirectory $_) -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path $StageDirectory | Out-Null

$Project = Join-Path $LauncherRoot 'src\QmtMcp.Launcher.Desktop\QmtMcp.Launcher.Desktop.csproj'
Invoke-Checked -Command dotnet -CommandArguments @(
    'restore', $Project, '--runtime', 'win-x64', '--locked-mode'
)
Invoke-Checked -Command dotnet -CommandArguments @(
    'publish', $Project,
    '--configuration', 'Release',
    '--runtime', 'win-x64',
    '--self-contained', 'true',
    '--no-restore',
    '--output', $StageDirectory,
    "--property:Version=$Version",
    '--property:DebugType=None',
    '--property:DebugSymbols=false'
)

$AssetsDirectory = Join-Path $StageDirectory 'Assets'
New-Item -ItemType Directory -Force -Path $AssetsDirectory | Out-Null
Copy-Item `
    (Join-Path $LauncherRoot 'src\QmtMcp.Launcher.Desktop\Assets\app-icon.ico') `
    $AssetsDirectory

$RuntimeDirectory = Join-Path $StageDirectory 'runtime\python'
New-Item -ItemType Directory -Force -Path $RuntimeDirectory | Out-Null
$Archive = Resolve-PythonArchive
$ActualHash = (Get-FileHash -Algorithm SHA256 $Archive).Hash.ToLowerInvariant()
if ($ActualHash -ne $PythonSha256) {
    throw "Python archive checksum mismatch: expected $PythonSha256, got $ActualHash"
}
Expand-Archive -Path $Archive -DestinationPath $RuntimeDirectory

$SitePackages = Join-Path $RuntimeDirectory 'Lib\site-packages'
New-Item -ItemType Directory -Force -Path $SitePackages | Out-Null
@(
    'python311.zip'
    '.'
    'Lib'
    'Lib\site-packages'
    '..\..\server'
    'import site'
) | Set-Content -Encoding ASCII (Join-Path $RuntimeDirectory 'python311._pth')

$Requirements = Join-Path $PSScriptRoot 'requirements-windows.txt'
Invoke-Checked -Command $DependencyPython -CommandArguments @(
    '-c',
    "import sys; assert sys.version_info[:2] == (3, 11), 'DependencyPython must be Python 3.11'"
)
Invoke-Checked -Command $DependencyPython -CommandArguments @(
    '-m', 'pip', 'install',
    '--disable-pip-version-check',
    '--require-hashes',
    '--only-binary=:all:',
    '--target', $SitePackages,
    '--requirement', $Requirements
)

$ServerDirectory = Join-Path $StageDirectory 'server'
New-Item -ItemType Directory -Force -Path $ServerDirectory | Out-Null
Copy-Item (Join-Path $RepositoryRoot 'appliance\mcp\qmt_mcp.py') $ServerDirectory
Get-ChildItem (Join-Path $RepositoryRoot 'appliance\mcp') -Directory -Filter 'qmt_mcp_*' |
    ForEach-Object { Copy-Item $_.FullName $ServerDirectory -Recurse }
Remove-PackagingOnlyFiles `
    -StageRoot $StageDirectory `
    -SitePackagesRoot $SitePackages `
    -PythonRoot $RuntimeDirectory

Copy-Item (Join-Path $RepositoryRoot 'LICENSE') $StageDirectory
Copy-Item (Join-Path $PSScriptRoot 'README.windows.txt') (Join-Path $StageDirectory 'README.txt')
Set-Content -Encoding ASCII (Join-Path $StageDirectory 'VERSION') $Version

$EmbeddedPython = Join-Path $RuntimeDirectory 'python.exe'
Invoke-Checked -Command $EmbeddedPython -CommandArguments @(
    '-c',
    "import importlib.util, os, sys; import cffi, cryptography, numpy, pandas, qmt_mcp, win32api, win32job; from pathlib import Path; from qmt_mcp_core.runtime_paths import runtime_path; from qmt_mcp_xtdata.search_cache import cache_path; assert sys.version_info[:2] == (3, 11); assert importlib.util.find_spec('asyncpg') is None; assert runtime_path(r'D:\QMT', 'nt') == r'D:\QMT'; expected = Path(os.environ['LOCALAPPDATA']) / 'QMT-MCP' / 'cache' / 'instrument-search-v1.json'; assert cache_path(str(expected)) == expected; print('lean native MCP runtime OK')"
)

$RequiredPaths = @(
    'QmtMcp.Launcher.exe'
    'Assets\app-icon.ico'
    'runtime\python\python.exe'
    'runtime\python\python311._pth'
    'server\qmt_mcp.py'
    'server\qmt_mcp_core\app.py'
    'server\qmt_mcp_apps\resources\kline-chart-v1.html'
    'LICENSE'
    'README.txt'
    'VERSION'
)
foreach ($RequiredPath in $RequiredPaths) {
    if (-not (Test-Path (Join-Path $StageDirectory $RequiredPath))) {
        throw "Package layout is missing $RequiredPath"
    }
}

$ZipPath = Join-Path $OutputDirectory $ZipName
Compress-Archive -Path (Join-Path $StageDirectory '*') -DestinationPath $ZipPath -CompressionLevel Optimal

if (-not $SkipInstaller) {
    $Iscc = Find-InnoCompiler
    $InstallerScript = Join-Path $PSScriptRoot 'qmt-mcp-launcher.iss'
    Invoke-Checked -Command $Iscc -CommandArguments @(
        "/DMyVersion=$Version",
        "/DStageDir=$StageDirectory",
        "/DOutputDir=$OutputDirectory",
        "/DOutputBaseFilename=$([IO.Path]::GetFileNameWithoutExtension($SetupName))",
        $InstallerScript
    )
}

$Artifacts = @($ZipPath)
if (-not $SkipInstaller) {
    $Artifacts += Join-Path $OutputDirectory $SetupName
}
$ChecksumPath = Join-Path $OutputDirectory 'LAUNCHER_SHA256SUMS'
$ChecksumLines = foreach ($Artifact in $Artifacts) {
    $Hash = (Get-FileHash -Algorithm SHA256 $Artifact).Hash.ToLowerInvariant()
    "$Hash  $([IO.Path]::GetFileName($Artifact))"
}
$ChecksumLines | Set-Content -Encoding ASCII $ChecksumPath

Write-Host "Windows launcher artifacts:"
$Artifacts + $ChecksumPath | ForEach-Object { Write-Host "  $_" }
