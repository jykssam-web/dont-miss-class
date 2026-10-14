; 놓치지마수업 설치 스크립트 (Inno Setup 6). 빌드: ISCC.exe installer.iss
#define AppName "놓치지마수업"
#define AppVer "1.0.0"
#define ExeName "DontMissClass.exe"

[Setup]
AppId={{7D3B6A52-4C1E-4E8B-9A57-2F0C8E6B1D94}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=공부하는정쌤
AppPublisherURL=https://lifeforteacher.com
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 관리자 권한 없이 내 계정에만 설치한다(학교 PC에서도 설치되게)
PrivilegesRequired=lowest
OutputDir=installer_out
OutputBaseFilename=DontMissClass_Setup_{#AppVer}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#ExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; Flags: unchecked

[Files]
Source: "dist\DontMissClass\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Registry]
; 제거할 때 윈도우 시작 자동 실행 등록도 함께 지운다
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "DontMissClass"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#ExeName}"; Description: "지금 바로 시작해서 설정하기"; Flags: nowait postinstall skipifsilent

[Code]
procedure KillRunning();
var R: Integer;
begin
  Exec('taskkill', '/F /IM {#ExeName}', '', SW_HIDE, ewWaitUntilTerminated, R);
end;

function InitializeSetup(): Boolean;
begin
  KillRunning();
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  KillRunning();
  Result := True;
end;
