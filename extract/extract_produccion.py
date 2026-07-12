"""
extract_produccion.py — Producción Agrícola Municipal A04/A05 (MinAgricultura).

Fuente oficial: datos.gov.co · Socrata `uejq-wxrr`.
Hoja de Ruta Sectorial Agropecuaria · dataset estratégico.

Refactor 2026-05: usa `utils/extraction_quality` para garantizar:
- Reintentos exponenciales contra Socrata
- Schema validado (cultivo, municipio, año, área, rendimiento)
- Sin filas con NULL en columnas críticas
- Tipos numéricos forzados (sin perder filas válidas por errors='coerce')
- Deduplicación por (id_municipio, cultivo, año)
- Rangos sanos (años 2007-2030, áreas y rendimientos > 0)
- Reporte JSON de calidad emitido en data/quality_reports/
"""
import logging

import pandas as pd

from config.settings import DATA_RAW, SOURCES, YEAR_END, YEAR_START
from utils.extraction_quality import paginate_socrata, standardize

logger = logging.getLogger(__name__)

REPORTS_DIR = DATA_RAW.parent / "quality_reports"

# Columnas reales del dataset Socrata uejq-wxrr (acentos → underscore)
REQUIRED_COLS = [
    "a_o", "departamento", "municipio", "cultivo",
    "rea_sembrada", "rea_cosechada", "producci_n", "rendimiento",
]
NUMERIC_COLS = ["a_o", "rea_sembrada", "rea_cosechada", "producci_n", "rendimiento"]
STRING_COLS  = ["departamento", "municipio", "cultivo", "ciclo_del_cultivo",
                "grupo_cultivo", "subgrupo", "desagregaci_n_cultivo"]

# Renombre semántico para downstream (load/transform)
RENAME_MAP = {
    "rea_sembrada":      "area_sembrada_ha",
    "rea_cosechada":     "area_cosechada_ha",
    "producci_n":        "produccion_t",
    "rendimiento":       "rendimiento_t_ha",
    "a_o":               "anio",
    "ciclo_del_cultivo": "ciclo_cultivo",
    "c_digo_dane_municipio":   "codigo_dane_municipio",
    "c_digo_dane_departamento": "codigo_dane_departamento",
}


def extract_produccion() -> pd.DataFrame:
    """Descarga A04/A05 con paginación robusta y reporte de calidad."""
    url = SOURCES["produccion_datosgov"]
    extra = {"$where": f"a_o >= {YEAR_START} AND a_o <= {YEAR_END}"}
    logger.info("Descargando producción agrícola A04/A05 (años %s-%s)...", YEAR_START, YEAR_END)

    rows = paginate_socrata(url, extra_params=extra, page_size=50_000, timeout=90)
    if not rows:
        logger.warning("Producción agrícola: la API de Socrata devolvió 0 filas.")
        return pd.DataFrame()
    df = pd.DataFrame(rows)

    df, report = standardize(
        df,
        fuente         = "PRODUCCION_AGRICOLA_A04_A05",
        source_uri     = url,
        required       = REQUIRED_COLS,
        numeric        = NUMERIC_COLS,
        string_strip   = STRING_COLS,
        critical_nulls = ["a_o", "municipio", "cultivo", "rendimiento"],
        key_cols       = ["a_o", "departamento", "municipio", "cultivo", "periodo"],
        range_filters  = {
            "a_o":            (2000, 2030),
            "rea_sembrada":   (0, 1e6),
            "rea_cosechada":  (0, 1e6),
            "rendimiento":    (0, 200),
        },
        reports_dir    = REPORTS_DIR,
    )

    # Rename a nombres semánticos para que downstream use columnas claras
    df = df.rename(columns=RENAME_MAP)

    out = DATA_RAW / "produccion" / "produccion_agricola_raw.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    logger.info(
        "A04/A05: %s registros válidos · %s columnas · completitud media %.1f%% → %s",
        len(df),
        df.shape[1],
        sum(report["completitud_pct"].values()) / max(1, len(report["completitud_pct"])),
        out,
    )
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    extract_produccion()
