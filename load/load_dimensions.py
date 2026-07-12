import pandas as pd
import logging
from datetime import date
from config.settings import REGIONES_NATURALES, YEAR_START, YEAR_END
from .db import upsert

logger = logging.getLogger(__name__)

MESES = ["enero","febrero","marzo","abril","mayo","junio",
         "julio","agosto","septiembre","octubre","noviembre","diciembre"]

def load_dim_region_natural(engine):
    df = pd.DataFrame([
        {"nombre_region": r} for r in REGIONES_NATURALES
    ])
    upsert(engine, "dim_region_natural", df, ["nombre_region"])

def load_dim_tiempo(engine, anios_nino: list = None):
    """
    Genera dim_tiempo con un registro por mes desde YEAR_START hasta YEAR_END.
    anios_nino: lista de años con El Niño activo para marcar es_anio_nino=True.
    """
    anios_nino = anios_nino or [1997,1998,2002,2003,2009,2010,2015,2016,2018,2019,2023,2024]
    rows = []
    for anio in range(YEAR_START, YEAR_END + 1):
        for mes in range(1, 13):
            trimestre = (mes - 1) // 3 + 1
            semestre  = "A" if mes <= 6 else "B"
            rows.append({
                "fecha":        date(anio, mes, 1),
                "anio":         anio,
                "mes":          mes,
                "trimestre":    trimestre,
                "semestre":     semestre,
                "nombre_mes":   MESES[mes - 1],
                "es_anio_nino": anio in anios_nino,
            })
    df = pd.DataFrame(rows)
    upsert(engine, "dim_tiempo", df, ["fecha"])
    logger.info(f"dim_tiempo: {len(df)} períodos cargados")

def load_dim_municipio(engine, df_divipola: pd.DataFrame, df_region_map: pd.DataFrame):
    """
    df_divipola: resultado del extractor DIVIPOLA
    df_region_map: mapeo id_municipio -> id_region (construido manualmente o por departamento)
    """
    df = df_divipola.rename(columns={
        "cod_mpio":   "id_municipio",
        "nom_mpio":   "nombre_municipio",
        "cod_dpto":   "id_departamento",
        "dpto":       "nombre_departamento",
        "latitud":    "latitud_centroide",
        "longitud":   "longitud_centroide",
    })[["id_municipio","nombre_municipio","id_departamento",
        "nombre_departamento","latitud_centroide","longitud_centroide"]]
    df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(5)
    df["latitud_centroide"] = df["latitud_centroide"].astype(str).str.replace(",", ".").replace("nan", "0").astype(float)
    df["longitud_centroide"] = df["longitud_centroide"].astype(str).str.replace(",", ".").replace("nan", "0").astype(float)
    if df_region_map is not None:
        if "nombre_region" in df_region_map.columns and "id_region" not in df_region_map.columns:
            dim_region_db = pd.read_sql(
                "SELECT id_region, nombre_region FROM dim_region_natural",
                engine,
            )
            df_region_map = df_region_map.merge(dim_region_db, on="nombre_region", how="left")
        df = df.merge(df_region_map, on="id_municipio", how="left")
    expected_cols = [
        "id_municipio",
        "nombre_municipio",
        "id_departamento",
        "nombre_departamento",
        "latitud_centroide",
        "longitud_centroide",
        "id_region",
    ]
    df = df[[col for col in expected_cols if col in df.columns]]
    upsert(engine, "dim_municipio", df, ["id_municipio"])
    logger.info(f"dim_municipio: {len(df)} municipios cargados")

def load_dim_cultivo(engine, df_cultivos: pd.DataFrame):
    upsert(engine, "dim_cultivo", df_cultivos, ["nombre_normalizado"])

def load_dim_estacion_ideam(engine, df_estaciones: pd.DataFrame):
    upsert(engine, "dim_estacion_ideam", df_estaciones, ["id_estacion"])

def load_dim_central_abastos(engine, df_centrales: pd.DataFrame):
    import numpy as np
    df = df_centrales.copy()
    # id_municipio NaN viola la FK — convertir a None para que Postgres acepte NULL
    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].where(
            df["id_municipio"].notna() & (df["id_municipio"] != "nan"), other=None
        )
    upsert(engine, "dim_central_abastos", df, ["nombre_central", "ciudad"])

