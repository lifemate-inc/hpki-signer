# スクリーンショット

公開ドキュメントで参照する画像の格納先です。
[`scripts/capture_screenshots.py`](../../scripts/capture_screenshots.py) で自動撮影されます。

## 撮影済みの画像

### 接続状態

| ファイル名 | 内容 |
|-----------|------|
| `00-disconnected.png` | ブリッジ未起動時の案内（赤色チップ） |
| `01-beta-consent-dialog.png` | 初回起動時のベータ同意ダイアログ |

### メイン署名画面

| ファイル名 | 内容 |
|-----------|------|
| `05-main-ui.png` | カード選択・PIN入力・フォルダ選択のメイン画面 |
| `06-advanced-settings.png` | 詳細設定（TSA選択・出力サフィックス等）展開時 |
| `07-custom-dll-input.png` | カスタムDLLパス入力欄（上級者向け）展開時 |
| `40-signing-progress.png` | 署名処理中（オーバーレイ + プログレスバー） |
| `30-done-success.png` | 4件すべて成功時の完了画面 |
| `31-done-with-error.png` | 一部失敗時の完了画面（エラー件名表示） |
| `50-mobile-main-ui.png` | 狭い幅（タブレット/縦型ディスプレイ）でのメイン画面 |

### セットアップ・案内

| ファイル名 | 内容 |
|-----------|------|
| `10-setup-welcome.png` | セットアップウィザード ステップ1: ようこそ |
| `11-setup-environment.png` | セットアップウィザード ステップ2: 環境確認 |
| `20-security-page.png` | セキュリティの仕組みページ全景 |

### Windows / Acrobat 統合

| ファイル名 | 内容 |
|-----------|------|
| `02-installer-smartscreen.png` | SmartScreen 警告（MOTW 付き未署名 exe 起動時） |
| `03-installer-wizard.png` | Inno Setup ウィザード welcome 画面 |
| `08-folder-pick.png` | Windows ネイティブのフォルダ選択ダイアログ |
| `60-acrobat-verified.png` | Acrobat Reader で署名済 PDF を開いた「すべての署名が有効」表示 |
| `61-acrobat-trust-setting.png` | Acrobat 環境設定 → 署名 → 検証 セクション |

## 自動撮影スクリプト

ブラウザ UI のスクショ (00-50 番台) は以下で再生成可能:

```powershell
# bridge を起動した状態で実行
.\bridge\venv\Scripts\python.exe scripts\capture_screenshots.py
```

Windows / Acrobat 統合のスクショ (60-61 番台) は別スクリプト:

```powershell
# Acrobat で署名済 PDF を開いた状態で実行
.\bridge\venv\Scripts\python.exe scripts\capture_acrobat_trust.py
# その後 PowerShell で screenshot_helper を直接呼ぶ
.\scripts\screenshot_helper.ps1 -OutPath docs\screenshots\60-acrobat-verified.png -WindowTitle "Acrobat"
```

playwright が未インストールならインストール:

```powershell
.\bridge\venv\Scripts\python.exe -m pip install playwright pywinauto Pillow
.\bridge\venv\Scripts\python.exe -m playwright install chromium
```

## 公開ドキュメントでの参照箇所

- [`README.md`](../../README.md): メインUI・完了画面
- [`docs/install-guide.md`](../install-guide.md): セットアップウィザード
- [`docs/manuals/end-user/02_daily-use.md`](../manuals/end-user/02_daily-use.md): 日々の使い方フロー

---

最終更新: 2026-05-19
