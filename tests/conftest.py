"""
pytest 共通設定。
bridge/ ディレクトリを import path に追加する。
"""
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent / 'bridge'
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))
