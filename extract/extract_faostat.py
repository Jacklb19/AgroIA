"""
extract_faostat.py — FAOSTAT API (FAO · ONU). Datos oficiales de producción
agrícola para Colombia, gratuitos y sin key.

Endpoint base: https://fenixservices.fao.org/faostat/api/v1/en
Documentación: https://www.fao.org/faostat/en/#data
Dataset usado: QCL (Crops and livestock products).
"""
import logging

import pandas as pd

from config.settings import DATA_RAW
from utils.extraction_quality import fetch_json, standardize, FetchError

logger = logging.getLogger(__name__)

FAOSTAT_BASE = "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL"
REPORTS_DIR  = DATA_RAW.parent / "quality_reports"

# 48 = Colombia (FAOSTAT M49 sin prefijo)
COUNTRY_CODE = "48"
# Elementos: 5510 producción (t), 5312 área cosechada (ha), 5419 rendimiento (kg/ha)
ELEMENT_CODES = "5510,5312,5419"


def extract_faostat(anio_inicio: int = 2010, anio_fin: int = 2024) -> pd.DataFrame:
    """Producción, área y rendimiento por cultivo y año en Colombia."""
    anios = ",".join(str(y) for y in range(anio_inicio, anio_fin + 1))
    params = {
        "area":     COUNTRY_CODE,
        "year":     anios,
        "element":  ELEMENT_CODES,
        "show_codes": "true",
        "show_unit":  "true",
        "show_flags": "true",
        "output_type": "json",
        "page_size":  "5000",
    }
    try:
        js = fetch_json(FAOSTAT_BASE, params=params, timeout=90)
    except FetchError as e:
        logger.warning("FAOSTAT API no disponible (%s). Pipeline continúa sin esta fuente.", e)
        return pd.DataFrame()
    data = js.get("data", []) if isinstance(js, dict) else []
    if not data:
        logger.warning("FAOSTAT sin datos para los años %s-%s", anio_inicio, anio_fin)
        return pd.DataFrame()

    df = pd.DataFrame(data)
    rename = {
        "Area":         "pais",
        "Item":         "cultivo",
        "Item Code":    "item_code",
        "Element":      "elemento",
        "Element Code": "element_code",
        "Year":         "anio",
        "Unit":         "unidad",
        "Value":        "valor",
        "Flag":         "flag",
    }
    df = df.rename(columns=rename)

    df, _ = standardize(
        df,
        fuente         = "FAOSTAT_QCL",
        source_uri     = FAOSTAT_BASE,
        required       = ["cultivo", "elemento", "anio", "valor"],
        numeric        = ["anio", "valor"],
        string_strip   = ["cultivo", "elemento", "unidad"],
        critical_nulls = ["cultivo", "elemento", "anio", "valor"],
        key_cols       = ["cultivo", "element_code", "anio"],
        range_filters  = {"anio": (1960, 2030), "valor": (0, 1e12)},
        reports_dir    = REPORTS_DIR,
    )
    out_path = DATA_RAW / "faostat" / "qcl_colombia.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    logger.info("FAOSTAT: %s registros → %s", len(df), out_path)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    extract_faostat()
