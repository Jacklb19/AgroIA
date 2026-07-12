import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

from config.settings import MANUAL_DATA_DIR, DATA_RAW

logger = logging.getLogger(__name__)

_CATEGORY_COLS  = ["clase_aptitud", "aptitud", "categoria", "clase"]
_SOIL_COLS      = ["tipo_suelo", "suelo"]
_TEXTURE_COLS   = ["textura_suelo", "textura"]
_SLOPE_COLS     = ["pendiente_dominante", "pendiente"]
_DRAIN_COLS     = ["drenaje"]
_LIMIT_COLS     = ["limitante_principal", "limitante"]
_PRODUCT_COLS   = ["producto", "cultivo", "_source_file"]


def _pick_col(obj, candidates: list) -> str | None:
    cols = obj.columns if hasattr(obj, "columns") else obj
    lower = {c.lower(): c for c in cols}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _read_municipios_polygons() -> gpd.GeoDataFrame:
    base = MANUAL_DATA_DIR / "municipios"
    if not base.exists():
        return gpd.GeoDataFrame()
    candidates = (
        list(base.glob("*.geojson"))
        + list(base.glob("*.json"))
        + list(base.glob("*.gpkg"))
        + list(base.glob("*.shp"))
    )
    if not candidates:
        return gpd.GeoDataFrame()
    return gpd.read_file(candidates[0])


def resumir_aptitud_suelo_por_municipio(
    gdf_sipra: gpd.GeoDataFrame,
    df_divipola: pd.DataFrame,
) -> pd.DataFrame:
    """
    Extrae la clase dominante de aptitud agrícola por municipio.
    Fast path: usa codmunicipio si la capa SIPRA lo contiene (GeoJSONs de UPRA).
    Fallback: join espacial con polígonos municipales.
    """
    if gdf_sipra.empty:
        return pd.DataFrame()

    cod_col = _pick_col(gdf_sipra, ["codmunicipio", "cod_municipio", "id_municipio", "divipola"])
    if cod_col:
        return _resumir_por_codigo(gdf_sipra, cod_col)
    return _resumir_por_overlay(gdf_sipra)


def _resumir_por_codigo(gdf: gpd.GeoDataFrame, cod_col: str) -> pd.DataFrame:
    """Ruta directa — no necesita polígonos municipales."""
    df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))
    df = df.rename(columns={cod_col: "id_municipio"})
    df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(5)

    cols_map = {
        "clase_aptitud":       _pick_col(df, _CATEGORY_COLS),
        "tipo_suelo":          _pick_col(df, _SOIL_COLS),
        "textura_suelo":       _pick_col(df, _TEXTURE_COLS),
        "pendiente_dominante": _pick_col(df, _SLOPE_COLS),
        "drenaje":             _pick_col(df, _DRAIN_COLS),
        "limitante_principal": _pick_col(df, _LIMIT_COLS),
        "producto":            _pick_col(df, _PRODUCT_COLS),
    }

    result = pd.DataFrame({"id_municipio": df["id_municipio"]})
    for out_col, src_col in cols_map.items():
        result[out_col] = df[src_col] if src_col else None

    # Limpiar nombre de producto cuando viene del nombre de archivo
    if result["producto"].notna().any():
        result["producto"] = (
            result["producto"]
            .str.replace(r"^aptitud_", "", regex=True)
            .str.upper()
        )

    dedup_keys = ["id_municipio"]
    if result["producto"].notna().any():
        dedup_keys.append("producto")
    result = result.drop_duplicates(subset=dedup_keys, keep="first")

    logger.info(
        "SIPRA aptitud (directo): %s registros — %s municipios",
        len(result), result["id_municipio"].nunique(),
    )
    return result


def _resumir_por_overlay(gdf_sipra: gpd.GeoDataFrame) -> pd.DataFrame:
    """Join espacial con polígonos municipales (fallback cuando no hay codmunicipio)."""
    gdf_municipios = _read_municipios_polygons()
    if gdf_municipios.empty:
        logger.warning(
            "SIPRA sin codmunicipio y sin polígonos municipales — "
            "no es posible construir fact_aptitud_suelo. "
            "Ejecuta extract_municipios_geo() para generar los polígonos."
        )
        return pd.DataFrame()

    muni_id_col = _pick_col(gdf_municipios, ["id_municipio", "cod_mpio", "divipola"])
    if muni_id_col is None:
        logger.warning("Capa municipal sin columna id_municipio/cod_mpio/divipola")
        return pd.DataFrame()

    gdf_municipios = gdf_municipios.rename(columns={muni_id_col: "id_municipio"})
    gdf_municipios["id_municipio"] = gdf_municipios["id_municipio"].astype(str).str.zfill(5)

    if gdf_sipra.crs and gdf_municipios.crs and gdf_sipra.crs != gdf_municipios.crs:
        gdf_sipra = gdf_sipra.to_crs(gdf_municipios.crs)

    joined = gpd.overlay(gdf_sipra, gdf_municipios[["id_municipio", "geometry"]], how="intersection")
    if joined.empty:
        return pd.DataFrame()

    joined["_area"] = joined.geometry.area
    joined = joined.sort_values(["id_municipio", "_area"], ascending=[True, False])
    grouped = joined.groupby("id_municipio", as_index=False).first()

    cols_map = {
        "clase_aptitud":       _pick_col(grouped, _CATEGORY_COLS),
        "tipo_suelo":          _pick_col(grouped, _SOIL_COLS),
        "textura_suelo":       _pick_col(grouped, _TEXTURE_COLS),
        "pendiente_dominante": _pick_col(grouped, _SLOPE_COLS),
        "drenaje":             _pick_col(grouped, _DRAIN_COLS),
        "limitante_principal": _pick_col(grouped, _LIMIT_COLS),
        "producto":            _pick_col(grouped, _PRODUCT_COLS),
    }

    result = pd.DataFrame({"id_municipio": grouped["id_municipio"]})
    for out_col, src_col in cols_map.items():
        result[out_col] = grouped[src_col] if src_col else None

    logger.info("SIPRA aptitud (overlay): %s municipios", result["id_municipio"].nunique())
    return result


def load_censo_agropecuario_local() -> pd.DataFrame:
    # 1. Buscar archivo extraído automáticamente por el pipeline (extract_cna.py)
    auto_path = DATA_RAW / "cna_raw_automatizado.csv"
    if auto_path.exists():
        logger.info("Leyendo archivo CNA automatizado: %s", auto_path.name)
        df = pd.read_csv(auto_path)
    else:
        # 2. Fallback a directorio manual si no existe el automático
        base = MANUAL_DATA_DIR / "cna"
        candidates = (
            list(base.glob("*.csv"))
            + list(base.glob("*.xlsx"))
            + list(base.glob("*.xls"))
            + list(base.glob("*.parquet"))
        )
        if not candidates:
            return pd.DataFrame()

        path = candidates[0]
        logger.info("Leyendo archivo CNA manual: %s", path.name)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix == ".parquet":
            df = pd.read_parquet(path)
        else:
            df = pd.read_excel(path)

    rename_map = {}
    lower_map = {col.lower(): col for col in df.columns}
    optional = {
        "id_municipio":                   ["id_municipio", "cod_mpio", "divipola"],
        "anio_censo":                     ["anio_censo", "año_censo", "anio"],
        "upa_promedio_ha":                ["upa_promedio_ha", "upa_promedio"],
        "pct_tenencia_propia":            ["pct_tenencia_propia", "tenencia_propia_pct"],
        "pct_tenencia_arrendada":         ["pct_tenencia_arrendada", "tenencia_arrendada_pct"],
        "pct_acceso_riego":               ["pct_acceso_riego", "acceso_riego_pct"],
        "pct_asistencia_tecnica":         ["pct_asistencia_tecnica", "asistencia_tecnica_pct"],
        "area_cultivos_permanentes_ha":   ["area_cultivos_permanentes_ha"],
        "area_cultivos_transitorios_ha":  ["area_cultivos_transitorios_ha"],
    }
    for target, cands in optional.items():
        for candidate in cands:
            if candidate.lower() in lower_map:
                rename_map[lower_map[candidate.lower()]] = target
                break

    df = df.rename(columns=rename_map)
    if "id_municipio" in df.columns:
        df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(5)
    return df
