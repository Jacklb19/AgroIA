"""
clean_clima.py — Limpieza y unificación de datos climáticos IDEAM.

Recibe DataFrames ya agregados a nivel mensual desde el extractor
(que usa SoQL del servidor Socrata) y los unifica en un solo DataFrame
alineado al schema de fact_clima_mensual.
"""
import pandas as pd
import numpy as np
import logging
from config.settings import DATA_PROCESSED

logger = logging.getLogger(__name__)


def unificar_clima_mensual(df_precip: pd.DataFrame,
                           df_combinado: pd.DataFrame) -> pd.DataFrame:
    """
    Unifica datos de precipitación y variables combinadas en un solo DataFrame
    con las columnas del schema de fact_clima_mensual.

    Ambos DataFrames vienen del extractor con columnas explícitas:
      codigoestacion, anio, mes, total_valor, promedio_valor,
      max_valor, min_valor, num_lecturas
    """
    result_dfs = []

    # --- Precipitación: ya viene como SUMA mensual ---
    if not df_precip.empty:
        df_p = df_precip.copy()
        if "total_valor" not in df_p.columns and "valor_agregado" in df_p.columns:
            df_p["total_valor"] = df_p["valor_agregado"]
        df_p = df_p.rename(columns={
            "codigoestacion": "id_estacion",
            "total_valor": "precipitacion_mm"
        })
        df_p["anio"] = pd.to_numeric(df_p["anio"], errors="coerce").astype("Int64")
        df_p["mes"] = pd.to_numeric(df_p["mes"], errors="coerce").astype("Int64")
        df_p["precipitacion_mm"] = pd.to_numeric(df_p["precipitacion_mm"], errors="coerce")
        
        # Filtro de calidad: Precipitación en rango [0, 3000] mm/mes
        df_p.loc[df_p["precipitacion_mm"] < 0, "precipitacion_mm"] = 0
        df_p.loc[df_p["precipitacion_mm"] > 3000, "precipitacion_mm"] = np.nan
        
        df_p = df_p[["id_estacion", "anio", "mes", "precipitacion_mm"]].dropna(
            subset=["id_estacion", "anio", "mes"]
        )
        result_dfs.append(df_p)
        logger.info(f"Precipitación mensual: {len(df_p)} registros")

    # --- Clima combinado: ya viene como PROMEDIO mensual ---
    # Este dataset mezcla variables (temperatura, humedad, etc.) diferenciadas por descripcionsensor.
    if not df_combinado.empty:
        df_c = df_combinado.copy()
        if "promedio_valor" not in df_c.columns and "valor_agregado" in df_c.columns:
            df_c["promedio_valor"] = df_c["valor_agregado"]
        if "max_valor" not in df_c.columns:
            df_c["max_valor"] = df_c.get("promedio_valor")
        if "min_valor" not in df_c.columns:
            df_c["min_valor"] = df_c.get("promedio_valor")
        for col in ["promedio_valor", "max_valor", "min_valor"]:
            df_c[col] = pd.to_numeric(df_c[col], errors="coerce")
        df_c["variable"] = "otro"
        sensor = df_c["descripcionsensor"].astype(str).str.lower()
        df_c.loc[sensor.str.contains("temperatura|temp", na=False), "variable"] = "temperatura_media_c"
        df_c.loc[sensor.str.contains("humedad", na=False), "variable"] = "humedad_relativa_pct"
        df_c.loc[sensor.str.contains("brillo|solar|radiaci", na=False), "variable"] = "brillo_solar_horas_dia"
        
        # Solo tomamos lo que nos interesa
        df_c = df_c[df_c["variable"] != "otro"]
        
        if not df_c.empty:
            df_c_pivot = df_c.pivot_table(
                index=["codigoestacion", "anio", "mes"],
                columns="variable",
                values=["promedio_valor", "max_valor", "min_valor"],
                aggfunc="mean",
            ).reset_index()

            df_c_pivot.columns = [
                "_".join([str(part) for part in col if part]).strip("_")
                if isinstance(col, tuple) else col
                for col in df_c_pivot.columns
            ]

            rename_cols = {
                "codigoestacion": "id_estacion",
                "promedio_valor_temperatura_media_c": "temperatura_media_c",
                "max_valor_temperatura_media_c": "temperatura_max_c",
                "min_valor_temperatura_media_c": "temperatura_min_c",
                "promedio_valor_humedad_relativa_pct": "humedad_relativa_pct",
                "promedio_valor_brillo_solar_horas_dia": "brillo_solar_horas_dia",
            }
            df_c_pivot = df_c_pivot.rename(columns=rename_cols)
            df_c_pivot["anio"] = pd.to_numeric(df_c_pivot["anio"], errors="coerce").astype("Int64")
            df_c_pivot["mes"] = pd.to_numeric(df_c_pivot["mes"], errors="coerce").astype("Int64")
            
            # Limpiar nulos en llaves
            df_c_pivot = df_c_pivot.dropna(subset=["id_estacion", "anio", "mes"])
            
            # Filtros de calidad: Temperatura en [-10, 50], Humedad en [0, 100]
            for t_col in ["temperatura_media_c", "temperatura_max_c", "temperatura_min_c"]:
                if t_col in df_c_pivot.columns:
                    df_c_pivot.loc[(df_c_pivot[t_col] < -10) | (df_c_pivot[t_col] > 50), t_col] = np.nan
            
            if "humedad_relativa_pct" in df_c_pivot.columns:
                df_c_pivot.loc[(df_c_pivot["humedad_relativa_pct"] < 0) | (df_c_pivot["humedad_relativa_pct"] > 100), "humedad_relativa_pct"] = np.nan
                
            result_dfs.append(df_c_pivot)
            logger.info(f"Clima combinado mensual: {len(df_c_pivot)} registros unificados")

    if not result_dfs:
        logger.warning("Sin datos climáticos para unificar")
        return pd.DataFrame()

    # Unir precipitación + temperatura por estación/año/mes
    if len(result_dfs) == 2:
        result = result_dfs[0].merge(result_dfs[1], on=["id_estacion", "anio", "mes"], how="outer")
    else:
        result = result_dfs[0]

    # Asegurar columnas del schema (rellenar con None las que no tenemos aún)
    for col in ["precipitacion_mm"]:
        if col not in result.columns:
            result[col] = None

    out = DATA_PROCESSED / "clima_mensual.parquet"
    result.to_parquet(out, index=False)
    logger.info(f"Clima mensual unificado: {len(result)} registros -> {out}")
    return result
