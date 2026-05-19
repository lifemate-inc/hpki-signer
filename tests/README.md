# テスト

```powershell
# 開発機（PowerShell）
cd C:\Users\user\Desktop\michael-systems\projects\hpki-pdf-signer
.\bridge\venv\Scripts\python.exe -m pip install pytest pytest-cov
.\bridge\venv\Scripts\python.exe -m pytest tests/ -v
```

## カバーしているもの

- `bridge.py`
  - `_semver_gt` の比較ロジック
  - `_load_allowed_origins` のフォールバックポート対応
  - CSRF / Shutdown トークン生成の最低限の性質
  - CSRF 免除リストの整合性

- `signer.py`
  - mock モード判定
  - CA 証明書パス定義

- `launcher.go`
  - `preserveFiles` リストの仕様（ファイル読みで間接検証）

## まだカバーしていないもの

- 実カード（HPKI / JPKI）を使った PKCS#11 署名 → 手動テスト
- 自動更新の `_download_update_payload`（HTTP モック必要）
- launcher.go の `applyPendingUpdate` ロジック → Go 側テスト未整備
- E2E（インストーラ → 起動 → 署名 → 検証）

## CI 連携

`.github/workflows/ci.yml` の `python-checks` ジョブでテストが自動実行されます。
