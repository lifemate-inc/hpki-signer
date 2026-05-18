# 技術責任者向け：セキュリティ仕様の詳細

このツールを導入するにあたって、IT部門としてレビューすべきセキュリティ仕様の全容です。

---

## 脅威モデル

### 守るべき資産

| 資産 | 重要度 | 保護手段 |
|------|------|---------|
| PIN コード | **最高** | localhost を出ない・即時クリア |
| PDF の内容 | **最高** | localhost を出ない |
| 患者・利用者の個人情報 | **最高** | localhost を出ない |
| 署名証明書（公開鍵側） | 中 | 通常運用で問題なし |
| 動作記録（ログ） | 低 | PIN を含まない |

### 想定される脅威

| 脅威 | 影響 | 対策 |
|------|-----|------|
| MITM 攻撃（中間者攻撃） | PIN 盗聴 | localhost 通信のため発生不可 |
| 悪意あるWebサイトからの不正操作 | 勝手な署名 | CORS allowlist + CSRF token |
| 同一PC内の他のソフトからの攻撃 | shutdown / 操作 | shutdown_token・PIN は別経路 |
| クロスサイトスクリプティング | データ窃取 | CSP で完全防止 |
| キーロガー | PIN 窃取 | OS レベルの問題（IT部門で対策） |
| カード盗難 | 不正使用 | PIN 5回間違いでロック・物理保管 |
| マルウェア感染 | 全データ漏洩 | OS レベルの問題 |
| ベンダー（lifemate-inc）の悪意 | コードに仕込まれた可能性 | OSS 公開・GitHub Actions ビルドで検証可能 |

---

## レイヤー別のセキュリティ対策

### ① ブラウザ層

#### CSP (Content Security Policy)

```html
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none';
           script-src 'self' 'unsafe-inline';
           style-src  'self' 'unsafe-inline';
           img-src    'self' data:;
           connect-src 'self' http://127.0.0.1:14733 http://localhost:14733;
           form-action 'none';
           frame-ancestors 'none';
           base-uri 'none'">
```

- `default-src 'none'`: デフォルトすべて拒否
- `connect-src`: localhost にのみ通信許可
- `frame-ancestors 'none'`: clickjacking 防止
- `form-action 'none'`: 外部フォーム送信不可

`'unsafe-inline'` は現状の HTML/JS が inline で書かれているため。
将来 nonce ベースに移行可能。

#### Referrer-Policy

```html
<meta name="referrer" content="no-referrer">
```

外部サイトに Referrer ヘッダーを送らない。

#### Autocomplete 無効化

PIN 入力欄：
```html
<input type="password" autocomplete="off" autocorrect="off"
       autocapitalize="off" spellcheck="false" data-form-type="other">
```

ブラウザのパスワード保存機能を回避。

#### PIN メモリクリア

```javascript
const pin = pinInput.value;
pinInput.value = '';   // 即時クリア
// ...送信...
pin = null;           // JS変数も消去
```

加えて：
- `visibilitychange` (タブ非表示時)
- `pagehide` (ページ離脱時)
- `beforeunload` (ウィンドウ閉じる時)

これらで強制クリア。

### ② Bridge 層

#### CORS allowlist

`bridge/allowed_origins.txt` に明示したオリジンのみ許可：

```
http://localhost:14733
http://127.0.0.1:14733
https://lifemate-inc.github.io
```

これ以外のオリジンからのリクエストは、`Access-Control-Allow-Origin` ヘッダーを返さない。

#### CSRF Token

```python
CSRF_TOKEN = secrets.token_urlsafe(32)   # 起動毎に変わる、256bit エントロピー

@app.before_request
def csrf_check():
    if request.method == 'GET' or request.path in _CSRF_EXEMPT:
        return None
    token = request.headers.get('X-CSRF-Token', '')
    if not secrets.compare_digest(token, CSRF_TOKEN):
        return jsonify({'error': 'CSRFトークン不正'}), 403
```

`secrets.compare_digest` でタイミング攻撃対策。

#### Shutdown Token（ファイルベース）

```python
SHUTDOWN_TOKEN = secrets.token_urlsafe(32)
(appDir / '.shutdown_token').write_text(SHUTDOWN_TOKEN)

@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    token = request.headers.get('X-Shutdown-Token', '')
    if not secrets.compare_digest(token, SHUTDOWN_TOKEN):
        return jsonify({'error': 'unauthorized'}), 403
    # ...
```

ブラウザ JS は `.shutdown_token` ファイルを読めないため、CSRF 攻撃で shutdown できない。

#### ログのサニタイズ

`/api/diagnostics` で送る log_tail は、念のため正規表現でマスク：

```python
log_tail = re.sub(r"('pin':\s*')[^']*(')", r'\1[REDACTED]\2', log_tail)
```

通常のログには PIN は出力されないが、二重防御。

### ③ ネットワーク層

#### 受信ポート

- **127.0.0.1:14733** （or fallback 14734-14737）
- `host='127.0.0.1'` で bind しているため、**外部 NIC からアクセス不可**
- ファイアウォール設定**不要**

#### 送信通信

| 接続先 | プロトコル | 送信データ |
|--------|----------|-----------|
| GitHub Pages | HTTPS | なし (GET) |
| GitHub API | HTTPS | User-Agent のみ |
| GitHub Releases | HTTPS | なし (GET) |
| TSA | HTTP/HTTPS | PDF のハッシュ値（SHA-256）のみ |
| CRL Distribution Point | HTTP | なし (GET) |

**いずれの通信にも PIN・PDF 本体・個人情報は含まれない。**

### ④ ファイルシステム層

#### 権限

- インストールは `%LOCALAPPDATA%` 配下（**管理者権限不要**）
- 動作時もユーザー権限のみ
- システムフォルダに書き込まない

#### CA 証明書の検証

PDF 署名時に使う CA 証明書は **bridge ディレクトリに同梱**：
- J-LIS 署名用 CA 第1〜3世代
- MEDIS HPKI CA（認証用・署名用）
- MHLW HPKI Root CA V2

これらは payload に含まれて配信。改ざんされていないか心配なら、各機関の公式値と SHA-256 ハッシュを照合可能。

---

## 監査ログ

`bridge/bridge.log` に記録されるもの：

```
[bridge] 許可オリジン: ['http://127.0.0.1:14733', 'http://localhost:14733', ...]
[bridge] J-LIS 署名用CA3 (2023-)証明書をCMSに追加: ...
[bridge] 署名証明書 SHA1: 3261CF9CCA7010DA6837A3BCAB525975BD72888E
[bridge] 署名証明書 Subject: Common Name: ...; Country: JP
[bridge] LTV情報を埋め込みました
127.0.0.1 - - [18/May/2026 10:30:00] "POST /api/sign HTTP/1.1" 200 -
```

| 記録される | 記録されない |
|-----------|-------------|
| 操作時刻・パス・ステータスコード | **PIN** |
| 署名証明書の Subject DN | **PDF の内容** |
| エラー Traceback | **個人を特定する PII** |
| 使用した CA 証明書 | （患者情報など） |

`Subject DN` には署名者の名前が含まれます（医師名・看護師名）。
これは「誰がいつ署名したか」の業務記録として必要なため。

### 監査ログのレビュー

担当 IT 部門で定期的に：

```powershell
# 異常な API アクセスがないか
Get-Content "$env:LOCALAPPDATA\HpkiSigner\bridge\bridge.log" |
    Select-String -Pattern "500|403" -Context 0,3

# 想定外の Origin が出ていないか
Get-Content "$env:LOCALAPPDATA\HpkiSigner\bridge\bridge.log" |
    Select-String -Pattern "Origin:"
```

---

## ベンダー（lifemate-inc）への信頼

「**ベンダーが悪意あるコードを仕込んだら？**」というリスクへの対策：

### 1. OSS なのでコードレビュー可能

すべてのソースコードが GitHub で公開：
<https://github.com/lifemate-inc/hpki-signer>

### 2. ビルドが GitHub Actions で実行される

`/.github/workflows/release.yml` で、リリースは GitHub Actions の CI 上で再現可能。
配布されるバイナリと GitHub Actions のビルド結果が一致するか検証可能。

### 3. 依存ライブラリも全て OSS

- pyhanko: MatthiasValvekens 氏 (MIT)
- python-pkcs11: danni 氏 (MIT)
- Flask: Pallets (BSD)
- cryptography: PyCA (Apache 2.0)

### 4. 自前ビルドが可能

不安なら、ご自身でビルドして配布できます：

```powershell
git clone https://github.com/lifemate-inc/hpki-signer.git
cd hpki-signer
.\scripts\build_all.ps1 -Version "X.Y.Z"
```

---

## セキュリティ事故時の対応

### 報告窓口

- メール: security@(...)
- GitHub Security Advisories: <https://github.com/lifemate-inc/hpki-signer/security/advisories>

### 開示ポリシー

- 修正完了まで非公開
- 修正後 30日経過してから公開

### 緊急対応フロー

1. 報告 → 24時間以内に受領確認
2. 検証 → 48時間以内
3. 修正版開発
4. 緊急リリース
5. 全配布先へ通知

詳細は [../../TROUBLESHOOTING.md](../../TROUBLESHOOTING.md) の「セキュリティ重大欠陥時のプレイブック」を参照。

---

最終更新: 2026-05-18
