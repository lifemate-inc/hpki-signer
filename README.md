# HPKI 電子署名ツール

訪問看護ステーション・診療所のために作られた、シンプルな PDF 電子署名ツールです。

**HPKIカード**（医師・看護師カード）または **マイナンバーカード** を使って、複数の PDF にまとめて電子署名できます。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## ✨ 特徴

- 🔒 **PINや書類はインターネットを通らない**（あなたのPC内で完結）
- 🪪 **マイナンバーカード対応**（公的個人認証サービス）
- 🏥 **HPKIカード対応**（医師・看護師）
- 📁 **フォルダ内のPDFを一括署名**
- ⏱ **タイムスタンプ局（TSA）連携**（PAdES LTV対応）
- 🌏 **完全日本語UI**（看護師さん向けに設計）
- 💾 **オフライン動作**（初回起動後はネット不要）

## 📥 ダウンロード

[最新リリース](../../releases/latest) から `hpki-signer-setup-X.Y.Z.exe`（約2MB）をダウンロードして実行してください。

## 🔧 必要なもの

| 項目 | 内容 |
|------|------|
| OS | Windows 10 / 11 (64bit) |
| カードリーダー | 推奨：[サンワサプライ ADR-MNICU2](https://www.sanwa.co.jp/product/syohin?code=ADR-MNICU2)（¥7,040） |
| カード | HPKIカード または マイナンバーカード |
| カードリーダードライバ | 各メーカーの公式DL |
| HPKIクライアントソフト | HPKIカード発行時に同梱（医師/看護師向け） |
| JPKI利用者ソフト | [J-LIS 公式](https://www.jpki.go.jp/download/)（無料） |
| 署名検証用 | Adobe Acrobat Reader（無料） |

セットアップウィザードが必要なソフトの未インストールを自動検知し、公式ダウンロードページを案内します。

## 🚀 使い方

1. インストーラ（`hpki-signer-setup-X.Y.Z.exe`）をダブルクリック
2. 初回起動時にセットアップウィザードが起動 → 案内に従って準備
3. デスクトップの **「HPKI電子署名ツール」** をダブルクリック
4. ブラウザが開く → カード種別を選び PIN を入力
5. 署名したいフォルダを選択 → 「署名を開始する」

## 🔒 セキュリティ

PIN や PDF の内容は**インターネットに送信されません**。

```
┌─ あなたのPC（オフライン部分） ─────────────────┐
│  ブラウザ → localhost:14733 → カードリーダー │
└──────────────────────────────────────────────┘
            ↑ インターネット（PINは絶対通らない）
┌─ GitHub Pages（HTMLだけ） ──────────────────┐
│  index.html / setup.html                     │
└──────────────────────────────────────────────┘
```

詳しくは [セキュリティについて](docs/security.html) をご覧ください。

実装している保護機構：
- **CORS allowlist**：指定したオリジン以外からの API 呼び出しを拒否
- **CSRF token**：起動毎に生成。すべての POST で必須
- **CSP (Content Security Policy)**：外部スクリプト・iframe 全面禁止
- **PIN auto-clear**：送信直後に入力欄・JS変数からクリア
- **No PIN logging**：bridge.log には PIN を一切出力しない

## 🛠 開発

### 必要なツール

- Python 3.13+
- Go 1.21+（launcher.exe ビルド）
- Inno Setup 6（インストーラ生成）

### 開発用起動

```powershell
cd bridge
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python bridge.py
```

ブラウザで <http://127.0.0.1:14733> を開いてください。

### リリースビルド

```powershell
.\scripts\build_all.ps1 -Version "1.1.0"
```

`build/` に `payload-vX.Y.Z.zip` と `hpki-signer-setup-X.Y.Z.exe` が生成されます。

詳細は [installer/README.md](installer/README.md) を参照。

## 🏗 構成

```
hpki-signer/
├── bridge/                    Python Flask ブリッジ（PKCS#11 仲介役）
│   ├── bridge.py
│   ├── signer.py              pyhanko 経由でPDFに署名
│   ├── allowed_origins.txt   CORS設定
│   └── *.cer                  J-LIS / MEDIS / MHLW CA証明書
├── docs/                      GitHub Pages 公開部
│   ├── index.html             メインUI
│   ├── setup.html             初回セットアップウィザード
│   └── security.html          セキュリティ説明
├── installer/                 配布パッケージ生成
│   ├── HpkiSigner.iss         Inno Setup スクリプト
│   ├── launcher/launcher.go   Go ネイティブランチャー
│   └── README.md
├── scripts/                   ビルドスクリプト
│   ├── build_all.ps1
│   └── build_payload.ps1
└── .github/workflows/         GitHub Actions
    └── release.yml            tag push で自動リリース
```

## 📋 動作確認済み環境

- HPKIカード（医師・看護師カード）
- マイナンバーカード（J-LIS 署名用CA 第3世代）
- カードリーダー：サンワサプライ ADR-MNICU2、Circle CIR125

## 📜 ライセンス

[MIT License](LICENSE) — ご自由にお使いください。改変・再配布も自由です。

ただし**動作・適合性・安全性は保証しません**。電子署名の法的有効性はカード発行元の運用ガイドラインに準じます。

## 🤝 フィードバック

[Issues](../../issues) でバグ報告や機能要望を受け付けています。

訪問看護ステーションでの利用感想・改善案も大歓迎です！

## 📝 謝辞

- [pyhanko](https://github.com/MatthiasValvekens/pyHanko) — PAdES署名のコア
- [python-pkcs11](https://github.com/danni/python-pkcs11) — PKCS#11 バインディング
- 看護師の皆さんからのフィードバック
