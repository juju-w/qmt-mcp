#ifndef MyVersion
  #error MyVersion must be provided with /DMyVersion=X.Y.Z
#endif
#ifndef StageDir
  #error StageDir must be provided with /DStageDir=path
#endif
#ifndef OutputDir
  #error OutputDir must be provided with /DOutputDir=path
#endif
#ifndef OutputBaseFilename
  #error OutputBaseFilename must be provided
#endif

[Setup]
AppId={{A04138B3-E30D-4F16-9754-255AB75D0917}
AppName=QMT-MCP
AppVersion={#MyVersion}
AppPublisher=QMT-MCP contributors
AppPublisherURL=https://github.com/juju-w/qmt-mcp
DefaultDirName={localappdata}\Programs\QMT-MCP
DefaultGroupName=QMT-MCP
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#StageDir}\Assets\app-icon.ico
UninstallDisplayIcon={app}\QmtMcp.Launcher.exe
VersionInfoVersion={#MyVersion}
VersionInfoProductName=QMT-MCP
VersionInfoDescription=Native Windows launcher for QMT-MCP
CloseApplications=yes
RestartApplications=no

[InstallDelete]
; Remove files left by the pre-single-file launcher and rebuild packaged trees.
; User profiles, secrets, logs, and caches live outside {app} under QMT-MCP.
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\server"
Type: filesandordirs; Name: "{app}\Assets"
Type: files; Name: "{app}\*.dll"
Type: files; Name: "{app}\*.pdb"
Type: files; Name: "{app}\*.deps.json"
Type: files; Name: "{app}\*.runtimeconfig.json"
Type: files; Name: "{app}\createdump.exe"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\QMT-MCP"; Filename: "{app}\QmtMcp.Launcher.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\QmtMcp.Launcher.exe"; Description: "Launch QMT-MCP"; Flags: nowait postinstall skipifsilent
