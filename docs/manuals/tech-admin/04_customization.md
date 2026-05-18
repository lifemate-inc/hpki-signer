# 技術責任者向け：設定のカスタマイズ

ステーション独自の運用要件に合わせた設定変更方法のリファレンス。

---

## 設定ファイル一覧

| ファイル | 用途 | 更新タイミング |
|---------|-----|--------------|
| `bridge/allowed_origins.txt` | CORS 許可オリジン | 公開URL変更時 |
| `launcher.json` | launcher 動作設定 | 必要に応じて |
| `bridge/requirements.txt` | 依存ライブラリ（参照用） | 変更非推奨 |

これらは payload 更新時に**自動保護**されます。

---

## bridge/allowed_origins.txt

CORS で許可するオリジンを指定。

### 標準値（自動で含まれる、変更不要）

```
http://localhost:14733
http://localhost:14734
... (port_range のすべて)
http://127.0.0.1:14733
... (同上)
null
```

### 追加できるもの

```
# 自社ドメインのコピーから利用したい場合
https://signer.your-company.com

# 別のステーション用に複数の URL を許可する場合
https://anothersite.example.com
```

書き方ルール：
- 1行に1オリジン
- `#` で始まる行はコメント
- 末尾スラッシュ `/` は不要
- 大文字小文字は区別なし

---

## launcher.json（任意）

`%LOCALAPPDATA%\HpkiSigner\launcher.json` に置くと、launcher の動作を変更できます。

### デフォルト値

```json
{
  "port_range": [14733, 14734, 14735, 14736, 14737],
  "bridge_startup_timeout_seconds": 60,
  "retry_on_startup_failure": true,
  "bridge_poll_interval_ms": 500,
  "shutdown_timeout_seconds": 6
}
```

### 各パラメータ

#### port_range

bridge が listen するポート候補リスト。先頭から空きポートを探す。

```json
"port_range": [14733, 14734, 14735, 14736, 14737]
```

**変更すべきケース**:
- 14733 系を他のソフトが恒常的に使う（社内システム等）
- ファイアウォール ポリシーで特定ポートのみ許可

例：18080-18084 を使う場合
```json
"port_range": [18080, 18081, 18082, 18083, 18084]
```

#### bridge_startup_timeout_seconds

bridge 起動を待つ最大秒数（デフォルト 60秒）。

**変更すべきケース**:
- 古い PC で起動が遅い → 120, 180 に増やす
- アンチウイルスのスキャンに時間がかかる → 同上

```json
"bridge_startup_timeout_seconds": 180
```

#### retry_on_startup_failure

起動失敗時に 3 秒待って 1 回だけ再試行するか。

**変更すべきケース**:
- USB が起動直後に認識されないことが多い → true（デフォルト）のまま
- リトライを完全に止めたい → false

#### bridge_poll_interval_ms

起動完了 polling の間隔（ミリ秒）。

**変更すべきケース**: 通常変更不要。

#### shutdown_timeout_seconds

アップデート適用前の bridge 停止を待つ秒数。

**変更すべきケース**: 通常変更不要。bridge が異常に遅いシステムで増やす。

---

## 環境変数

launcher → bridge に渡される環境変数：

| 変数名 | 値 | 用途 |
|--------|-----|------|
| `HPKI_BRIDGE_PORT` | port_range から選ばれた数値 | bridge が listen するポート |

直接 bridge を起動するときに使えます：

```powershell
$env:HPKI_BRIDGE_PORT = 18080
python.exe bridge\bridge.py
```

---

## 詳細設定の例

### ケース 1: 社内 IT 部門の標準ポリシーに合わせる

社内の Web アプリで 8080 番台を予約済み、ファイアウォールで 19xxx 番台のみ許可されている場合：

```json
{
  "port_range": [19000, 19001, 19002]
}
```

### ケース 2: 古い PC で起動が遅い

Windows 10 32bit、メモリ 4GB、HDD の PC：

```json
{
  "bridge_startup_timeout_seconds": 180,
  "bridge_poll_interval_ms": 1000
}
```

### ケース 3: マスデプロイ（IT 部門が一括設定）

複数のステーションに同じ設定を配る場合：

```powershell
# 1. launcher.json を作成
$config = @{
    port_range = @(14733, 14734)
    bridge_startup_timeout_seconds = 120
    retry_on_startup_failure = $true
} | ConvertTo-Json

# 2. 全 PC にコピー
$config | Set-Content "$env:LOCALAPPDATA\HpkiSigner\launcher.json" -Encoding UTF8
```

---

## TSA（タイムスタンプ局）の選択

アプリ UI の「詳細設定」→「タイムスタンプ局（TSA）」で選択：

| プロバイダ | URL | 料金 | 備考 |
|---------|-----|------|-----|
| **SSL.com** | http://ts.ssl.com | 無料 | 推奨 |
| FreeTSA | https://freetsa.org/tsr | 無料 | 利用制限あり |
| サイバートラスト | https://eservice.cybertrust.ne.jp | 有料 | 法的有効性が高い |
| カスタム | (URL を入力) | - | 自前 TSA を立てる場合 |

#### TSA の選び方

- **業務用途で法的根拠が必要** → 認定 TSA（サイバートラスト等）
- **テスト用途・コスト重視** → SSL.com

TSA 設定は localStorage に保存されるため、PC ごとに設定が必要。

---

## CA 証明書のカスタマイズ

`bridge/*.cer` を追加・変更することで、独自の CA を信頼させることができます。

例：自社で発行したルート CA を信頼させる場合：

```
bridge/
├── company_root_ca.cer   ← 追加
└── ...
```

ただし、`signer.py` のコードを変更しないと **CMS に埋め込まれない**ため、
高度な作業が必要。必要なら開発担当に相談。

---

## 詳細設定（アプリ UI 経由）

アプリの「詳細設定」セクションで変更できる項目：

| 項目 | 用途 | 保存場所 |
|------|-----|---------|
| PKCS#11 ライブラリパス | DLL の場所を手動指定 | localStorage |
| TSA URL | タイムスタンプ局 | localStorage |
| 出力ファイル名サフィックス | 例: `_signed` | localStorage |
| 上書き保存 | 元ファイルを上書きするか | localStorage |

localStorage に保存されるため、ブラウザを変えるとリセットされます。

---

## 既存設定のバックアップ

```powershell
$backup = "C:\Backup\HpkiSigner-config-$(Get-Date -Format yyyyMMdd)"
New-Item -ItemType Directory -Path $backup -Force
Copy-Item "$env:LOCALAPPDATA\HpkiSigner\bridge\allowed_origins.txt" $backup
Copy-Item "$env:LOCALAPPDATA\HpkiSigner\launcher.json" $backup -ErrorAction SilentlyContinue
```

---

最終更新: 2026-05-18
