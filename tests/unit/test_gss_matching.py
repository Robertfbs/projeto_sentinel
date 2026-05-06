from __future__ import annotations

import unittest

import pandas as pd

from gss_matching import enrich_tickets_with_gss, enrich_with_gss


class GssMatchingTests(unittest.TestCase):
    def test_enrich_with_gss_only_fills_missing_fields(self) -> None:
        tickets = pd.DataFrame(
            [
                {
                    "ticket_id": 1,
                    "matricula": "4001",
                    "bairro": None,
                    "municipio": "Rio",
                }
            ]
        )
        gss = pd.DataFrame(
            [
                {
                    "gss_os_id": "2026-1",
                    "matricula": "4001",
                    "bairro": "Centro",
                    "municipio": "Niteroi",
                    "nome_logradouro": "Rua A",
                    "endereco_requerente": "Rua A, 10",
                    "numero_porta": "10",
                    "complemento": None,
                    "telefone": "9999-9999",
                    "nome_cliente": "Cliente Teste",
                    "nome_requerente": "Requerente Teste",
                    "data_emissao": pd.Timestamp("2026-04-01"),
                    "data_execucao": pd.NaT,
                    "data_agendamento": pd.NaT,
                }
            ]
        )

        result = enrich_with_gss(tickets, gss)

        self.assertEqual(result.loc[0, "bairro"], "Centro")
        self.assertEqual(result.loc[0, "municipio"], "Rio")

    def test_enrich_tickets_with_gss_preserves_original_os(self) -> None:
        tickets = pd.DataFrame(
            [
                {
                    "ticket_id": 1,
                    "matricula": "4001",
                    "numero_os": "12345",
                }
            ]
        )
        gss = pd.DataFrame(
            [
                {
                    "gss_os_id": "2026-12345",
                    "matricula": "4001",
                    "numero_os": "12345",
                    "data_emissao": pd.Timestamp("2026-04-01"),
                }
            ]
        )

        result = enrich_tickets_with_gss(tickets, gss)

        self.assertEqual(result.loc[0, "numero_os_original"], "12345")
        self.assertEqual(result.loc[0, "origem_numero_os"], "ZENDESK")
        self.assertEqual(result.loc[0, "status_vinculo_os"], "MATCH_EXATO_ZENDESK_GSS")


if __name__ == "__main__":
    unittest.main()
