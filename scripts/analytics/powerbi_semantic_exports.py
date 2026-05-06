from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "03_database" / "pre_contencioso.db"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "semantic"


SEMANTIC_QUERIES = {
    "fato_tickets": "SELECT * FROM fato_tickets",
    "fato_audiencias": "SELECT * FROM fato_audiencias",
    "dim_tempo": "SELECT * FROM dim_tempo",
    "dim_canal": "SELECT * FROM dim_canal",
    "dim_status": "SELECT * FROM dim_status",
    "dim_atribuido": "SELECT * FROM dim_atribuido",
    "dim_assunto": "SELECT * FROM dim_assunto",
}


def _read_query(conn: sqlite3.Connection, query: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(query, conn)
    except Exception:
        return pd.DataFrame()


def generate_powerbi_semantic_exports(
    db_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    active_db_path = db_path or DEFAULT_DB_PATH
    active_output_dir = output_dir or DEFAULT_OUTPUT_DIR
    active_output_dir.mkdir(parents=True, exist_ok=True)

    exported_files: dict[str, Path] = {}
    workbook_path = active_output_dir / "sentinel_powerbi_semantic_model.xlsx"

    with sqlite3.connect(active_db_path) as conn:
        semantic_frames = {
            dataset_name: _read_query(conn, query)
            for dataset_name, query in SEMANTIC_QUERIES.items()
        }

    with pd.ExcelWriter(workbook_path, engine="xlsxwriter") as writer:
        for dataset_name, frame in semantic_frames.items():
            frame.to_excel(writer, sheet_name=dataset_name[:31], index=False)

    exported_files["semantic_workbook"] = workbook_path
    return exported_files


if __name__ == "__main__":
    generate_powerbi_semantic_exports()
