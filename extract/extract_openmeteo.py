"""
extract/extract_openmeteo.py — Temperatura, humedad y brillo solar desde
Open-Meteo Historical Archive API (ERA5 reanalysis, sin API key).

Rellena temperatura_media_c, temperatura_max_c, temperatura_min_c,
humedad_relativa_pct y brillo_solar_horas_dia en fact_clima_mensual.

Usa el parámetro `daily` (archive-api no soporta `monthly`) y agrega a mensual en Python.
Cache persistente en data/raw/clima/openmeteo_combined.parquet.
Guarda incrementalmente para sobrevivir a caídas de proceso.
Salta estaciones que ya tienen datos en fact_clima_mensual.
"""
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from config.settings import CLIMA_YEAR_START, DATA_RAW, YEAR_END

logger = logging.getLogger(__name__)

OPENMETEO_URL  = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS     = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "sunshine_duration",        # segundos/día
]
MAX_RETRIES       = 3
TIMEOUT           = 90
RATE_LIMIT_SLEEP  = 65  # segundos fijos a esperar en caso de 429 (ventana de 1 min)
INTER_STATION_SLEEP = 5  # segundos entre estaciones para respetar rate limit

CACHE_PATH = DATA_RAW / "clima" / "openmeteo_combined.parquet"


def _load_cache() -> pd.DataFrame | None:
    if not CACHE_PATH.exists():
        return None
    try:
        df = pd.read_parquet(CACHE_PATH)
        if df.empty:
            return None
        logger.info("OpenMeteo: cache cargado (%d registros) desde %s", len(df), CACHE_PATH)
        return df
    except Exception as e:
        logger.warning("OpenMeteo: cache corrupto (%s), se re-descargará.", e)
        return None


def _save_cache(df: pd.DataFrame) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(CACHE_PATH, index=False)
    except Exception as e:
        logger.warning("OpenMeteo: no se pudo guardar cache incremental: %s", e)


def _fetch_station(id_estacion: str, lat: float, lon: float,
                   start_date: str, end_date: str) -> pd.DataFrame:
    """
    Descarga datos diarios de Open-Meteo para una estación y los agrega a mensual.

    archive-api.open-meteo.com solo acepta `daily`, no `monthly`.
    Agrupamos por (anio, mes) aquí mismo.
    """
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": start_date,
        "end_date":   end_date,
        "daily":      ",".join(DAILY_VARS),
        "timezone":   "America/Bogota",
    }

    time.sleep(INTER_STATION_SLEEP)

    data = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(OPENMETEO_URL, params=params, timeout=TIMEOUT)
            if r.status_code == 429:
                logger.warning("OpenMeteo [%s]: 429 rate limit, esperando %ds (intento %d/%d)",
                               id_estacion, RATE_LIMIT_SLEEP, attempt + 1, MAX_RETRIES)
                time.sleep(RATE_LIMIT_SLEEP)
                continue
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(3)
            else:
                logger.error("OpenMeteo [%s]: error tras %d intentos: %s",
                             id_estacion, MAX_RETRIES, e)
                return pd.DataFrame()

    if data is None:
        return pd.DataFrame()

    daily = data.get("daily", {})
    times = daily.get("time", [])
    if not times:
        logger.warning("OpenMeteo [%s]: respuesta sin datos diarios", id_estacion)
        return pd.DataFrame()

    df = pd.DataFrame({"fecha": pd.to_datetime(times)})
    for v in DAILY_VARS:
        df[v] = pd.to_numeric(daily.get(v), errors="coerce")

    df["anio"] = df["fecha"].dt.year
    df["mes"]  = df["fecha"].dt.month

    # sunshine_duration (segundos/día) → horas/día antes de agrupar
    df["brillo_solar_horas_dia"] = df["sunshine_duration"] / 3600.0

    # Agregación diaria → mensual
    monthly = (
        df.groupby(["anio", "mes"], as_index=False)
        .agg(
            temperatura_media_c        =("temperature_2m_mean",       "mean"),
            temperatura_max_c          =("temperature_2m_max",         "mean"),
            temperatura_min_c          =("temperature_2m_min",         "mean"),
            humedad_relativa_pct       =("relative_humidity_2m_mean",  "mean"),
            brillo_solar_horas_dia     =("brillo_solar_horas_dia",     "mean"),
        )
    )

    monthly["id_estacion"] = str(id_estacion)

    return monthly[[
        "id_estacion", "anio", "mes",
        "temperatura_media_c", "temperatura_max_c", "temperatura_min_c",
        "humedad_relativa_pct", "brillo_solar_horas_dia",
    ]]


def _get_done_stations(engine) -> set:
    """Estaciones que ya tienen temperatura_media_c no-nula en fact_clima_mensual."""
    try:
        df = pd.read_sql(
            "SELECT DISTINCT id_estacion FROM fact_clima_mensual "
            "WHERE temperatura_media_c IS NOT NULL",
            engine,
        )
        return set(df["id_estacion"].astype(str))
    except Exception as e:
        logger.warning("OpenMeteo: no se pudo consultar estaciones ya procesadas: %s", e)
        return set()


def extract_openmeteo_clima(engine) -> pd.DataFrame:
    """
    Descarga temperatura, humedad y brillo solar de Open-Meteo (ERA5) para todas
    las estaciones con coordenadas válidas presentes en fact_clima_mensual.

    Usa cache persistente (data/raw/clima/openmeteo_combined.parquet).
    Guarda incrementalmente cada estación para sobrevivir caídas de proceso.
    Salta estaciones que ya tienen temperatura_media_c en fact_clima_mensual.
    Borra el archivo de cache para forzar re-descarga completa.

    Retorna DataFrame con columnas:
        id_estacion, anio, mes,
        temperatura_media_c, temperatura_max_c, temperatura_min_c,
        humedad_relativa_pct, brillo_solar_horas_dia
    """
    if engine is None:
        logger.error("OpenMeteo: engine no disponible.")
        return pd.DataFrame()

    # Usar cache si existe (cubre el caso de run completo previo)
    df_cached = _load_cache()
    if df_cached is not None:
        return df_cached

    # Estaciones con coordenadas válidas presentes en fact_clima_mensual
    query = """
        SELECT DISTINCT
               e.id_estacion,
               CAST(e.latitud  AS DOUBLE PRECISION) AS latitud,
               CAST(e.longitud AS DOUBLE PRECISION) AS longitud
        FROM dim_estacion_ideam e
        INNER JOIN fact_clima_mensual f ON f.id_estacion = e.id_estacion
        WHERE e.latitud      IS NOT NULL
          AND e.longitud     IS NOT NULL
          AND e.id_municipio IS NOT NULL
    """
    try:
        df_stations = pd.read_sql(query, engine)
    except Exception as exc:
        logger.error("OpenMeteo: error consultando estaciones: %s", exc)
        return pd.DataFrame()

    if df_stations.empty:
        logger.warning("OpenMeteo: ninguna estación con coordenadas en fact_clima_mensual.")
        return pd.DataFrame()

    # Saltar estaciones que ya tienen datos en fact_clima_mensual
    done_stations = _get_done_stations(engine)
    if done_stations:
        n_before = len(df_stations)
        df_stations = df_stations[~df_stations["id_estacion"].astype(str).isin(done_stations)]
        logger.info(
            "OpenMeteo: %d estaciones ya tienen datos — saltando. Quedan %d por procesar.",
            n_before - len(df_stations), len(df_stations)
        )

    if df_stations.empty:
        logger.info("OpenMeteo: todas las estaciones ya tienen datos. Cargando desde DB...")
        # Retornar los datos ya existentes en la DB para construir el DataFrame
        try:
            return pd.read_sql(
                """SELECT id_estacion, EXTRACT(YEAR FROM t.fecha)::int AS anio,
                          EXTRACT(MONTH FROM t.fecha)::int AS mes,
                          temperatura_media_c, temperatura_max_c, temperatura_min_c,
                          humedad_relativa_pct, brillo_solar_horas_dia
                   FROM fact_clima_mensual f
                   JOIN dim_tiempo t ON t.id_tiempo = f.id_tiempo
                   WHERE temperatura_media_c IS NOT NULL""",
                engine,
            )
        except Exception:
            return pd.DataFrame()

    n          = len(df_stations)
    now        = datetime.now()
    start_date = f"{CLIMA_YEAR_START}-01-01"
    # ERA5 tiene un retraso de ~5 días; usamos el último día del mes anterior para seguridad
    safe_end   = now.replace(day=1) - timedelta(days=1)
    end_date   = safe_end.strftime("%Y-%m-%d")

    logger.info("OpenMeteo: %d estaciones pendientes | %s → %s | secuencial con %ds entre llamadas",
                n, start_date, end_date, INTER_STATION_SLEEP)

    all_frames: list[pd.DataFrame] = []
    done = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3  # Abort if rate-limited on 3 stations in a row

    for _, row in df_stations.iterrows():
        id_est = str(row["id_estacion"])
        df_m = _fetch_station(id_est, float(row["latitud"]), float(row["longitud"]),
                              start_date, end_date)
        done += 1
        if not df_m.empty:
            all_frames.append(df_m)
            consecutive_failures = 0
            # Guardar cache incremental tras cada estación exitosa
            df_so_far = pd.concat(all_frames, ignore_index=True)
            _save_cache(df_so_far)
        else:
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "OpenMeteo: %d estaciones consecutivas sin datos (rate limit persistente). "
                    "Abortando extracción para no bloquear el pipeline. "
                    "Reintente más tarde (cuota diaria se reinicia a medianoche UTC).",
                    consecutive_failures,
                )
                break

        if done % 10 == 0 or done == n:
            logger.info("  OpenMeteo: [%d/%d] estaciones procesadas (%d con datos)",
                        done, n, len(all_frames))

    if not all_frames:
        logger.warning("OpenMeteo: sin datos de ninguna estación.")
        return pd.DataFrame()

    df_all = pd.concat(all_frames, ignore_index=True)
    logger.info("OpenMeteo: %d registros mensuales para %d/%d estaciones.",
                len(df_all), len(all_frames), n)

    # Guardar cache final consolidado
    _save_cache(df_all)
    logger.info("OpenMeteo: cache guardado → %s", CACHE_PATH)

    return df_all
