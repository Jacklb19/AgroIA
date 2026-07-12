"""
extract_municipios_geo.py — Genera polígonos aproximados de municipios de Colombia.

Usa tesselación de Voronoi sobre los centroides del DIVIPOLA para crear polígonos
aproximados de cada municipio, recortados a la caja delimitadora de Colombia.
El resultado se guarda en data/raw/manual/municipios/municipios_colombia.geojson
y se reutiliza en ejecuciones posteriores sin regenerar.
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import MultiPoint, box, Point
from shapely.ops import voronoi_diagram

from config.settings import DATA_RAW, MANUAL_DATA_DIR

logger = logging.getLogger(__name__)

_OUTPUT_PATH = MANUAL_DATA_DIR / "municipios" / "municipios_colombia.geojson"
_COLOMBIA_BBOX = box(-82.5, -5.5, -64.0, 14.5)


def extract_municipios_geo(df_divipola: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Carga polígonos municipales existentes o los genera desde centroides DIVIPOLA.
    El archivo generado sirve como base para joins espaciales con capas SIPRA.
    """
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if _OUTPUT_PATH.exists():
        logger.info("Polígonos municipales existentes: %s", _OUTPUT_PATH)
        return gpd.read_file(_OUTPUT_PATH)

    logger.info("Generando polígonos municipales (Voronoi) desde centroides DIVIPOLA...")
    gdf = _create_voronoi(df_divipola)

    if not gdf.empty:
        gdf.to_file(_OUTPUT_PATH, driver="GeoJSON")
        logger.info("Polígonos guardados: %s municipios -> %s", len(gdf), _OUTPUT_PATH)
    else:
        logger.warning("No se pudieron generar polígonos municipales")

    return gdf


def _create_voronoi(df_divipola: pd.DataFrame) -> gpd.GeoDataFrame:
    lat_col = next((c for c in df_divipola.columns if "latitud" in c.lower()), None)
    lon_col = next((c for c in df_divipola.columns if "longitud" in c.lower()), None)
    id_col  = next((c for c in df_divipola.columns if "cod_mpio" in c.lower()), None)
    nom_col = next((c for c in df_divipola.columns if "nom_mpio" in c.lower()), None)

    if not (lat_col and lon_col and id_col):
        logger.warning("DIVIPOLA sin columnas lat/lon/cod_mpio — no se puede crear Voronoi")
        return gpd.GeoDataFrame()

    df = df_divipola.copy()
    # DIVIPOLA usa coma como separador decimal (ej: -75,581775)
    df[lat_col] = pd.to_numeric(df[lat_col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])
    df[id_col] = df[id_col].astype(str).str.zfill(5)
    df = df.drop_duplicates(subset=[id_col])

    if len(df) < 4:
        logger.warning("Insuficientes municipios con coordenadas para Voronoi")
        return gpd.GeoDataFrame()

    coords = list(zip(df[lon_col].values, df[lat_col].values))
    multi_point = MultiPoint(coords)

    try:
        regions = voronoi_diagram(multi_point, envelope=_COLOMBIA_BBOX, tolerance=0.001)
    except Exception as exc:
        logger.error("Error generando diagrama Voronoi: %s", exc)
        return gpd.GeoDataFrame()

    centroid_pts = [Point(lon, lat) for lon, lat in coords]
    ids   = df[id_col].tolist()
    names = df[nom_col].tolist() if nom_col else [""] * len(df)

    rows = []
    for region in regions.geoms:
        if region.is_empty:
            continue
        rc = region.centroid
        distances = [rc.distance(pt) for pt in centroid_pts]
        best = int(np.argmin(distances))
        clipped = region.intersection(_COLOMBIA_BBOX)
        if clipped.is_empty:
            continue
        rows.append({
            "id_municipio":     ids[best],
            "nombre_municipio": names[best],
            "geometry":         clipped,
        })

    if not rows:
        return gpd.GeoDataFrame()

    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
