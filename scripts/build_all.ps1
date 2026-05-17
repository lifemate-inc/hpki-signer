# ════════════════════════════════════════════════════════════════════
#  HPKI電子署名ツール — 全体ビルドスクリプト
# ════════════════════════════════════════════════════════════════════
#
# 一発で以下をビルドします:
#   1. launcher.exe (Go)
#   2. payload-vX.Y.Z.zip (Python + 依存ライブラリ + bridge + docs)
#   3. hpki-signer-setup-vX.Y.Z.exe (Inno Setup)
#
# 必要なツール:
#   ・Go (https://go.dev/dl/)
#   ・Inno Setup 6 (https://jrsoftware.org/isinfo.php)
#   ・Python 3.13 + pip
#
# 使い方:
#   .\scripts\build_all.ps1 -Version "1.1.0"
#
# ════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [switch]$SkipLauncher,
    [switch]$SkipPayload,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ROOT = Resolve-Path (Join-Path $PSScriptRoot "..")

function Write-Stage($msg) {
    Write-Host ""
    Write-Host "═════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "═════════════════════════════════════════════" -ForegroundColor Cyan
}

# ─── ① launcher.exe をビルド (Go) ──────────────────────────────────
if (-not $SkipLauncher) {
    Write-Stage "1/3: launcher.exe をビルド (Go)"
    $launcherDir = Join-Path $ROOT "installer\launcher"

    # Go の探索順: PATH → プロジェクト内 .tools/go
    $goExe = Get-Command go -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
    if (-not $goExe) {
        $localGo = Join-Path $ROOT ".tools\go\bin\go.exe"
        if (Test-Path $localGo) { $goExe = $localGo }
    }
    if (-not $goExe) {
        throw "Go コンパイラが見つかりません。https://go.dev/dl/ からインストールするか、.tools/go/ に portable版を配置してください。"
    }

    Push-Location $launcherDir
    try {
        $env:GOOS = "windows"
        $env:GOARCH = "amd64"
        & $goExe build -ldflags "-s -w -H windowsgui" -o launcher.exe .
        if ($LASTEXITCODE -ne 0) { throw "go build に失敗" }
        $sizeKB = [math]::Round((Get-Item "launcher.exe").Length / 1KB, 0)
        Write-Host "  ✅ launcher.exe ビルド完了 ($sizeKB KB) — $goExe" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

# ─── ② payload をビルド ────────────────────────────────────────────
if (-not $SkipPayload) {
    Write-Stage "2/3: payload-v$Version.zip をビルド"
    & (Join-Path $PSScriptRoot "build_payload.ps1") -Version $Version
    if ($LASTEXITCODE -ne 0) { throw "payload ビルドに失敗" }
}

# ─── ③ Inno Setup でインストーラをビルド ──────────────────────────
if (-not $SkipInstaller) {
    Write-Stage "3/3: hpki-signer-setup-v$Version.exe をビルド (Inno Setup)"

    # Inno Setup の検出（winget 経由は user-local に入る）
    $iscc = $null
    foreach ($p in @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )) {
        if (Test-Path $p) { $iscc = $p; break }
    }
    if (-not $iscc) {
        throw "Inno Setup 6 が見つかりません。https://jrsoftware.org/isinfo.php からインストールしてください。"
    }

    # MyAppVersion を上書きするため /D で渡す
    & $iscc "/DMyAppVersion=$Version" (Join-Path $ROOT "installer\HpkiSigner.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup ビルドに失敗" }
}

Write-Stage "✅ 全ステージ完了"
Get-ChildItem (Join-Path $ROOT "build") -Filter "*.exe" | Format-Table Name, @{N='Size(MB)';E={[math]::Round($_.Length/1MB,1)}}
Get-ChildItem (Join-Path $ROOT "build") -Filter "*.zip" | Format-Table Name, @{N='Size(MB)';E={[math]::Round($_.Length/1MB,1)}}
