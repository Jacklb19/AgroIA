"""
extract_ant.py — Tierras adjudicadas y formalización ANT (Agencia Nacional de Tierras).
Fuente: datos.gov.co · Hoja de Ruta Sectorial Agropecuaria.

NOTA importante: el resource ID de Socrata para "Tierras Formalizadas ANT"
ha rotado en el portal datos.gov.co. Antes de ejecutar este script, valida
manualmente la URI buscando "Tierras formalizadas" o "ANT adjudicación" en
https://www.datos.gov.co/ y actualiza ANT_URL con el resource ID actual.

Si la URL no es accesible, el extractor degrada con gracia: no lanza
excepción, registra warning y deja el catálogo marcando 0 filas.
"""
import logging

import pandas as pd

from config.settings import DATA_RAW, SOURCES
from utils.extraction_quality import paginate_socrata, standardize, FetchError

logger = logging.getLogger(__name__)

# Placeholder verificable: cambiar por el resource ID actual.
# Se intenta con la URL configurada; si falla, el script lo reporta sin romper el pipeline.
ANT_URL    = SOURCES.get("ant_tierras", "https://www.datos.gov.co/resource/ckwx-9gr5.json")
REPORTS_DIR = DATA_RAW.parent / "quality_reports"


def extract_ant() -> pd.DataFrame:
    logger.info("ANT (tierras formalizadas): %s", ANT_URL)
    try:
        rows = paginate_socrata(ANT_URL, page_size=50_000, timeout=60)
    except FetchError as e:
        logger.warning("ANT no disponible (%s). Verifica el resource ID en datos.gov.co.", e)
        return pd.DataFrame()
    if not rows:
        logger.warning("ANT: 0 filas devueltas. Verifica el resource ID.")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df, _ = standardize(
        df,
        fuente         = "ANT_TIERRAS_FORMALIZADAS",
        source_uri     = ANT_URL,
        required       = list(df.columns)[:1],   # mínimo 1 columna
        critical_nulls = list(df.columns)[:1],
        reports_dir    = REPORTS_DIR,
    )
    out = DATA_RAW / "ant" / "ant_tierras_raw.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    logger.info("ANT: %s registros → %s", len(df), out)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    extract_ant()
