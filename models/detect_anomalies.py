"""
detect_anomalies.py — Detección de anomalías de rendimiento por cultivo.

Usa IsolationForest sobre series anuales de rendimiento (rendimiento_t_ha,
desviación interanual, anomalía vs. promedio del cultivo). Marca la columna
`pred_rendimiento.es_anomalia` para alimentar dashboards y el chat.
"""
import logging

import numpy as np
import pandas as pd

from load.db import get_engine

logger = logging.getLogger(__name__)


def _ensure_anomalia_columns(engine) -> bool:
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE pred_rendimiento ADD COLUMN IF NOT EXISTS es_anomalia BOOLEAN DEFAULT FALSE"))
            conn.execute(text("ALTER TABLE pred_rendimiento ADD COLUMN IF NOT EXISTS anomalia_score NUMERIC"))
        return True
    except Exception as e:
        logger.warning("No se pudo asegurar columnas de anomalía: %s", e)
        return False


def detect_and_persist(engine=None) -> dict:
    """Calcula score de anomalía por (cultivo, año, municipio) y persiste."""
    if engine is None:
        engine = get_engine()

    df = pd.read_sql(
        """
        SELECT pr.id_municipio, pr.id_cultivo, pr.id_tiempo,
               pr.rendimiento_predicho_t_ha AS yhat,
               c.nombre_cultivo,
               t.anio
        FROM pred_rendimiento pr
        JOIN dim_cultivo c ON c.id_cultivo = pr.id_cultivo
        JOIN dim_tiempo  t ON t.id_tiempo  = pr.id_tiempo
        """,
        engine,
    )
    if df.empty:
        logger.warning("No hay predicciones para evaluar anomalías.")
        return {"detectadas": 0, "total": 0}

    if not _ensure_anomalia_columns(engine):
        return {"detectadas": 0, "total": len(df)}

    from sklearn.ensemble import IsolationForest

    df = df.sort_values(["nombre_cultivo", "id_municipio", "anio"]).copy()
    df["delta_anual"] = (
        df.groupby(["nombre_cultivo", "id_municipio"])["yhat"].diff().fillna(0)
    )
    df["promedio_cultivo"] = df.groupby("nombre_cultivo")["yhat"].transform("mean")
    df["anomalia_vs_cultivo"] = df["yhat"] - df["promedio_cultivo"]

    detectadas_total = 0
    df["es_anomalia"]    = False
    df["anomalia_score"] = 0.0

    for cultivo, sub in df.groupby("nombre_cultivo"):
        if len(sub) < 20:
            continue
        X = sub[["yhat", "delta_anual", "anomalia_vs_cultivo"]].fillna(0).values
        iso = IsolationForest(
            n_estimators=200,
            contamination=0.07,
            random_state=42,
            n_jobs=-1,
        )
        iso.fit(X)
        labels = iso.predict(X)
        scores = -iso.score_samples(X)
        df.loc[sub.index, "es_anomalia"]    = labels == -1
        df.loc[sub.index, "anomalia_score"] = scores
        detectadas_total += int((labels == -1).sum())

    from sqlalchemy import text
    payload = df[["id_municipio", "id_cultivo", "id_tiempo", "es_anomalia", "anomalia_score"]].to_dict("records")
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE pred_rendimiento
                SET es_anomalia = :es_anomalia,
                    anomalia_score = :anomalia_score
                WHERE id_municipio = :id_municipio
                  AND id_cultivo   = :id_cultivo
                  AND id_tiempo    = :id_tiempo
            """),
            payload,
        )

    logger.info(
        "Anomalías: %s detectadas sobre %s predicciones (%.1f%%)",
        detectadas_total, len(df), 100 * detectadas_total / max(1, len(df)),
    )
    return {"detectadas": detectadas_total, "total": int(len(df))}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    print(detect_and_persist())
