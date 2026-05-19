"""
bridge.py の基本機能テスト。
PKCS#11 / pyhanko を必要としない単体テストのみ。
"""
import os
import sys
from pathlib import Path

import pytest


# ─── _semver_gt: バージョン比較 ──────────────────────────────────────


def _import_bridge():
    """bridge をモックモードで import する（pyhanko 等の重い依存を回避）"""
    # PORT を有効値に固定
    os.environ.setdefault('HPKI_BRIDGE_PORT', '14733')
    import importlib
    if 'bridge' in sys.modules:
        importlib.reload(sys.modules['bridge'])
    import bridge   # type: ignore
    return bridge


@pytest.fixture(scope='module')
def bridge_mod():
    return _import_bridge()


class TestSemverGt:
    """_semver_gt は a > b を semantic version で比較する"""

    def test_minor_upgrade(self, bridge_mod):
        assert bridge_mod._semver_gt('1.1.7', '1.1.6')

    def test_patch_upgrade(self, bridge_mod):
        assert bridge_mod._semver_gt('1.0.10', '1.0.9')

    def test_major_upgrade(self, bridge_mod):
        assert bridge_mod._semver_gt('2.0.0', '1.9.9')

    def test_equal(self, bridge_mod):
        assert not bridge_mod._semver_gt('1.1.6', '1.1.6')

    def test_downgrade(self, bridge_mod):
        assert not bridge_mod._semver_gt('1.0.0', '1.1.0')

    def test_invalid(self, bridge_mod):
        assert not bridge_mod._semver_gt('foo', '1.0.0')
        assert not bridge_mod._semver_gt('1.0.0', 'bar')

    def test_with_v_prefix_stripped_already(self, bridge_mod):
        # bridge.py 側で lstrip('v') してから呼ばれる前提
        assert bridge_mod._semver_gt('1.1.7', '1.1.6')


class TestAllowedOrigins:
    """allowed_origins の読み込み: localhost のフォールバックポートが全部含まれること"""

    def test_includes_all_fallback_ports(self, bridge_mod):
        origins = bridge_mod._load_allowed_origins()
        for port in (14733, 14734, 14735, 14736, 14737):
            assert f'http://localhost:{port}' in origins
            assert f'http://127.0.0.1:{port}' in origins

    def test_includes_null_for_file_protocol(self, bridge_mod):
        origins = bridge_mod._load_allowed_origins()
        assert 'null' in origins


class TestVersion:
    """_get_version: VERSION.txt があれば優先、なければ既定値"""

    def test_returns_string(self, bridge_mod):
        v = bridge_mod._get_version()
        assert isinstance(v, str)
        assert len(v) > 0


class TestCsrfTokenGeneration:
    """CSRF/Shutdown トークン: 起動毎に生成され、暗号学的に強い"""

    def test_csrf_token_length(self, bridge_mod):
        # secrets.token_urlsafe(32) は 32 bytes → 約 43 文字
        assert len(bridge_mod.CSRF_TOKEN) >= 32

    def test_shutdown_token_length(self, bridge_mod):
        assert len(bridge_mod.SHUTDOWN_TOKEN) >= 32

    def test_tokens_are_different(self, bridge_mod):
        # CSRF と Shutdown は別のトークン
        assert bridge_mod.CSRF_TOKEN != bridge_mod.SHUTDOWN_TOKEN


class TestCsrfExempt:
    """CSRF 免除エンドポイント: GET 用と shutdown のみ"""

    def test_health_exempt(self, bridge_mod):
        assert '/api/health' in bridge_mod._CSRF_EXEMPT

    def test_shutdown_exempt(self, bridge_mod):
        # shutdown は X-Shutdown-Token で別途認証する
        assert '/api/shutdown' in bridge_mod._CSRF_EXEMPT

    def test_sign_not_exempt(self, bridge_mod):
        # PIN を含む POST は CSRF 必須
        assert '/api/sign' not in bridge_mod._CSRF_EXEMPT

    def test_session_start_not_exempt(self, bridge_mod):
        assert '/api/session/start' not in bridge_mod._CSRF_EXEMPT
