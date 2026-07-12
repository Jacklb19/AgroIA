"""
build_features.py — Feature Store para AgroIA.

Granularidad: una fila por (id_municipio, id_cultivo, anio).
Integra producción + clima (con lags) + ENSO + precios SIPSA + insumos +
aptitud SIPRA + agregados históricos del municipio.
"""
import logging

import numpy as np
import pandas as pd

from load.db import get_engine

logger = logging.getLogger(__name__)


_QUERY = """
WITH clima_anual AS (
    SELECT
        fc.id_municipio,
        dt.anio,
        SUM(fc.precipitacion_mm)                                              AS lluvia_acumulada_anual,
        AVG(fc.temperatura_media_c)                                           AS temp_promedio_anual,
        MAX(fc.temperatura_max_c)                                             AS temp_maxima_anual,
        MIN(fc.temperatura_min_c)                                             AS temp_minima_anual,
        AVG(fc.humedad_relativa_pct)                                          AS humedad_promedio_anual,
        AVG(fc.brillo_solar_horas_dia)                                        AS brillo_solar_promedio,
        STDDEV(fc.precipitacion_mm)                                           AS lluvia_std_mensual,
        STDDEV(fc.temperatura_media_c)                                        AS temp_std_mensual,
        SUM(CASE WHEN dt.mes BETWEEN 1  AND 6  THEN fc.precipitacion_mm END)  AS lluvia_semestre_a,
        SUM(CASE WHEN dt.mes BETWEEN 7  AND 12 THEN fc.precipitacion_mm END)  AS lluvia_semestre_b,
        AVG(CASE WHEN dt.mes BETWEEN 1  AND 6  THEN fc.temperatura_media_c END) AS temp_semestre_a,
        AVG(CASE WHEN dt.mes BETWEEN 7  AND 12 THEN fc.temperatura_media_c END) AS temp_semestre_b
    FROM fact_clima_mensual fc
    JOIN dim_tiempo dt ON dt.id_tiempo = fc.id_tiempo
    GROUP BY fc.id_municipio, dt.anio
),
enso_anual AS (
    SELECT
        dt.anio,
        AVG(fa.indice_spi)                       AS spi_promedio,
        AVG(fa.anomalia_precipitacion_pct)       AS anomalia_lluvia_pct,
        AVG(fa.probabilidad_deficit_hidrico)     AS prob_deficit,
        AVG(fa.probabilidad_exceso_hidrico)      AS prob_exceso,
        BOOL_OR(dt.es_anio_nino)                 AS es_anio_nino
    FROM fact_alerta_enso fa
    JOIN dim_tiempo dt ON dt.id_tiempo = fa.id_tiempo
    GROUP BY dt.anio
),
precios_anual AS (
    SELECT
        dt.anio,
        fp.id_cultivo,
        AVG(fp.precio_promedio_cop_kg) AS precio_promedio_cop_kg,
        STDDEV(fp.precio_promedio_cop_kg) AS precio_std_cop_kg,
        AVG(fp.volumen_abastecimiento_ton) AS volumen_promedio_ton
    FROM fact_precios_mayoristas fp
    JOIN dim_tiempo dt ON dt.id_tiempo = fp.id_tiempo
    GROUP BY dt.anio, fp.id_cultivo
),
insumos_anual AS (
    SELECT
        dt.anio,
        AVG(fpi.precio_cop_unidad) AS precio_insumo_promedio,
        STDDEV(fpi.precio_cop_unidad) AS precio_insumo_std
    FROM fact_precios_insumos fpi
    JOIN dim_tiempo dt ON dt.id_tiempo = fpi.id_tiempo
    GROUP BY dt.anio
),
aptitud AS (
    SELECT
        id_municipio,
        id_cultivo,
        clase_aptitud
    FROM fact_aptitud_suelo
),
produccion AS (
    SELECT
        fp.id_municipio,
        fp.id_cultivo,
        dt.anio,
        fp.id_tiempo,
        fp.area_sembrada_ha,
        fp.area_cosechada_ha,
        fp.produccion_total_ton,
        fp.rendimiento_t_ha
    FROM fact_produccion_agricola fp
    JOIN dim_tiempo dt ON dt.id_tiempo = fp.id_tiempo
)
SELECT
    p.id_municipio,
    p.id_cultivo,
    p.anio,
    p.id_tiempo,
    p.area_sembrada_ha,
    p.area_cosechada_ha,
    p.produccion_total_ton,
    p.rendimiento_t_ha,
    -- clima año actual
    c.lluvia_acumulada_anual,
    c.temp_promedio_anual,
    c.temp_maxima_anual,
    c.temp_minima_anual,
    c.humedad_promedio_anual,
    c.brillo_solar_promedio,
    c.lluvia_std_mensual,
    c.temp_std_mensual,
    c.lluvia_semestre_a,
    c.lluvia_semestre_b,
    c.temp_semestre_a,
    c.temp_semestre_b,
    -- ENSO
    e.spi_promedio,
    e.anomalia_lluvia_pct,
    e.prob_deficit,
    e.prob_exceso,
    e.es_anio_nino,
    -- precios mercado
    pr.precio_promedio_cop_kg,
    pr.precio_std_cop_kg,
    pr.volumen_promedio_ton,
    -- insumos
    ins.precio_insumo_promedio,
    ins.precio_insumo_std,
    -- aptitud
    ap.clase_aptitud,
    -- contexto municipio
    m.id_departamento,
    m.id_region,
    m.latitud_centroide,
    m.longitud_centroide
FROM produccion p
JOIN dim_municipio m       ON m.id_municipio = p.id_municipio
LEFT JOIN clima_anual c    ON c.id_municipio = p.id_municipio AND c.anio = p.anio
LEFT JOIN enso_anual  e    ON e.anio = p.anio
LEFT JOIN precios_anual pr ON pr.anio = p.anio AND pr.id_cultivo = p.id_cultivo
LEFT JOIN insumos_anual ins ON ins.anio = p.anio
LEFT JOIN aptitud ap       ON ap.id_municipio = p.id_municipio AND ap.id_cultivo = p.id_cultivo
"""


_LAG_COLS = [
    "lluvia_acumulada_anual",
    "temp_promedio_anual",
    "spi_promedio",
    "precio_promedio_cop_kg",
]
_HIST_COLS_MUNI = ["rendimiento_t_ha", "produccion_total_ton"]
_APTITUD_MAP = {"alta": 3, "moderada": 2, "marginal": 1, "no_apta": 0}


def _add_lags(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega lags 1 y 3 años para clima/ENSO/precios."""
    df = df.sort_values(["id_municipio", "id_cultivo", "anio"]).copy()
    grp = df.groupby(["id_municipio", "id_cultivo"], group_keys=False)
    for col in _LAG_COLS:
        if col in df.columns:
            df[f"{col}_lag1"] = grp[col].shift(1)
            df[f"{col}_lag3"] = grp[col].shift(3)
    return df


def _add_municipio_history(df: pd.DataFrame) -> pd.DataFrame:
    """Promedio histórico (excluye año actual) por municipio×cultivo."""
    df = df.sort_values(["id_municipio", "id_cultivo", "anio"]).copy()
    grp = df.groupby(["id_municipio", "id_cultivo"], group_keys=False)
    for col in _HIST_COLS_MUNI:
        if col in df.columns:
            cum_sum   = grp[col].cumsum()  - df[col]
            cum_count = grp[col].cumcount()
            df[f"{col}_hist_avg"] = np.where(cum_count > 0, cum_sum / cum_count.replace(0, np.nan), np.nan)
    return df


def _encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["id_municipio_enc"]    = df["id_municipio"].astype(str).astype("category").cat.codes
    df["id_departamento_enc"] = df["id_departamento"].astype(str).astype("category").cat.codes
    df["id_region"]           = pd.to_numeric(df["id_region"], errors="coerce").fillna(-1).astype(int)
    df["clase_aptitud_score"] = df["clase_aptitud"].map(_APTITUD_MAP).fillna(-1).astype(int)
    df["es_anio_nino_int"]    = df["es_anio_nino"].fillna(False).astype(int)
    return df


def build_ml_features(engine=None) -> pd.DataFrame:
    """
    Feature Store enriquecido. Una fila = una cosecha (muni × cultivo × año).
    """
    logger.info("Construyendo Feature Store enriquecido...")
    if engine is None:
        engine = get_engine()

    try:
        df = pd.read_sql(_QUERY, engine)
    except Exception as e:
        logger.error("Error construyendo Feature Store: %s", e)
        return pd.DataFrame()

    if df.empty:
        logger.warning("Feature Store vacío — verifica datos en la BD.")
        return df

    df = _add_lags(df)
    df = _add_municipio_history(df)
    df = _encode_categoricals(df)

    logger.info(
        "Feature Store: %s filas, %s columnas (%s features candidatas)",
        len(df),
        df.shape[1],
        df.shape[1] - 4,
    )
    return df
