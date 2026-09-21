"""
clean_precios_diarios.py — Normalización de precios mayoristas diarios (SIPSA).

Unifica nombres de producto/mercado/departamento entre fuentes (SOAP y Excel),
valida rangos y deduplica por (mercado, producto, fecha). No inventa datos:
las filas inválidas se descartan y se reporta cuántas.
"""
import logging

import pandas as pd

from config.precios import (
    DEPARTAMENTO_ALIAS,
    GRUPO_ALIAS,
    MERCADO_ALIAS,
    MERCADOS_EXCEL_AGREGADOS,
    PALABRAS_MENORES,
    PRECIO_MAX_KG,
)
from load.load_facts import _normalizar_nombre

logger = logging.getLogger(__name__)

COLUMNAS_SALIDA = [
    "fecha", "mercado", "ciudad", "id_municipio", "id_departamento", "departamento",
    "producto", "producto_norm", "grupo",
    "precio_min_kg", "precio_max_kg", "precio_prom_kg", "fuente",
]


def _espacios(texto) -> str:
    return " ".join(str(texto).replace("\r", " ").replace("\n", " ").split())


def canon_producto(nombre) -> tuple[str, str]:
    """('Papa negra*') -> ('Papa negra', 'PAPA NEGRA'): sin '*', sin tildes ni mayúsculas para la llave."""
    limpio = _espacios(str(nombre).replace("*", " "))
    if not limpio:
        return "", ""
    return limpio[:1].upper() + limpio[1:], _normalizar_nombre(limpio)


def canon_mercado(nombre) -> str:
    limpio = _espacios(nombre)
    return MERCADO_ALIAS.get(limpio, limpio)


def canon_titulo(nombre) -> str:
    """'NORTE DE SANTANDER' -> 'Norte de Santander'; 'BOGOTÁ, D. C.' -> 'Bogotá D.C.'."""
    limpio = _espacios(nombre)
    if limpio.upper() in DEPARTAMENTO_ALIAS:
        return DEPARTAMENTO_ALIAS[limpio.upper()]
    palabras = limpio.lower().split(" ")
    return " ".join(
        p if (i > 0 and p in PALABRAS_MENORES) else p.capitalize()
        for i, p in enumerate(palabras)
    )


def canon_grupo(nombre) -> str | None:
    if nombre is None or (not isinstance(nombre, str) and pd.isna(nombre)):
        return None
    limpio = _espacios(nombre)
    if not limpio or limpio.lower() == "nan":
        return None
    return GRUPO_ALIAS.get(limpio.upper(), limpio.capitalize())


def _map_unicos(serie: pd.Series, fn) -> pd.Series:
    """Aplica fn solo a los valores únicos (700k filas, ~100 valores distintos)."""
    tabla = {v: fn(v) for v in serie.dropna().unique()}
    return serie.map(tabla)


def normalizar_soap(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe filas crudas de `promediosSipsaParcial` (todas las columnas como texto):
    artiNombre, grupNombre, deptNombre, muniId, muniNombre, fuenNombre,
    enmaFecha, minimoKg, maximoKg, promedioKg.
    """
    if df_raw.empty:
        return pd.DataFrame(columns=COLUMNAS_SALIDA)

    df = pd.DataFrame(index=df_raw.index)
    df["fecha"] = pd.to_datetime(df_raw["enmaFecha"].astype(str).str[:10], errors="coerce")
    for src, dst in (("minimoKg", "precio_min_kg"), ("maximoKg", "precio_max_kg"), ("promedioKg", "precio_prom_kg")):
        df[dst] = pd.to_numeric(df_raw[src], errors="coerce")

    df["producto"] = _map_unicos(df_raw["artiNombre"], lambda v: canon_producto(v)[0])
    df["producto_norm"] = _map_unicos(df_raw["artiNombre"], lambda v: canon_producto(v)[1])
    df["mercado"] = _map_unicos(df_raw["fuenNombre"], canon_mercado)
    df["ciudad"] = _map_unicos(df_raw["muniNombre"], canon_titulo)
    df["departamento"] = _map_unicos(df_raw["deptNombre"], canon_titulo)
    df["grupo"] = _map_unicos(df_raw["grupNombre"], canon_grupo)

    muni = df_raw["muniId"].astype(str).str.strip()
    df["id_municipio"] = muni.where(muni.str.fullmatch(r"\d{5}"))
    df["id_departamento"] = df["id_municipio"].str[:2]
    df["fuente"] = "soap"
    return validar_y_deduplicar(df)


def normalizar_excel(df_largo: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe el boletín diario en formato largo (fecha, mercado, producto, precio_prom_kg),
    tal como sale de extract_sipsa_diario.parse_boletin. El Excel no trae mín/máx,
    municipio ni departamento: esos campos quedan vacíos (se resuelven por el mercado
    ya registrado en dim_central_abastos).
    """
    if df_largo.empty:
        return pd.DataFrame(columns=COLUMNAS_SALIDA)

    agregados = df_largo["mercado"].map(_espacios).isin(MERCADOS_EXCEL_AGREGADOS)
    if agregados.any():
        logger.info("Excel: %s filas de ciudades agregadas omitidas (%s)", int(agregados.sum()), sorted(MERCADOS_EXCEL_AGREGADOS))
        df_largo = df_largo[~agregados]
        if df_largo.empty:
            return pd.DataFrame(columns=COLUMNAS_SALIDA)

    df = pd.DataFrame(index=df_largo.index)
    df["fecha"] = pd.to_datetime(df_largo["fecha"], errors="coerce")
    df["precio_prom_kg"] = pd.to_numeric(df_largo["precio_prom_kg"], errors="coerce")
    df["producto"] = _map_unicos(df_largo["producto"], lambda v: canon_producto(v)[0])
    df["producto_norm"] = _map_unicos(df_largo["producto"], lambda v: canon_producto(v)[1])
    df["mercado"] = _map_unicos(df_largo["mercado"], canon_mercado)
    for col in ("precio_min_kg", "precio_max_kg"):
        df[col] = float("nan")
    for col in ("ciudad", "id_municipio", "id_departamento", "departamento", "grupo"):
        df[col] = None
    df["fuente"] = "excel"
    return validar_y_deduplicar(df)


def validar_y_deduplicar(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    ok = (
        df["fecha"].notna()
        & df["mercado"].notna() & (df["mercado"] != "")
        & df["producto_norm"].notna() & (df["producto_norm"] != "")
        & df["precio_prom_kg"].notna()
        & (df["precio_prom_kg"] > 0)
        & (df["precio_prom_kg"] <= PRECIO_MAX_KG)
    )
    df = df[ok].copy()
    descartadas = total - len(df)

    # min/max solo se conservan si son coherentes con el promedio
    min_malo = df["precio_min_kg"].notna() & ((df["precio_min_kg"] <= 0) | (df["precio_min_kg"] > df["precio_prom_kg"]))
    max_malo = df["precio_max_kg"].notna() & ((df["precio_max_kg"] <= 0) | (df["precio_max_kg"] < df["precio_prom_kg"]))
    df.loc[min_malo, "precio_min_kg"] = float("nan")
    df.loc[max_malo, "precio_max_kg"] = float("nan")

    antes = len(df)
    df = (
        df.groupby(["mercado", "producto_norm", "fecha"], as_index=False, sort=False)
        .agg(
            ciudad=("ciudad", "first"),
            id_municipio=("id_municipio", "first"),
            id_departamento=("id_departamento", "first"),
            departamento=("departamento", "first"),
            producto=("producto", "first"),
            grupo=("grupo", "first"),
            precio_min_kg=("precio_min_kg", "min"),
            precio_max_kg=("precio_max_kg", "max"),
            precio_prom_kg=("precio_prom_kg", "mean"),
            fuente=("fuente", "first"),
        )
    )
    fusionadas = antes - len(df)
    logger.info(
        "Precios normalizados: %s filas de entrada, %s descartadas (precio/fecha/nombre invalido), "
        "%s fusionadas por alias de mercado, %s finales",
        total, descartadas, fusionadas, len(df),
    )
    return df[COLUMNAS_SALIDA]
