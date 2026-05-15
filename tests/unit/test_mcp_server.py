from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing

from mcp_server.server import (
    analytics_channel_volume,
    analytics_weekly_productivity,
    etl_last_run,
    get_gold_db_path,
    gold_describe_table,
    gold_list_tables,
    integrations_outlook_prepare_email,
    integrations_planner_prepare_task,
    integrations_teams_prepare_message,
    open_gold_read_only,
    powerbi_export_semantic_model,
    prompt_relatorio_executivo_corporativo,
    prompt_resumo_executivo_produtividade,
    reports_generate_weekly_productivity,
    resource_gold_schema,
    resource_outputs_catalog,
    resource_project_prd,
    resource_rules_catalog,
    sentinel_health,
    tickets_processed,
)


class SentinelMcpServerTests(unittest.TestCase):
    def test_health_finds_official_gold(self) -> None:
        result = sentinel_health()

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["gold_database_found"])
        self.assertTrue(result["gold_database_path"].endswith("03_database\\pre_contencioso.db"))
        self.assertEqual(result["mode"], "read_only")

    def test_gold_list_tables_includes_core_objects(self) -> None:
        result = gold_list_tables()

        self.assertIn("tickets", result["tables"])
        self.assertIn("etl_runs", result["tables"])
        self.assertIn("fato_tickets", result["views"])

    def test_gold_describe_table_returns_schema(self) -> None:
        result = gold_describe_table("tickets", include_row_count=False)

        column_names = {column["name"] for column in result["columns"]}
        self.assertEqual(result["object"]["name"], "tickets")
        self.assertEqual(result["object"]["type"], "table")
        self.assertIn("ticket_id", column_names)
        self.assertIn("data_resolucao", column_names)
        self.assertIsNone(result["row_count"])

    def test_gold_describe_table_rejects_invalid_identifier(self) -> None:
        with self.assertRaises(ValueError):
            gold_describe_table("tickets; DROP TABLE tickets", include_row_count=False)

    def test_gold_connection_is_read_only(self) -> None:
        with closing(open_gold_read_only(get_gold_db_path())) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE mcp_read_only_probe (id INTEGER)")

    def test_weekly_productivity_returns_expected_shape(self) -> None:
        result = analytics_weekly_productivity(reference_date="2026-05-13")

        self.assertEqual(result["period"], {"start_date": "2026-05-04", "end_date": "2026-05-08"})
        self.assertIn("total", result)
        self.assertIn("by_collaborator", result)
        self.assertIn("by_channel", result)

    def test_channel_volume_returns_aggregate(self) -> None:
        result = analytics_channel_volume(start_date="2026-05-01", end_date="2026-05-08")

        self.assertEqual(result["period"], {"start_date": "2026-05-01", "end_date": "2026-05-08"})
        self.assertIn("total", result)
        self.assertIn("by_channel", result)

    def test_tickets_processed_masks_pii(self) -> None:
        result = tickets_processed(start_date="2026-05-01", end_date="2026-05-08", limit=5)

        self.assertLessEqual(result["returned"], 5)
        for ticket in result["tickets"]:
            self.assertNotIn("cpf_cliente", ticket)
            self.assertNotIn("telefone", ticket)
            self.assertNotIn("email_solicitante", ticket)
            self.assertIn("canal_normalizado", ticket)

    def test_last_etl_run_returns_payload(self) -> None:
        result = etl_last_run(log_limit=5)

        self.assertIn("latest_run", result)
        self.assertIn("logs", result)
        self.assertLessEqual(len(result["logs"]), 5)

    def test_generation_tools_require_confirmation(self) -> None:
        with self.assertRaises(PermissionError):
            reports_generate_weekly_productivity(confirmacao=False)
        with self.assertRaises(PermissionError):
            powerbi_export_semantic_model(confirmacao=False)

    def test_resources_return_content(self) -> None:
        self.assertIn("Projeto Sentinel", resource_project_prd())
        self.assertIn('"objects"', resource_gold_schema())
        self.assertIn('"rules"', resource_rules_catalog())
        self.assertIn('"outputs"', resource_outputs_catalog())

    def test_prompts_return_templates(self) -> None:
        self.assertIn(
            "resumo executivo",
            prompt_resumo_executivo_produtividade("2026-05-04 a 2026-05-08", "{}").lower(),
        )
        self.assertIn("Gold", prompt_relatorio_executivo_corporativo("Diretoria", "{}"))

    def test_microsoft_tools_are_draft_only(self) -> None:
        teams = integrations_teams_prepare_message("Canal CX", "Resumo semanal", "Conteudo")
        email = integrations_outlook_prepare_email("destino@empresa.com", "Assunto", "Corpo")
        task = integrations_planner_prepare_task("Validar relatorio", "Conferir output", due_date="2026-05-20")

        self.assertFalse(teams["sent"])
        self.assertFalse(email["sent"])
        self.assertFalse(task["created"])
        self.assertEqual(teams["mode"], "draft_only")


if __name__ == "__main__":
    unittest.main()
