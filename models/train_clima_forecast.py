"""
train_clima_forecast.py — Pronóstico climático mensual.

Usa Holt-Winters (statsmodels.tsa.holtwinters) para pronosticar precipitación
y temperatura por municipio, 6 meses hacia adelante. Persiste en
pred_clima_forecast (creada si no existe).

Es un modelo de series temporales con estacionalidad multiplicativa, alineado
con el nivel avanzado (analítica predictiva avanzada sobre datos abiertos).
"""
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from load.db import get_engine

logger = logging.getLogger(__name__)


_DDL = """
CREATE TABLE IF NOT EXISTS pred_clima_forecast (
    id              SERIAL PRIMARY KEY,
    id_municipio    CHAR(5) NOT NULL,
    fecha           DATE    NOT NULL,
    horizonte_meses SMALLINT NOT NULL,
    precipitacion_mm   DOUBLE PRECISION,
    temperatura_med_c  DOUBLE PRECISION,
    metodo          VARCHAR(50) NOT NULL DEFAULT 'holt_winters',
    fecha_calculo   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_municipio, fecha, horizonte_meses)
);
"""


def _ensure_table(engine) -> None:
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(_DDL))


def _forecast_serie(serie: pd.Series, horizon: int) -> np.ndarray | None:
    """Holt-Winters aditivo, fallback a media móvil si falla."""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        model = ExponentialSmoothing(
            serie.astype(float),
            trend="add",
            seasonal="add",
            seasonal_periods=12,
            initialization_method="estimated",
        ).fit(optimized=True)
        return model.forecast(horizon).values
    except Exception:
        try:
            avg = float(serie.tail(12).mean())
            return np.array([avg] * horizon, dtype=float)
        except Exception:
            return None


def forecast_and_persist(engine=None, horizonte_meses: int = 6) -> dict:
    if engine is None:
        engine = get_engine()
    _ensure_table(engine)

    df = pd.read_sql(
        """
        SELECT fc.id_municipio,
               t.fecha,
               fc.precipitacion_mm,
               fc.temperatura_media_c
        FROM fact_clima_mensual fc
        JOIN dim_tiempo t ON t.id_tiempo = fc.id_tiempo
        ORDER BY fc.id_municipio, t.fecha
        """,
        engine,
    )
    if df.empty:
        logger.warning("Sin datos climáticos para entrenar.")
        return {"municipios": 0, "filas": 0}

    out_rows = []
    municipios_ok = 0

    for muni, sub in df.groupby("id_municipio"):
        sub = sub.dropna(subset=["fecha"]).sort_values("fecha")
        if len(sub) < 24:
            continue
        last_date = pd.to_datetime(sub["fecha"].iloc[-1])

        prec = _forecast_serie(sub.set_index("fecha")["precipitacion_mm"].asfreq("MS").interpolate(), horizonte_meses)
        tmp  = _forecast_serie(sub.set_index("fecha")["temperatura_media_c"].asfreq("MS").interpolate(), horizonte_meses)
        if prec is None or tmp is None:
            continue

        for h in range(horizonte_meses):
            fecha_h = (last_date + pd.DateOffset(months=h + 1)).date()
            out_rows.append({
                "id_municipio":      muni,
                "fecha":             fecha_h,
                "horizonte_meses":   h + 1,
                "precipitacion_mm":  float(max(0, prec[h])),
                "temperatura_med_c": float(tmp[h]),
                "metodo":            "holt_winters",
            })
        municipios_ok += 1

    if not out_rows:
        logger.warning("Ningún municipio con suficiente historial (>= 24 meses).")
        return {"municipios": 0, "filas": 0}

    out = pd.DataFrame(out_rows)
    from load.db import upsert
    upsert(engine, "pred_clima_forecast", out, ["id_municipio", "fecha", "horizonte_meses"])

    logger.info(
        "Forecast climático: %s municipios × %s meses = %s filas",
        municipios_ok, horizonte_meses, len(out),
    )
    return {"municipios": municipios_ok, "filas": int(len(out)), "horizonte": horizonte_meses}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    print(forecast_and_persist())
