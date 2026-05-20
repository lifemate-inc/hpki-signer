"""
PostMessage で Acrobat に Ctrl+K を送り、環境設定ダイアログを開く。
"""
import sys
import time
import ctypes
from ctypes import wintypes
from pathlib import Path

from pywinauto import Application

ROOT = Path(__file__).resolve().parent.parent

user32 = ctypes.windll.user32

# Acrobat 接続
app = Application(backend='uia').connect(title_re=r'.*Adobe Acrobat.*')
main = app.top_window()
hwnd = main.handle
print(f'Acrobat hwnd: {hwnd}')

# まず Acrobat を fg へ (AttachThreadInput トリック)
fg = user32.GetForegroundWindow()
fg_tid = user32.GetWindowThreadProcessId(fg, 0)
my_tid = ctypes.windll.kernel32.GetCurrentThreadId()
target_tid = user32.GetWindowThreadProcessId(hwnd, 0)
user32.AttachThreadInput(fg_tid, target_tid, True)
user32.BringWindowToTop(hwnd)
user32.SetForegroundWindow(hwnd)
user32.AttachThreadInput(fg_tid, target_tid, False)
time.sleep(1.0)

# PostMessage で直接 Acrobat に Ctrl+K を送信 (フォーカス不要)
WM_KEYDOWN = 0x0100
WM_KEYUP   = 0x0101
VK_CONTROL = 0x11
VK_K = 0x4B
user32.PostMessageW(hwnd, WM_KEYDOWN, VK_CONTROL, 0)
time.sleep(0.03)
user32.PostMessageW(hwnd, WM_KEYDOWN, VK_K, 0)
time.sleep(0.03)
user32.PostMessageW(hwnd, WM_KEYUP, VK_K, 0)
time.sleep(0.03)
user32.PostMessageW(hwnd, WM_KEYUP, VK_CONTROL, 0)
print('PostMessage Ctrl+K 送信完了')

# 同時に foreground にも keybd_event を送る (どちらかが効くのを期待)
KEYEVENTF_KEYUP = 0x0002
user32.keybd_event(VK_CONTROL, 0, 0, 0); time.sleep(0.03)
user32.keybd_event(VK_K, 0, 0, 0); time.sleep(0.03)
user32.keybd_event(VK_K, 0, KEYEVENTF_KEYUP, 0); time.sleep(0.03)
user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

time.sleep(3.0)

# 環境設定ダイアログを探す
prefs = None
for _ in range(10):
    try:
        prefs = Application(backend='uia').connect(title='環境設定').top_window()
        break
    except Exception:
        time.sleep(0.5)

if prefs is None:
    print('環境設定ダイアログ未表示')
    sys.exit(1)
print(f'環境設定: hwnd={prefs.handle}')

# ダイアログを左上 + 大きく
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
user32.SetWindowPos(prefs.handle, 0, 0, 0, 1280, 820, SWP_NOZORDER | SWP_SHOWWINDOW)
time.sleep(0.5)

# 「署名」カテゴリを選択
selected = False
for li in prefs.descendants(control_type='ListItem'):
    try:
        nm = li.window_text()
        if nm == '署名':
            try: li.select()
            except Exception: pass
            try: li.click_input()
            except Exception: pass
            print(f'カテゴリ「{nm}」選択')
            selected = True
            break
    except Exception:
        pass

time.sleep(1.0)

# 「詳細」ボタン (検証セクション = 2番目) をクリック
buttons = []
for btn in prefs.descendants(control_type='Button'):
    try:
        nm = btn.window_text()
        if '詳細' in nm:
            buttons.append((nm, btn))
    except Exception:
        pass
print(f'「詳細」ボタン候補: {len(buttons)}')
for nm, _ in buttons:
    print(f'  - {nm}')

if buttons:
    # 2番目が検証 (1番目は作成、3番目は ID)
    idx = min(1, len(buttons) - 1)
    target_name, target_btn = buttons[idx]
    try:
        target_btn.invoke()
        print(f'invoke: {target_name}')
    except Exception as e:
        print(f'invoke 失敗: {e} → click_input')
        try: target_btn.click_input()
        except Exception as e2: print(f'click_input 失敗: {e2}')
    time.sleep(2.5)
    print('nested ダイアログ表示完了 (はず)')
