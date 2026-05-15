from __future__ import annotations

import sqlite3
import unittest

import pandas as pd

from business_rules import (
    apply_classification_audit_rules,
    apply_ticket_manual_overrides,
    build_archive_flag,
    filter_removed_tickets,
    purge_stale_audit_records,
)


class BusinessRulesTests(unittest.TestCase):
    def test_manual_override_marks_ticket_as_anexo(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "ticket_id": 42726461,
                    "tipo_manifestacao": None,
                    "classificacao_notificacoes": None,
                    "flag_arquivado_relatorio": 0,
                }
            ]
        )

        result = apply_ticket_manual_overrides(df, "solicitacao")

        self.assertEqual(result.loc[0, "tipo_manifestacao"], "ANEXO")
        self.assertEqual(int(result.loc[0, "flag_arquivado_relatorio"]), 1)

    def test_audit_rule_flags_governance_channel_with_unexpected_group(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "ticket_id": 999001,
                    "tipo_solicitacao": "PROCON",
                    "grupo_tickets": "Grupo Divergente",
                    "flag_arquivado_relatorio": 0,
                    "data_criacao": pd.Timestamp("2026-04-20 10:00:00"),
                    "data_resolucao": pd.NaT,
                    "atribuido": "Analista Teste",
                    "titulo": "Ticket de teste",
                    "arquivo_origem": "fonte.xlsx",
                }
            ]
        )

        result = apply_classification_audit_rules(df)

        self.assertEqual(int(result.loc[0, "flag_auditoria_classificacao"]), 1)
        self.assertEqual(int(result.loc[0, "flag_arquivado_relatorio"]), 1)
        self.assertEqual(result.loc[0, "status_auditoria_classificacao"], "PENDENTE_VALIDACAO")

    def test_expected_group_with_routing_prefix_is_not_flagged_for_audit(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "ticket_id": 17746470,
                    "tipo_solicitacao": "Canais de Atrito::CEDOC",
                    "grupo_tickets": "[routing]Oceano Canais de Atrito N2",
                    "flag_arquivado_relatorio": 0,
                    "data_criacao": pd.Timestamp("2026-05-06 10:00:00"),
                    "data_resolucao": pd.NaT,
                    "atribuido": "Analista Teste",
                    "titulo": "Ticket de teste",
                    "arquivo_origem": "fonte.xlsx",
                }
            ]
        )

        result = apply_classification_audit_rules(df)

        self.assertEqual(int(result.loc[0, "flag_auditoria_classificacao"]), 0)
        self.assertEqual(int(result.loc[0, "flag_arquivado_relatorio"]), 0)

    def test_private_internal_group_is_archived(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "ticket_id": 40851024,
                    "grupo_tickets": "[internal]Ticket Privado Oceano Canais de atrito",
                    "tipo_manifestacao": "Manifestacao",
                    "classificacao_notificacoes": None,
                }
            ]
        )

        archive_flag = build_archive_flag(df)

        self.assertEqual(int(archive_flag.iloc[0]), 1)

    def test_manual_archive_ticket_id_is_archived(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "ticket_id": 16153239,
                    "grupo_tickets": "Grupo comum",
                    "tipo_manifestacao": None,
                    "classificacao_notificacoes": None,
                }
            ]
        )

        archive_flag = build_archive_flag(df)

        self.assertEqual(int(archive_flag.iloc[0]), 1)

    def test_removed_ticket_is_filtered_out(self) -> None:
        df = pd.DataFrame(
            [
                {"ticket_id": 18948864, "titulo": "fora do escopo"},
                {"ticket_id": 99999999, "titulo": "permanece"},
            ]
        )

        result = filter_removed_tickets(df, context="unit_test")

        self.assertEqual(result["ticket_id"].tolist(), [99999999])

    def test_stale_pending_audit_records_are_purged_against_current_ticket_flag(self) -> None:
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(
                """
                CREATE TABLE tickets (
                    ticket_id INTEGER PRIMARY KEY,
                    flag_auditoria_classificacao INTEGER
                );
                CREATE TABLE tickets_auditoria_classificacao (
                    ticket_id INTEGER PRIMARY KEY,
                    status_auditoria TEXT
                );
                CREATE TABLE tickets_auditoria_operacional (
                    auditoria_operacional_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    status_validacao TEXT
                );
                INSERT INTO tickets VALUES (16153239, 0);
                INSERT INTO tickets VALUES (33190240, 1);
                INSERT INTO tickets_auditoria_classificacao VALUES (16153239, 'PENDENTE_VALIDACAO');
                INSERT INTO tickets_auditoria_classificacao VALUES (33190240, 'PENDENTE_VALIDACAO');
                INSERT INTO tickets_auditoria_classificacao VALUES (99999999, 'VALIDADO');
                INSERT INTO tickets_auditoria_operacional (ticket_id, status_validacao)
                    VALUES (16153239, 'PENDENTE_VALIDACAO');
                INSERT INTO tickets_auditoria_operacional (ticket_id, status_validacao)
                    VALUES (33190240, 'PENDENTE_VALIDACAO');
                """
            )

            purge_stale_audit_records(conn)

            classification_rows = conn.execute(
                "SELECT ticket_id, status_auditoria FROM tickets_auditoria_classificacao ORDER BY ticket_id"
            ).fetchall()
            operational_rows = conn.execute(
                "SELECT ticket_id, status_validacao FROM tickets_auditoria_operacional ORDER BY ticket_id"
            ).fetchall()

            self.assertEqual(classification_rows, [(33190240, "PENDENTE_VALIDACAO"), (99999999, "VALIDADO")])
            self.assertEqual(operational_rows, [(33190240, "PENDENTE_VALIDACAO")])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
