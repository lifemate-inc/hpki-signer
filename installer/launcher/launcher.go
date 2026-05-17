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
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"
	"unsafe"
)

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

	// 既に起動していたらブラウザだけ開く
	if isBridgeRunning() {
		openBrowser(bridgeURL)
		return
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
