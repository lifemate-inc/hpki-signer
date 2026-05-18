// HPKI電子署名ツール — ランチャー
//
// このバイナリの役割：
//   1. ブリッジ（Python Flask）が既に起動していたらブラウザを開くだけ
//   2. 起動していなければ python\python.exe bridge\bridge.py を起動
//   3. 起動完了を待ってからブラウザを開く
//   4. すべての出力を bridge.log に追記
//
// ビルド: go build -ldflags "-s -w -H windowsgui" -o launcher.exe

package main

import (
	"archive/zip"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

// デバッグログを launcher.log に書き出す（GUI モードでコンソール出力がないため）
var launcherLog *log.Logger

func initLog(appDir string) {
	logPath := filepath.Join(appDir, "launcher.log")
	f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	launcherLog = log.New(f, "[launcher] ", log.LstdFlags)
	launcherLog.Println("---- launcher start ----")
}

func logf(format string, args ...interface{}) {
	if launcherLog != nil {
		launcherLog.Printf(format, args...)
	}
}

const (
	// ブラウザに表示する URL は localhost を使用（127.0.0.1 と同じだが見た目が親しみやすい）
	// ヘルスチェックは 127.0.0.1 を使用（DNS解決を経ない確実な確認）
	bridgeURL     = "http://localhost:14733"
	bridgeHealth  = "http://127.0.0.1:14733"
	healthPath    = "/api/health"
	startupWaitMs = 500
	startupMaxMs  = 30000
	logFileName   = "bridge.log"
)

// ブラウザを開く（Windows標準）
func openBrowser(url string) error {
	return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
}

// ブリッジに /api/health で疎通確認（127.0.0.1 直接アクセス）
func isBridgeRunning() bool {
	client := &http.Client{Timeout: 1 * time.Second}
	resp, err := client.Get(bridgeHealth + healthPath)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

// ブリッジに /api/shutdown を投げて自己終了させる
// X-Shutdown-Token ヘッダーで認証（ファイルから読む）
func shutdownBridge(appDir string) {
	tokenBytes, err := os.ReadFile(filepath.Join(appDir, ".shutdown_token"))
	if err != nil {
		logf("shutdown token 読込失敗: %v", err)
		return
	}
	client := &http.Client{Timeout: 2 * time.Second}
	req, err := http.NewRequest("POST", bridgeHealth+"/api/shutdown", nil)
	if err != nil {
		return
	}
	req.Header.Set("X-Shutdown-Token", strings.TrimSpace(string(tokenBytes)))
	resp, err := client.Do(req)
	if err != nil {
		logf("shutdown 要求失敗: %v", err)
		return
	}
	resp.Body.Close()
}

// ブリッジを起動。コンソール非表示。
func startBridge(appDir string) error {
	python := filepath.Join(appDir, "python", "python.exe")
	script := filepath.Join(appDir, "bridge", "bridge.py")
	logPath := filepath.Join(appDir, "bridge", logFileName)

	if _, err := os.Stat(python); err != nil {
		return fmt.Errorf("Python が見つかりません: %s", python)
	}
	if _, err := os.Stat(script); err != nil {
		return fmt.Errorf("bridge.py が見つかりません: %s", script)
	}

	logFile, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("ログファイルを開けません: %v", err)
	}

	cmd := exec.Command(python, script)
	cmd.Dir = appDir
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	cmd.SysProcAttr = &syscall.SysProcAttr{
		HideWindow:    true,
		CreationFlags: 0x08000000, // CREATE_NO_WINDOW
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("ブリッジ起動に失敗: %v", err)
	}
	return nil
}

// 起動完了を待つ
func waitForBridge() bool {
	deadline := time.Now().Add(time.Duration(startupMaxMs) * time.Millisecond)
	for time.Now().Before(deadline) {
		if isBridgeRunning() {
			return true
		}
		time.Sleep(time.Duration(startupWaitMs) * time.Millisecond)
	}
	return false
}

// ─── 自動アップデート適用 ─────────────────────────────────────
// _pending/ フォルダに payload-*.zip と .ready ファイルがあれば展開して上書き

// 設定ファイルなど「上書きしない」もの
// VERSION.txt は新版で必ず上書きされる必要があるため、ここに含めない
// launcher.exe も payload に含まれない設計なので、ここに含めない
var preserveFiles = []string{
	"bridge/allowed_origins.txt",
	"bridge/bridge.log",
}

func applyPendingUpdate(appDir string) bool {
	pendingDir := filepath.Join(appDir, "_pending")
	readyFlag := filepath.Join(pendingDir, ".ready")
	logf("applyPendingUpdate: pendingDir=%s", pendingDir)

	if _, err := os.Stat(readyFlag); err != nil {
		logf("  .ready ファイルなし: %v → 何もしない", err)
		return false
	}
	logf("  .ready 検出")

	// payload zip を探す
	matches, _ := filepath.Glob(filepath.Join(pendingDir, "payload-*.zip"))
	if len(matches) == 0 {
		logf("  payload-*.zip が見つからない")
		os.Remove(readyFlag)
		return false
	}
	zipPath := matches[0]
	logf("  zipPath = %s", zipPath)

	// 展開
	if err := extractZipOverwrite(zipPath, appDir); err != nil {
		logf("  ❌ extractZipOverwrite 失敗: %v", err)
		messageBox("HPKI電子署名ツール",
			"アップデートの適用に失敗しました。\n以前のバージョンで起動を続けます。\n\n"+err.Error(),
			true)
		os.Remove(readyFlag)
		os.Remove(zipPath)
		return false
	}
	logf("  ✅ extractZipOverwrite 成功")

	// 適用完了 — ペンディングをクリーンアップ
	os.Remove(readyFlag)
	os.Remove(zipPath)
	return true
}

func extractZipOverwrite(zipPath, destDir string) error {
	r, err := zip.OpenReader(zipPath)
	if err != nil {
		return fmt.Errorf("zip open: %w", err)
	}
	defer r.Close()

	preserveSet := make(map[string]bool)
	for _, p := range preserveFiles {
		preserveSet[filepath.ToSlash(p)] = true
	}

	for _, f := range r.File {
		name := filepath.ToSlash(f.Name)

		// 保持リストに含まれるファイルはスキップ（既存を上書きしない）
		// ただし元ファイルがない場合は展開する
		fullPath := filepath.Join(destDir, filepath.FromSlash(name))
		if preserveSet[name] {
			if _, err := os.Stat(fullPath); err == nil {
				continue // 既存ファイルがある → 上書きしない
			}
		}

		// ディレクトリエントリ
		if strings.HasSuffix(name, "/") {
			os.MkdirAll(fullPath, 0755)
			continue
		}

		// 親ディレクトリ作成
		os.MkdirAll(filepath.Dir(fullPath), 0755)

		// 解凍
		src, err := f.Open()
		if err != nil {
			return fmt.Errorf("open entry %s: %w", name, err)
		}
		dst, err := os.OpenFile(fullPath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0644)
		if err != nil {
			src.Close()
			return fmt.Errorf("create %s: %w", fullPath, err)
		}
		if _, err := io.Copy(dst, src); err != nil {
			src.Close()
			dst.Close()
			return fmt.Errorf("write %s: %w", fullPath, err)
		}
		src.Close()
		dst.Close()
	}
	return nil
}

// Windows API: MessageBoxW
func messageBox(title, body string, isError bool) {
	user32 := syscall.NewLazyDLL("user32.dll")
	msgBoxW := user32.NewProc("MessageBoxW")
	const (
		MB_ICONINFORMATION = 0x00000040
		MB_ICONERROR       = 0x00000010
	)
	flags := uintptr(MB_ICONINFORMATION)
	if isError {
		flags = MB_ICONERROR
	}
	t, _ := syscall.UTF16PtrFromString(title)
	b, _ := syscall.UTF16PtrFromString(body)
	msgBoxW.Call(0, uintptr(unsafe.Pointer(b)), uintptr(unsafe.Pointer(t)), flags)
}

func main() {
	exePath, err := os.Executable()
	if err != nil {
		messageBox("HPKI電子署名ツール", "起動エラー: 実行パスを取得できません", true)
		return
	}
	appDir := filepath.Dir(exePath)
	initLog(appDir)
	logf("appDir = %s", appDir)

	// 保留中のアップデートがあるか確認
	pendingReady := filepath.Join(appDir, "_pending", ".ready")
	hasPendingUpdate := false
	if _, err := os.Stat(pendingReady); err == nil {
		hasPendingUpdate = true
		logf("保留中のアップデートを検出")
	}

	// bridge 稼働中の処理分岐
	if isBridgeRunning() {
		if hasPendingUpdate {
			// アップデート適用のため bridge を停止
			logf("bridge 稼働中だがアップデートあり → 停止要求")
			shutdownBridge(appDir)
			// ポート解放・ファイルロック解放を待つ
			for i := 0; i < 20; i++ {
				time.Sleep(300 * time.Millisecond)
				if !isBridgeRunning() {
					break
				}
			}
			logf("  bridge 停止完了")
		} else {
			// アップデートなし → ブラウザだけ開いて終了
			logf("bridge は既に起動中。ブラウザを開いて終了。")
			openBrowser(bridgeURL)
			return
		}
	}

	// 🔄 保留中のアップデートを静かに適用
	if hasPendingUpdate {
		if applyPendingUpdate(appDir) {
			logf("アップデートを適用しました")
		}
	}

	if err := startBridge(appDir); err != nil {
		messageBox("HPKI電子署名ツール",
			"起動に失敗しました:\n"+err.Error()+
				"\n\n「はじめにセットアップを実行する」を先に行ってください。",
			true)
		return
	}

	if !waitForBridge() {
		messageBox("HPKI電子署名ツール",
			"起動に時間がかかっています。\n"+
				"しばらく待ってから、もう一度起動してください。\n"+
				"それでも改善しない場合は担当者にご連絡ください。",
			true)
		return
	}

	openBrowser(bridgeURL)
}
