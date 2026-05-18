# ════════════════════════════════════════════════════════════════════
#  HPKI電子署名ツール — payload ビルドスクリプト
# ════════════════════════════════════════════════════════════════════
#
# このスクリプトは GitHub Releases にアップロードする payload-vX.Y.Z.zip
# を作成します。内容:
#   ・Python 3.13 embed
#   ・依存ライブラリ (pyhanko, python-pkcs11, flask, etc.)
#   ・bridge/* (Pythonスクリプト, CA証明書)
#   ・docs/*  (HTML/CSS/JS)
#
# 使い方:
#   .\scripts\build_payload.ps1 -Version "1.1.0"
#
# 出力:
#   build\payload-{Version}.zip
#
# ════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [string]$PythonVersion = "3.13.0",

    [switch]$SkipPythonDownload,
    [switch]$KeepStaging
)

$ErrorActionPreference = "Stop"

# ─── パス設定 ─────────────────────────────────────────────────────
$ROOT     = Resolve-Path (Join-Path $PSScriptRoot "..")
$BUILD    = Join-Path $ROOT "build"
$STAGING  = Join-Path $BUILD "payload-$Version-staging"
$OUTPUT   = Join-Path $BUILD "payload-$Version.zip"
$WHEELS   = Join-Path $BUILD "wheels-cache"

if (Test-Path $STAGING) { Remove-Item $STAGING -Recurse -Force }
New-Item -ItemType Directory -Force -Path $STAGING, $BUILD, $WHEELS | Out-Null

Write-Host "═════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  HPKI Signer Payload Build  v$Version"  -ForegroundColor Cyan
Write-Host "═════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ステージング: $STAGING"
Write-Host "  出力:         $OUTPUT"
Write-Host ""

# ─── ① Python embed のダウンロード・展開 ──────────────────────────
$PYTHON_EMBED_ZIP = Join-Path $BUILD "python-$PythonVersion-embed.zip"
$PYTHON_EMBED_URL = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"

if (-not $SkipPythonDownload -or -not (Test-Path $PYTHON_EMBED_ZIP)) {
    Write-Host "▶ Python $PythonVersion embed をダウンロード中..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $PYTHON_EMBED_URL -OutFile $PYTHON_EMBED_ZIP -UseBasicParsing
}
Write-Host "▶ Python embed を展開中..." -ForegroundColor Yellow
$PY_DIR = Join-Path $STAGING "python"
Expand-Archive -Path $PYTHON_EMBED_ZIP -DestinationPath $PY_DIR -Force

# embed 版は site-packages を読まないので有効化
# python313._pth に `import site` を追加し、サイトパッケージのインポートを許可する
$pthFile = Get-ChildItem -Path $PY_DIR -Filter "python*._pth" | Select-Object -First 1
if ($pthFile) {
    $pthContent = Get-Content $pthFile.FullName
    if (-not ($pthContent -match "^\s*import site\s*$")) {
        Add-Content -Path $pthFile.FullName -Value "`nimport site"
    }
    # Lib\site-packages も検索パスに追加
    if (-not ($pthContent -match "Lib\\site-packages")) {
        Add-Content -Path $pthFile.FullName -Value "Lib\site-packages"
    }
}

# ─── ② 依存ライブラリのビルドと配置 ────────────────────────────────
Write-Host "▶ 依存ライブラリの wheel を取得中..." -ForegroundColor Yellow

# 開発側の Python で wheel を取得（embed には pip がない）
$REQ = Join-Path $ROOT "bridge\requirements.txt"
if (-not (Test-Path $REQ)) {
    # 後方互換: bridge\venv の installed packages から生成
    $REQ = Join-Path $BUILD "requirements-generated.txt"
    @(
        "pyhanko==0.35.1",
        "python-pkcs11",
        "flask",
        "cryptography",
        "asn1crypto",
        "requests"
    ) | Set-Content $REQ
}

# pip wheel は現在の Python 環境用の wheel を作るため、
# このスクリプトを実行する開発機が「Python 3.13 + Windows」である必要がある。
# それを保証するために事前チェック:
$pyVer = (python -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
if ($pyVer -ne "3.13") {
    Write-Host "⚠️  警告: 現在のPython は $pyVer。配布物はembed版 3.13向け wheel を必要とします。" -ForegroundColor Yellow
    Write-Host "    Python 3.13 で実行することを推奨。"
}

# pip download なら --python-version が使える（クロスバージョンのDLができる）
# PowerShellのパーサーで--が誤認識されるのを避けるため配列展開を使う
# stderr の通知メッセージで PowerShell が NativeCommandError を出すのを抑える
$prevErrPref = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$dlArgs = @(
    '-m', 'pip', 'download',
    '-d', $WHEELS,
    '-r', $REQ,
    '--python-version', '3.13',
    '--platform', 'win_amd64',
    '--only-binary=:all:'
)
& python @dlArgs *> $null
$dlExit = $LASTEXITCODE
$ErrorActionPreference = $prevErrPref
if ($dlExit -ne 0) { throw "pip download に失敗（要件解決失敗の可能性）コード=$dlExit" }
Write-Host "  ✅ wheel ダウンロード完了" -ForegroundColor Green

# site-packages に展開
$SITE_PACKAGES = Join-Path $PY_DIR "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $SITE_PACKAGES | Out-Null

# 全 wheel を site-packages に展開
# wheel は単なる ZIP なので、現在の Python バージョンに依存せず直接展開する
# (pip install --target だと現在のPython版と wheel の cpXX が一致しないと失敗)
$wheelFiles = Get-ChildItem $WHEELS -Filter "*.whl"
Write-Host "▶ $($wheelFiles.Count) 個の wheel を site-packages に展開..." -ForegroundColor Yellow
Add-Type -AssemblyName System.IO.Compression.FileSystem
foreach ($w in $wheelFiles) {
    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($w.FullName)
        foreach ($entry in $zip.Entries) {
            # ディレクトリエントリはスキップ
            if ($entry.Name -eq '') { continue }
            $target = Join-Path $SITE_PACKAGES $entry.FullName
            $targetDir = Split-Path $target -Parent
            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            }
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
        }
        $zip.Dispose()
    } catch {
        Write-Host "  ⚠️ $($w.Name) の展開エラー: $_" -ForegroundColor Red
    }
}
Write-Host "  ✅ 展開完了" -ForegroundColor Green

# ─── ③ bridge と docs の同梱 ──────────────────────────────────────
Write-Host "▶ bridge と docs をコピー..." -ForegroundColor Yellow

# bridge をコピー（venv, __pycache__, ログは除外）
$bridgeDest = Join-Path $STAGING "bridge"
Copy-Item -Path (Join-Path $ROOT "bridge") -Destination $bridgeDest -Recurse `
    -Exclude @("venv", "__pycache__", "*.pyc", "bridge.log")
# venv フォルダが Copy-Item の Exclude では完全に除外できないので明示削除
if (Test-Path "$bridgeDest\venv") { Remove-Item "$bridgeDest\venv" -Recurse -Force }
Get-ChildItem -Path $bridgeDest -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# docs をコピー
Copy-Item -Path (Join-Path $ROOT "docs") -Destination (Join-Path $STAGING "docs") -Recurse

# launcher.exe は payload に含めない（インストーラ直接同梱）
# 理由: 自プロセスのexe上書きは Windows でファイルロック衝突するため、
# サイレント自動更新の対象から外す。launcher 更新はインストーラ再実行で対応。

# バージョン情報を埋め込む
Set-Content -Path (Join-Path $STAGING "VERSION.txt") -Value "$Version"

# ─── ④ ZIP 化 ─────────────────────────────────────────────────────
Write-Host "▶ ZIP 化中..." -ForegroundColor Yellow
if (Test-Path $OUTPUT) { Remove-Item $OUTPUT -Force }
Compress-Archive -Path "$STAGING\*" -DestinationPath $OUTPUT -CompressionLevel Optimal

# ─── ⑤ 結果表示 ───────────────────────────────────────────────────
$sizeMB = [math]::Round((Get-Item $OUTPUT).Length / 1MB, 1)
Write-Host ""
Write-Host "═════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ ビルド完了" -ForegroundColor Green
Write-Host "═════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ファイル: $OUTPUT"
Write-Host "  サイズ:   $sizeMB MB"
Write-Host ""

if (-not $KeepStaging) {
    Remove-Item $STAGING -Recurse -Force
}
