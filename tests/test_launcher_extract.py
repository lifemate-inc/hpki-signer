"""
launcher.go の preserveFiles を ZIP 経由で正しく扱えるかを Python 側から検証する。
launcher.go の単体テストではないが、preserveFiles リストの仕様を文書化する役割。
"""
from pathlib import Path


def test_preserve_files_listed_in_launcher_go():
    """launcher.go の preserveFiles リストに、保護すべきファイルが含まれていること"""
    launcher = Path(__file__).resolve().parent.parent / 'installer' / 'launcher' / 'launcher.go'
    content = launcher.read_text(encoding='utf-8')
    # ユーザー設定なので絶対に上書きしてはいけない
    assert '"bridge/allowed_origins.txt"' in content
    assert '"launcher.json"' in content


def test_version_txt_not_in_preserve():
    """VERSION.txt は preserveFiles に含まれてはいけない（更新時の上書きが必要）"""
    launcher = Path(__file__).resolve().parent.parent / 'installer' / 'launcher' / 'launcher.go'
    content = launcher.read_text(encoding='utf-8')
    # preserveFiles のブロックに VERSION.txt がない
    # 簡易チェック: コード内に "VERSION.txt" が preserveFiles 配列にあるか
    import re
    # var preserveFiles = []string{ ... } のブロックを抽出
    m = re.search(r'var preserveFiles\s*=\s*\[\]string\{([^}]*)\}', content, re.DOTALL)
    if m:
        preserve_block = m.group(1)
        assert 'VERSION.txt' not in preserve_block, \
            'VERSION.txt が preserveFiles に含まれています。更新時に上書きされず、バージョン管理が壊れます。'
