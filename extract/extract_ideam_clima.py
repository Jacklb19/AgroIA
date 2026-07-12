"""
extract_ideam_clima.py — Descarga datos climáticos del IDEAM desde Socrata.

ESTRATEGIA ULTRA-OPTIMIZADA (V4 — corregida):
  - Consulta MES POR MES.
  - No usamos funciones date_extract en el servidor (son muy lentas).
  - Agregamos el año y mes en Python después de recibir los datos.

CORRECCIONES V4.1:
  - FIX: bucle for/else + break exterior no salía correctamente al terminar el año en curso.
  - FIX: condición de mes futuro usaba break en lugar de continue, lo que activaba
         la salida del bucle exterior por el mecanismo for/else.
  - FIX: total_valor y promedio_valor ya no son asignados igual; se diferencian
         según la función de agregación usada (sum vs avg).
  - FIX: divisiones por cero en promedio ponderado ahora se registran como NaN
         y se reportan con un warning en lugar de rellenarse silenciosamente con 0.
  - FIX: un bloque fallido ya no descarta bloques anteriores exitosos; se retorna
         lo parcialmente descargado con una advertencia.
  - FIX: consecutive_failures se reinicia al cambiar de año.
  - FIX: el cache se valida al cargarlo; si está vacío o corrupto se re-descarga.
"""
import requests
import pandas as pd
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from config.settings import SOURCES, DATA_RAW, CLIMA_YEAR_START, YEAR_END, SOCRATA_TOKEN

logger = logging.getLogger(__name__)

TIMEOUT = 120
MAX_RETRIES = 3
MAX_CONSECUTIVE_FAILURES = 3


def _load_cache(path: Path) -> pd.DataFrame | None:
    """
    Carga un archivo parquet de cache con validación básica.
    Retorna None si no existe, está vacío o está corrupto,
    para forzar una re-descarga en esos casos.
    """
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty:
            logger.warning(f"Cache vacío encontrado, se re-descargará: {path.name}")
            return None
        return df
    except Exception as e:
        logger.warning(f"Cache corrupto ({path.name}), se re-descargará: {e}")
        return None


def _download_month_fast(
    url: str,
    agg_func: str,
    anio: int,
    mes: int,
    include_sensor: bool = False,
) -> pd.DataFrame:
    """
    Descarga datos agregados de un mes fragmentando en bloques de 10 días
    para evitar timeouts.

    Si un bloque falla tras MAX_RETRIES intentos, se registra el error y se
    continúa con los bloques restantes (en lugar de abortar todo el mes).
    """
    headers = {}
    if SOCRATA_TOKEN:
        headers["X-App-Token"] = SOCRATA_TOKEN

    next_mes = mes + 1 if mes < 12 else 1
    next_anio = anio if mes < 12 else anio + 1
    start_date = datetime(anio, mes, 1)
    end_date = datetime(next_anio, next_mes, 1)

    # Construir lista de bloques de 10 días
    chunks = []
    current = start_date
    while current < end_date:
        next_current = min(current + timedelta(days=10), end_date)
        chunks.append((
            current.strftime("%Y-%m-%dT00:00:00"),
            next_current.strftime("%Y-%m-%dT00:00:00"),
        ))
        current = next_current

    all_rows = []
    failed_chunks = 0

    for start_str, end_str in chunks:
        where = f"fechaobservacion >= '{start_str}' AND fechaobservacion < '{end_str}'"

        if include_sensor:
            select = (
                f"codigoestacion, descripcionsensor, "
                f"{agg_func}(valorobservado) as valor_agregado, "
                f"count(*) as num_lecturas"
            )
            group = "codigoestacion, descripcionsensor"
        else:
            select = (
                f"codigoestacion, "
                f"{agg_func}(valorobservado) as valor_agregado, "
                f"count(*) as num_lecturas"
            )
            group = "codigoestacion"

        offset = 0
        limit = 50000
        chunk_ok = True

        while True:
            params = {
                "$select": select,
                "$group": group,
                "$where": where,
                "$limit": limit,
                "$offset": offset,
            }

            batch = []
            for attempt in range(MAX_RETRIES):
                try:
                    r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
                    r.raise_for_status()
                    batch = r.json()
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(5)
                    else:
                        logger.error(
                            f"      Bloque {start_str} falló tras {MAX_RETRIES} intentos: {e}. "
                            "Se omite este bloque pero se conservan los anteriores."
                        )
                        chunk_ok = False

            if not chunk_ok:
                failed_chunks += 1
                break  # pasa al siguiente bloque de 10 días

            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < limit:
                break
            offset += limit

    if failed_chunks:
        logger.warning(
            f"  {anio}-{mes:02d}: {failed_chunks}/{len(chunks)} bloques fallaron. "
            "Los datos del mes pueden estar incompletos."
        )

    if not all_rows:
        return pd.DataFrame()

    df_chunks = pd.DataFrame(all_rows)

    df_chunks["valor_agregado"] = pd.to_numeric(df_chunks["valor_agregado"], errors="coerce")
    df_chunks["num_lecturas"] = pd.to_numeric(df_chunks["num_lecturas"], errors="coerce").fillna(0)

    group_cols = ["codigoestacion", "descripcionsensor"] if include_sensor else ["codigoestacion"]

    if agg_func.lower() == "sum":
        df = df_chunks.groupby(group_cols, as_index=False).agg(
            total_valor=("valor_agregado", "sum"),
            num_lecturas=("num_lecturas", "sum"),
        )
        # Para suma, promedio_valor no tiene sentido semántico aquí,
        # pero lo dejamos como NaN para que clean_clima.py lo ignore explícitamente.
        df["promedio_valor"] = float("nan")

    elif agg_func.lower() == "avg":
        # Promedio ponderado real entre bloques
        df_chunks["suma_parcial"] = df_chunks["valor_agregado"] * df_chunks["num_lecturas"]
        df = df_chunks.groupby(group_cols, as_index=False).agg(
            suma_parcial=("suma_parcial", "sum"),
            num_lecturas=("num_lecturas", "sum"),
        )
        df["promedio_valor"] = df["suma_parcial"] / df["num_lecturas"]

        # Reportar NaN en lugar de enmascarar divisiones por cero
        n_nan = df["promedio_valor"].isna().sum()
        if n_nan:
            logger.warning(
                f"  {anio}-{mes:02d}: {n_nan} estaciones con num_lecturas=0 "
                "producen promedio NaN (se conservan como NaN, no se reemplazan por 0)."
            )

        df = df.drop(columns=["suma_parcial"])
        # total_valor no tiene sentido semántico para avg
        df["total_valor"] = float("nan")

    else:
        # Fallback genérico
        df = df_chunks.groupby(group_cols, as_index=False).agg(
            total_valor=("valor_agregado", agg_func),
            num_lecturas=("num_lecturas", "sum"),
        )
        df["promedio_valor"] = float("nan")

    df["anio"] = anio
    df["mes"] = mes
    return df


def _iter_anio_mes(year_start: int, year_end: int):
    """
    Generador que produce (anio, mes) desde year_start hasta el mes actual
    inclusive, sin sobrepasar year_end. Evita la lógica break/continue
    confusa dentro de los bucles anidados.
    """
    now = datetime.now()
    for anio in range(year_start, year_end + 1):
        for mes in range(1, 13):
            # No descargar meses futuros
            if anio == now.year and mes > now.month:
                return  # termina el generador limpiamente
            if anio > now.year:
                return
            yield anio, mes


def _extract_variable(
    url: str,
    agg_func: str,
    include_sensor: bool,
    out_dir: Path,
    cache_prefix: str,
    out_file: Path,
    variable_name: str,
) -> pd.DataFrame:
    """
    Lógica común de extracción para cualquier variable climática.
    Separa la lógica de iteración, cache y conteo de fallos del código
    específico de cada variable.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    all_dfs = []
    consecutive_failures = 0
    prev_anio = None

    for anio, mes in _iter_anio_mes(CLIMA_YEAR_START, YEAR_END):
        # Reiniciar el contador al cambiar de año
        if prev_anio is not None and anio != prev_anio:
            consecutive_failures = 0
        prev_anio = anio

        cache = out_dir / f"{cache_prefix}_{anio}_{mes:02d}.parquet"
        df_m = _load_cache(cache)

        if df_m is not None:
            consecutive_failures = 0
        else:
            df_m = _download_month_fast(url, agg_func, anio, mes, include_sensor=include_sensor)
            if not df_m.empty:
                df_m.to_parquet(cache, index=False)
                logger.info(f"  {anio}-{mes:02d}: {len(df_m)} registros descargados")
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(
                    f"  {variable_name} — {anio}-{mes:02d}: sin datos "
                    f"({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES} fallos consecutivos)"
                )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        f"{variable_name}: {consecutive_failures} meses consecutivos sin respuesta. "
                        "El servidor parece caído — se omite el resto de la descarga."
                    )
                    break

        if not df_m.empty:
            all_dfs.append(df_m)

    if all_dfs:
        df_all = pd.concat(all_dfs, ignore_index=True)
        df_all.to_parquet(out_file, index=False)
        return df_all

    logger.warning(
        f"{variable_name}: no se obtuvieron datos. "
        "El pipeline continuará sin esta variable."
    )
    return pd.DataFrame()


def extract_precipitacion_mensual() -> pd.DataFrame:
    """Precipitación mensual total por estación."""
    out_dir = DATA_RAW / "clima"
    logger.info("Descargando precipitación IDEAM (V4.1)...")
    return _extract_variable(
        url=SOURCES["precipitacion_ideam"],
        agg_func="sum",
        include_sensor=False,
        out_dir=out_dir,
        cache_prefix="precip_v4",
        out_file=out_dir / "precipitacion_mensual_total.parquet",
        variable_name="Precipitación IDEAM",
    )


def extract_clima_combinado_mensual() -> pd.DataFrame:
    """Variables climáticas combinadas (temperatura, humedad, etc.) por estación y sensor."""
    out_dir = DATA_RAW / "clima"
    logger.info("Descargando variables climáticas IDEAM (V4.1)...")
    return _extract_variable(
        url=SOURCES["clima_combinado_ideam"],
        agg_func="avg",
        include_sensor=True,
        out_dir=out_dir,
        cache_prefix="clima_v4",
        out_file=out_dir / "clima_combined_mensual_total.parquet",
        variable_name="Clima combinado IDEAM",
    )


def extract_all_clima() -> tuple[pd.DataFrame, pd.DataFrame]:
    return extract_precipitacion_mensual(), extract_clima_combinado_mensual()