import logging

import pandas as pd

from clean.clean_municipios import agregar_id_municipio

logger = logging.getLogger(__name__)


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {col.lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def normalizar_precios_sipsa(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Homologa microdatos SIPSA a la forma mensual esperada por el loader."""
    if df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()
    col_fecha = _find_column(df, ["fecha", "fecha_registro", "fecha del precio"])
    col_producto = _find_column(df, ["producto", "articulo", "nombre_producto"])
    col_central = _find_column(df, ["central", "central_abastos", "plaza"])
    col_ciudad = _find_column(df, ["ciudad", "municipio", "ciudad_central"])
    col_precio_min = _find_column(df, ["precio_min", "precio_min_cop_kg", "precio minimo"])
    col_precio_max = _find_column(df, ["precio_max", "precio_max_cop_kg", "precio maximo"])
    col_precio_prom = _find_column(df, ["precio_promedio", "precio_promedio_cop_kg", "precio"])
    col_volumen = _find_column(df, ["volumen", "volumen_ton", "cantidad"])

    required = [col_fecha, col_producto, col_central, col_ciudad, col_precio_prom]
    if any(col is None for col in required):
        logger.warning("SIPSA: faltan columnas mínimas para normalizar")
        return pd.DataFrame()

    df = df.rename(columns={
        col_fecha: "fecha_registro",
        col_producto: "producto",
        col_central: "nombre_central",
        col_ciudad: "ciudad",
    })
    if col_precio_min:
        df = df.rename(columns={col_precio_min: "precio_min_cop_kg"})
    if col_precio_max:
        df = df.rename(columns={col_precio_max: "precio_max_cop_kg"})
    df = df.rename(columns={col_precio_prom: "precio_promedio_cop_kg"})
    if col_volumen:
        df = df.rename(columns={col_volumen: "volumen_abastecimiento_ton"})

    df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
    df = df.dropna(subset=["fecha_registro", "producto", "nombre_central", "ciudad"])
    for col in ["producto", "nombre_central", "ciudad"]:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
    df["anio"] = df["fecha_registro"].dt.year
    df["mes"] = df["fecha_registro"].dt.month

    for col in ["precio_min_cop_kg", "precio_max_cop_kg", "precio_promedio_cop_kg", "volumen_abastecimiento_ton"]:
        if col not in df.columns:
            df[col] = None
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["municipio"] = df["ciudad"]
    df = agregar_id_municipio(df, "municipio")

    aggregated = (
        df.groupby(["anio", "mes", "producto", "nombre_central", "ciudad", "id_municipio"], dropna=False)
        .agg({
            "precio_min_cop_kg": "mean",
            "precio_max_cop_kg": "mean",
            "precio_promedio_cop_kg": "mean",
            "volumen_abastecimiento_ton": "sum",
        })
        .reset_index()
    )
    logger.info("SIPSA normalizado: %s registros mensuales", len(aggregated))
    return aggregated


def construir_dim_centrales(df_precios: pd.DataFrame) -> pd.DataFrame:
    if df_precios.empty:
        return pd.DataFrame()
    return (
        df_precios[["nombre_central", "ciudad", "id_municipio"]]
        .dropna(subset=["nombre_central", "ciudad"])
        .drop_duplicates()
    )
