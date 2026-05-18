"""
HPKI電子署名ブリッジ  v1.1（セキュリティ強化版）
localhost:14733 で起動し、ブラウザからの署名リクエストを PKCS#11 カードに橋渡しする。

【セキュリティ設計】
  ・PIN・PDFは127.0.0.1から外に出ない（インターネット非通過）
  ・CORS は allowed_origins.txt で明示的に許可したオリジンのみ受け付ける
  ・全 POST に CSRF トークン必須（起動時にランダム生成、/api/health で配布）
  ・PIN はログに一切出力しない（後段の signer.py も同じ規約）
"""

import os
import sys
import json
import base64
import secrets
import subprocess
import threading
import webbrowser
from pathlib import Path

# Python embed では sys.path に自分のディレクトリが自動追加されないため明示的に追加
# (これにより `import signer` がどんな起動方法でも動く)
_self_dir = str(Path(__file__).resolve().parent)
if _self_dir not in sys.path:
    sys.path.insert(0, _self_dir)

from flask import Flask, request, jsonify, send_from_directory

BRIDGE_DIR = Path(__file__).parent
DOCS_DIR   = BRIDGE_DIR.parent / 'docs'
PORT       = 14733

app = Flask(__name__)

# ─── CSRFトークン: 起動ごとに新規生成 ────────────────────────────────────────
# このプロセス内に閉じ、ファイル等には書き出さない（プロセス再起動で破棄される）
CSRF_TOKEN = secrets.token_urlsafe(32)

# CSRF検証を免除するエンドポイント（読み取り専用 GET と、トークン取得用 health）
# /api/shutdown は localhost からのみ受け付ける（launcher が呼ぶため）
_CSRF_EXEMPT = {'/api/health', '/api/check-update', '/api/check-reader', '/api/diagnostics',
                '/api/self-update/status', '/api/shutdown',
                '/api/browse-dll', '/api/cert/download',
                '/api/jpki-ca/download', '/api/jpki-ca/bundle', '/api/jpki-ca/identify'}

# ─── 許可オリジンの読み込み ────────────────────────────────────────────────────

def _load_allowed_origins() -> set:
    """allowed_origins.txt から許可オリジンを読み込む。常に localhost を含める。"""
    origins = {
        'http://localhost:14733',
        'http://127.0.0.1:14733',
        'null',   # file:// 経由（一部のテスト用途）
    }
    cfg = BRIDGE_DIR / 'allowed_origins.txt'
    if cfg.exists():
        for line in cfg.read_text(encoding='utf-8').splitlines():
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            origins.add(s.rstrip('/').lower())
    return origins

ALLOWED_ORIGINS = _load_allowed_origins()
print(f'[bridge] 許可オリジン: {sorted(ALLOWED_ORIGINS)}', flush=True)


# ─── CORS: 厳格な allowlist ────────────────────────────────────────────────────

@app.after_request
def cors(response):
    origin = request.headers.get('Origin', '').rstrip('/').lower()
    if origin and origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin']  = request.headers.get('Origin')
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRF-Token'
        response.headers['Vary'] = 'Origin'
    return response


# ─── CSRF: POST には X-CSRF-Token ヘッダーが必須 ──────────────────────────────

@app.before_request
def csrf_check():
    # プリフライト(OPTIONS)は素通し（CORS が捌く）
    if request.method == 'OPTIONS':
        return None
    # GET と読み取り専用エンドポイントは免除
    if request.method == 'GET' or request.path in _CSRF_EXEMPT:
        return None
    # 同一オリジン(localhost自身)の POST は受け付ける（ブリッジ配信のページ）
    origin = request.headers.get('Origin', '').rstrip('/').lower()
    if origin in ('http://localhost:14733', 'http://127.0.0.1:14733'):
        # それでも CSRF ヘッダーを要求する（GitHub Pages 経由の場合と区別しない）
        pass
    token = request.headers.get('X-CSRF-Token', '')
    if not secrets.compare_digest(token, CSRF_TOKEN):
        return jsonify({'error': 'CSRFトークン不正。ページを再読み込みしてください。'}), 403
    return None


# ─── PKCS#11 DLL 自動検出 ────────────────────────────────────────────────────

_KNOWN_PKCS11_LIBS = [
    # (path, label, type)
    # ラベルは UI のカードピッカーに表示されるため簡潔に
    (r'C:\Windows\System32\HpkiAuthP11_MPKCS11H.dll', 'HPKIカード', 'hpki'),
    (r'C:\Windows\System32\HpkiSigP11_MPKCS11H.dll',  'HPKIカード', 'hpki'),
    (r'C:\Program Files\JPKI\JPKIPKCS11Sign64.dll',   'マイナンバーカード', 'jpki'),
    (r'C:\Program Files\JPKI\JPKIPKCS11Sign.dll',     'マイナンバーカード', 'jpki'),
]

def _detect_pkcs11_lib() -> str | None:
    """最優先の DLL パスだけを返す（後方互換）"""
    for path, _, _ in _KNOWN_PKCS11_LIBS:
        if Path(path).exists():
            return path
    return None

def _detect_all_libs() -> list:
    """存在する DLL をすべてリストアップして返す"""
    seen_types = set()
    result = []
    for path, label, lib_type in _KNOWN_PKCS11_LIBS:
        if Path(path).exists() and lib_type not in seen_types:
            seen_types.add(lib_type)
            result.append({'path': path, 'label': label, 'type': lib_type})
    return result


# ─── セッション管理 ────────────────────────────────────────────────────────────

_session = None
_session_lock = threading.Lock()
_last_signing_cert = None   # 直近のセッションで使われた署名証明書（セッション終了後の診断用）


# ─── カードリーダー検出 ────────────────────────────────────────────────────────

# 推奨ハードウェア（サンワサプライ ADR-MNICU2）
RECOMMENDED_READER = {
    'product':       'サンワサプライ ADR-MNICU2',
    'price':         '¥7,040',
    'productUrl':    'https://www.sanwa.co.jp/product/syohin?code=ADR-MNICU2',
    'driverPageUrl': 'https://www.sanwa.co.jp/support/download/dl_driver_ichiran?code=ADR-MNICU2',
    'amazonUrl':     'https://www.amazon.co.jp/s?k=ADR-MNICU2',
    'compatible':    ['マイナンバーカード', 'HPKIカード', 'e-Tax', 'LGPKI'],
}


def _list_pcsc_readers() -> list:
    """WinSCard API でカードリーダーを列挙する。"""
    import ctypes
    from ctypes import wintypes
    try:
        winscard = ctypes.WinDLL('winscard.dll')
    except OSError:
        return []
    SCardEstablishContext = winscard.SCardEstablishContext
    SCardListReadersW     = winscard.SCardListReadersW
    SCardReleaseContext   = winscard.SCardReleaseContext

    SCARD_SCOPE_SYSTEM = 2
    SCARD_S_SUCCESS    = 0
    SCARD_E_NO_READERS_AVAILABLE = 0x8010002E

    ctx = ctypes.c_void_p(0)
    rv = SCardEstablishContext(SCARD_SCOPE_SYSTEM, None, None, ctypes.byref(ctx))
    if rv != SCARD_S_SUCCESS:
        return []
    try:
        # 必要なバッファサイズを取得（wchar数）
        size = wintypes.DWORD(0)
        SCardListReadersW(ctx, None, None, ctypes.byref(size))
        if size.value == 0:
            return []
        buf = ctypes.create_unicode_buffer(size.value)
        rv = SCardListReadersW(ctx, None, buf, ctypes.byref(size))
        if rv == SCARD_E_NO_READERS_AVAILABLE or rv != SCARD_S_SUCCESS:
            return []
        # マルチストリング: \0 区切り、末尾 \0\0
        # buf は c_wchar_Array なので、各要素を結合してから分割
        chars = ''.join(buf[i] for i in range(size.value))
        readers = [s for s in chars.split('\x00') if s]
        return readers
    finally:
        SCardReleaseContext(ctx)


@app.route('/api/check-reader')
def check_reader():
    """接続中のカードリーダーを検出して返す。"""
    readers = _list_pcsc_readers()
    is_sanwa = any('ICCR' in r or 'ADR-MNICU' in r or 'Sanwa' in r for r in readers)
    return jsonify({
        'count':            len(readers),
        'readers':          readers,
        'isRecommended':    is_sanwa,
        'recommended':      RECOMMENDED_READER,
    })


# ─── API ──────────────────────────────────────────────────────────────────────

@app.route('/api/browse-dll')
def browse_dll():
    ps_script = (
        'Add-Type -AssemblyName System.Windows.Forms; '
        '$d = New-Object System.Windows.Forms.OpenFileDialog; '
        '$d.Title = "PKCS#11ライブラリ (.dll) を選択してください"; '
        '$d.Filter = "DLLファイル (*.dll)|*.dll|すべてのファイル (*.*)|*.*"; '
        '$d.InitialDirectory = "C:\\Windows\\System32"; '
        'if ($d.ShowDialog() -eq "OK") { Write-Output $d.FileName }'
    )
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True, text=True, encoding='utf-8', timeout=60,
        )
        path = result.stdout.strip()
        if path:
            return jsonify({'path': path})
        return jsonify({'path': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# バージョン（VERSION.txt があればそれを優先、なければ既定値）
def _get_version() -> str:
    vfile = BRIDGE_DIR.parent / 'VERSION.txt'
    if vfile.exists():
        return vfile.read_text(encoding='utf-8').strip()
    return '1.1.0'

VERSION = _get_version()
# GitHub リポジトリ（リリースAPI参照先）— allowed_origins.txt と同じ場所で変更可能
GITHUB_REPO = 'lifemate-inc/hpki-signer'


@app.route('/api/health')
def health():
    import signer as s
    libs = _detect_all_libs()
    return jsonify({
        'status':        'ok',
        'version':       VERSION,
        'mockMode':      s.is_mock_mode() or len(libs) == 0,
        'detectedLib':   libs[0]['path'] if libs else None,
        'availableLibs': libs,
        # CSRFトークン: 起動ごとに変わる。ブラウザはこれを取って後続POSTで返送する。
        'csrfToken':     CSRF_TOKEN,
    })


@app.route('/api/diagnostics')
def diagnostics():
    """
    トラブル時の診断情報を返す（PIN や PDF 内容は含まない）。
    UI から「診断情報をコピー」ボタンで呼ばれ、結果をメール添付等で開発者へ送信できる。
    """
    import platform
    log_path = BRIDGE_DIR / 'bridge.log'
    log_tail = ''
    log_size = 0
    if log_path.exists():
        log_size = log_path.stat().st_size
        try:
            with open(log_path, 'rb') as f:
                f.seek(max(0, log_size - 16384))   # 末尾 16KB
                log_bytes = f.read()
                log_tail = log_bytes.decode('utf-8', errors='replace')
                # PIN 漏洩防止: 念のため pin: で始まる行をマスク（通常ログには出ないが二重防御）
                import re
                log_tail = re.sub(r"('pin':\s*')[^']*(')", r'\1[REDACTED]\2', log_tail)
        except Exception as e:
            log_tail = f'(ログ取得エラー: {e})'

    libs = _detect_all_libs()
    return jsonify({
        'version':       VERSION,
        'time':          __import__('datetime').datetime.now().isoformat(),
        'os':            f'{platform.system()} {platform.release()} ({platform.version()})',
        'python':        platform.python_version(),
        'arch':          platform.machine(),
        'card_readers':  _list_pcsc_readers(),
        'pkcs11_libs':   libs,
        'log_size':      log_size,
        'log_tail':      log_tail,
    })


# ─── 自動アップデート ──────────────────────────────────────────────────────────

# 更新ファイルの保留先（launcher.exe が次回起動時に適用する）
_APP_DIR     = BRIDGE_DIR.parent
_PENDING_DIR = _APP_DIR / '_pending'

# shutdown 用トークン: ローカルファイルに書き込み、launcher だけが読める権限
# （ブラウザJSは fetch 経由でファイル読み込み不可なので CSRF 攻撃を防ぐ）
SHUTDOWN_TOKEN = secrets.token_urlsafe(32)
try:
    _shutdown_token_path = _APP_DIR / '.shutdown_token'
    _shutdown_token_path.write_text(SHUTDOWN_TOKEN, encoding='utf-8')
except Exception:
    pass

# 現在ダウンロード中かどうかのフラグ（重複DL防止）
_update_download_lock = threading.Lock()
_update_download_state = {'status': 'idle', 'version': None, 'progress': 0, 'error': None}


def _download_update_payload(release_url: str, latest_version: str):
    """バックグラウンドスレッドで payload-vX.Y.Z.zip をダウンロードする。"""
    global _update_download_state
    import urllib.request

    payload_url = f'https://github.com/{GITHUB_REPO}/releases/download/v{latest_version}/payload-{latest_version}.zip'
    target = _PENDING_DIR / f'payload-{latest_version}.zip'
    ready_flag = _PENDING_DIR / '.ready'

    try:
        _PENDING_DIR.mkdir(parents=True, exist_ok=True)
        # 古い保留ファイルをクリア
        for old in _PENDING_DIR.glob('payload-*.zip'):
            if old.name != target.name:
                try: old.unlink()
                except Exception: pass
        if ready_flag.exists():
            try: ready_flag.unlink()
            except Exception: pass

        with _update_download_lock:
            _update_download_state = {'status': 'downloading', 'version': latest_version, 'progress': 0, 'error': None}

        # ダウンロード（プログレス計測なしのシンプル実装）
        req = urllib.request.Request(payload_url, headers={'User-Agent': f'HpkiSigner/{VERSION}'})
        with urllib.request.urlopen(req, timeout=300) as resp:
            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            with open(target, 'wb') as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        with _update_download_lock:
                            _update_download_state['progress'] = int(downloaded * 100 / total)

        # ダウンロード完了フラグを作成（launcher が見る）
        ready_flag.write_text(latest_version, encoding='utf-8')

        with _update_download_lock:
            _update_download_state = {'status': 'ready', 'version': latest_version, 'progress': 100, 'error': None}
        print(f'[bridge] アップデート v{latest_version} をダウンロード完了。次回起動時に適用されます。', flush=True)
    except Exception as e:
        with _update_download_lock:
            _update_download_state = {'status': 'error', 'version': latest_version, 'progress': 0, 'error': str(e)}
        print(f'[bridge] アップデートダウンロード失敗: {e}', flush=True)


@app.route('/api/self-update/trigger', methods=['POST'])
def self_update_trigger():
    """新版があればバックグラウンドDL開始（重複起動防止）。フロントから自動で呼ばれる。"""
    global _update_download_state
    with _update_download_lock:
        if _update_download_state['status'] == 'downloading':
            return jsonify({'status': 'already_downloading', 'state': _update_download_state})

    # check-update を内部呼び出し
    import urllib.request, json
    try:
        req = urllib.request.Request(
            f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest',
            headers={'User-Agent': f'HpkiSigner/{VERSION}'},
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
        latest = data.get('tag_name', '').lstrip('v')
        if not _semver_gt(latest, VERSION):
            return jsonify({'status': 'up_to_date', 'current': VERSION})

        # 既に同じバージョンをDL済みなら skip
        ready_flag = _PENDING_DIR / '.ready'
        if ready_flag.exists() and ready_flag.read_text(encoding='utf-8').strip() == latest:
            return jsonify({'status': 'already_ready', 'version': latest})

        # バックグラウンドDL開始
        t = threading.Thread(target=_download_update_payload, args=(data.get('html_url'), latest), daemon=True)
        t.start()
        return jsonify({'status': 'started', 'version': latest})
    except Exception as e:
        return jsonify({'error': str(e)}), 200


@app.route('/api/self-update/status')
def self_update_status():
    """ダウンロード状況を返す（UIのプログレス表示用）"""
    with _update_download_lock:
        return jsonify(dict(_update_download_state))


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    """ブリッジを自己終了する。launcher が更新適用のために呼ぶ。
    X-Shutdown-Token ヘッダーでファイルベースの認証を行うことで、
    悪意あるWebサイトからの CSRF 攻撃を防ぐ。
    """
    import os
    token = request.headers.get('X-Shutdown-Token', '')
    if not secrets.compare_digest(token, SHUTDOWN_TOKEN):
        return jsonify({'error': 'unauthorized'}), 403
    def _exit_later():
        import time
        time.sleep(0.5)   # レスポンス返却を待ってから終了
        os._exit(0)
    threading.Thread(target=_exit_later, daemon=True).start()
    return jsonify({'status': 'shutting_down'})


@app.route('/api/check-update')
def check_update():
    """GitHub Releases API で最新版を確認（ネットなし環境では黙って失敗）"""
    import urllib.request, json
    try:
        req = urllib.request.Request(
            f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest',
            headers={'User-Agent': f'HpkiSigner/{VERSION}'},
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
        latest = data.get('tag_name', '').lstrip('v')
        return jsonify({
            'current':         VERSION,
            'latest':          latest,
            'updateAvailable': _semver_gt(latest, VERSION),
            'releaseUrl':      data.get('html_url', ''),
            'releaseNotes':    data.get('body', ''),
        })
    except Exception as e:
        # ネット切れ・レート制限などはエラー詳細を返すだけ（UIは無視する）
        return jsonify({'error': str(e), 'current': VERSION, 'updateAvailable': False})


def _semver_gt(a: str, b: str) -> bool:
    """a > b を semantic version で比較。形式が違えば False。"""
    def parse(v: str):
        try:
            return tuple(int(x) for x in v.split('-')[0].split('.')[:3])
        except Exception:
            return None
    pa, pb = parse(a), parse(b)
    if not pa or not pb:
        return False
    return pa > pb


@app.route('/api/session/start', methods=['POST'])
def session_start():
    global _session, _last_signing_cert
    import signer as s

    data = request.json or {}
    try:
        with _session_lock:
            if _session:
                _session.close()
            _session = s.SigningSession(
                pin        = data.get('pin', ''),
                pkcs11_lib = data.get('pkcs11Lib', '').strip() or None,
                slot_no    = int(data.get('slotNo', 0) or 0),
                key_label  = data.get('keyLabel',  '').strip() or None,
                cert_label = data.get('certLabel', '').strip() or None,
                tsa_url    = data.get('tsaUrl',    '').strip() or None,
            )
            # 診断用に署名証明書を保持（セッション終了後の identify 用）
            try:
                _last_signing_cert = _session._signer.signing_cert
            except Exception:
                _last_signing_cert = None
        return jsonify({'status': 'ok', 'certInfo': _session.get_cert_info()})
    except Exception as e:
        import traceback
        traceback.print_exc()   # ← bridge.log にフルトレースバックを出力
        return jsonify({'error': str(e)}), 500


@app.route('/api/sign', methods=['POST'])
def sign():
    data    = request.json or {}
    pdf_b64 = data.get('pdf', '')

    if not pdf_b64:
        return jsonify({'error': 'PDFデータが空です'}), 400

    # PKCS#11 セッションはスレッドセーフでないため、署名処理全体をロックする
    with _session_lock:
        if not _session:
            return jsonify({'error': 'セッションが開始されていません。再度「署名開始」を押してください。'}), 400
        try:
            pdf_bytes    = base64.b64decode(pdf_b64)
            signed_bytes = _session.sign_pdf(pdf_bytes)
            return jsonify({'signed': base64.b64encode(signed_bytes).decode()})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': repr(e)}), 500


@app.route('/api/session/end', methods=['POST'])
def session_end():
    global _session
    with _session_lock:
        if _session:
            _session.close()
            _session = None
    return jsonify({'status': 'ok'})


@app.route('/api/cert/download')
def cert_download():
    """署名に使った証明書を .cer ファイルとしてダウンロードする（セットアップ用）"""
    with _session_lock:
        if not _session:
            return jsonify({'error': 'セッションが開始されていません'}), 400
        try:
            cert_bytes = _session._signer.signing_cert.dump()
            card_type  = getattr(_session, '_card_type', 'hpki')
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    from flask import Response
    fname = 'jpki_signing_cert.cer' if card_type == 'jpki' else 'hpki_signing_cert.cer'
    return Response(
        cert_bytes,
        mimetype='application/x-x509-ca-cert',
        headers={'Content-Disposition': f'attachment; filename="{fname}"'},
    )


def _identify_jpki_parent_ca():
    """
    署名証明書を発行した J-LIS CA を特定する。
    AKI と SKI を突合する。アクティブなセッションがなくても、
    直近の署名証明書 (_last_signing_cert) があれば判定する。
    戻り値: (path, label) または None
    """
    from signer import JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH
    from asn1crypto import x509 as asn1x509

    user_cert = None
    if _session:
        try:
            user_cert = _session._signer.signing_cert
        except Exception:
            user_cert = None
    if user_cert is None:
        user_cert = _last_signing_cert
    if user_cert is None:
        return None
    try:
        user_aki = user_cert.authority_key_identifier
    except Exception:
        return None
    if not user_aki:
        return None

    candidates = [
        (JPKI_SIGN_CA03_PATH, 'J-LIS 署名用CA3 (2023-)'),
        (JPKI_SIGN_CA02_PATH, 'J-LIS 署名用CA2 (2019-)'),
        (JPKI_SIGN_CA01_PATH, 'J-LIS 署名用CA1 (2015-)'),
    ]
    for path, label in candidates:
        if not path.exists():
            continue
        ca = asn1x509.Certificate.load(path.read_bytes())
        if ca.key_identifier == user_aki:
            return (path, label)
    return None


@app.route('/api/jpki-ca/identify')
def jpki_ca_identify():
    """現在のセッションのマイナンバーカード署名証明書を発行した CA を特定して返す（診断情報込み）"""
    from signer import JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH
    from asn1crypto import x509 as asn1x509

    diag = {'found': False, 'session_active': False, 'cert_source': None, 'user_aki': None, 'user_issuer': None, 'cas': []}

    with _session_lock:
        user_cert = None
        if _session:
            try:
                user_cert = _session._signer.signing_cert
                diag['session_active'] = True
                diag['cert_source']   = 'current_session'
            except Exception:
                user_cert = None
        if user_cert is None and _last_signing_cert is not None:
            user_cert = _last_signing_cert
            diag['cert_source'] = 'last_session_cache'
        if user_cert is None:
            diag['error'] = 'まだ一度もマイナンバーカードでセッションを開いていません。「署名開始」を1回行ってから再度お試しください。'
            return jsonify(diag)

        try:
            user_aki = user_cert.authority_key_identifier
            diag['user_issuer'] = str(user_cert.issuer.human_friendly)
            diag['user_aki']    = user_aki.hex() if user_aki else None
        except Exception as e:
            diag['error'] = f'証明書解析エラー: {e}'
            return jsonify(diag)

    for ca_path, label in [
        (JPKI_SIGN_CA03_PATH, 'J-LIS 署名用CA3 (2023-)'),
        (JPKI_SIGN_CA02_PATH, 'J-LIS 署名用CA2 (2019-)'),
        (JPKI_SIGN_CA01_PATH, 'J-LIS 署名用CA1 (2015-)'),
    ]:
        ca_info = {'filename': ca_path.name, 'label': label, 'exists': ca_path.exists()}
        if ca_path.exists():
            try:
                ca = asn1x509.Certificate.load(ca_path.read_bytes())
                ca_ski = ca.key_identifier
                ca_info['ski']     = ca_ski.hex() if ca_ski else None
                ca_info['subject'] = str(ca.subject.human_friendly)
                ca_info['matches'] = (user_aki and ca_ski == user_aki)
                if ca_info['matches']:
                    diag['found']   = True
                    diag['filename'] = ca_path.name
                    diag['label']   = label
            except Exception as e:
                ca_info['error'] = str(e)
        diag['cas'].append(ca_info)

    return jsonify(diag)


@app.route('/api/jpki-ca/download')
def jpki_ca_download():
    """
    J-LIS 署名用 CA 証明書をダウンロード。
    アクティブなセッションがあれば該当する世代の CA を、なければ最新世代を返す。
    """
    from signer import JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH
    from flask import Response

    with _session_lock:
        match = _identify_jpki_parent_ca()
    if match:
        ca_path, _ = match
    else:
        ca_path = next(
            (p for p in [JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH] if p.exists()),
            None,
        )
    if ca_path and ca_path.exists():
        return Response(
            ca_path.read_bytes(),
            mimetype='application/x-x509-ca-cert',
            headers={'Content-Disposition': f'attachment; filename="{ca_path.name}"'},
        )
    return jsonify({'error': 'J-LIS CA 証明書ファイルが見つかりません'}), 404


@app.route('/api/jpki-ca/install-to-windows', methods=['POST'])
def jpki_ca_install_to_windows():
    """
    J-LIS CA 証明書（全世代）をユーザの Windows 証明書ストアの
    「信頼されたルート証明機関」にインポートする（管理者権限不要）。
    Acrobat の「Windows 統合」を有効にすれば自動で信頼される。
    """
    from signer import JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH
    import subprocess

    results = []
    for ca_path in [JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH]:
        if not ca_path.exists():
            continue
        # ユーザ Root ストア（HKCU）にインポート（管理者権限不要）
        ps_cmd = (
            f"Import-Certificate -FilePath '{str(ca_path)}' "
            f"-CertStoreLocation Cert:\\CurrentUser\\Root | "
            f"Select-Object -ExpandProperty Thumbprint"
        )
        try:
            r = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_cmd],
                capture_output=True, text=True, encoding='utf-8', timeout=30,
            )
            thumb = r.stdout.strip()
            if r.returncode == 0 and thumb:
                results.append({'filename': ca_path.name, 'status': 'ok', 'thumbprint': thumb})
            else:
                results.append({'filename': ca_path.name, 'status': 'error', 'message': r.stderr.strip() or 'unknown'})
        except Exception as e:
            results.append({'filename': ca_path.name, 'status': 'error', 'message': str(e)})

    ok_count = sum(1 for r in results if r['status'] == 'ok')
    return jsonify({
        'installed': ok_count,
        'total':     len(results),
        'results':   results,
        'next_step': 'Acrobat の「環境設定 → 署名 → 確認 → 詳細」で「Windows 証明書ストアでのすべてのルート証明書を信頼する」にチェックを入れてください。',
    })


@app.route('/api/jpki-ca/bundle')
def jpki_ca_bundle():
    """J-LIS 署名用 CA を全世代まとめて PKCS#7 (.p7b) で返す（Acrobat に一括インポート可能）"""
    from signer import JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH
    from asn1crypto import x509 as asn1x509, cms
    from flask import Response

    certs = []
    for ca_path in [JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH]:
        if ca_path.exists():
            certs.append(asn1x509.Certificate.load(ca_path.read_bytes()))
    if not certs:
        return jsonify({'error': 'J-LIS CA 証明書が1つも見つかりません'}), 404

    # PKCS#7 SignedData (degenerate / certs-only) を構築
    signed_data = cms.SignedData({
        'version': 'v1',
        'digest_algorithms': [],
        'encap_content_info': {'content_type': 'data'},
        'certificates': certs,
        'signer_infos': [],
    })
    pkcs7 = cms.ContentInfo({
        'content_type': 'signed_data',
        'content': signed_data,
    })
    return Response(
        pkcs7.dump(),
        mimetype='application/x-pkcs7-certificates',
        headers={'Content-Disposition': 'attachment; filename="jpki_sign_ca_all.p7b"'},
    )


# ─── 静的ファイル ─────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def index():
    return send_from_directory(str(DOCS_DIR), 'index.html')

@app.route('/setup', methods=['GET'])
def setup_page():
    return send_from_directory(str(DOCS_DIR), 'setup.html')

@app.route('/security', methods=['GET'])
def security_page():
    return send_from_directory(str(DOCS_DIR), 'security.html')


# ─── 起動 ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 52)
    print('  HPKI電子署名ブリッジ v1.0')
    print(f'  http://127.0.0.1:{PORT}')
    print('  終了: Ctrl+C')
    print('=' * 52)
    print('=' * 52)
    threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
