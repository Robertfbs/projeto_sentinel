import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class RawSourceConfig:
    prefixes: tuple[str, ...]
    allowed_extensions: tuple[str, ...] = (".xlsx", ".xls")


RAW_SOURCE_CONFIGS: dict[str, RawSourceConfig] = {
    "zendesk_geral": RawSourceConfig(prefixes=("ANALYTICS_BASE_TICKETS_GERAL",)),
    "zendesk_n1": RawSourceConfig(prefixes=("ANALYTICS_BASE_TICKETS_N1",)),
    "audiencias": RawSourceConfig(prefixes=("PRE_CONTENCIOSO_AUDIENCIAS",)),
    "gss": RawSourceConfig(prefixes=("Base_GSS",)),
}


def find_source_files(raw_dir: Path, source_name: str) -> list[Path]:
    config = RAW_SOURCE_CONFIGS[source_name]
    matching_files = [
        path
        for path in raw_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in config.allowed_extensions
        and not path.name.startswith("~$")
        and any(path.name.upper().startswith(prefix.upper()) for prefix in config.prefixes)
    ]
    return sorted(set(matching_files), key=lambda path: path.stat().st_mtime)


def read_source_file(path: Path) -> pd.DataFrame:
    try:
        return pd.read_excel(path)
    except PermissionError as exc:
        raise RuntimeError(
            f"Arquivo Excel bloqueado ou sem permissao de leitura: {path.name}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Falha ao ler arquivo Excel da carga: {path.name}"
        ) from exc


def extract_source_reports(raw_dir: Path, source_name: str) -> pd.DataFrame:
    files = find_source_files(raw_dir, source_name)
    if not files:
        logging.warning("Nenhum arquivo encontrado para a fonte '%s'.", source_name)
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for path in files:
        frame = read_source_file(path)
        frame["arquivo_origem"] = path.name
        frame["arquivo_mtime"] = path.stat().st_mtime
        frame["fonte_raw"] = source_name
        frames.append(frame)

    result = pd.concat(frames, ignore_index=True)
    logging.info(
        "Extracao concluida para %s: %s linhas lidas em %s arquivo(s).",
        source_name.upper(),
        len(result),
        len(files),
    )
    return result
