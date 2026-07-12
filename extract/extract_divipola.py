import requests
import pandas as pd
import logging
from config.settings import SOURCES, DATA_RAW

logger = logging.getLogger(__name__)

def extract_divipola() -> pd.DataFrame:
    """Descarga el catálogo DIVIPOLA completo desde datos.gov.co (Socrata).
    Si la red falla y ya existe el CSV en disco (del ciclo actual), lo reutiliza.
    """
    out = DATA_RAW / "divipola.csv"
    url = SOURCES["divipola"]
    rows, offset, limit = [], 0, 1000
    logger.info("Descargando DIVIPOLA...")
    try:
        while True:
            r = requests.get(url, params={"$limit": limit, "$offset": offset}, timeout=30)
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            rows.extend(batch)
            offset += limit
        df = pd.DataFrame(rows)
        df.to_csv(out, index=False)
        logger.info(f"DIVIPOLA: {len(df)} municipios -> {out}")
        return df
    except Exception as e:
        if out.exists():
            logger.warning(f"DIVIPOLA: fallo de red ({e}), usando cache local -> {out}")
            return pd.read_csv(out, dtype=str)
        raise
