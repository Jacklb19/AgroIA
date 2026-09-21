"""
build_features.py — Feature Store para AgroIA.

Granularidad: una fila por (id_municipio, id_cultivo, anio).
Integra producción + clima (con lags) + ENSO + precios SIPSA + insumos +
aptitud SIPRA + agregados históricos del municipio.
"""
import logging

import pandas as pd

from load.db import get_engine

logger = logging.getLogger(__name__)


_CLIMA_CTE = """
clima_mes AS (
    -- Un valor por municipio y mes: promedio entre estaciones (antes se SUMABAN las estaciones,
    -- lo que inflaba la lluvia de municipios con varias estaciones).
    SELECT fc.id_municipio, fc.id_tiempo,
           AVG(fc.precipitacion_mm)       AS precipitacion_mm,
           AVG(fc.temperatura_media_c)    AS temperatura_media_c,
           MAX(fc.temperatura_max_c)      AS temperatura_max_c,
           MIN(fc.temperatura_min_c)      AS temperatura_min_c,
           AVG(fc.humedad_relativa_pct)   AS humedad_relativa_pct,
           AVG(fc.brillo_solar_horas_dia) AS brillo_solar_horas_dia
    FROM fact_clima_mensual fc
    GROUP BY fc.id_municipio, fc.id_tiempo
),
clima_anual AS (
    SELECT
        cm.id_municipio,
        dt.anio,
        -- La lluvia anual solo es comparable con >= 10 meses de dato; con menos, queda NULL (no una suma parcial)
        CASE WHEN COUNT(cm.precipitacion_mm) >= 10 THEN SUM(cm.precipitacion_mm) END AS lluvia_acumulada_anual,
        AVG(cm.temperatura_media_c)                                           AS temp_promedio_anual,
        MAX(cm.temperatura_max_c)                                             AS temp_maxima_anual,
        MIN(cm.temperatura_min_c)                                             AS temp_minima_anual,
        AVG(cm.humedad_relativa_pct)                                          AS humedad_promedio_anual,
        AVG(cm.brillo_solar_horas_dia)                                        AS brillo_solar_promedio,
        STDDEV(cm.precipitacion_mm)                                           AS lluvia_std_mensual,
        STDDEV(cm.temperatura_media_c)                                        AS temp_std_mensual,
        SUM(CASE WHEN dt.mes BETWEEN 1  AND 6  THEN cm.precipitacion_mm END)  AS lluvia_semestre_a,
        SUM(CASE WHEN dt.mes BETWEEN 7  AND 12 THEN cm.precipitacion_mm END)  AS lluvia_semestre_b,
        AVG(CASE WHEN dt.mes BETWEEN 1  AND 6  THEN cm.temperatura_media_c END) AS temp_semestre_a,
        AVG(CASE WHEN dt.mes BETWEEN 7  AND 12 THEN cm.temperatura_media_c END) AS temp_semestre_b,
        COUNT(cm.precipitacion_mm)                                            AS meses_con_lluvia
    FROM clima_mes cm
    JOIN dim_tiempo dt ON dt.id_tiempo = cm.id_tiempo
    GROUP BY cm.id_municipio, dt.anio
)"""

_ENSO_CTE = """
enso_anual AS (
    SELECT
        dt.anio,
        AVG(fa.indice_spi)                       AS spi_promedio,
        AVG(fa.indice_oni)                       AS oni_promedio,
        AVG(fa.anomalia_precipitacion_pct)       AS anomalia_lluvia_pct,
        AVG(fa.probabilidad_deficit_hidrico)     AS prob_deficit,
        AVG(fa.probabilidad_exceso_hidrico)      AS prob_exceso,
        BOOL_OR(dt.es_anio_nino)                 AS es_anio_nino
    FROM fact_alerta_enso fa
    JOIN dim_tiempo dt ON dt.id_tiempo = fa.id_tiempo
    GROUP BY dt.anio
)"""

# Precios del cultivo por año. Con la serie diaria SIPSA (2020+) enlazada a los cultivos de la EVA
# (dim_producto_precio.id_cultivo); si esa tabla no existe se usa la tabla mensual antigua.
_PRECIOS_DIARIO_CTE = """
precios_anual AS (
    SELECT EXTRACT(YEAR FROM f.fecha)::int    AS anio,
           p.id_cultivo,
           AVG(f.precio_prom_kg)              AS precio_promedio_cop_kg,
           STDDEV(f.precio_prom_kg)           AS precio_std_cop_kg,
           NULL::double precision             AS volumen_promedio_ton
    FROM fact_precio_diario f
    JOIN dim_producto_precio p ON p.id_producto = f.id_producto
    WHERE p.id_cultivo IS NOT NULL
    GROUP BY 1, 2
)"""

_PRECIOS_MENSUAL_CTE = """
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
)"""

# Insumos como ÍNDICE (base 100 = promedio de cada serie): no se promedian precios de unidades
# distintas (COP/ton, jornal, litro), que no tienen significado conjunto.
_INSUMOS_CTE = """
insumos_norm AS (
    SELECT dt.anio, fpi.nombre_insumo, fpi.id_region,
           fpi.precio_cop_unidad
             / NULLIF(AVG(fpi.precio_cop_unidad) OVER (PARTITION BY fpi.nombre_insumo, fpi.id_region), 0) * 100 AS indice
    FROM fact_precios_insumos fpi
    JOIN dim_tiempo dt ON dt.id_tiempo = fpi.id_tiempo
),
insumos_anual AS (
    SELECT anio,
           AVG(indice)    AS precio_insumo_promedio,
           STDDEV(indice) AS precio_insumo_std
    FROM insumos_norm
    GROUP BY anio
)"""

_RESTO_CTE = """
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
)"""

_SELECT = """
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
    e.oni_promedio,
    e.anomalia_lluvia_pct,
    e.prob_deficit,
    e.prob_exceso,
    e.es_anio_nino,
    -- precios mercado
    pr.precio_promedio_cop_kg,
    pr.precio_std_cop_kg,
    pr.volumen_promedio_ton,
    -- insumos (índice base 100)
    ins.precio_insumo_promedio,
    ins.precio_insumo_std,
    -- aptitud
    ap.clase_aptitud,
    -- contexto municipio
    m.id_departamento,
    m.id_region,
    m.latitud_centroide,
    m.longitud_centroide,
    -- banderas: distinguen "sin dato" de un valor real (el modelo no debe leer NULL como 0)
    (c.lluvia_acumulada_anual IS NOT NULL)::int      AS tiene_clima,
    (pr.precio_promedio_cop_kg IS NOT NULL)::int     AS tiene_precio
FROM produccion p
JOIN dim_municipio m       ON m.id_municipio = p.id_municipio
LEFT JOIN clima_anual c    ON c.id_municipio = p.id_municipio AND c.anio = p.anio
LEFT JOIN enso_anual  e    ON e.anio = p.anio
LEFT JOIN precios_anual pr ON pr.anio = p.anio AND pr.id_cultivo = p.id_cultivo
LEFT JOIN insumos_anual ins ON ins.anio = p.anio
LEFT JOIN aptitud ap       ON ap.id_municipio = p.id_municipio AND ap.id_cultivo = p.id_cultivo
"""


def construir_query(precio_diario: bool = True) -> str:
    """Consulta del feature store. Une los CTE con coma; `precio_diario` elige la fuente de precios."""
    precios = _PRECIOS_DIARIO_CTE if precio_diario else _PRECIOS_MENSUAL_CTE
    return "WITH" + ",".join([_CLIMA_CTE, _ENSO_CTE, precios, _INSUMOS_CTE, _RESTO_CTE]) + _SELECT


def _tabla_existe(engine, nombre: str) -> bool:
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            return bool(conn.execute(text("SELECT to_regclass(:n) IS NOT NULL"), {"n": nombre}).scalar())
    except Exception:
        return False


_LAG_COLS = [
    "lluvia_acumulada_anual",
    "temp_promedio_anual",
    "spi_promedio",
    "oni_promedio",
    "precio_promedio_cop_kg",
]
_HIST_COLS_MUNI = ["rendimiento_t_ha", "produccion_total_ton"]
_APTITUD_MAP = {"alta": 3, "moderada": 2, "marginal": 1, "no_apta": 0}


def _add_lags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rezagos de 1 y 3 AÑOS calendario para clima/ENSO/precios. Se unen por (municipio, cultivo, año - k):
    si falta un año en la serie, el rezago queda NaN en vez de tomar por error el dato de un año anterior
    (un shift por fila asumía años consecutivos).
    """
    df = df.sort_values(["id_municipio", "id_cultivo", "anio"]).reset_index(drop=True)
    llaves = ["id_municipio", "id_cultivo"]
    for k in (1, 3):
        previo = df[llaves + ["anio"] + [c for c in _LAG_COLS if c in df.columns]].copy()
        previo["anio"] = previo["anio"] + k
        previo = previo.rename(columns={c: f"{c}_lag{k}" for c in _LAG_COLS if c in df.columns})
        df = df.merge(previo, on=llaves + ["anio"], how="left")
    return df


def _add_municipio_history(df: pd.DataFrame) -> pd.DataFrame:
    """
    Promedio histórico (solo años ANTERIORES, nunca el actual) por municipio×cultivo, ignorando vacíos:
    cuenta únicamente los años con dato (antes un vacío desplazaba el conteo y el promedio).
    """
    df = df.sort_values(["id_municipio", "id_cultivo", "anio"]).copy()
    llaves = [df["id_municipio"], df["id_cultivo"]]
    for col in _HIST_COLS_MUNI:
        if col not in df.columns:
            continue
        valor = pd.to_numeric(df[col], errors="coerce")
        con_dato = valor.notna().astype(int)
        suma_previa = valor.fillna(0).groupby(llaves).cumsum() - valor.fillna(0)
        n_previo = con_dato.groupby(llaves).cumsum() - con_dato
        df[f"{col}_hist_avg"] = suma_previa / n_previo.where(n_previo > 0)
    return df


def _encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """Codifica categóricas. "Sin dato" se deja como NaN (XGBoost lo trata como faltante), nunca como -1 ni 0."""
    df = df.copy()
    df["id_municipio_enc"]    = df["id_municipio"].astype(str).astype("category").cat.codes
    df["id_departamento_enc"] = df["id_departamento"].astype(str).astype("category").cat.codes
    df["id_region"]           = pd.to_numeric(df["id_region"], errors="coerce")
    df["clase_aptitud_score"] = df["clase_aptitud"].map(_APTITUD_MAP).astype("float")
    df["es_anio_nino_int"]    = df["es_anio_nino"].map({True: 1.0, False: 0.0}).astype("float")
    return df

def build_ml_features(engine=None) -> pd.DataFrame:
    """
    Feature Store enriquecido. Una fila = una cosecha (muni × cultivo × año).
    """
    logger.info("Construyendo Feature Store enriquecido...")
    if engine is None:
        engine = get_engine()

    try:
        precio_diario = _tabla_existe(engine, "fact_precio_diario") and _tabla_existe(engine, "dim_producto_precio")
        df = pd.read_sql(construir_query(precio_diario), engine)
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
