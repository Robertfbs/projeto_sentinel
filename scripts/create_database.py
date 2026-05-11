import logging
import sqlite3
from pathlib import Path

from db_utils import assert_table, connect as connect_db


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "03_database" / "pre_contencioso.db"


def _add_column_if_missing(cursor: sqlite3.Cursor, table_name: str, column_sql: str) -> None:
    """Adiciona coluna se ainda nao existir.

    Filtra apenas o erro especifico "duplicate column name"; qualquer outro
    OperationalError (tabela inexistente, sintaxe invalida, DB corrompido)
    eh propagado para nao mascarar problemas de schema.
    """
    safe_table = assert_table(table_name)
    try:
        cursor.execute(f"ALTER TABLE {safe_table} ADD COLUMN {column_sql}")
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise


def setup_database() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)

    conn = connect_db(DB_PATH)
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
        data_inicio_vigencia DATETIME,
        data_fim_vigencia DATETIME,
        flag_ativo INTEGER DEFAULT 1,
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

    CREATE TABLE IF NOT EXISTS tickets_auditoria_operacional (
        auditoria_operacional_id INTEGER PRIMARY KEY AUTOINCREMENT,
        auditoria_operacional_key TEXT,
        ticket_id INTEGER,
        origem_regra TEXT,
        tipo_inconsistencia TEXT,
        descricao_inconsistencia TEXT,
        status_validacao TEXT,
        data_identificacao DATETIME,
        data_validacao DATETIME,
        validado_por TEXT,
        acao_tomada TEXT,
        observacao TEXT,
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
    );

    CREATE TABLE IF NOT EXISTS etl_runs (
        run_id TEXT PRIMARY KEY,
        pipeline_name TEXT,
        data_execucao DATETIME,
        status TEXT,
        tempo_execucao REAL,
        qtd_registros_processados INTEGER,
        erro TEXT,
        qtd_arquivos_lidos INTEGER,
        qtd_fontes_processadas INTEGER,
        data_inicio DATETIME,
        data_fim DATETIME
    );

    CREATE TABLE IF NOT EXISTS etl_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        timestamp_log DATETIME,
        nivel TEXT,
        etapa TEXT,
        status TEXT,
        volume_processado INTEGER,
        tempo_etapa REAL,
        erro TEXT,
        payload_json TEXT,
        FOREIGN KEY (run_id) REFERENCES etl_runs(run_id)
    );

    CREATE TABLE IF NOT EXISTS tickets_historico (
        ticket_hist_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        case_id TEXT,
        matricula TEXT,
        numero_os TEXT,
        status TEXT,
        atribuido TEXT,
        titulo TEXT,
        assunto TEXT,
        tipo_solicitacao TEXT,
        tipo_manifestacao TEXT,
        resultado_tratativa TEXT,
        grupo_tickets TEXT,
        flag_arquivado_relatorio INTEGER,
        ticket_notificacao_id INTEGER,
        status_vinculo TEXT,
        data_criacao DATETIME,
        data_resolucao DATETIME,
        data_inicio_vigencia DATETIME,
        data_fim_vigencia DATETIME,
        flag_ativo INTEGER DEFAULT 1,
        run_id TEXT,
        hash_dados TEXT NOT NULL,
        payload_json TEXT,
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id),
        FOREIGN KEY (run_id) REFERENCES etl_runs(run_id)
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

    CREATE INDEX IF NOT EXISTS idx_tickets_status_resolucao
        ON tickets (status, data_resolucao);

    CREATE INDEX IF NOT EXISTS idx_tickets_tipo_solicitacao
        ON tickets (tipo_solicitacao);

    CREATE INDEX IF NOT EXISTS idx_audiencias_data
        ON audiencias (data_audiencia, data_reagendamento);

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

    CREATE INDEX IF NOT EXISTS idx_etl_runs_status_data
        ON etl_runs (status, data_execucao);

    CREATE INDEX IF NOT EXISTS idx_etl_logs_run_etapa
        ON etl_logs (run_id, etapa, timestamp_log);

    CREATE INDEX IF NOT EXISTS idx_tickets_historico_ticket_ativo
        ON tickets_historico (ticket_id, flag_ativo, data_inicio_vigencia);

    CREATE INDEX IF NOT EXISTS idx_tickets_historico_hash
        ON tickets_historico (ticket_id, hash_dados);

    CREATE INDEX IF NOT EXISTS idx_tickets_auditoria_operacional_status
        ON tickets_auditoria_operacional (status_validacao, tipo_inconsistencia);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_auditoria_operacional_key
        ON tickets_auditoria_operacional (auditoria_operacional_key);
    """

    view_script = """
    CREATE VIEW IF NOT EXISTS vw_tickets_ativos AS
    SELECT *
    FROM tickets
    WHERE COALESCE(flag_ativo, 1) = 1;

    CREATE VIEW IF NOT EXISTS fato_tickets AS
    SELECT
        ticket_id,
        case_id,
        matricula,
        bloco,
        numero_os,
        data_criacao,
        data_resolucao,
        status,
        atribuido,
        titulo,
        assunto,
        tipo_solicitacao,
        tipo_manifestacao,
        resultado_tratativa,
        grupo_tickets,
        canal_origem,
        classificacao_solicitacoes,
        classificacao_notificacoes,
        flag_arquivado_relatorio,
        flag_auditoria_classificacao,
        qtde_assuntos_ticket,
        flag_multiplos_assuntos,
        ticket_notificacao_id,
        status_vinculo,
        data_inicio_vigencia,
        data_fim_vigencia,
        flag_ativo
    FROM vw_tickets_ativos
    WHERE COALESCE(flag_arquivado_relatorio, 0) = 0;

    CREATE VIEW IF NOT EXISTS fato_audiencias AS
    SELECT
        a.ticket_id,
        a.ticket_audiencia_id,
        a.ticket_relacionado_id,
        a.audiencia,
        a.data_audiencia,
        a.status_ticket,
        a.preposto_id,
        a.preposto,
        a.local_procon,
        a.tipo_audiencia,
        a.atribuido,
        a.data_reagendamento
    FROM audiencias a
    LEFT JOIN vw_tickets_ativos t
        ON t.ticket_id = a.ticket_id
    WHERE t.ticket_id IS NULL OR COALESCE(t.flag_arquivado_relatorio, 0) = 0;

    CREATE VIEW IF NOT EXISTS dim_tempo AS
    WITH datas AS (
        SELECT date(data_criacao) AS data_calendario FROM tickets WHERE data_criacao IS NOT NULL
        UNION
        SELECT date(data_resolucao) AS data_calendario FROM tickets WHERE data_resolucao IS NOT NULL
        UNION
        SELECT date(data_audiencia) AS data_calendario FROM audiencias WHERE data_audiencia IS NOT NULL
        UNION
        SELECT date(data_reagendamento) AS data_calendario FROM audiencias WHERE data_reagendamento IS NOT NULL
    )
    SELECT
        replace(data_calendario, '-', '') AS data_key,
        data_calendario,
        CAST(strftime('%Y', data_calendario) AS INTEGER) AS ano,
        CAST(strftime('%m', data_calendario) AS INTEGER) AS mes,
        CAST(strftime('%d', data_calendario) AS INTEGER) AS dia,
        printf('%s-%s', strftime('%Y', data_calendario), strftime('%m', data_calendario)) AS ano_mes,
        ((CAST(strftime('%m', data_calendario) AS INTEGER) - 1) / 3) + 1 AS trimestre,
        CASE strftime('%m', data_calendario)
            WHEN '01' THEN 'Janeiro'
            WHEN '02' THEN 'Fevereiro'
            WHEN '03' THEN 'Marco'
            WHEN '04' THEN 'Abril'
            WHEN '05' THEN 'Maio'
            WHEN '06' THEN 'Junho'
            WHEN '07' THEN 'Julho'
            WHEN '08' THEN 'Agosto'
            WHEN '09' THEN 'Setembro'
            WHEN '10' THEN 'Outubro'
            WHEN '11' THEN 'Novembro'
            WHEN '12' THEN 'Dezembro'
        END AS nome_mes,
        CAST(strftime('%w', data_calendario) AS INTEGER) AS dia_semana_num
    FROM datas
    WHERE data_calendario IS NOT NULL;

    CREATE VIEW IF NOT EXISTS dim_canal AS
    SELECT DISTINCT
        COALESCE(tipo_solicitacao, 'NAO_INFORMADO') AS canal_key,
        COALESCE(tipo_solicitacao, 'NAO_INFORMADO') AS canal
    FROM fato_tickets;

    CREATE VIEW IF NOT EXISTS dim_status AS
    SELECT DISTINCT
        COALESCE(status, 'NAO_INFORMADO') AS status_key,
        COALESCE(status, 'NAO_INFORMADO') AS status
    FROM fato_tickets;

    CREATE VIEW IF NOT EXISTS dim_atribuido AS
    SELECT DISTINCT
        COALESCE(atribuido, 'NAO_ATRIBUIDO') AS atribuido_key,
        COALESCE(atribuido, 'NAO_ATRIBUIDO') AS atribuido
    FROM fato_tickets;

    CREATE VIEW IF NOT EXISTS dim_assunto AS
    SELECT DISTINCT
        COALESCE(assunto_normalizado, 'SEM_ASSUNTO') AS assunto_key,
        COALESCE(assunto_normalizado, 'SEM_ASSUNTO') AS assunto_normalizado
    FROM ticket_assunto;

    CREATE VIEW IF NOT EXISTS gold_ai_ready AS
    SELECT
        ticket_id,
        case_id,
        matricula,
        bloco,
        data_criacao,
        data_resolucao,
        status,
        atribuido,
        COALESCE(titulo, '') AS titulo,
        COALESCE(assunto, '') AS assunto,
        COALESCE(tipo_solicitacao, '') AS canal_semantico,
        COALESCE(tipo_manifestacao, '') AS tipo_manifestacao,
        COALESCE(resultado_tratativa, '') AS resultado_tratativa,
        COALESCE(classificacao_solicitacoes, '') AS classificacao_solicitacoes,
        COALESCE(classificacao_notificacoes, '') AS classificacao_notificacoes,
        COALESCE(grupo_tickets, '') AS grupo_tickets,
        COALESCE(municipio, '') AS municipio,
        COALESCE(bairro, '') AS bairro,
        COALESCE(endereco, '') AS endereco,
        COALESCE(flag_auditoria_classificacao, 0) AS flag_auditoria_classificacao
    FROM vw_tickets_ativos
    WHERE COALESCE(flag_arquivado_relatorio, 0) = 0;

    CREATE INDEX IF NOT EXISTS idx_tickets_flag_ativo
        ON tickets (flag_ativo, data_inicio_vigencia);
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
        "data_inicio_vigencia DATETIME",
        "data_fim_vigencia DATETIME",
        "flag_ativo INTEGER DEFAULT 1",
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

    tickets_auditoria_operacional_columns = [
        "auditoria_operacional_key TEXT",
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
        for column_sql in tickets_auditoria_operacional_columns:
            _add_column_if_missing(cursor, "tickets_auditoria_operacional", column_sql)

        cursor.executescript(view_script)
        conn.commit()
        logging.info("Banco de dados inicializado/atualizado com sucesso em: %s", DB_PATH)
    except Exception as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        logging.error("Erro ao criar/atualizar banco de dados: %s", exc)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()
