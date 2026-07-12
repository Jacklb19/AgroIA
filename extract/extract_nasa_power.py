"""
extract_nasa_power.py — NASA POWER API (Prediction Of Worldwide Energy Resources).

Datos climáticos diarios oficiales de NASA, reanalysis MERRA-2: temperatura,
precipitación, humedad y radiación solar por coordenada. API pública, sin key.

Endpoint: https://power.larc.nasa.gov/api/temporal/daily/point
Documentación: https://power.larc.nasa.gov/docs/services/api/temporal/

Uso: complementa IDEAM con cobertura nacional homogénea (sirve de respaldo
en zonas con baja densidad de estaciones).
"""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from config.settings import DATA_RAW
from load.db import get_engine
from utils.extraction_quality import fetch_json, standardize, FetchError

logger = logging.getLogger(__name__)

NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS_NASA = ",".join([
    "T2M",          # Temperatura media a 2m (°C)
    "T2M_MAX",      # Temperatura máxima
    "T2M_MIN",      # Temperatura mínima
    "PRECTOTCORR",  # Precipitación corregida (mm/día)
    "RH2M",         # Humedad relativa a 2m (%)
    "ALLSKY_SFC_SW_DWN",  # Radiación solar (kWh/m²/día)
])
REPORTS_DIR = DATA_RAW.parent / "quality_reports"


def _municipios_con_coords(engine, limite: int | None = 30) -> pd.DataFrame:
    """Lista municipios con coordenadas válidas, priorizando los más relevantes."""
    sql = """
        SELECT id_municipio, nombre_municipio,
               latitud_centroide AS lat, longitud_centroide AS lon
        FROM dim_municipio
        WHERE latitud_centroide  IS NOT NULL
          AND longitud_centroide IS NOT NULL
        ORDER BY id_municipio
    """
    df = pd.read_sql(sql, engine)
    return df.head(limite) if limite else df


def _fetch_municipio(lat: float, lon: float, anio_inicio: int, anio_fin: int) -> pd.DataFrame:
    """Descarga la serie diaria para un punto. Retorna DF con una fila por día."""
    params = {
        "parameters": PARAMS_NASA,
        "community":  "AG",
        "longitude":  f"{lon:.4f}",
        "latitude":   f"{lat:.4f}",
        "start":      f"{anio_inicio}0101",
        "end":        f"{anio_fin}1231",
        "format":     "JSON",
    }
    js = fetch_json(NASA_URL, params=params, timeout=90)
    series = js.get("properties", {}).get("parameter", {})
    if not series:
        return pd.DataFrame()

    # NASA POWER retorna {param: {YYYYMMDD: value}}
    fechas = sorted(set().union(*(series[p].keys() for p in series)))
    rows = []
    for f in fechas:
        rows.append({
            "fecha":            datetime.strptime(f, "%Y%m%d").date(),
            "temperatura_med_c":  series.get("T2M", {}).get(f),
            "temperatura_max_c":  series.get("T2M_MAX", {}).get(f),
            "temperatura_min_c":  series.get("T2M_MIN", {}).get(f),
            "precipitacion_mm":   series.get("PRECTOTCORR", {}).get(f),
            "humedad_pct":        series.get("RH2M", {}).get(f),
            "radiacion_kwh_m2":   series.get("ALLSKY_SFC_SW_DWN", {}).get(f),
        })
    return pd.DataFrame(rows)


def extract_nasa_power(anio_inicio: int = 2018, anio_fin: int | None = None,
                       max_municipios: int = 30) -> pd.DataFrame:
    """
    Descarga clima diario NASA POWER para los primeros N municipios con coords.
    Filtra valores centinela (-999), descarta filas con NULL en clima crítico.
    """
    if anio_fin is None:
        anio_fin = datetime.utcnow().year
    engine = get_engine()
    municipios = _municipios_con_coords(engine, max_municipios)
    if municipios.empty:
        logger.warning("Sin municipios con coordenadas — corre primero extract_municipios_geo.")
        return pd.DataFrame()

    logger.info("NASA POWER: %s municipios × %s años", len(municipios), anio_fin - anio_inicio + 1)
    out_frames = []
    for _, m in municipios.iterrows():
        try:
            df = _fetch_municipio(m["lat"], m["lon"], anio_inicio, anio_fin)
        except FetchError as e:
            logger.error("Falló %s (%s): %s", m["nombre_municipio"], m["id_municipio"], e)
            continue
        if df.empty:
            continue
        df["id_municipio"]     = m["id_municipio"]
        df["nombre_municipio"] = m["nombre_municipio"]
        out_frames.append(df)

    if not out_frames:
        return pd.DataFrame()
    full = pd.concat(out_frames, ignore_index=True)

    # NASA POWER usa -999 como centinela de "sin dato".
    for col in ["temperatura_med_c", "temperatura_max_c", "temperatura_min_c",
                "precipitacion_mm", "humedad_pct", "radiacion_kwh_m2"]:
        full.loc[full[col] <= -900, col] = pd.NA

    full, _ = standardize(
        full,
        fuente         = "NASA_POWER",
        source_uri     = NASA_URL,
        required       = ["id_municipio", "fecha"],
        numeric        = ["temperatura_med_c", "temperatura_max_c", "temperatura_min_c",
                          "precipitacion_mm", "humedad_pct", "radiacion_kwh_m2"],
        critical_nulls = ["id_municipio", "fecha"],
        key_cols       = ["id_municipio", "fecha"],
        range_filters  = {
            "temperatura_med_c": (-10, 50),
            "precipitacion_mm":  (0, 500),
            "humedad_pct":       (0, 100),
        },
        reports_dir    = REPORTS_DIR,
    )

    out_path = DATA_RAW / "nasa_power" / "clima_diario.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    full.to_parquet(out_path, index=False)
    logger.info("NASA POWER: %s registros válidos → %s", len(full), out_path)
    return full


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    extract_nasa_power()
