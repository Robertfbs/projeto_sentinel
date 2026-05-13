from __future__ import annotations

import unittest

import pandas as pd

from contracts import ContractValidationError, DataContractValidator


class ContractValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = DataContractValidator()

    def test_valid_zendesk_geral_contract_passes(self) -> None:
        df = pd.DataFrame(
            {
                "ID do ticket": [1],
                "Criação do ticket - Carimbo de data/hora": ["2026-04-20 10:00:00"],
                "Status do ticket": ["Aberto"],
                "Formulário de ticket": ["SOLICITAÇÃO"],
                "Assunto do ticket": ["Teste"],
                "Tipos de Solicitações": ["PROCON"],
            }
        )

        issues = self.validator.validate_source("zendesk_geral", df)
        self.assertEqual(issues, [])

    def test_missing_ticket_identifier_raises_blocking_error(self) -> None:
        df = pd.DataFrame(
            {
                "Status do ticket": ["Aberto"],
                "Formulário de ticket": ["SOLICITAÇÃO"],
            }
        )

        with self.assertRaises(ContractValidationError):
            self.validator.validate_or_raise("zendesk_geral", df)


    def test_gss_contract_accepts_supported_raw_alias_columns(self) -> None:
        df = pd.DataFrame(
            {
                "Matricula": ["4001001"],
                "No. da O.S.": ["12345"],
                "Dt. Emissao": ["2026-05-10"],
                "Servico Executado": ["RELIGACAO"],
            }
        )

        issues = self.validator.validate_source("gss", df)
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
