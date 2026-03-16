import logging
import sqlite3
from pathlib import Path


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "03_database" / "pre_contencioso.db"


def _add_column_if_missing(cursor: sqlite3.Cursor, table_name: str, column_sql: str) -> None:
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
    except sqlite3.OperationalError:
        pass


def setup_database() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sql_script = """
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS clientes (
        matricula TEXT PRIMARY KEY
    );

    CREATE TABLE IF NOT EXISTS cases (
        case_id TEXT PRIMARY KEY,
        protocolo_agenersa TEXT
    );

    CREATE TABLE IF NOT EXISTS tickets (
        ticket_id INTEGER PRIMARY KEY,
        case_id TEXT,
        matricula TEXT,
        numero_os TEXT,
        data_criacao DATETIME,
        data_resolucao DATETIME,
        status TEXT,
        atribuido TEXT,
        titulo TEXT,
        assunto TEXT,
        tipo_conversa TEXT,
        tipo_solicitacao TEXT,
        tipo_manifestacao TEXT,
        resultado_tratativa TEXT,
        protocolo_procon TEXT,
        protocolo_defensoria TEXT,
        protocolo_codecon TEXT,
        case_jec TEXT,
        ticket_solicitacao_id INTEGER,
        ticket_notificacao_id INTEGER,
        data_entrada_reclamacao DATETIME,
        data_criacao_solicitacao DATETIME,
        dias_defasagem_abertura INTEGER,
        criterio_vinculo TEXT,
        confianca_vinculo REAL,
        status_vinculo TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(case_id),
        FOREIGN KEY (matricula) REFERENCES clientes(matricula)
    );

    CREATE TABLE IF NOT EXISTS tickets_notificacao (
        ticket_id INTEGER PRIMARY KEY,
        case_id TEXT,
        matricula TEXT,
        numero_os TEXT,
        data_criacao DATETIME,
        data_resolucao DATETIME,
        status TEXT,
        atribuido TEXT,
        titulo TEXT,
        assunto TEXT,
        tipo_conversa TEXT,
        tipo_solicitacao TEXT,
        tipo_manifestacao TEXT,
        resultado_tratativa TEXT,
        protocolo_procon TEXT,
        protocolo_defensoria TEXT,
        protocolo_codecon TEXT,
        case_jec TEXT,
        arquivo_origem TEXT,
        data_carga DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ticket_relacionamentos (
        ticket_solicitacao_id INTEGER PRIMARY KEY,
        ticket_notificacao_id INTEGER,
        status_vinculo TEXT NOT NULL,
        criterio_vinculo TEXT,
        confianca_vinculo REAL,
        data_entrada_reclamacao DATETIME,
        data_criacao_solicitacao DATETIME,
        dias_defasagem_abertura INTEGER,
        quantidade_candidatos INTEGER DEFAULT 0,
        observacao TEXT,
        atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ticket_solicitacao_id) REFERENCES tickets(ticket_id),
        FOREIGN KEY (ticket_notificacao_id) REFERENCES tickets_notificacao(ticket_id)
    );

    CREATE TABLE IF NOT EXISTS ticket_vinculos_manuais (
        ticket_solicitacao_id INTEGER PRIMARY KEY,
        ticket_notificacao_id INTEGER NOT NULL,
        justificativa TEXT,
        usuario TEXT,
        atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ticket_solicitacao_id) REFERENCES tickets(ticket_id),
        FOREIGN KEY (ticket_notificacao_id) REFERENCES tickets_notificacao(ticket_id)
    );

    CREATE TABLE IF NOT EXISTS audiencias (
        audiencia_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER UNIQUE,
        audiencia TEXT,
        data_audiencia DATETIME,
        preposto TEXT,
        local_procon TEXT,
        tipo_audiencia TEXT,
        data_reagendamento DATETIME,
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
    );

    CREATE INDEX IF NOT EXISTS idx_tickets_matricula_os
        ON tickets (matricula, numero_os, data_criacao);

    CREATE INDEX IF NOT EXISTS idx_tickets_notificacao_matricula_os
        ON tickets_notificacao (matricula, numero_os, data_criacao);

    CREATE INDEX IF NOT EXISTS idx_tickets_notificacao_case_id
        ON tickets_notificacao (case_id);
    """

    ticket_columns = [
        "protocolo_procon TEXT",
        "protocolo_defensoria TEXT",
        "protocolo_codecon TEXT",
        "case_jec TEXT",
        "ticket_solicitacao_id INTEGER",
        "ticket_notificacao_id INTEGER",
        "data_entrada_reclamacao DATETIME",
        "data_criacao_solicitacao DATETIME",
        "dias_defasagem_abertura INTEGER",
        "criterio_vinculo TEXT",
        "confianca_vinculo REAL",
        "status_vinculo TEXT",
    ]

    try:
        cursor.executescript(sql_script)

        for column_sql in ticket_columns:
            _add_column_if_missing(cursor, "tickets", column_sql)

        conn.commit()
        logging.info("Banco de dados inicializado/atualizado com sucesso em: %s", DB_PATH)
    except Exception as exc:
        logging.error("Erro ao criar/atualizar banco de dados: %s", exc)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()
