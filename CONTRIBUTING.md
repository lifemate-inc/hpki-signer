# Contributing to HPKI 電子署名ツール

本プロジェクトへの貢献にご関心をお寄せいただきありがとうございます。

このガイドは、バグ報告・機能要望・コード変更・ドキュメント改善などをご提案いただく方向けの案内です。

---

## 🐛 バグ報告・機能要望

[GitHub Issues](https://github.com/lifemate-inc/hpki-signer/issues) よりお寄せください。

### バグ報告に含めていただきたい情報

- **症状**: 何が起きたか
- **再現手順**: どう操作したら発生するか
- **環境**: Windows のバージョン、カード種別、本ツールのバージョン
- **診断情報**: アプリ画面下の「📋 診断情報をコピー」で取得できる情報
- **期待動作**: 本来どうあるべきか

### 機能要望のテンプレート

- **背景**: どんな業務シーンで困っているか
- **提案する機能**: どのような機能があると助かるか
- **代替案**: 現状でどう対処しているか

---

## 🔐 セキュリティに関する報告

**脆弱性は公開 Issue では報告しないでください**（攻撃者に情報が渡るリスクがあります）。

代わりに以下を利用してください：

- 🔒 [GitHub Security Advisories](https://github.com/lifemate-inc/hpki-signer/security/advisories)（推奨）

報告者と開発元の間で連携し、修正完了後に公開します（責任ある開示）。

---

## 💻 開発環境のセットアップ

### 必要なツール

| ツール | バージョン | 用途 |
|-------|----------|------|
| Python | 3.13+ | bridge 本体 |
| Go | 1.21+ | launcher.exe ビルド |
| Inno Setup | 6 | インストーラ生成 |
| Git | 最新 | バージョン管理 |

### 初期セットアップ

```powershell
# リポジトリをクローン
git clone https://github.com/lifemate-inc/hpki-signer.git
cd hpki-signer

# bridge の依存をインストール
cd bridge
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 起動して動作確認
python bridge.py
```

ブラウザで <http://localhost:14733> を開けば動作確認できます。

### ビルド

```powershell
# 配布パッケージ（payload + installer）を生成
.\scripts\build_all.ps1 -Version "1.1.X"
```

`build/` に `payload-vX.Y.Z.zip` と `hpki-signer-setup-X.Y.Z.exe` が生成されます。

---

## 📝 Pull Request の出し方

1. このリポジトリを fork します
2. ブランチを切ります（例: `fix/card-detection`, `feat/multi-tsa`）
3. 変更をコミットします
   - コミットメッセージは [Conventional Commits](https://www.conventionalcommits.org/ja/v1.0.0/) 形式が望ましい
   - 例: `feat(signer): add support for PSS padding`
4. fork したリポジトリに push します
5. このリポジトリへ Pull Request を作成します

### PR レビューで確認される観点

- ✅ 既存のコードスタイルと一貫しているか
- ✅ セキュリティに影響する変更が含まれていないか
- ✅ ユーザーへの影響が大きい変更には説明があるか
- ✅ ドキュメントが更新されているか

---

## ⚠️ コミットすべきでないもの

以下のファイルは `.gitignore` で除外されていますが、念のためご確認ください：

| 種類 | 例 |
|------|-----|
| 個人の署名証明書 | `*_signing*.cer`, `*_personal*.cer` |
| テスト用秘密鍵 | `*.p12`, `*.pfx`, `*.pem`, `*.key` |
| ベンダー配布 DLL | `*.dll`（再配布制限あり） |
| 認証情報 | `.env`, APIキー、トークン |
| ログ・キャッシュ | `*.log`, `__pycache__/` |
| ビルド成果物 | `build/`, `*.zip` |

PR を出される前に `git status` でご確認ください。

---

## 🎨 コードスタイル

### Python（bridge / signer）

- [PEP 8](https://peps.python.org/pep-0008/) に準拠
- 関数・変数名は snake_case
- クラス名は PascalCase
- 日本語コメント可（ユーザー向け業務ロジックには日本語が望ましい）

### Go（launcher）

- `gofmt` でフォーマット
- Goの標準的な慣習に従う

### JavaScript / HTML / CSS

- インデントは 2 スペース
- セミコロンはなしでも可（一貫していれば）
- ES2020+ 機能 OK

### コミットメッセージ

```
<type>(<scope>): <subject>

<body>

Co-Authored-By: ...
```

`type`:
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント
- `chore`: その他（ビルド・設定など）
- `refactor`: リファクタリング
- `test`: テスト追加
- `perf`: パフォーマンス改善

---

## 🧪 テストとビルド

PR を出す前に、ローカルで動作確認をお願いします：

```powershell
# launcher のセルフチェック
& "installer\launcher\launcher.exe" --check

# 全体ビルドが通るか
.\scripts\build_all.ps1 -Version "0.0.0-test"
```

---

## 📜 ライセンス

このプロジェクトは [MIT License](LICENSE) の下で公開されています。
あなたが貢献されるコードも、同ライセンスの下で公開されることに同意したものとみなします。

---

## 🙏 行動規範

すべての貢献者に対して、敬意と建設的な姿勢でのコミュニケーションをお願いします。

医療・介護現場で実際に使われるツールですので、現場の声を尊重した提案を歓迎します。

---

## 📬 ご連絡先

- 一般的な質問・バグ報告: [GitHub Issues](https://github.com/lifemate-inc/hpki-signer/issues)
- セキュリティ報告: [GitHub Security Advisories](https://github.com/lifemate-inc/hpki-signer/security/advisories)
- その他: 配布元の担当窓口（配布物の同意書に記載）
