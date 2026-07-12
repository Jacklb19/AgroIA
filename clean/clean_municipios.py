import pandas as pd
import numpy as np
import unicodedata
import logging
from config.settings import DATA_RAW, BASE_DIR, SPATIAL_JOIN_RADIUS_KM

logger = logging.getLogger(__name__)

DEPARTAMENTO_REGION = {
    "05": "Andina",
    "08": "Caribe",
    "11": "Andina",
    "13": "Caribe",
    "15": "Andina",
    "17": "Andina",
    "18": "Amazonía",
    "19": "Pacífico",
    "20": "Caribe",
    "23": "Caribe",
    "25": "Andina",
    "27": "Pacífico",
    "41": "Andina",
    "44": "Caribe",
    "47": "Caribe",
    "50": "Orinoquía",
    "52": "Pacífico",
    "54": "Andina",
    "63": "Andina",
    "66": "Andina",
    "68": "Andina",
    "70": "Caribe",
    "73": "Andina",
    "76": "Pacífico",
    "81": "Orinoquía",
    "85": "Orinoquía",
    "86": "Amazonía",
    "88": "Caribe",
    "91": "Amazonía",
    "94": "Amazonía",
    "95": "Amazonía",
    "97": "Amazonía",
    "99": "Orinoquía",
}

def _normalizar_texto(s: str) -> str:
    """Minúsculas, sin tildes, sin paréntesis de departamento."""
    if not isinstance(s, str):
        return ""
    s = s.lower().strip()
    s = s.split("(")[0].strip()                    # quita "(Santander)" etc.
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="coerce")

def build_synonym_map() -> dict:
    """
    Lee config/synonyms_municipios.csv y devuelve {nombre_normalizado: divipola}.
    El CSV tiene columnas: sinonimo, divipola
    """
    path = BASE_DIR / "config" / "synonyms_municipios.csv"
    if not path.exists():
        logger.warning("synonyms_municipios.csv no encontrado, usando mapa vacío")
        return {}
    df = pd.read_csv(path, dtype=str)
    return {_normalizar_texto(row["sinonimo"]): row["divipola"] for _, row in df.iterrows()}

def load_divipola_map() -> dict:
    """
    Carga el CSV de DIVIPOLA descargado y devuelve {nombre_normalizado: codigo_divipola}.
    """
    path = DATA_RAW / "divipola.csv"
    df = pd.read_csv(path, dtype=str)
    result = {}
    for _, row in df.iterrows():
        nombre = _normalizar_texto(row.get("nom_mpio", row.get("municipio", "")))
        codigo = str(row.get("cod_mpio", row.get("divipola", ""))).zfill(5)
        if nombre:
            result[nombre] = codigo
    return result

def resolver_municipio(nombre: str, divipola_map: dict, synonym_map: dict) -> str | None:
    """
    Devuelve el código DIVIPOLA (5 dígitos) para un nombre de municipio.
    Prioridad: 1) mapa directo, 2) sinónimos, 3) None.
    """
    norm = _normalizar_texto(nombre)
    if norm in divipola_map:
        return divipola_map[norm]
    if norm in synonym_map:
        return synonym_map[norm]
    logger.debug(f"Municipio no resuelto: '{nombre}' -> '{norm}'")
    return None

def agregar_id_municipio(df: pd.DataFrame, col_nombre: str) -> pd.DataFrame:
    """
    Agrega columna id_municipio (DIVIPOLA) a cualquier DataFrame
    que tenga una columna con nombres de municipio.
    """
    divipola_map = load_divipola_map()
    synonym_map  = build_synonym_map()
    df = df.copy()
    df["id_municipio"] = df[col_nombre].apply(
        lambda x: resolver_municipio(x, divipola_map, synonym_map)
    )
    nulos = df["id_municipio"].isna().sum()
    total = len(df)
    pct   = nulos / total * 100
    logger.info(f"Normalización municipios: {total - nulos}/{total} resueltos ({pct:.1f}% sin resolver)")
    if pct > 5:
        logger.warning(f"Más del 5% de municipios sin resolver — revisar synonyms_municipios.csv")
    return df


def build_region_map_from_divipola(df_divipola: pd.DataFrame) -> pd.DataFrame:
    """Construye un mapeo municipio -> región natural usando el código de departamento."""
    df = df_divipola.copy()
    df["id_municipio"] = df["cod_mpio"].astype(str).str.zfill(5)
    df["id_departamento"] = df["cod_dpto"].astype(str).str.zfill(2)
    df["nombre_region"] = df["id_departamento"].map(DEPARTAMENTO_REGION)
    return df[["id_municipio", "nombre_region"]].drop_duplicates()


def _haversine_km(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2.0) ** 2
    )
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return 6371.0 * c


def asignar_estaciones_a_municipios(
    df_estaciones: pd.DataFrame,
    df_divipola: pd.DataFrame,
    fallback_col: str = "municipio",
    max_radius_km: float = SPATIAL_JOIN_RADIUS_KM,
) -> pd.DataFrame:
    """
    Asigna cada estación al municipio más cercano usando coordenadas.
    Si faltan coordenadas o no hay match confiable, usa el nombre del municipio como respaldo.
    """
    df = df_estaciones.copy()
    df["latitud"] = _to_float(df["latitud"])
    df["longitud"] = _to_float(df["longitud"])

    municipios = df_divipola.copy()
    municipios["id_municipio"] = municipios["cod_mpio"].astype(str).str.zfill(5)
    municipios["latitud_centroide"] = _to_float(municipios["latitud"])
    municipios["longitud_centroide"] = _to_float(municipios["longitud"])
    # Añadimos altitud de divipola si existe, o 0 si no
    municipios["altitud_muni"] = _to_float(municipios.get("altitud", pd.Series(0, index=municipios.index)))
    municipios = municipios.dropna(subset=["latitud_centroide", "longitud_centroide"])

    muni_lat = municipios["latitud_centroide"].to_numpy()
    muni_lon = municipios["longitud_centroide"].to_numpy()
    muni_alt = municipios["altitud_muni"].to_numpy()
    muni_ids = municipios["id_municipio"].to_numpy()

    assigned_ids: list[str | None] = []
    distances: list[float | None] = []
    methods: list[str] = []

    divipola_map = load_divipola_map()
    synonym_map = build_synonym_map()

    for row in df.itertuples(index=False):
        lat = getattr(row, "latitud", None)
        lon = getattr(row, "longitud", None)
        fallback_name = getattr(row, fallback_col, None) if hasattr(row, fallback_col) else None

        alt_estacion = _to_float(pd.Series([getattr(row, "altitud", 0)])).iloc[0]

        if pd.notna(lat) and pd.notna(lon) and len(muni_ids) > 0:
            dist_2d = _haversine_km(float(lat), float(lon), muni_lat, muni_lon)
            
            # Penalización altitudinal: sumar 10km por cada 100m de diferencia (ajuste empírico)
            diferencia_alt = np.abs(muni_alt - alt_estacion)
            penalizacion = (diferencia_alt / 100.0) * 10.0
            
            # Distancia penalizada
            dist = dist_2d + penalizacion
            
            idx = int(np.argmin(dist))
            nearest_distance = float(dist_2d[idx]) # Guardamos la distancia 2D real, no la penalizada
            assigned_ids.append(str(muni_ids[idx]))
            distances.append(nearest_distance)
            if nearest_distance <= max_radius_km and diferencia_alt[idx] <= 400:
                methods.append("spatial_within_radius_and_altitude")
            else:
                methods.append("spatial_nearest_outside_radius_or_altitude")
            continue

        fallback_id = resolver_municipio(fallback_name, divipola_map, synonym_map)
        assigned_ids.append(fallback_id)
        distances.append(None)
        methods.append("text_fallback" if fallback_id else "unresolved")

    df["id_municipio"] = assigned_ids
    df["distancia_municipio_km"] = distances
    df["metodo_asignacion_municipio"] = methods

    fuera_radio = (df["metodo_asignacion_municipio"] == "spatial_nearest_outside_radius_or_altitude").sum()
    sin_resolver = df["id_municipio"].isna().sum()
    logger.info(
        "Asignación espacial estaciones->municipio: %s estaciones, %s fuera del radio, %s sin resolver",
        len(df),
        int(fuera_radio),
        int(sin_resolver),
    )
    return df
