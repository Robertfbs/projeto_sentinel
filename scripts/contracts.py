from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from gss_matching import GSS_COLUMN_RENAME_CANDIDATES
from schema_validation import SchemaValidationIssue, find_missing_columns, has_any_non_empty_value


class ContractValidationError(Exception):
    def __init__(self, source_name: str, issues: list[SchemaValidationIssue]):
        self.source_name = source_name
        self.issues = issues
        super().__init__(f"Falha de contrato na fonte '{source_name}'.")


@dataclass(frozen=True)
class SourceContract:
    source_name: str
    required_columns: list[str]
    critical_presence_groups: list[list[str]]
    column_aliases: dict[str, list[str]] | None = None


def _build_column_aliases(rename_candidates: dict[str, str]) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for alias_name, canonical_name in rename_candidates.items():
        aliases.setdefault(canonical_name, []).append(alias_name)
    return aliases


GSS_CONTRACT_COLUMN_ALIASES = _build_column_aliases(GSS_COLUMN_RENAME_CANDIDATES)


SOURCE_CONTRACTS: dict[str, SourceContract] = {
    "zendesk_geral": SourceContract(
        source_name="zendesk_geral",
        required_columns=[
            "id_do_ticket",
            "criacao_do_ticket_carimbo_de_data_hora",
            "status_do_ticket",
            "formulario_de_ticket",
        ],
        critical_presence_groups=[
            ["id_do_ticket"],
            ["formulario_de_ticket"],
            ["status_do_ticket"],
            ["assunto_do_ticket", "assuntos_do_ticket"],
            ["tipos_de_solicitacoes", "classificacao_solicitacoes", "canais_de_atrito"],
        ],
    ),
    "zendesk_n1": SourceContract(
        source_name="zendesk_n1",
        required_columns=[
            "id_do_ticket",
            "criacao_do_ticket_carimbo_de_data_hora",
            "status_do_ticket",
        ],
        critical_presence_groups=[
            ["id_do_ticket"],
            ["criacao_do_ticket_carimbo_de_data_hora"],
        ],
    ),
    "audiencias": SourceContract(
        source_name="audiencias",
        required_columns=[],
        critical_presence_groups=[
            ["id_do_ticket", "ticket_relacionado_id"],
            ["data_da_audiencia_carimbo_de_data_hora", "data_de_reagendamento_carimbo_de_data_hora"],
        ],
    ),
    "gss": SourceContract(
        source_name="gss",
        required_columns=[
            "matricula",
            "numero_os",
            "data_emissao",
            "servico_executado",
        ],
        critical_presence_groups=[
            ["matricula"],
            ["numero_os"],
            ["data_emissao", "data_execucao"],
            ["servico_executado"],
        ],
        column_aliases=GSS_CONTRACT_COLUMN_ALIASES,
    ),
}


class DataContractValidator:
    def validate_source(self, source_name: str, df: pd.DataFrame) -> list[SchemaValidationIssue]:
        contract = SOURCE_CONTRACTS.get(source_name)
        if contract is None or df.empty:
            return []

        issues: list[SchemaValidationIssue] = []
        missing_columns = find_missing_columns(
            df,
            contract.required_columns,
            contract.column_aliases,
        )
        if missing_columns:
            issues.append(
                SchemaValidationIssue(
                    source_name=source_name,
                    severity="ERROR",
                    code="MISSING_REQUIRED_COLUMNS",
                    message="Colunas obrigatorias ausentes na fonte.",
                    details={"missing_columns": missing_columns},
                )
            )

        for group in contract.critical_presence_groups:
            if not has_any_non_empty_value(df, group, contract.column_aliases):
                issues.append(
                    SchemaValidationIssue(
                        source_name=source_name,
                        severity="ERROR",
                        code="MISSING_CRITICAL_DATA",
                        message="Nao ha dados preenchidos para um grupo critico do contrato.",
                        details={"candidate_columns": group},
                    )
                )

        return issues

    def validate_or_raise(self, source_name: str, df: pd.DataFrame) -> list[SchemaValidationIssue]:
        issues = self.validate_source(source_name, df)
        blocking_issues = [issue for issue in issues if issue.severity == "ERROR"]
        if blocking_issues:
            raise ContractValidationError(source_name, blocking_issues)
        return issues
