"""
extract_worldbank.py — World Bank Open Data API (gratis, sin key).

Indicadores macro-agrícolas oficiales para Colombia. Sirven de baseline
para comparar producción local con tendencias nacionales.

Endpoint: https://api.worldbank.org/v2/country/COL/indicator/{id}?format=json
Documentación: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""
import logging

import pandas as pd

from config.settings import DATA_RAW
from utils.extraction_quality import fetch_json, standardize

logger = logging.getLogger(__name__)

WB_BASE  = "https://api.worldbank.org/v2/country/COL/indicator"
REPORTS_DIR = DATA_RAW.parent / "quality_reports"

INDICADORES = {
    "AG.PRD.CROP.XD":   "indice_produccion_cultivos",       # Crop production index
    "AG.PRD.LVSK.XD":   "indice_produccion_pecuario",       # Livestock production index
    "AG.YLD.CREL.KG":   "rendimiento_cereales_kg_ha",       # Cereal yield kg/ha
    "AG.LND.AGRI.K2":   "tierra_agricola_km2",              # Agricultural land km²
    "AG.LND.ARBL.HA":   "tierra_arable_ha",                 # Arable land ha
    "AG.LND.IRIG.AG.ZS": "irrigacion_pct_tierra_agricola",  # % de tierra agrícola con riego
    "NV.AGR.TOTL.ZS":   "valor_agregado_agricola_pct_pib",  # Valor agregado agro % del PIB
}


def _fetch_indicator(code: str) -> pd.DataFrame:
    """Descarga un indicador del Banco Mundial (todos los años disponibles)."""
    url    = f"{WB_BASE}/{code}"
    js     = fetch_json(url, params={"format": "json", "per_page": 200}, timeout=45)
    if not isinstance(js, list) or len(js) < 2 or not js[1]:
        return pd.DataFrame()
    rows = [
        {
            "indicator_id":   r.get("indicator", {}).get("id"),
            "indicator_name": r.get("indicator", {}).get("value"),
            "anio":           int(r["date"]) if r.get("date", "").isdigit() else None,
            "valor":          r.get("value"),
        }
        for r in js[1]
    ]
    return pd.DataFrame(rows)


def extract_worldbank() -> pd.DataFrame:
    """Descarga todos los indicadores configurados y los une en formato largo."""
    logger.info("World Bank: %s indicadores para Colombia", len(INDICADORES))
    frames = []
    for code, alias in INDICADORES.items():
        try:
            df = _fetch_indicator(code)
            if df.empty:
                logger.warning("WB %s sin datos", code)
                continue
            df["alias_local"] = alias
            frames.append(df)
            logger.info("  %s: %s años", code, len(df))
        except Exception as e:
            logger.error("WB %s falló: %s", code, e)

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames, ignore_index=True)
    full, _ = standardize(
        full,
        fuente         = "WORLD_BANK",
        source_uri     = WB_BASE,
        required       = ["indicator_id", "anio", "valor"],
        numeric        = ["anio", "valor"],
        critical_nulls = ["indicator_id", "anio"],
        key_cols       = ["indicator_id", "anio"],
        range_filters  = {"anio": (1960, 2030)},
        reports_dir    = REPORTS_DIR,
    )
    out_path = DATA_RAW / "worldbank" / "indicadores_colombia.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    full.to_parquet(out_path, index=False)
    logger.info("World Bank: %s registros → %s", len(full), out_path)
    return full


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    extract_worldbank()
