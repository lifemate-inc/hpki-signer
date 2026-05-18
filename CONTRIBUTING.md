# 開発・運用ガイドライン

このリポジトリにコミットする前に必ず確認してください。

---

## 🔒 公開してはいけないもの

このリポジトリは **public** で、GitHub Pages 経由でも一部が配信されます。
**絶対にコミットしてはいけない**ものは以下：

### ❌ 個人情報を含むファイル

- 個人の署名証明書（`*signing*.cer`, `*signer*.cer`）
- テスト用 P12（`test_cert.p12` 等）
- 個人の PIN・パスフレーズを含むファイル
- 顧客の氏名・連絡先を含むファイル

### ❌ 社内運用ドキュメント

- 営業担当向けマニュアル（`docs/manuals/sales/`）
- フォロー担当向けマニュアル（`docs/manuals/support/`）
- 用語使い分けガイド（`docs/manuals/glossary.md`）
- 配布先データベース・顧客リスト

これらは別の **private リポジトリ** または社内ストレージで管理してください。

### ❌ 認証情報

- API キー
- パスワード
- アクセストークン
- 環境変数ファイル（`.env`）

### ❌ ベンダー配布ソフト

- HPKI クライアントソフト DLL
- JPKI 利用者ソフト DLL
- カードリーダードライバ

これらは再配布禁止です。

---

## ✅ 公開して問題ないもの

- ソースコード（bridge, docs, installer, scripts）
- 公開 CA 証明書（J-LIS, MEDIS, MHLW のルート）
- 配布先向けマニュアル（`docs/manuals/end-user/`, `docs/manuals/tech-admin/`）
- インストールガイド・同意書テンプレート
- README, LICENSE, CHANGELOG

---

## コミット前のチェックリスト

```
[ ] git status で意図しないファイルが含まれていないか
[ ] git diff で個人情報が混ざっていないか
[ ] テストデータに本物の患者情報がないか
[ ] PIN・パスワードが含まれていないか
[ ] スクリーンショットに個人名が映っていないか
```

---

## 内部マニュアルの管理場所

社内向けマニュアル（営業・サポート）は以下のいずれかで管理：

| 選択肢 | メリット | デメリット |
|--------|--------|-----------|
| **private GitHub リポジトリ**（推奨） | Git でバージョン管理、変更履歴明確 | GitHub の料金がかかる場合あり |
| **Google Drive / Notion** | 編集が簡単、誰でも更新可能 | バージョン管理が弱い |
| **デスクトップローカル** | オフラインで開ける | 個別の PC に閉じる |

現在の社内マニュアルは：
- ローカルに保管: `~/Desktop/hpki-signer-internal-manuals-YYYY-MM-DD/`
- 将来的に private repo へ移行予定

---

## 誤って公開してしまったとき

万が一、社内資料を public にコミットしてしまったら：

### 即座にやること

1. **慌てない**（パニックで誤った操作をすると傷口を広げる）
2. ローカルでファイルを削除（または別フォルダへ）
3. `git rm` して commit + push（**最新ブランチからは消える**）
4. ただし**履歴には残る**ので、次に進む

### 履歴からも完全削除

```powershell
# git-filter-repo をインストール（初回のみ）
pip install git-filter-repo

# バックアップを取る
git clone --mirror . ../backup-$(Get-Date -Format yyyyMMdd).git

# 該当パスを全履歴から削除
python -m git_filter_repo --path docs/manuals/sales/ --invert-paths --force

# remote を再登録（filter-repo が外す）
git remote add origin https://github.com/lifemate-inc/hpki-signer.git

# force push
git push origin main --force
```

### GitHub の reflog からも完全削除

force push 後、GitHub のサーバ側でも 60-90 日間はコミットハッシュ経由でアクセス可能：

- **方法 A**: GC を待つ（60-90日で自動消去）
- **方法 B**: GitHub Support に削除依頼
  - <https://support.github.com/contact/private-information>
  - 「Sensitive information was force-pushed but commit hashes still accessible」と説明
- **方法 C**: リポジトリ削除→作り直し（即時・確実だが Releases/Pages/Star がリセット）

---

## リリースワークフロー

新バージョンをリリースする手順：

```powershell
# 1. ローカルでビルド
.\scripts\build_all.ps1 -Version "1.1.X"

# 2. 動作確認
& "$env:LOCALAPPDATA\HpkiSigner\launcher.exe" --check

# 3. コミット
git add -A
git commit -m "release: v1.1.X"
git push

# 4. タグ + GitHub Release 作成
git tag v1.1.X
git push origin v1.1.X
gh release create v1.1.X build\hpki-signer-setup-1.1.X.exe build\payload-1.1.X.zip `
  --title "HPKI電子署名ツール v1.1.X" --notes "..."
```

---

## 緊急時の連絡先

- セキュリティ事案: security@(...)
- 開発担当: developer@(...)
- 営業・サポート責任者: (...)

---

最終更新: 2026-05-19
