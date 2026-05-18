// HPKI電子署名ツール — ランチャー v2
//
// このバイナリの役割：
//   ・ブリッジ（Python Flask）の起動とブラウザの自動オープン
//   ・サイレント自動アップデートの適用（_pending/.ready 検出時）
//   ・失敗時のロールバック（_backup/ から復元）
//   ・ポート衝突時の代替ポート使用
//   ・self-check モード（--check 引数）
//
// 設計方針：このバイナリは payload 経由で更新できないため、
//   なるべく変更不要な「ブートローダー」として動作する。
//   実際のロジックは bridge.py（更新可能）に置く。
//
// ビルド: go build -ldflags "-s -w -H windowsgui" -o launcher.exe

package main

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

// ─── ログ ────────────────────────────────────────────────────

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

// ─── 設定（launcher.json から読み込む。デフォルト値あり）─────────

type Config struct {
	PortRange                 []int `json:"port_range"`
	BridgeStartupTimeoutSecs  int   `json:"bridge_startup_timeout_seconds"`
	RetryOnStartupFailure     bool  `json:"retry_on_startup_failure"`
	BridgePollIntervalMs      int   `json:"bridge_poll_interval_ms"`
	ShutdownTimeoutSecs       int   `json:"shutdown_timeout_seconds"`
}

var config = Config{
	PortRange:                []int{14733, 14734, 14735, 14736, 14737},
	BridgeStartupTimeoutSecs: 60,    // 旧 30s → 60s
	RetryOnStartupFailure:    true,
	BridgePollIntervalMs:     500,
	ShutdownTimeoutSecs:      6,
}

func loadConfig(appDir string) {
	cfgPath := filepath.Join(appDir, "launcher.json")
	data, err := os.ReadFile(cfgPath)
	if err != nil {
		logf("launcher.json なし → デフォルト設定使用")
		return
	}
	var c Config
	if err := json.Unmarshal(data, &c); err != nil {
		logf("launcher.json パースエラー（デフォルト使用）: %v", err)
		return
	}
	// 部分上書き
	if len(c.PortRange) > 0 {
		config.PortRange = c.PortRange
	}
	if c.BridgeStartupTimeoutSecs > 0 {
		config.BridgeStartupTimeoutSecs = c.BridgeStartupTimeoutSecs
	}
	if c.BridgePollIntervalMs > 0 {
		config.BridgePollIntervalMs = c.BridgePollIntervalMs
	}
	if c.ShutdownTimeoutSecs > 0 {
		config.ShutdownTimeoutSecs = c.ShutdownTimeoutSecs
	}
	config.RetryOnStartupFailure = c.RetryOnStartupFailure
	logf("launcher.json 読込: ports=%v timeout=%ds", config.PortRange, config.BridgeStartupTimeoutSecs)
}

// ─── ポート管理 ───────────────────────────────────────────────

// 各ポートでブリッジが動いているか確認 → 動いているポートを返す（なければ -1）
func findRunningBridgePort() int {
	for _, p := range config.PortRange {
		if isPortBridge(p) {
			return p
		}
	}
	return -1
}

// 各ポートが「使用中だが我々のブリッジではない」かを確認 → 空きポートを返す
func findFreePort() int {
	for _, p := range config.PortRange {
		if isPortFree(p) {
			return p
		}
	}
	return -1
}

func isPortBridge(port int) bool {
	client := &http.Client{Timeout: 1 * time.Second}
	resp, err := client.Get(fmt.Sprintf("http://127.0.0.1:%d/api/health", port))
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

func isPortFree(port int) bool {
	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		return false
	}
	ln.Close()
	return true
}

// ─── ブラウザ ─────────────────────────────────────────────────

func openBrowser(url string) error {
	return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
}

// ─── ブリッジ操作 ─────────────────────────────────────────────

func shutdownBridge(appDir string, port int) {
	tokenBytes, err := os.ReadFile(filepath.Join(appDir, ".shutdown_token"))
	if err != nil {
		logf("shutdown token 読込失敗: %v", err)
		return
	}
	client := &http.Client{Timeout: 2 * time.Second}
	req, err := http.NewRequest("POST", fmt.Sprintf("http://127.0.0.1:%d/api/shutdown", port), nil)
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

func startBridge(appDir string, port int) error {
	python := filepath.Join(appDir, "python", "python.exe")
	script := filepath.Join(appDir, "bridge", "bridge.py")
	logPath := filepath.Join(appDir, "bridge", "bridge.log")

	if _, err := os.Stat(python); err != nil {
		return fmt.Errorf("E_PYTHON_MISSING: Python が見つかりません: %s", python)
	}
	if _, err := os.Stat(script); err != nil {
		return fmt.Errorf("E_BRIDGE_MISSING: bridge.py が見つかりません: %s", script)
	}

	logFile, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("E_LOG_OPEN: ログファイルを開けません: %v", err)
	}

	cmd := exec.Command(python, script)
	cmd.Dir = appDir
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	// 環境変数で port を bridge に伝える
	cmd.Env = append(os.Environ(), fmt.Sprintf("HPKI_BRIDGE_PORT=%d", port))
	cmd.SysProcAttr = &syscall.SysProcAttr{
		HideWindow:    true,
		CreationFlags: 0x08000000,
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("E_BRIDGE_START: ブリッジ起動に失敗: %v", err)
	}
	return nil
}

func waitForBridge(port int) bool {
	deadline := time.Now().Add(time.Duration(config.BridgeStartupTimeoutSecs) * time.Second)
	for time.Now().Before(deadline) {
		if isPortBridge(port) {
			return true
		}
		time.Sleep(time.Duration(config.BridgePollIntervalMs) * time.Millisecond)
	}
	return false
}

// ─── アップデート適用 ─────────────────────────────────────────

var preserveFiles = []string{
	"bridge/allowed_origins.txt",
	"bridge/bridge.log",
	"launcher.json",
}

// 適用前に対象ファイルを _backup/ に退避（ロールバック用）
func backupCurrentFiles(appDir, zipPath string) error {
	backupDir := filepath.Join(appDir, "_backup")
	os.RemoveAll(backupDir)
	if err := os.MkdirAll(backupDir, 0755); err != nil {
		return err
	}

	// 上書き対象を ZIP の中身から抽出してリスト化
	r, err := zip.OpenReader(zipPath)
	if err != nil {
		return err
	}
	defer r.Close()

	preserveSet := make(map[string]bool)
	for _, p := range preserveFiles {
		preserveSet[filepath.ToSlash(p)] = true
	}

	for _, f := range r.File {
		name := filepath.ToSlash(f.Name)
		if preserveSet[name] || strings.HasSuffix(name, "/") {
			continue
		}
		srcPath := filepath.Join(appDir, filepath.FromSlash(name))
		if _, err := os.Stat(srcPath); err != nil {
			continue // 既存ファイルがなければ退避不要
		}
		dstPath := filepath.Join(backupDir, filepath.FromSlash(name))
		os.MkdirAll(filepath.Dir(dstPath), 0755)
		if err := copyFile(srcPath, dstPath); err != nil {
			return fmt.Errorf("backup %s: %w", name, err)
		}
	}
	return nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0644)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

// _backup/ から復元
func rollbackFromBackup(appDir string) error {
	backupDir := filepath.Join(appDir, "_backup")
	if _, err := os.Stat(backupDir); err != nil {
		return fmt.Errorf("バックアップなし")
	}
	return filepath.Walk(backupDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(backupDir, path)
		if err != nil {
			return err
		}
		dst := filepath.Join(appDir, rel)
		os.MkdirAll(filepath.Dir(dst), 0755)
		return copyFile(path, dst)
	})
}

func applyPendingUpdate(appDir string) (bool, error) {
	pendingDir := filepath.Join(appDir, "_pending")
	readyFlag := filepath.Join(pendingDir, ".ready")
	logf("applyPendingUpdate: pendingDir=%s", pendingDir)

	if _, err := os.Stat(readyFlag); err != nil {
		return false, nil
	}
	logf("  .ready 検出")

	matches, _ := filepath.Glob(filepath.Join(pendingDir, "payload-*.zip"))
	if len(matches) == 0 {
		os.Remove(readyFlag)
		return false, nil
	}
	zipPath := matches[0]
	logf("  zipPath = %s", zipPath)

	// バックアップ
	logf("  バックアップ作成中...")
	if err := backupCurrentFiles(appDir, zipPath); err != nil {
		logf("  ⚠️ バックアップ作成失敗: %v（続行）", err)
	}

	// 展開
	if err := extractZipOverwrite(zipPath, appDir); err != nil {
		logf("  ❌ 展開失敗: %v → ロールバック試行", err)
		if rbErr := rollbackFromBackup(appDir); rbErr != nil {
			logf("  ❌ ロールバックも失敗: %v", rbErr)
			return false, fmt.Errorf("適用失敗かつロールバック失敗: %v / %v", err, rbErr)
		}
		logf("  ✅ ロールバック完了")
		os.Remove(readyFlag)
		os.Remove(zipPath)
		return false, fmt.Errorf("E_UPDATE_FAILED_ROLLED_BACK: アップデート適用失敗（前版に戻しました）: %v", err)
	}
	logf("  ✅ 展開成功")

	os.Remove(readyFlag)
	os.Remove(zipPath)
	return true, nil
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
		fullPath := filepath.Join(destDir, filepath.FromSlash(name))
		if preserveSet[name] {
			if _, err := os.Stat(fullPath); err == nil {
				continue
			}
		}
		if strings.HasSuffix(name, "/") {
			os.MkdirAll(fullPath, 0755)
			continue
		}
		os.MkdirAll(filepath.Dir(fullPath), 0755)
		src, err := f.Open()
		if err != nil {
			return fmt.Errorf("open %s: %w", name, err)
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

// ─── エラー画面（具体的なアクションを提示）─────────────────────

// エラーコードに応じた次のアクションを返す
func errorActionMessage(errStr string) string {
	switch {
	case strings.Contains(errStr, "E_PYTHON_MISSING") || strings.Contains(errStr, "E_BRIDGE_MISSING"):
		return "\n\n【対応】\n" +
			"インストールが不完全です。インストーラを再実行してください：\n" +
			"https://github.com/lifemate-inc/hpki-signer/releases/latest"
	case strings.Contains(errStr, "E_NO_FREE_PORT"):
		return "\n\n【対応】\n" +
			"ポート14733〜14737 がすべて他のソフトに使用されています。\n" +
			"・他の電子署名ソフトを終了\n" +
			"・PC を再起動\n" +
			"・それでも解決しない場合は担当者へ連絡"
	case strings.Contains(errStr, "E_UPDATE_FAILED_ROLLED_BACK"):
		return "\n\n【対応】\n" +
			"アップデート適用に失敗しましたが、前のバージョンに戻しました。\n" +
			"そのままご利用いただけます。後ほど自動で再試行されます。"
	case strings.Contains(errStr, "E_BRIDGE_TIMEOUT"):
		return "\n\n【対応】\n" +
			"起動に時間がかかっています。\n" +
			"・もう一度ダブルクリックしてお待ちください（最大60秒）\n" +
			"・改善しない場合: 診断情報を担当者へ送付"
	default:
		return "\n\n【対応】\n" +
			"・PC を再起動してから、もう一度お試しください\n" +
			"・改善しない場合: launcher.log を担当者へ送付\n" +
			"  場所: %LOCALAPPDATA%\\HpkiSigner\\launcher.log"
	}
}

func showError(title, body, errCode string) {
	msg := body + errorActionMessage(errCode)
	messageBox(title, msg, true)
}

// Win32 MessageBox
func messageBox(title, body string, isError bool) {
	user32 := syscall.NewLazyDLL("user32.dll")
	msgBoxW := user32.NewProc("MessageBoxW")
	const (
		MB_ICONINFORMATION = 0x00000040
		MB_ICONERROR       = 0x00000010
		MB_OK              = 0x00000000
		MB_TOPMOST         = 0x00040000
	)
	flags := uintptr(MB_OK | MB_TOPMOST | MB_ICONINFORMATION)
	if isError {
		flags = MB_OK | MB_TOPMOST | MB_ICONERROR
	}
	t, _ := syscall.UTF16PtrFromString(title)
	b, _ := syscall.UTF16PtrFromString(body)
	msgBoxW.Call(0, uintptr(unsafe.Pointer(b)), uintptr(unsafe.Pointer(t)), flags)
}

// ─── Self-check モード ────────────────────────────────────────

func runSelfCheck(appDir string) {
	results := []string{"【HPKI 電子署名ツール — 自己診断結果】", ""}

	// Python
	python := filepath.Join(appDir, "python", "python.exe")
	if _, err := os.Stat(python); err == nil {
		results = append(results, "✅ Python: OK")
	} else {
		results = append(results, "❌ Python: 見つかりません — インストーラ再実行が必要")
	}

	// bridge.py
	if _, err := os.Stat(filepath.Join(appDir, "bridge", "bridge.py")); err == nil {
		results = append(results, "✅ ブリッジスクリプト: OK")
	} else {
		results = append(results, "❌ ブリッジスクリプト: 見つかりません")
	}

	// VERSION
	if v, err := os.ReadFile(filepath.Join(appDir, "VERSION.txt")); err == nil {
		results = append(results, fmt.Sprintf("✅ バージョン: %s", strings.TrimSpace(string(v))))
	}

	// ポート
	freePort := findFreePort()
	runningPort := findRunningBridgePort()
	if runningPort > 0 {
		results = append(results, fmt.Sprintf("✅ ブリッジ稼働中: port %d", runningPort))
	} else if freePort > 0 {
		results = append(results, fmt.Sprintf("✅ 空きポート: %d", freePort))
	} else {
		results = append(results, "❌ 利用可能なポートなし")
	}

	// _pending
	if _, err := os.Stat(filepath.Join(appDir, "_pending", ".ready")); err == nil {
		results = append(results, "ℹ️ 保留中のアップデートあり（次回起動時に適用）")
	}

	messageBox("自己診断結果", strings.Join(results, "\n"), false)
}

// ─── メイン ──────────────────────────────────────────────────

func main() {
	exePath, err := os.Executable()
	if err != nil {
		messageBox("HPKI電子署名ツール", "起動エラー: 実行パスを取得できません", true)
		return
	}
	appDir := filepath.Dir(exePath)
	initLog(appDir)
	loadConfig(appDir)
	logf("appDir = %s", appDir)

	// 引数チェック: --check
	if len(os.Args) > 1 && (os.Args[1] == "--check" || os.Args[1] == "-c") {
		logf("self-check モード")
		runSelfCheck(appDir)
		return
	}

	// 既に稼働中のブリッジを探す
	runningPort := findRunningBridgePort()

	// 保留中のアップデートを確認
	hasPendingUpdate := false
	if _, err := os.Stat(filepath.Join(appDir, "_pending", ".ready")); err == nil {
		hasPendingUpdate = true
		logf("保留中のアップデートを検出")
	}

	// 既存ブリッジ稼働中
	if runningPort > 0 {
		if hasPendingUpdate {
			logf("ブリッジ稼働中(port=%d)だがアップデートあり → 停止要求", runningPort)
			shutdownBridge(appDir, runningPort)
			// ポート解放を待つ
			deadline := time.Now().Add(time.Duration(config.ShutdownTimeoutSecs) * time.Second)
			for time.Now().Before(deadline) {
				if !isPortBridge(runningPort) {
					break
				}
				time.Sleep(300 * time.Millisecond)
			}
		} else {
			logf("ブリッジ稼働中(port=%d) → ブラウザを開いて終了", runningPort)
			openBrowser(fmt.Sprintf("http://localhost:%d", runningPort))
			return
		}
	}

	// アップデート適用
	if hasPendingUpdate {
		applied, err := applyPendingUpdate(appDir)
		if err != nil {
			showError("HPKI電子署名ツール — アップデート",
				"アップデートに問題が発生しました:\n"+err.Error(),
				err.Error())
			// ロールバック済みなら起動継続を試みる
			if !strings.Contains(err.Error(), "E_UPDATE_FAILED_ROLLED_BACK") {
				return
			}
		} else if applied {
			logf("アップデート適用成功")
		}
	}

	// 空きポートを探して起動
	port := findFreePort()
	if port < 0 {
		showError("HPKI電子署名ツール",
			"利用可能なポートが見つかりません。",
			"E_NO_FREE_PORT")
		return
	}
	logf("port=%d で起動", port)

	if err := startBridge(appDir, port); err != nil {
		// 1回だけリトライ
		if config.RetryOnStartupFailure {
			logf("起動失敗 → 3秒待って1回だけ再試行")
			time.Sleep(3 * time.Second)
			if err2 := startBridge(appDir, port); err2 != nil {
				showError("HPKI電子署名ツール",
					"起動に失敗しました:\n"+err.Error(),
					err.Error())
				return
			}
		} else {
			showError("HPKI電子署名ツール",
				"起動に失敗しました:\n"+err.Error(),
				err.Error())
			return
		}
	}

	if !waitForBridge(port) {
		showError("HPKI電子署名ツール",
			"起動に時間がかかっています。",
			"E_BRIDGE_TIMEOUT")
		return
	}

	openBrowser(fmt.Sprintf("http://localhost:%d", port))
}
