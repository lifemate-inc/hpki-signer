"""
既存の Chrome (localhost:14733 開き済) を操作してフォルダピッカーを出す。
"""
import time
import ctypes
import sys
from pathlib import Path

from pywinauto import Application

user32 = ctypes.windll.user32

# Chrome の HPKI ウィンドウを Win32 で見つける
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
found_hwnd = [0]
found_title = [""]

def cb(hwnd, lparam):
    if not user32.IsWindowVisible(hwnd):
        return True
    n = user32.GetWindowTextLengthW(hwnd)
    if n == 0:
        return True
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    t = buf.value
    if 'HPKI' in t and 'Chrome' in t:
        found_hwnd[0] = hwnd
        found_title[0] = t
        return False
    return True

user32.EnumWindows(EnumWindowsProc(cb), 0)

if found_hwnd[0] == 0:
    print('HPKI Chrome ウィンドウ未発見')
    sys.exit(1)

print(f'Chrome hwnd={found_hwnd[0]} title="{found_title[0]}"')
chrome = Application(backend='uia').connect(handle=found_hwnd[0]).window(handle=found_hwnd[0])
# fg へ
user32.SetForegroundWindow(chrome.handle)
time.sleep(1.5)

# ベータ同意ダイアログのチェックボックス → 同意ボタン
print('チェックボックスを探す...')
cb_clicked = False
for c in chrome.descendants(control_type='CheckBox'):
    try:
        cn = c.window_text()
        print(f'  CheckBox: "{cn}"')
        if not cb_clicked:
            c.click_input()
            print('  → クリック')
            cb_clicked = True
            time.sleep(0.5)
    except Exception:
        pass

print('「同意して利用を開始」を探す...')
btn_clicked = False
for el in chrome.descendants():
    try:
        nm = el.window_text()
        if nm == '同意して利用を開始':
            el.click_input()
            print('  クリック')
            btn_clicked = True
            break
    except Exception:
        pass

time.sleep(2)

# 「タップして選んでください」をクリック
print('フォルダ選択エリアを探す...')
for el in chrome.descendants():
    try:
        nm = el.window_text()
        if nm and ('タップして' in nm or '選んでください' in nm):
            print(f'  発見: "{nm}"')
            el.click_input()
            print('  クリック')
            break
    except Exception:
        pass

time.sleep(2.5)
print('フォルダピッカー出てるはず...')
