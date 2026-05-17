; ════════════════════════════════════════════════════════════════════
;  HPKI電子署名ツール — インストーラ定義
; ════════════════════════════════════════════════════════════════════
;
; Inno Setup 6+ でビルドします。
;
; ビルドコマンド:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\HpkiSigner.iss
;
; 出力: build\hpki-signer-setup-{Version}.exe
;
; ════════════════════════════════════════════════════════════════════

#define MyAppName            "HPKI電子署名ツール"
#define MyAppShortName       "HpkiSigner"
; MyAppVersion は /DMyAppVersion=X.Y.Z で上書き可能（CIで使用）
#ifndef MyAppVersion
  #define MyAppVersion       "1.1.1"
#endif
#define MyAppPublisher       "lifemate-inc"
#define MyAppURL             "https://lifemate-inc.github.io/hpki-signer/"
#define MyAppExeName         "launcher.exe"

; LocalTest=1 を /D で渡すと、ローカル HTTP サーバ (localhost:8888) を payload 取得先にする
#ifdef LocalTest
  #define MyPayloadURL "http://127.0.0.1:8888/payload-" + MyAppVersion + ".zip"
#else
  #define MyPayloadURL "https://github.com/lifemate-inc/hpki-signer/releases/download/v" + MyAppVersion + "/payload-" + MyAppVersion + ".zip"
#endif

[Setup]
AppId={{E7A2C8F3-1B6D-4F2E-9A0C-3D5E7F1B8C9A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; ユーザー領域インストール（管理者権限不要）
DefaultDirName={localappdata}\{#MyAppShortName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no
DisableWelcomePage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 出力設定
OutputDir=..\build
OutputBaseFilename=hpki-signer-setup-{#MyAppVersion}
SetupIconFile=HpkiSigner.ico
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120

; 対応OS
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LanguageDetectionMethod=locale

; アンインストール時に AppDir 配下を消す
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; \
    GroupDescription: "追加アイコン:"; Flags: checkedonce

[Files]
; 同梱するファイルは最小限（payload は実行時にDL）
Source: "HpkiSigner.ico"; DestDir: "{app}"; Flags: ignoreversion
; payload-{Version}.zip を同梱する場合（オフラインインストール用、コメントアウト中）
; Source: "..\build\payload-{#MyAppVersion}.zip"; DestDir: "{app}\_payload"; Flags: ignoreversion deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\HpkiSigner.ico"
Name: "{group}\セットアップを開く"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--setup"; IconFilename: "{app}\HpkiSigner.ico"
Name: "{group}\アンインストール"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\HpkiSigner.ico"; Tasks: desktopicon

[Run]
; インストール完了後、自動でセットアップを開始
Filename: "{app}\{#MyAppExeName}"; Description: "今すぐ起動する"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; アンインストール時に Python / 依存ライブラリ / ログを完全削除
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\bridge"
Type: filesandordirs; Name: "{app}\docs"
Type: files;          Name: "{app}\launcher.exe"
Type: files;          Name: "{app}\VERSION.txt"
Type: dirifempty;     Name: "{app}"

[Code]
{ ══════════════════════════════════════════════════════════════════
   payload ZIP を GitHub Releases からダウンロード・展開
  ══════════════════════════════════════════════════════════════════ }

var
  DownloadPage: TDownloadWizardPage;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(
    'ファイルをダウンロード中',
    '必要なファイル（Python・ライブラリ等 約50MB）をダウンロードしています。',
    nil
  );
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ZipPath: string;
  ResultCode: Integer;
begin
  if CurPageID = wpReady then begin
    ZipPath := ExpandConstant('{tmp}\payload.zip');
    DownloadPage.Clear;
    DownloadPage.Add('{#MyPayloadURL}', 'payload.zip', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        Result := True;
      except
        SuppressibleMsgBox(
          'ダウンロードに失敗しました。インターネット接続を確認してから、もう一度お試しください。' + #13#10 + #13#10 + GetExceptionMessage,
          mbCriticalError, MB_OK, IDOK
        );
        Result := False;
      end;
    finally
      DownloadPage.Hide;
    end;

    { 展開 — PowerShell の Expand-Archive を使用 }
    if Result then begin
      WizardForm.StatusLabel.Caption := '展開中...';
      Exec(
        ExpandConstant('{cmd}'),
        '/c powershell -NoProfile -Command "Expand-Archive -Path ''' + ZipPath + ''' -DestinationPath ''' + ExpandConstant('{app}') + ''' -Force"',
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode
      );
      if ResultCode <> 0 then begin
        SuppressibleMsgBox(
          'ファイルの展開に失敗しました。コード: ' + IntToStr(ResultCode),
          mbCriticalError, MB_OK, IDOK
        );
        Result := False;
      end;
      DeleteFile(ZipPath);
    end;
  end else
    Result := True;
end;
