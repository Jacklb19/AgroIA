"""
extract_finagro.py — Crédito agropecuario colocado (Finagro).
Fuente: datos.gov.co · Hoja de Ruta Sectorial Agropecuaria.

NOTA importante: el resource ID de Socrata para "Colocaciones Finagro" rota
periódicamente. Verifica la URL actual en https://www.datos.gov.co/
buscando "Finagro" o "crédito agropecuario" antes de ejecutar.

El extractor degrada con gracia si la API responde 404.
"""
import logging

import pandas as pd

from config.settings import DATA_RAW, SOURCES
from utils.extraction_quality import paginate_socrata, standardize, FetchError

logger = logging.getLogger(__name__)

FINAGRO_URL = SOURCES.get("finagro_credito", "https://www.datos.gov.co/resource/8e8j-2x86.json")
REPORTS_DIR = DATA_RAW.parent / "quality_reports"


def extract_finagro() -> pd.DataFrame:
    logger.info("Finagro (crédito agropecuario): %s", FINAGRO_URL)
    try:
        rows = paginate_socrata(FINAGRO_URL, page_size=50_000, timeout=60)
    except FetchError as e:
        logger.warning("Finagro no disponible (%s). Verifica el resource ID en datos.gov.co.", e)
        return pd.DataFrame()
    if not rows:
        logger.warning("Finagro: 0 filas devueltas. Verifica el resource ID.")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df, _ = standardize(
        df,
        fuente         = "FINAGRO_COLOCACIONES",
        source_uri     = FINAGRO_URL,
        required       = list(df.columns)[:1],
        critical_nulls = list(df.columns)[:1],
        reports_dir    = REPORTS_DIR,
    )
    out = DATA_RAW / "finagro" / "finagro_credito_raw.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    logger.info("Finagro: %s registros → %s", len(df), out)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    extract_finagro()
