from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

from repository import DatabaseRepository


def configure_structured_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def json_log(level: str, event: dict) -> None:
    payload = json.dumps(event, ensure_ascii=False, default=str)
    upper = (level or "").upper()
    log_fn = getattr(logging, level.lower(), logging.info) if upper in _VALID_LEVELS else logging.info
    if upper not in _VALID_LEVELS:
        logging.warning("json_log recebeu nivel desconhecido %r; usando INFO.", level)
    log_fn(payload)


@dataclass(frozen=True)
class EtlRun:
    run_id: str
    pipeline_name: str
    data_execucao: str
    status: str
    tempo_execucao: float | None = None
    qtd_registros_processados: int | None = None
    erro: str | None = None
    qtd_arquivos_lidos: int | None = None
    qtd_fontes_processadas: int | None = None
    data_inicio: str | None = None
    data_fim: str | None = None


class EtlRunTracker:
    def __init__(self, repository: DatabaseRepository):
        self.repository = repository

    def start_run(self, pipeline_name: str) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_id = uuid.uuid4().hex
        self.repository.execute(
            """
            INSERT INTO etl_runs (
                run_id, pipeline_name, data_execucao, status, data_inicio
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, pipeline_name, now, "RUNNING", now),
        )
        self.repository.commit()
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str,
        tempo_execucao: float,
        qtd_registros_processados: int,
        erro: str | None = None,
        qtd_arquivos_lidos: int | None = None,
        qtd_fontes_processadas: int | None = None,
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.repository.execute(
            """
            UPDATE etl_runs
            SET status = ?,
                tempo_execucao = ?,
                qtd_registros_processados = ?,
                erro = ?,
                qtd_arquivos_lidos = ?,
                qtd_fontes_processadas = ?,
                data_fim = ?
            WHERE run_id = ?
            """,
            (
                status,
                round(tempo_execucao, 3),
                qtd_registros_processados,
                erro,
                qtd_arquivos_lidos,
                qtd_fontes_processadas,
                now,
                run_id,
            ),
        )
        self.repository.commit()


class StructuredLogger:
    def __init__(self, repository: DatabaseRepository):
        self.repository = repository

    def log_step(
        self,
        run_id: str,
        etapa: str,
        status: str,
        volume: int | None = None,
        tempo_etapa: float | None = None,
        erro: str | None = None,
        detalhes: dict | None = None,
        nivel: str = "INFO",
    ) -> None:
        # Captura o instante uma unica vez para evitar skew entre o JSON
        # estruturado e o registro do banco.
        now = datetime.now()
        event = {
            "run_id": run_id,
            "timestamp": now.isoformat(timespec="seconds"),
            "nivel": nivel,
            "etapa": etapa,
            "status": status,
            "volume_processado": volume,
            "tempo_etapa": round(tempo_etapa, 3) if tempo_etapa is not None else None,
            "erro": erro,
            "detalhes": detalhes or {},
        }
        json_log(nivel, event)
        self.repository.execute(
            """
            INSERT INTO etl_logs (
                run_id, timestamp_log, nivel, etapa, status,
                volume_processado, tempo_etapa, erro, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                nivel,
                etapa,
                status,
                volume,
                round(tempo_etapa, 3) if tempo_etapa is not None else None,
                erro,
                json.dumps(event, ensure_ascii=False),
            ),
        )
        self.repository.commit()


class StepTimer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed(self) -> float:
        return time.perf_counter() - self._start
