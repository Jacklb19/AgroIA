"""
derive_clima_indices.py — Índices derivados de los datos reales (no valores por defecto).

1. Anomalía de precipitación (%) y SPI estandarizado por región y mes, calculados desde
   fact_clima_mensual. Antes `anomalia_precipitacion_pct` quedaba siempre NULL y en `indice_spi`
   se guardaba el índice Niño 3.4 de NOAA (que no es un SPI).
2. `dim_tiempo.es_anio_nino` derivado del ONI (>= 0,5 en al menos 5 meses del año) en lugar de
   una lista de años escrita a mano.

Limitación conocida: el "SPI" aquí es una anomalía ESTANDARIZADA (z) contra la climatología del
propio periodo con datos (2018+ del IDEAM, unos 8 años), no el SPI clásico con ajuste gamma sobre
30 o más años. Se calcula solo cuando hay al menos MIN_ANIOS años para ese mes y región.
"""
import logging

import numpy as np
import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

logger = logging.getLogger(__name__)

MIN_ANIOS = 4
UMBRAL_ONI = 0.5
MIN_MESES_NINO = 5


def indices_precipitacion(df: pd.DataFrame, min_anios: int = MIN_ANIOS) -> pd.DataFrame:
    """
    df: id_region, anio, mes, precip (mm mensuales promedio de la región).
    Retorna las mismas filas con `anomalia_pct` (vs la media del mismo mes) y `spi_z` (anomalía estandarizada).
    Ambos quedan NaN si hay menos de `min_anios` años para ese mes y región, o si no hay variación.
    """
    df = df.copy()
    g = df.groupby(["id_region", "mes"])["precip"]
    media, desv, n = g.transform("mean"), g.transform("std"), g.transform("count")
    valido = n >= min_anios
    df["anomalia_pct"] = np.where(valido & (media > 0), (df["precip"] - media) / media * 100, np.nan)
    df["spi_z"] = np.where(valido & (desv > 0), (df["precip"] - media) / desv, np.nan)
    return df


def anios_nino(oni_mensual: pd.DataFrame, umbral: float = UMBRAL_ONI, min_meses: int = MIN_MESES_NINO) -> dict[int, bool]:
    """oni_mensual: anio, indice_oni. Un año es 'Niño' si el ONI >= umbral en al menos `min_meses` meses."""
    cuenta = oni_mensual.assign(n=(oni_mensual["indice_oni"] >= umbral)).groupby("anio")["n"].sum()
    return {int(a): bool(c >= min_meses) for a, c in cuenta.items()}


def actualizar_indices_precipitacion(engine) -> int:
    """Escribe anomalia_precipitacion_pct e indice_spi en fact_alerta_enso a partir del clima real."""
    df = pd.read_sql(
        text("""
            SELECT m.id_region, dt.anio, dt.mes, dt.id_tiempo, AVG(fc.precipitacion_mm) AS precip
            FROM fact_clima_mensual fc
            JOIN dim_municipio m ON m.id_municipio = fc.id_municipio
            JOIN dim_tiempo dt   ON dt.id_tiempo = fc.id_tiempo
            WHERE fc.precipitacion_mm IS NOT NULL AND m.id_region IS NOT NULL
            GROUP BY m.id_region, dt.anio, dt.mes, dt.id_tiempo
        """),
        engine,
    )
    if df.empty:
        logger.warning("Sin clima para calcular anomalías de precipitación")
        return 0
    res = indices_precipitacion(df).dropna(subset=["spi_z", "anomalia_pct"], how="all")
    filas = [
        (int(r.id_tiempo), int(r.id_region),
         None if pd.isna(r.anomalia_pct) else float(r.anomalia_pct),
         None if pd.isna(r.spi_z) else float(r.spi_z))
        for r in res.itertuples(index=False)
    ]
    if not filas:
        return 0
    sql = """
        UPDATE fact_alerta_enso f SET anomalia_precipitacion_pct = v.anom, indice_spi = v.spi
        FROM (VALUES %s) AS v(id_tiempo, id_region, anom, spi)
        WHERE f.id_tiempo = v.id_tiempo AND f.id_region = v.id_region
        RETURNING 1
    """
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            devueltas = execute_values(cur, sql, filas, template="(%s::int, %s::int, %s::float8, %s::float8)", page_size=5000, fetch=True)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    logger.info("fact_alerta_enso: %s filas con anomalía y SPI estandarizado", len(devueltas))
    return len(devueltas)


def actualizar_es_anio_nino(engine) -> dict[int, bool]:
    """Marca dim_tiempo.es_anio_nino según el ONI real. Retorna {año: es_nino}."""
    oni = pd.read_sql(
        text("""
            SELECT dt.anio, AVG(fa.indice_oni) AS indice_oni
            FROM fact_alerta_enso fa JOIN dim_tiempo dt ON dt.id_tiempo = fa.id_tiempo
            WHERE fa.indice_oni IS NOT NULL
            GROUP BY dt.anio, dt.mes
        """),
        engine,
    )
    if oni.empty:
        return {}
    mapa = anios_nino(oni)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE dim_tiempo SET es_anio_nino = :nino WHERE anio = :anio"),
            [{"anio": a, "nino": n} for a, n in mapa.items()],
        )
    logger.info("dim_tiempo.es_anio_nino derivado del ONI: años Niño = %s", sorted(a for a, n in mapa.items() if n))
    return mapa
