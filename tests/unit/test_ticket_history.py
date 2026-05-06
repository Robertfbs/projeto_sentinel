from __future__ import annotations

import sqlite3
import unittest

import pandas as pd

from load_database import persist_ticket_history, sync_current_ticket_version_metadata


class TicketHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE tickets (
                ticket_id INTEGER PRIMARY KEY,
                data_inicio_vigencia DATETIME,
                data_fim_vigencia DATETIME,
                flag_ativo INTEGER
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE tickets_historico (
                ticket_hist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
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
                flag_ativo INTEGER,
                run_id TEXT,
                hash_dados TEXT,
                payload_json TEXT
            )
            """
        )

    def tearDown(self) -> None:
        self.conn.close()

    def test_persist_ticket_history_versions_changed_rows(self) -> None:
        self.conn.execute("INSERT INTO tickets (ticket_id, flag_ativo) VALUES (1, 1)")

        first_snapshot = pd.DataFrame(
            [
                {
                    "ticket_id": 1,
                    "case_id": "CASE-1",
                    "matricula": "4001",
                    "numero_os": "123",
                    "status": "ABERTO",
                    "atribuido": "Analista",
                    "titulo": "Titulo",
                    "assunto": "Assunto",
                    "tipo_solicitacao": "PROCON",
                    "tipo_manifestacao": "MANIFESTACAO",
                    "resultado_tratativa": None,
                    "grupo_tickets": "Grupo",
                    "flag_arquivado_relatorio": 0,
                    "ticket_notificacao_id": None,
                    "status_vinculo": None,
                    "data_criacao": "2026-04-01 10:00:00",
                    "data_resolucao": None,
                }
            ]
        )
        changed = persist_ticket_history(first_snapshot, self.conn, "run-1", "2026-04-24 10:00:00")
        sync_current_ticket_version_metadata([1], changed, self.conn, "2026-04-24 10:00:00")

        second_snapshot = first_snapshot.copy()
        second_snapshot.loc[0, "status"] = "RESOLVIDO"
        changed = persist_ticket_history(second_snapshot, self.conn, "run-2", "2026-04-24 11:00:00")
        sync_current_ticket_version_metadata([1], changed, self.conn, "2026-04-24 11:00:00")

        history = pd.read_sql_query(
            "SELECT status, flag_ativo, data_inicio_vigencia, data_fim_vigencia FROM tickets_historico ORDER BY ticket_hist_id",
            self.conn,
        )
        current = pd.read_sql_query(
            "SELECT flag_ativo, data_inicio_vigencia, data_fim_vigencia FROM tickets WHERE ticket_id = 1",
            self.conn,
        )

        self.assertEqual(len(history), 2)
        self.assertEqual(history.loc[0, "status"], "ABERTO")
        self.assertEqual(int(history.loc[0, "flag_ativo"]), 0)
        self.assertEqual(history.loc[1, "status"], "RESOLVIDO")
        self.assertEqual(int(history.loc[1, "flag_ativo"]), 1)
        self.assertEqual(int(current.loc[0, "flag_ativo"]), 1)
        self.assertEqual(current.loc[0, "data_fim_vigencia"], None)


if __name__ == "__main__":
    unittest.main()
