"""Utilitários centrais para conexões SQLite e validação de identificadores SQL.

Centraliza:
- abertura de conexão com PRAGMAs corretos (foreign_keys ON, WAL mode);
- allowlist de tabelas conhecidas para uso em interpolação SQL;
- validação genérica de identificadores SQLite.

Use ``connect(db_path)`` em todos os módulos novos no lugar de ``sqlite3.connect``.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

# Tabelas oficiais do schema Gold do Sentinel. Qualquer tabela criada/lida pelo
# ETL e pelos analytics precisa estar listada aqui para passar pela allowlist.
ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "clientes",
        "cases",
        "tickets",
        "tickets_notificacao",
        "tickets_n1",
        "ticket_assunto",
        "ticket_relacionamentos",
        "ticket_vinculos_manuais",
        "tickets_historico",
        "tickets_auditoria_classificacao",
        "tickets_auditoria_operacional",
        "audiencias",
        "gss_ordens_servico",
        "etl_runs",
        "etl_logs",
    }
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def assert_table(name: str) -> str:
    """Valida que ``name`` consta na allowlist e retorna o próprio nome.

    Lançar exceção em vez de aceitar entrada desconhecida fecha o vetor de
    SQL injection presente em pontos onde nomes de tabela são interpolados
    via f-string (limitação do SQLite, que não parametriza identificadores).
    """
    if not isinstance(name, str) or name not in ALLOWED_TABLES:
        raise ValueError(f"Tabela nao permitida na allowlist: {name!r}")
    return name


def assert_identifier(name: str) -> str:
    """Valida que ``name`` é um identificador SQL seguro (alfa+_+dígitos).

    Útil para nomes de colunas ou aliases não cobertos pela allowlist de tabelas.
    """
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Identificador SQL invalido: {name!r}")
    return name


def connect(db_path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Abre conexão SQLite com PRAGMAs operacionais ativos.

    - ``foreign_keys = ON`` é necessário em **toda** conexão (a diretiva é por
      sessão; aplicá-la apenas em ``executescript`` no setup não persiste).
    - ``journal_mode = WAL`` permite escrita do ETL concorrente com leitura do
      Power BI sem causar SQLITE_BUSY.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    if not read_only:
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn
