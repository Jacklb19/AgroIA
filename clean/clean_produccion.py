"""
clean_produccion.py — Normaliza la producción agrícola (EVA A04/A05) a los nombres del esquema.

`extract_produccion` ya renombra las columnas de Socrata (a_o -> anio, producci_n -> produccion_t, ...),
pero el pipeline seguía esperando los nombres crudos y fallaba con KeyError. Aquí se aceptan ambos
esquemas (crudo y ya renombrado) y se deja un único contrato de salida.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)

# nombre de entrada (crudo de Socrata o ya renombrado por el extractor) -> nombre del esquema
RENOMBRE = {
    "a_o": "anio",
    "rea_sembrada": "area_sembrada_ha",
    "rea_cosechada": "area_cosechada_ha",
    "producci_n": "produccion_total_ton",
    "produccion_t": "produccion_total_ton",
    "rendimiento": "rendimiento_t_ha",
    "grupo_cultivo": "grupo_de_cultivo",
    "ciclo_del_cultivo": "ciclo_de_cultivo",
    "ciclo_cultivo": "ciclo_de_cultivo",
    "c_digo_dane_municipio": "id_municipio",
    "codigo_dane_municipio": "id_municipio",
}

COLUMNAS_NUMERICAS = [
    "anio", "area_sembrada_ha", "area_cosechada_ha", "produccion_total_ton", "rendimiento_t_ha",
]
COLUMNAS_TEXTO = ["cultivo", "grupo_de_cultivo", "ciclo_de_cultivo"]
OBLIGATORIAS = ["cultivo", "anio", "rendimiento_t_ha"]


def normalizar_produccion(df: pd.DataFrame) -> pd.DataFrame:
    """
    Devuelve la producción con nombres del esquema, numéricos convertidos y `id_municipio`
    de 5 dígitos cuando existe. NO rellena vacíos con 0: un dato ausente sigue siendo NaN.
    """
    df = df.rename(columns={k: v for k, v in RENOMBRE.items() if k in df.columns and v not in df.columns})

    faltan = [c for c in OBLIGATORIAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Producción: faltan columnas obligatorias {faltan}. Columnas recibidas: {list(df.columns)}")

    for col in COLUMNAS_NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif col != "anio":
            df[col] = float("nan")          # p. ej. si la fuente no trae área cosechada

    for col in COLUMNAS_TEXTO:
        if col not in df.columns:
            df[col] = None

    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].astype("string").str.strip().str.zfill(5)
    return df
