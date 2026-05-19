"""
signer.py のモックモード動作テスト。
カードがなくても通る最低限のチェック。
"""
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def signer_mod():
    _bridge_dir = Path(__file__).resolve().parent.parent / 'bridge'
    if str(_bridge_dir) not in sys.path:
        sys.path.insert(0, str(_bridge_dir))
    import signer
    return signer


class TestMockMode:
    """is_mock_mode: pkcs11 が import できない環境では True"""

    def test_returns_bool(self, signer_mod):
        result = signer_mod.is_mock_mode()
        assert isinstance(result, bool)


class TestCaCertificatePaths:
    """CA 証明書ファイルのパス定義が存在すること"""

    def test_medis_paths(self, signer_mod):
        assert signer_mod.MEDIS_SIGN_CA_PATH.name == 'medis_sign_ca.cer'
        assert signer_mod.MEDIS_AUTH_CA_PATH.name == 'medis_auth_ca.cer'
        assert signer_mod.MHLW_ROOT_CA_PATH.name == 'mhlw_hpki_root_ca_v2.cer'

    def test_jpki_paths(self, signer_mod):
        assert signer_mod.JPKI_SIGN_CA01_PATH.name == 'jpki_sign_ca01.cer'
        assert signer_mod.JPKI_SIGN_CA02_PATH.name == 'jpki_sign_ca02.cer'
        assert signer_mod.JPKI_SIGN_CA03_PATH.name == 'jpki_sign_ca03.cer'
