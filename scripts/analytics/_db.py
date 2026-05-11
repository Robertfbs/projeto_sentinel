"""Helper interno do módulo analytics: garante que ``scripts/`` esteja no path
e re-exporta utilitários de conexão SQLite com PRAGMAs corretos."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from db_utils import assert_table, connect  # noqa: E402,F401
