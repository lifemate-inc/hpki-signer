# Third-Party Licenses / 同梱依存ライブラリのライセンス表記

HPKI 電子署名ツール は、以下のオープンソースソフトウェアを利用しています。
配布物（`payload-X.Y.Z.zip` / `hpki-signer-setup-X.Y.Z.exe`）には、これらのライブラリのバイナリが同梱されています。

各ライセンスの完全な原文は、対応プロジェクトのリポジトリでご確認ください。

---

## Python ランタイム

### Python 3.13
- **ライセンス**: PSF License Agreement (Python Software Foundation License)
- **配布元**: <https://www.python.org/>
- **同梱**: `python/` 配下に Windows embed 版を同梱

---

## Python 依存ライブラリ

### pyhanko
- **役割**: PAdES 準拠の PDF 電子署名コアエンジン
- **ライセンス**: MIT License
- **リポジトリ**: <https://github.com/MatthiasValvekens/pyHanko>
- **著作権**: Copyright (c) Matthias Valvekens

### python-pkcs11
- **役割**: PKCS#11 バインディング（HPKI/JPKI カード通信）
- **ライセンス**: MIT License
- **リポジトリ**: <https://github.com/danni/python-pkcs11>
- **著作権**: Copyright (c) Danielle Madeley

### Flask
- **役割**: 軽量 HTTP サーバフレームワーク
- **ライセンス**: BSD 3-Clause License
- **リポジトリ**: <https://github.com/pallets/flask>
- **著作権**: Copyright 2010 Pallets

### Werkzeug
- **役割**: WSGI ユーティリティ（Flask の依存）
- **ライセンス**: BSD 3-Clause License
- **リポジトリ**: <https://github.com/pallets/werkzeug>
- **著作権**: Copyright 2007 Pallets

### Jinja2
- **役割**: テンプレートエンジン（Flask の依存）
- **ライセンス**: BSD 3-Clause License
- **リポジトリ**: <https://github.com/pallets/jinja>
- **著作権**: Copyright 2007 Pallets

### cryptography
- **役割**: 証明書解析・PKI 暗号処理
- **ライセンス**: Apache License 2.0 または BSD 3-Clause（デュアル）
- **リポジトリ**: <https://github.com/pyca/cryptography>
- **著作権**: Copyright (c) Individual contributors (Python Cryptographic Authority)
- **NOTICE**: Apache 2.0 の要件により、本ファイルにて当該配布物の利用を明記しています

### asn1crypto
- **役割**: ASN.1 / X.509 パーサ
- **ライセンス**: MIT License
- **リポジトリ**: <https://github.com/wbond/asn1crypto>
- **著作権**: Copyright (c) Will Bond

### requests
- **役割**: HTTP クライアント
- **ライセンス**: Apache License 2.0
- **リポジトリ**: <https://github.com/psf/requests>
- **著作権**: Copyright 2019 Kenneth Reitz
- **NOTICE**: Apache 2.0 の要件により、本ファイルにて当該配布物の利用を明記しています

### urllib3
- **役割**: HTTP プール（requests の依存）
- **ライセンス**: MIT License
- **リポジトリ**: <https://github.com/urllib3/urllib3>

### certifi
- **役割**: TLS ルート証明書バンドル
- **ライセンス**: Mozilla Public License 2.0
- **リポジトリ**: <https://github.com/certifi/python-certifi>

### charset-normalizer
- **役割**: 文字エンコーディング検出（requests の依存）
- **ライセンス**: MIT License
- **リポジトリ**: <https://github.com/jawah/charset_normalizer>

### idna
- **役割**: 国際化ドメイン名（requests の依存）
- **ライセンス**: BSD 3-Clause License
- **リポジトリ**: <https://github.com/kjd/idna>

### click
- **役割**: CLI ユーティリティ（Flask の依存）
- **ライセンス**: BSD 3-Clause License
- **リポジトリ**: <https://github.com/pallets/click>

### itsdangerous
- **役割**: 署名付きデータ（Flask の依存）
- **ライセンス**: BSD 3-Clause License
- **リポジトリ**: <https://github.com/pallets/itsdangerous>

### markupsafe
- **役割**: HTML エスケープ（Jinja2 の依存）
- **ライセンス**: BSD 3-Clause License
- **リポジトリ**: <https://github.com/pallets/markupsafe>

### blinker
- **役割**: シグナル（Flask の依存）
- **ライセンス**: MIT License
- **リポジトリ**: <https://github.com/pallets-eco/blinker>

### cffi / pycparser
- **役割**: cryptography が依存する C foreign function interface
- **ライセンス**: MIT License
- **リポジトリ**: <https://github.com/python-cffi/cffi>

### oscrypto（pyhanko の依存）
- **ライセンス**: MIT License
- **リポジトリ**: <https://github.com/wbond/oscrypto>

### tzlocal / pytz-deprecation-shim
- **役割**: タイムゾーン処理（pyhanko 依存）
- **ライセンス**: MIT License

### Pillow（pyhanko の任意依存）
- **役割**: 画像処理（署名外観の生成）
- **ライセンス**: HPND（Historical Permission Notice and Disclaimer）
- **リポジトリ**: <https://github.com/python-pillow/Pillow>

### qrcode / segno（pyhanko の任意依存）
- **ライセンス**: BSD-3 / MIT
- **リポジトリ**: 各プロジェクトを参照

> **注記**: 上記は配布物に同梱される主要ライブラリです。`pip download` の依存解決により追加で同梱される間接依存については、各 wheel パッケージ内の `METADATA` / `LICENSE` ファイルをご確認ください。

---

## Go 依存ライブラリ

### Go 標準ライブラリのみ
- launcher.exe は Go 標準ライブラリ（`archive/zip`, `net/http`, `os/exec` 等）のみを利用
- **ライセンス**: BSD-3 Clause (Go Programming Language License)
- **リポジトリ**: <https://github.com/golang/go>

---

## CA 証明書（同梱）

### J-LIS 署名用 CA 第1〜3世代
- **発行元**: 地方公共団体情報システム機構（J-LIS）
- **用途**: マイナンバーカード署名証明書の検証チェーン構築
- **ライセンス/取扱い**: 公開情報。再配布可（公的個人認証法に基づく）
- **入手元**: <https://www.jpki.go.jp/>

### MEDIS HPKI CA（認証用・署名用）
- **発行元**: 一般財団法人 医療情報システム開発センター（MEDIS）
- **用途**: HPKI カード署名証明書の検証チェーン構築
- **ライセンス/取扱い**: 公開情報。HPKI 仕様書に基づく利用

### MHLW HPKI Root CA V2
- **発行元**: 厚生労働省（MHLW）
- **用途**: HPKI 信頼チェーンのルート
- **ライセンス/取扱い**: 公開情報

---

## 開発時のみ利用するツール（配布物に同梱されない）

### Inno Setup 6
- **役割**: Windows インストーラ生成
- **ライセンス**: Inno Setup License（フリーソフトウェア）
- **リポジトリ**: <https://jrsoftware.org/isinfo.php>

### GitHub Actions
- **役割**: 自動リリース CI
- **提供元**: GitHub
- **ライセンス**: GitHub の利用規約に従う

---

## 各ライセンス全文の入手方法

各ライブラリのライセンス全文は、以下のいずれかでご確認いただけます:

1. **PyPI のプロジェクトページ**:
   `https://pypi.org/project/<ライブラリ名>/`
2. **GitHub リポジトリの LICENSE ファイル**:
   上記の「リポジトリ」リンク先 → LICENSE
3. **インストール済みパッケージ内**:
   `python\Lib\site-packages\<ライブラリ名>-*.dist-info\LICENSE`

---

## 本ソフトウェア自体のライセンス

本ソフトウェア「HPKI 電子署名ツール」は **MIT License** で提供されます。詳細は [LICENSE](LICENSE) を参照してください。

---

## お問い合わせ

ライセンス表記に関するご指摘・修正のご要望は以下までご連絡ください:

- 📋 GitHub Issues: <https://github.com/lifemate-inc/hpki-signer/issues>
- 📧 michael@life-mate.jp

---

最終更新: 2026-05-19
