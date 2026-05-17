# インストーラビルド手順

このフォルダには配布用インストーラのビルドに必要なファイルが入っています。

## 必要なツール

- **Go** 1.21 以上 — `launcher.exe` のビルド用
  - 通常: https://go.dev/dl/
  - プロジェクト内ポータブル: `.tools/go/bin/go.exe`（`scripts/build_all.ps1` 実行時に自動DL）
- **Inno Setup 6** — インストーラ生成
  - https://jrsoftware.org/isinfo.php
- **Python 3.13** — `pip wheel` で依存ライブラリを集めるため
  - `bridge/venv` の Python でも可

## ファイル構成

```
installer/
├── HpkiSigner.iss        ← Inno Setup スクリプト
├── HpkiSigner.ico        ← アイコン（256x256 推奨）
├── launcher/
│   ├── launcher.go       ← Go ソース
│   ├── go.mod
│   └── launcher.exe      ← ビルド成果物（gitignore）
└── README.md             ← このファイル
```

## ビルド手順

### 一発ビルド（推奨）

```powershell
.\scripts\build_all.ps1 -Version "1.1.0"
```

これで以下が `build/` 配下に出力されます：

- `payload-v1.1.0.zip`（約50MB）— GitHub Releases にアップロード
- `hpki-signer-setup-1.1.0.exe`（約3MB）— 配布用インストーラ

### 個別ビルド

```powershell
# launcher.exe のみ
cd installer\launcher
go build -ldflags "-s -w -H windowsgui" -o launcher.exe .

# payload のみ
.\scripts\build_payload.ps1 -Version "1.1.0"

# インストーラのみ（payload が既にビルド済みであること）
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" `
    /DMyAppVersion=1.1.0 installer\HpkiSigner.iss
```

## リリースフロー

1. `build_all.ps1` でビルド
2. GitHub に新しいリリースを作成（タグ `v1.1.0` など）
3. `payload-v1.1.0.zip` を Release Assets にアップロード
4. `hpki-signer-setup-1.1.0.exe` も Assets にアップロード
5. 看護師さんには `hpki-signer-setup-1.1.0.exe` の URL を送るだけ

## インストーラの動作仕様

1. ダブルクリックでウィザード起動
2. インストール先確認（デフォルト: `%LOCALAPPDATA%\HpkiSigner`）
3. ライセンス・規約同意（オプション）
4. GitHub Releases から payload-vX.Y.Z.zip をダウンロード（プログレス表示）
5. 展開・配置
6. デスクトップ/スタートメニューにショートカット作成
7. 初回セットアップウィザードを起動（任意）

## アンインストーラ

Inno Setup が自動生成。

- `%LOCALAPPDATA%\HpkiSigner\unins000.exe`
- スタートメニュー → アンインストール

## バージョン管理

- `HpkiSigner.iss` の `MyAppVersion` を更新
- `bridge/bridge.py` の `version` レスポンスも合わせて更新
- `docs/index.html` のフッタにバージョン表示する場合はそこも

## トラブルシューティング

### Inno Setup が見つからない
スクリプトが `Program Files (x86)\Inno Setup 6\ISCC.exe` を探します。別パスにインストールしている場合は環境変数 `ISCC` を設定するか、スクリプトを編集してください。

### Go ビルドエラー
Windows 限定の API を使っているので、ビルドは Windows 上で行います（または `GOOS=windows GOARCH=amd64` でクロスコンパイル）。

### payload ZIP のサイズが大きすぎる
不要なライブラリが入っていないか `bridge/requirements.txt` を確認。pyhanko の依存だけで 40MB ほどになります。

## 署名（将来）

コード署名証明書を取得した場合：

```powershell
# launcher.exe に署名
signtool sign /f cert.pfx /p PASSWORD /t http://timestamp.digicert.com `
    /fd sha256 installer\launcher\launcher.exe

# setup.exe に署名（Inno Setup の SignTool 設定経由）
# HpkiSigner.iss に SignTool ディレクティブを追加
```

Windows SmartScreen は実行回数で信頼を蓄積するので、最初は警告が出ても気にしないでください。
