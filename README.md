# HPKI 電子署名ツール

医療・介護現場での書類業務を効率化する、シンプルな PDF 電子署名ツールです。

**HPKIカード**（医師・看護師カード）または **マイナンバーカード** を使って、複数の PDF にまとめて電子署名できます。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status: Public Beta](https://img.shields.io/badge/Status-Public%20Beta-orange.svg)](https://github.com/lifemate-inc/hpki-signer/releases)

---

## ✨ 特徴

- 🔒 **オフライン完結** — PIN や書類はインターネットを通らず、ご利用パソコン内で処理が完了します
- 🪪 **マイナンバーカード対応** — 公的個人認証サービス（J-LIS）に準拠
- 🏥 **HPKIカード対応** — 医師・看護師向け
- 📁 **フォルダ一括署名** — 大量の PDF を一度に処理
- ⏱ **タイムスタンプ局（TSA）連携** — PAdES LTV 対応
- 🌏 **日本語UI** — 現場の方が直感的に使えるデザイン
- 💾 **オフライン動作** — 初回起動後はインターネット不要

---

## 📥 ダウンロード

[最新リリース](../../releases/latest) から `hpki-signer-setup-X.Y.Z.exe`（約 4 MB）をダウンロードしてご利用ください。

> **ご注意**: 現在 **パブリックベータ** での提供中です。動作保証は限定的ですが、ご利用にあたっての安全設計には最大限の配慮を行っています。

---

## 🔧 動作環境

| 項目 | 内容 |
|------|------|
| OS | Windows 10 / 11（64bit） |
| ICカードリーダー | PC/SC 規格対応品（推奨：サンワサプライ ADR-MNICU2） |
| ICカード | HPKIカード または マイナンバーカード |
| カードリーダードライバ | 各メーカーの公式ダウンロードページから取得 |
| HPKIクライアントソフト | HPKIカード発行元から取得（医師会・看護協会等） |
| JPKI利用者ソフト | [J-LIS 公式](https://www.jpki.go.jp/download/)（無料） |
| 署名検証用 | Adobe Acrobat Reader（無料） |

セットアップウィザードが必要なソフトの未インストールを自動検知し、公式ダウンロードページをご案内します。

---

## 🚀 使い方

1. インストーラ（`hpki-signer-setup-X.Y.Z.exe`）をダブルクリック
2. 初回起動時にセットアップウィザードが立ち上がり、必要な準備をご案内します
3. デスクトップの **「HPKI電子署名ツール」** をダブルクリック
4. ブラウザが開く → カード種別を選び PIN を入力
5. 署名したいフォルダを選択 → 「署名を開始する」

詳しい手順は [インストールガイド](docs/install-guide.md) をご覧ください。

---

## 🔒 セキュリティ設計

PIN や PDF の内容は**インターネットに送信されません**。

```
┌─ ご利用パソコン（オフライン完結） ──────────────┐
│   ブラウザ → ローカルプログラム → カードリーダー │
└──────────────────────────────────────────────┘
            ↑ インターネット（PIN は通りません）
┌─ GitHub Pages（HTMLのみ配信） ──────────────────┐
│   index.html / setup.html                        │
└──────────────────────────────────────────────┘
```

詳しくは [セキュリティについて](https://lifemate-inc.github.io/hpki-signer/security.html) をご覧ください。

### 実装されている保護機構

- **CORS allowlist** — 指定したサイト以外からの API 呼び出しを拒否
- **CSRF トークン** — 起動毎にランダム生成、全 POST で必須
- **Content Security Policy** — 外部スクリプト・iframe を全面制限
- **PIN 自動消去** — 送信直後に入力欄・メモリからクリア
- **PIN 非ログ化** — 動作ログには PIN を一切出力しない

---

## 🏗 リポジトリ構成

```
hpki-signer/
├── bridge/                    PKCS#11 を仲介する Python サーバ
│   ├── bridge.py
│   ├── signer.py              pyhanko による PDF 署名
│   └── *.cer                  J-LIS / MEDIS / MHLW の公開 CA 証明書
├── docs/                      GitHub Pages 配信部
│   ├── index.html             メイン UI
│   ├── setup.html             セットアップウィザード
│   ├── security.html          セキュリティ説明
│   ├── install-guide.md       インストールガイド
│   ├── legal/consent.md       利用同意書テンプレート
│   └── manuals/               各立場向けマニュアル
├── installer/                 配布パッケージ生成
│   ├── HpkiSigner.iss         Inno Setup スクリプト
│   └── launcher/launcher.go   ネイティブランチャー
├── scripts/                   ビルドスクリプト
└── .github/workflows/         GitHub Actions（自動リリース）
```

---

## 🛠 開発・自前ビルド

ソースコードは MIT ライセンスで公開しているため、ご自身でビルドすることも可能です。

### 必要なツール

- Python 3.13+
- Go 1.21+（launcher.exe ビルド用）
- Inno Setup 6（インストーラ生成用）

### 開発用起動

```powershell
cd bridge
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python bridge.py
```

ブラウザで <http://localhost:14733> を開いてください。

### リリースビルド

```powershell
.\scripts\build_all.ps1 -Version "1.1.X"
```

`build/` に `payload-vX.Y.Z.zip` と `hpki-signer-setup-X.Y.Z.exe` が生成されます。

---

## 📋 動作確認済み環境

- HPKIカード（医師・看護師カード）
- マイナンバーカード（J-LIS 署名用CA 第3世代）
- カードリーダー：サンワサプライ ADR-MNICU2、Circle CIR125

---

## 📜 ライセンス

本ソフトウェアは [MIT License](LICENSE) のもとで提供されています。

商用・非商用を問わずご利用・改変・再配布が可能ですが、**動作・適合性・安全性は保証されません**。
電子署名の法的有効性はカード発行元の運用ガイドラインに準じます。

---

## 🤝 フィードバック・お問い合わせ

ご不明点・バグ報告・機能要望は GitHub の Issues よりお寄せください。

- 📋 [Issue を作成する](https://github.com/lifemate-inc/hpki-signer/issues/new)
- 💬 [既存の Issue を見る](https://github.com/lifemate-inc/hpki-signer/issues)

医療・介護現場でのご利用感想やご要望もお待ちしております。

---

## 📝 謝辞

本ツールは以下のオープンソースソフトウェアの恩恵を受けています。

- [pyhanko](https://github.com/MatthiasValvekens/pyHanko) — PAdES 署名のコア
- [python-pkcs11](https://github.com/danni/python-pkcs11) — PKCS#11 バインディング
- [Flask](https://github.com/pallets/flask) — Web フレームワーク
- [Go](https://go.dev/) — ランチャーバイナリ

また、ご利用いただいている医療従事者の皆様からのフィードバックに深く感謝いたします。
