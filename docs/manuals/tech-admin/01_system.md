# 技術責任者向け：システム概要

ステーション内で HPKI電子署名ツールの導入・運用を担当する**IT担当者・技術責任者**向けの技術仕様書です。
専門用語をそのまま使います。

---

## システム全体像

```
┌─ ステーションの PC（このマシン内で完結）────────────────────────┐
│                                                                │
│  ┌─ Webブラウザ ─────────────────────────────────────┐         │
│  │                                                   │         │
│  │  HTML/CSS/JS                                      │         │
│  │  ・docs/index.html: メイン UI                     │         │
│  │  ・docs/setup.html: 初回セットアップウィザード     │         │
│  │  ・docs/security.html: セキュリティ説明           │         │
│  │                                                   │         │
│  │  CSRF token / CORS allowlist / CSP で保護         │         │
│  │                                                   │         │
│  └────┬──────────────────────────────────────────────┘         │
│       │ HTTP (localhost:14733)                                 │
│       ↓                                                        │
│  ┌─ Bridge (Python Flask) ──────────────────────────┐         │
│  │                                                   │         │
│  │  ・bridge.py: HTTP API サーバ                    │         │
│  │  ・signer.py: pyhanko による PDF 署名処理         │         │
│  │  ・python-pkcs11 経由でカード操作                 │         │
│  │                                                   │         │
│  └────┬──────────────────────────────────────────────┘         │
│       │ PKCS#11 (DLL 経由)                                     │
│       ↓                                                        │
│  ┌─ クライアントソフト ────────────────────────────────┐         │
│  │                                                   │         │
│  │  ・HPKIクライアント (HpkiAuthP11_MPKCS11H.dll)    │         │
│  │  ・JPKI 利用者ソフト (JPKIPKCS11Sign64.dll)       │         │
│  │                                                   │         │
│  └────┬──────────────────────────────────────────────┘         │
│       │ Windows Smart Card API (winscard.dll)                 │
│       ↓                                                        │
│  ┌─ カードリーダー（USB接続）────────────────────────┐         │
│  │  ADR-MNICU2 等 (PC/SC 規格)                       │         │
│  └────┬──────────────────────────────────────────────┘         │
│       │ ISO/IEC 7816 (T=0, T=1)                              │
│       ↓                                                        │
│  ┌─ ICカード ─────────────────────────────────────────┐         │
│  │  ・HPKIカード                                     │         │
│  │  ・マイナンバーカード                              │         │
│  └───────────────────────────────────────────────────┘         │
│                                                                │
└────────────────────────────────────────────────────────────────┘

                 インターネット
                       ↑
                       │
  ┌─ 外部サーバ（読み取り専用・PIN は送信しない）─────────────┐
  │                                                          │
  │  GitHub Pages: HTML/CSS/JS の配信                        │
  │  GitHub Releases API: 新バージョン情報・payload DL       │
  │  TSA (Time Stamping Authority): タイムスタンプ取得       │
  │  CRL Distribution Point: 証明書失効情報（HPKI のみ）    │
  │                                                          │
  └──────────────────────────────────────────────────────────┘
```

---

## 技術スタック

### フロントエンド
- **Vanilla HTML/CSS/JS**（フレームワーク不使用）
- **CSP**: 厳格な Content Security Policy で外部スクリプト禁止
- **localStorage**: ユーザー設定保存（PIN は保存しない）

### バックエンド（Bridge）
- **Python 3.13** (embed 版・約 10MB)
- **Flask**: 軽量 HTTP サーバ
- **pyhanko**: PAdES 準拠 PDF 署名ライブラリ
- **python-pkcs11**: PKCS#11 バインディング
- **cryptography**: 証明書解析

### ランチャー
- **Go**: 単一バイナリ（5.4MB）
- ブリッジ起動・自動アップデート適用・ロールバック・自己診断

### 配布
- **Inno Setup 6**: Windows インストーラ
- **GitHub Actions**: 自動リリース
- **GitHub Pages**: ドキュメント配信
- **GitHub Releases**: バイナリ配布

---

## ディレクトリ構造（インストール後）

```
%LOCALAPPDATA%\HpkiSigner\
├── launcher.exe                  Go製ランチャー（更新はインストーラ経由）
├── VERSION.txt                   現在のバージョン
├── .shutdown_token               起動毎に生成されるランダムトークン
├── HpkiSigner.ico                アイコン
├── launcher.log                  ランチャーの動作ログ
├── launcher.json                 (任意) ランチャー設定上書き
├── unins000.exe                  Inno Setup アンインストーラ
├── unins000.dat                  アンインストール情報
│
├── python\                       Python 3.13 embed
│   ├── python.exe
│   ├── python313.dll
│   ├── python313._pth            sys.path 設定
│   └── Lib\site-packages\        依存ライブラリ
│       ├── pyhanko\
│       ├── pkcs11\
│       ├── flask\
│       ├── cryptography\
│       └── ...
│
├── bridge\                       Bridge スクリプト
│   ├── bridge.py                 HTTP API サーバ
│   ├── signer.py                 PDF 署名ロジック
│   ├── allowed_origins.txt       CORS 許可オリジン
│   ├── requirements.txt          依存リスト（参照用）
│   ├── bridge.log                Bridge の動作ログ
│   ├── jpki_sign_ca01-03.cer     J-LIS CA 証明書（3世代分）
│   ├── medis_auth_ca.cer         HPKI 認証用CA
│   ├── medis_sign_ca.cer         HPKI 署名用CA
│   └── mhlw_hpki_root_ca_v2.cer  MHLW ルートCA
│
├── docs\                         Web UI
│   ├── index.html                メイン署名画面
│   ├── setup.html                セットアップウィザード
│   └── security.html             セキュリティ説明
│
├── _pending\                     アップデート保留先（自動生成）
│   ├── payload-X.Y.Z.zip
│   └── .ready
│
└── _backup\                      ロールバック用（自動生成）
    └── （前バージョンのファイル）
```

---

## ネットワーク仕様

### Bridge が外部と通信するタイミング

| 用途 | 接続先 | 頻度 | 送信データ |
|------|--------|------|-----------|
| GitHub Pages（HTML/CSS/JS） | github.io | 起動時のみ | なし（GET only） |
| アップデート確認 | api.github.com | 起動時 + 定期 | なし（GET only） |
| Payload DL | github.com (releases) | 新版発見時のみ | なし |
| TSA（タイムスタンプ） | TSA 各社 | 署名時のみ | **PDFのハッシュ値のみ**（内容は送らない） |
| CRL 取得（HPKI） | cert.medis.or.jp | 署名時に1回 | なし |

### **PIN・PDF 本体・個人情報は外部送信しない**

これがセキュリティの中核。コードレビューで確認可能。

### 必要なポート

- **127.0.0.1:14733** （デフォルト）
  - 14733 が使用中なら 14734-14737 を順に試す
  - `launcher.json` で `port_range` をカスタム可能

### 必要なファイアウォール設定

- **不要**（外向き通信のみ・受信ポートは localhost 限定）

---

## セキュリティ仕様

### CORS allowlist
- `bridge/allowed_origins.txt` で許可オリジンを明示
- 標準: `localhost:14733`, `127.0.0.1:14733`, GitHub Pages URL

### CSRF トークン
- プロセス起動毎に `secrets.token_urlsafe(32)` で生成
- `/api/health` で配布、全 POST で `X-CSRF-Token` ヘッダー必須
- `secrets.compare_digest` でタイミング攻撃にも耐性

### Shutdown トークン（v1.1.5+）
- launcher が bridge を停止するためのファイルベース認証
- `appDir/.shutdown_token` に書き込み
- ブラウザJSは読めない（CSRF経路でしか shutdown できない）

### CSP（Content Security Policy）
- `default-src 'none'`
- `connect-src 'self' http://127.0.0.1:14733 http://localhost:14733`
- `frame-ancestors 'none'` で clickjacking 防止
- `form-action 'none'` で外部フォーム送信防止

### PIN セキュリティ
- ブラウザ送信直後に入力欄クリア
- JS 変数も null 化
- `autocomplete="off"` でブラウザ保存無効
- `visibilitychange`/`pagehide`/`beforeunload` で強制クリア

詳細は [03_security.md](03_security.md) を参照。

---

## 主要 API エンドポイント

| エンドポイント | メソッド | 用途 | CSRF |
|--------------|---------|------|------|
| `/api/health` | GET | バージョン・CSRF token・カード/DLL検出 | 免除 |
| `/api/check-update` | GET | GitHub Releases API で新版確認 | 免除 |
| `/api/check-reader` | GET | WinSCard API でリーダー検出 | 免除 |
| `/api/diagnostics` | GET | 診断情報（OS・log末尾16KB） | 免除 |
| `/api/session/start` | POST | PKCS#11 セッション開始（PIN 入力） | 必須 |
| `/api/sign` | POST | PDF 署名実行 | 必須 |
| `/api/session/end` | POST | セッション終了 | 必須 |
| `/api/self-update/trigger` | POST | バックグラウンド payload DL 開始 | 必須 |
| `/api/self-update/status` | GET | DL 進捗 | 免除 |
| `/api/shutdown` | POST | bridge 自己終了（launcher用） | shutdown_token |
| `/api/cert/download` | GET | 現セッションの署名証明書 | 免除 |
| `/api/jpki-ca/identify` | GET | 親CA特定 | 免除 |
| `/api/jpki-ca/install-to-windows` | POST | Windows ストアへCAインストール | 必須 |

---

## ログとモニタリング

### ログファイル

| ファイル | 内容 | サイズ管理 |
|---------|-----|-----------|
| `bridge/bridge.log` | API アクセス・エラー・PKCS#11操作 | 手動ローテ（年1） |
| `launcher.log` | launcher 起動・更新適用 | 手動ローテ |

### ログに含まれるもの・含まれないもの

| 含まれる | 含まれない |
|---------|-----------|
| API アクセス時刻・パス・ステータス | **PIN** |
| 署名証明書の Subject DN, SHA-1 | **PDFの内容** |
| エラー Traceback | **個人を特定する情報** |

---

## 関連ドキュメント

- [02_install-detail.md](02_install-detail.md): 詳細なインストール手順
- [03_security.md](03_security.md): セキュリティ仕様の詳細
- [04_customization.md](04_customization.md): 設定のカスタマイズ
- [../../TROUBLESHOOTING.md](../../TROUBLESHOOTING.md): 障害対応マニュアル

---

最終更新: 2026-05-18 (v1.1.6 対応)
