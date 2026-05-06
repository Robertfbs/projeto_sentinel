from __future__ import annotations

import unittest

import pandas as pd

from main_etl import build_ticket_relationships


class TicketLinkingTests(unittest.TestCase):
    def test_build_ticket_relationships_matches_same_matricula_and_subject(self) -> None:
        solicitacoes = pd.DataFrame(
            [
                {
                    "ticket_id": 1001,
                    "matricula": "4001",
                    "protocolo_referencia": None,
                    "assunto_normalizado": "FALTA DE ENERGIA",
                    "data_criacao": pd.Timestamp("2026-04-20 10:00:00"),
                }
            ]
        )
        notificacoes = pd.DataFrame(
            [
                {
                    "ticket_id": 2001,
                    "matricula": "4001",
                    "protocolo_referencia": None,
                    "assunto_normalizado": "FALTA DE ENERGIA",
                    "data_criacao": pd.Timestamp("2026-04-19 12:00:00"),
                }
            ]
        )
        manual_links = pd.DataFrame(
            columns=["ticket_solicitacao_id", "ticket_notificacao_id", "justificativa", "usuario", "atualizado_em"]
        )

        relationships = build_ticket_relationships(solicitacoes, notificacoes, manual_links)

        self.assertEqual(len(relationships), 1)
        self.assertEqual(int(relationships.loc[0, "ticket_notificacao_id"]), 2001)
        self.assertEqual(relationships.loc[0, "status_vinculo"], "VINCULADO")


if __name__ == "__main__":
    unittest.main()
