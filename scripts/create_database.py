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
        bloco TEXT,
        numero_os TEXT,
        numero_os_original TEXT,
        numero_os_gss TEXT,
        gss_os_id TEXT,
        origem_numero_os TEXT,
        status_vinculo_os TEXT,
        score_vinculo_os REAL,
        criterio_vinculo_os TEXT,
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
        tags_ticket TEXT,
        grupo_tickets TEXT,
        superintendencia_adr TEXT,
        canal_origem TEXT,
        cpf_cliente TEXT,
        passou_nivel_1 TEXT,
        canais_de_atrito TEXT,
        protocolo_referencia_informado TEXT,
        motivo_espera TEXT,
        prioridade_ticket TEXT,
        controle_interno TEXT,
        concessionaria TEXT,
        classificacao_solicitacoes TEXT,
        bairro TEXT,
        municipio TEXT,
        logradouro TEXT,
        endereco TEXT,
        numero_porta TEXT,
        complemento TEXT,
        telefone TEXT,
        nome_cliente_gss TEXT,
        nome_requerente_gss TEXT,
        nome_solicitante TEXT,
        email_solicitante TEXT,
        formulario_ticket TEXT,
        classificacao_notificacoes TEXT,
        flag_arquivado_relatorio INTEGER,
        flag_auditoria_classificacao INTEGER,
        motivo_auditoria_classificacao TEXT,
        status_auditoria_classificacao TEXT,
        grupo_sugerido_auditoria TEXT,
        tipo_solicitacao_original_auditoria TEXT,
        data_auditoria_classificacao DATETIME,
        qtde_assuntos_ticket INTEGER,
        flag_multiplos_assuntos INTEGER,
        protocolo_procon TEXT,
        protocolo_defensoria TEXT,
        protocolo_codecon TEXT,
        case_jec TEXT,
        ticket_solicitacao_id INTEGER,
        ticket_notificacao_id INTEGER,
        data_entrada_reclamacao DATETIME,
        data_criacao_solicitacao DATETIME,
        data_criacao_notificacao DATETIME,
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
        bloco TEXT,
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
        tags_ticket TEXT,
        grupo_tickets TEXT,
        superintendencia_adr TEXT,
        canal_origem TEXT,
        cpf_cliente TEXT,
        passou_nivel_1 TEXT,
        canais_de_atrito TEXT,
        protocolo_referencia_informado TEXT,
        motivo_espera TEXT,
        prioridade_ticket TEXT,
        controle_interno TEXT,
        concessionaria TEXT,
        classificacao_solicitacoes TEXT,
        bairro TEXT,
        municipio TEXT,
        logradouro TEXT,
        endereco TEXT,
        numero_porta TEXT,
        complemento TEXT,
        telefone TEXT,
        nome_cliente_gss TEXT,
        nome_requerente_gss TEXT,
        nome_solicitante TEXT,
        email_solicitante TEXT,
        formulario_ticket TEXT,
        classificacao_notificacoes TEXT,
        flag_arquivado_relatorio INTEGER,
        protocolo_procon TEXT,
        protocolo_defensoria TEXT,
        protocolo_codecon TEXT,
        case_jec TEXT,
        arquivo_origem TEXT,
        data_carga DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ticket_assunto (
        ticket_assunto_id TEXT PRIMARY KEY,
        ticket_id INTEGER NOT NULL,
        formulario_ticket TEXT,
        assunto_raw TEXT,
        assunto_normalizado TEXT,
        ordem_assunto INTEGER,
        flag_assunto_principal INTEGER,
        arquivo_origem TEXT,
        data_carga DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
    );

    CREATE TABLE IF NOT EXISTS tickets_n1 (
        ticket_id INTEGER PRIMARY KEY,
        matricula TEXT,
        bloco TEXT,
        data_criacao DATETIME,
        data_resolucao DATETIME,
        status TEXT,
        titulo TEXT,
        assunto TEXT,
        grupo_tickets TEXT,
        canal_ticket TEXT,
        canal_origem TEXT,
        formulario_ticket TEXT,
        tipo_ticket TEXT,
        conversation_id TEXT,
        tipo_conversa TEXT,
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
        data_criacao_notificacao DATETIME,
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

    CREATE TABLE IF NOT EXISTS tickets_auditoria_classificacao (
        ticket_id INTEGER PRIMARY KEY,
        origem_regra TEXT NOT NULL,
        status_auditoria TEXT NOT NULL DEFAULT 'PENDENTE_VALIDACAO',
        motivo_auditoria TEXT,
        tipo_solicitacao_original TEXT,
        tipo_solicitacao_atual TEXT,
        grupo_tickets TEXT,
        grupo_sugerido TEXT,
        canal_normalizado TEXT,
        data_criacao DATETIME,
        data_resolucao DATETIME,
        atribuido TEXT,
        titulo TEXT,
        observacao TEXT,
        arquivo_origem TEXT,
        data_identificacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        data_validacao DATETIME,
        validado_por TEXT,
        acao_validacao TEXT,
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
    );

    CREATE TABLE IF NOT EXISTS audiencias (
        audiencia_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER UNIQUE,
        ticket_audiencia_id INTEGER,
        ticket_relacionado_id INTEGER,
        audiencia TEXT,
        data_audiencia DATETIME,
        status_ticket TEXT,
        preposto_id TEXT,
        preposto TEXT,
        local_procon TEXT,
        tipo_audiencia TEXT,
        atribuido TEXT,
        data_reagendamento DATETIME,
        arquivo_origem TEXT,
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
    );

    CREATE TABLE IF NOT EXISTS gss_ordens_servico (
        gss_os_id TEXT PRIMARY KEY,
        numero_os TEXT,
        ano_os TEXT,
        matricula TEXT,
        bloco TEXT,
        data_emissao DATETIME,
        servico_executado TEXT,
        nome_cliente TEXT,
        nome_requerente TEXT,
        telefone TEXT,
        endereco_requerente TEXT,
        nome_logradouro TEXT,
        numero_porta TEXT,
        complemento TEXT,
        bairro TEXT,
        municipio TEXT,
        data_agendamento DATETIME,
        data_impressao DATETIME,
        previsao_conclusao DATETIME,
        data_execucao DATETIME,
        executor TEXT,
        entrada_setor DATETIME,
        data_pedido TEXT,
        atendente TEXT,
        solicitacao_associada TEXT,
        tipo_solicitacao_gss TEXT,
        status_os_gss TEXT,
        servico_normalizado TEXT,
        arquivo_origem TEXT,
        data_carga DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_tickets_matricula_os
        ON tickets (matricula, numero_os, data_criacao);

    CREATE INDEX IF NOT EXISTS idx_tickets_notificacao_matricula_os
        ON tickets_notificacao (matricula, numero_os, data_criacao);

    CREATE INDEX IF NOT EXISTS idx_tickets_notificacao_case_id
        ON tickets_notificacao (case_id);

    CREATE INDEX IF NOT EXISTS idx_tickets_n1_matricula_data
        ON tickets_n1 (matricula, data_criacao);

    CREATE INDEX IF NOT EXISTS idx_gss_ordens_servico_matricula_data
        ON gss_ordens_servico (matricula, data_emissao);

    CREATE INDEX IF NOT EXISTS idx_gss_ordens_servico_numero_os
        ON gss_ordens_servico (numero_os);

    CREATE INDEX IF NOT EXISTS idx_ticket_assunto_ticket_id
        ON ticket_assunto (ticket_id);

    CREATE INDEX IF NOT EXISTS idx_ticket_assunto_normalizado
        ON ticket_assunto (assunto_normalizado);

    CREATE INDEX IF NOT EXISTS idx_tickets_auditoria_classificacao_status
        ON tickets_auditoria_classificacao (status_auditoria, origem_regra);
    """

    ticket_columns = [
        "bloco TEXT",
        "numero_os_original TEXT",
        "numero_os_gss TEXT",
        "gss_os_id TEXT",
        "origem_numero_os TEXT",
        "status_vinculo_os TEXT",
        "score_vinculo_os REAL",
        "criterio_vinculo_os TEXT",
        "protocolo_procon TEXT",
        "protocolo_defensoria TEXT",
        "protocolo_codecon TEXT",
        "case_jec TEXT",
        "tags_ticket TEXT",
        "grupo_tickets TEXT",
        "superintendencia_adr TEXT",
        "canal_origem TEXT",
        "cpf_cliente TEXT",
        "passou_nivel_1 TEXT",
        "canais_de_atrito TEXT",
        "protocolo_referencia_informado TEXT",
        "motivo_espera TEXT",
        "prioridade_ticket TEXT",
        "controle_interno TEXT",
        "concessionaria TEXT",
        "classificacao_solicitacoes TEXT",
        "bairro TEXT",
        "municipio TEXT",
        "logradouro TEXT",
        "endereco TEXT",
        "numero_porta TEXT",
        "complemento TEXT",
        "telefone TEXT",
        "nome_cliente_gss TEXT",
        "nome_requerente_gss TEXT",
        "nome_solicitante TEXT",
        "email_solicitante TEXT",
        "formulario_ticket TEXT",
        "classificacao_notificacoes TEXT",
        "flag_arquivado_relatorio INTEGER",
        "flag_auditoria_classificacao INTEGER",
        "motivo_auditoria_classificacao TEXT",
        "status_auditoria_classificacao TEXT",
        "grupo_sugerido_auditoria TEXT",
        "tipo_solicitacao_original_auditoria TEXT",
        "data_auditoria_classificacao DATETIME",
        "qtde_assuntos_ticket INTEGER",
        "flag_multiplos_assuntos INTEGER",
        "ticket_solicitacao_id INTEGER",
        "ticket_notificacao_id INTEGER",
        "data_entrada_reclamacao DATETIME",
        "data_criacao_solicitacao DATETIME",
        "data_criacao_notificacao DATETIME",
        "dias_defasagem_abertura INTEGER",
        "criterio_vinculo TEXT",
        "confianca_vinculo REAL",
        "status_vinculo TEXT",
    ]

    tickets_notificacao_columns = [
        "bloco TEXT",
        "tags_ticket TEXT",
        "grupo_tickets TEXT",
        "superintendencia_adr TEXT",
        "canal_origem TEXT",
        "cpf_cliente TEXT",
        "passou_nivel_1 TEXT",
        "canais_de_atrito TEXT",
        "protocolo_referencia_informado TEXT",
        "motivo_espera TEXT",
        "prioridade_ticket TEXT",
        "controle_interno TEXT",
        "concessionaria TEXT",
        "classificacao_solicitacoes TEXT",
        "bairro TEXT",
        "municipio TEXT",
        "logradouro TEXT",
        "endereco TEXT",
        "numero_porta TEXT",
        "complemento TEXT",
        "telefone TEXT",
        "nome_cliente_gss TEXT",
        "nome_requerente_gss TEXT",
        "nome_solicitante TEXT",
        "email_solicitante TEXT",
        "formulario_ticket TEXT",
        "classificacao_notificacoes TEXT",
        "flag_arquivado_relatorio INTEGER",
    ]

    audiencias_columns = [
        "ticket_audiencia_id INTEGER",
        "ticket_relacionado_id INTEGER",
        "status_ticket TEXT",
        "preposto_id TEXT",
        "atribuido TEXT",
        "arquivo_origem TEXT",
    ]

    tickets_n1_columns = [
        "bloco TEXT",
    ]

    gss_columns = [
        "bloco TEXT",
    ]

    try:
        cursor.executescript(sql_script)

        for column_sql in ticket_columns:
            _add_column_if_missing(cursor, "tickets", column_sql)
        for column_sql in tickets_notificacao_columns:
            _add_column_if_missing(cursor, "tickets_notificacao", column_sql)
        for column_sql in audiencias_columns:
            _add_column_if_missing(cursor, "audiencias", column_sql)
        for column_sql in tickets_n1_columns:
            _add_column_if_missing(cursor, "tickets_n1", column_sql)
        for column_sql in gss_columns:
            _add_column_if_missing(cursor, "gss_ordens_servico", column_sql)

        conn.commit()
        logging.info("Banco de dados inicializado/atualizado com sucesso em: %s", DB_PATH)
    except Exception as exc:
        logging.error("Erro ao criar/atualizar banco de dados: %s", exc)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()
