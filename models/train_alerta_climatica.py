"""
train_alerta_climatica.py — Clasificador de Riesgo Climático AgroIA Colombia

Genera alertas de nivel BAJO / MEDIO / ALTO por municipio y periodo,
cruzando datos climáticos IDEAM con la fase ENSO activa.

Escribe resultados en:
    - model_version     (registro de la versión con métricas)
    - pred_alerta_climatica (predicciones por municipio/tiempo)

Uso:
    python -m models.train_alerta_climatica
"""
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from load.db import get_engine

logger = logging.getLogger(__name__)

# ── SQL para construir el dataset de entrenamiento ──────────────────────────
TRAIN_SQL = """
WITH enso_municipio AS (
    SELECT
        m.id_municipio,
        dt.anio,
        dt.mes,
        dt.id_tiempo,
        ae.fase_enso,
        ae.indice_spi,
        ae.anomalia_precipitacion_pct,
        ae.probabilidad_deficit_hidrico,
        ae.probabilidad_exceso_hidrico
    FROM dim_municipio m
    JOIN dim_region_natural rn ON rn.id_region = m.id_region
    JOIN fact_alerta_enso ae ON ae.id_region = rn.id_region
    JOIN dim_tiempo dt ON dt.id_tiempo = ae.id_tiempo
)
SELECT
    fc.id_municipio,
    fc.id_tiempo,
    dt.anio,
    dt.mes,
    fc.precipitacion_mm,
    fc.temperatura_media_c,
    fc.temperatura_max_c,
    fc.temperatura_min_c,
    fc.humedad_relativa_pct,
    fc.brillo_solar_horas_dia,
    COALESCE(em.fase_enso, 'Neutro')             AS fase_enso,
    COALESCE(em.indice_spi, 0)                   AS indice_spi,
    COALESCE(em.anomalia_precipitacion_pct, 0)   AS anomalia_precipitacion_pct,
    COALESCE(em.probabilidad_deficit_hidrico, 0) AS prob_deficit,
    COALESCE(em.probabilidad_exceso_hidrico, 0)  AS prob_exceso
FROM fact_clima_mensual fc
JOIN dim_tiempo dt ON dt.id_tiempo = fc.id_tiempo
LEFT JOIN enso_municipio em
    ON em.id_municipio = fc.id_municipio
   AND em.id_tiempo = fc.id_tiempo
"""

# ── Categorías de tipo de evento (consistente entre dashboard y chat) ─────
TIPOS_EVENTO = {
    "SEQUIA":        "Sequía severa",
    "EXCESO_LLUVIA": "Exceso de lluvias",
    "ESTRES_TERMICO":"Estrés térmico",
    "PLAGAS":        "Plagas y enfermedades",
    "MERCADO":       "Volatilidad de mercado",
    "NORMAL":        "Sin evento crítico",
}


def _clasificar_tipo_evento(row: pd.Series) -> str:
    """
    Clasifica el tipo de evento agronómico predominante.
    Usa señales climáticas reales (SPI, anomalía, temperatura) en lugar de
    la fase ENSO genérica.
    """
    spi      = float(row.get("indice_spi", 0) or 0)
    anomalia = float(row.get("anomalia_precipitacion_pct", 0) or 0)
    pdef     = float(row.get("prob_deficit", 0) or 0)
    pexc     = float(row.get("prob_exceso", 0) or 0)
    tmax     = float(row.get("temperatura_max_c", 0) or 0)
    tmin     = float(row.get("temperatura_min_c", 0) or 0)
    hum      = float(row.get("humedad_relativa_pct", 0) or 0)

    # Sequía: SPI muy negativo, déficit hídrico alto o anomalía negativa fuerte
    if spi < -1.0 or pdef > 0.7 or anomalia < -40:
        return TIPOS_EVENTO["SEQUIA"]

    # Exceso de lluvia: SPI positivo alto, prob exceso alta, anomalía positiva fuerte
    if spi > 1.0 or pexc > 0.7 or anomalia > 50:
        return TIPOS_EVENTO["EXCESO_LLUVIA"]

    # Estrés térmico: temperatura máxima extrema
    if tmax > 36 or tmin < 4:
        return TIPOS_EVENTO["ESTRES_TERMICO"]

    # Plagas y enfermedades: humedad alta + temperatura cálida
    if hum > 80 and 22 <= tmax <= 32:
        return TIPOS_EVENTO["PLAGAS"]

    return TIPOS_EVENTO["NORMAL"]


# ── Etiquetado heurístico de riesgo ─────────────────────────────────────────
def _etiquetar_riesgo(row: pd.Series) -> str:
    """
    Regla heurística para generar la etiqueta de entrenamiento cuando no hay
    etiquetas históricas reales. Se puede sustituir por datos validados por expertos.
    """
    score = 0

    # SPI negativo = déficit hídrico
    spi = row.get("indice_spi", 0) or 0
    if spi < -1.5:
        score += 3
    elif spi < -1.0:
        score += 2
    elif spi < -0.5:
        score += 1

    # SPI positivo extremo = exceso hídrico
    if spi > 1.5:
        score += 2
    elif spi > 1.0:
        score += 1

    # Anomalía de precipitación
    anomalia = row.get("anomalia_precipitacion_pct", 0) or 0
    if abs(anomalia) > 50:
        score += 2
    elif abs(anomalia) > 25:
        score += 1

    # Probabilidad de déficit o exceso
    if (row.get("prob_deficit", 0) or 0) > 0.7:
        score += 2
    if (row.get("prob_exceso", 0) or 0) > 0.7:
        score += 2

    # Temperatura extrema
    temp_max = row.get("temperatura_max_c", 0) or 0
    if temp_max > 38:
        score += 2
    elif temp_max > 35:
        score += 1

    # Fase ENSO
    fase = str(row.get("fase_enso", "Neutro"))
    if fase in ("El Niño", "La Niña"):
        score += 1

    if score >= 5:
        return "ALTO"
    elif score >= 2:
        return "MEDIO"
    return "BAJO"


def load_training_frame(engine) -> pd.DataFrame:
    try:
        df = pd.read_sql(TRAIN_SQL, engine)
        logger.info("Dataset climático: %s registros cargados", len(df))
        return df
    except Exception as exc:
        logger.error("Error cargando dataset de entrenamiento climático: %s", exc)
        return pd.DataFrame()


def _encode_fase_enso(series: pd.Series) -> pd.Series:
    mapping = {"El Niño": 1, "La Niña": -1, "Neutro": 0}
    return series.map(mapping).fillna(0).astype(int)


def train_and_report(engine=None) -> dict:
    """
    Entrena el clasificador de alerta climática y persiste resultados en la BD.

    Returns:
        dict con model_name, metrics y n_predicciones
    """
    if engine is None:
        engine = get_engine()

    df = load_training_frame(engine)
    if df.empty:
        raise ValueError(
            "No hay datos climáticos suficientes para entrenar el modelo de alertas. "
            "Ejecuta primero el pipeline ETL core con datos IDEAM."
        )

    # ── Etiquetado ──────────────────────────────────────────────────────────
    df["nivel_riesgo"] = df.apply(_etiquetar_riesgo, axis=1)
    logger.info("Distribución de etiquetas:\n%s", df["nivel_riesgo"].value_counts().to_string())

    # ── Features ────────────────────────────────────────────────────────────
    df["fase_enso_enc"] = _encode_fase_enso(df["fase_enso"])
    feature_cols = [
        "precipitacion_mm",
        "temperatura_media_c",
        "temperatura_max_c",
        "temperatura_min_c",
        "humedad_relativa_pct",
        "brillo_solar_horas_dia",
        "fase_enso_enc",
        "indice_spi",
        "anomalia_precipitacion_pct",
        "prob_deficit",
        "prob_exceso",
        "anio",
        "mes",
    ]
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    label_map = {"BAJO": 0, "MEDIO": 1, "ALTO": 2}
    y = df["nivel_riesgo"].map(label_map)

    # ── Verificar que hay al menos 2 clases ──────────────────────────────────
    n_clases = y.nunique()
    if n_clases < 2:
        logger.warning(
            "Solo una clase de riesgo presente (%s). "
            "Se necesitan datos ENSO con SPI/anomalía diversificados para entrenar. "
            "Guardando predicciones heurísticas sin modelo supervisado.",
            df["nivel_riesgo"].unique().tolist(),
        )
        metrics = {"f1_weighted": 0.0, "note": "single_class_no_model"}
        id_version = _registrar_version(engine, "heuristica_alerta_climatica", metrics)
        # Guardar las predicciones heurísticas directamente
        df_pred = df[["id_municipio", "id_tiempo"]].copy()
        df_pred["nivel_riesgo"]       = df["nivel_riesgo"].values
        df_pred["tipo_evento"]        = df.apply(_clasificar_tipo_evento, axis=1).values
        df_pred["score_probabilidad"] = 0.5
        df_pred["descripcion_generada"] = df_pred.apply(
            lambda r: f"Alerta {r['nivel_riesgo']} — {r['tipo_evento']} (heurística).",
            axis=1,
        )
        df_pred["activa"]     = True
        df_pred["id_version"] = id_version
        _guardar_predicciones(engine, df_pred)
        return {"model_name": "heuristica_alerta_climatica", "metrics": metrics, "n_predicciones": len(df_pred)}

    # ── Dividir datos ────────────────────────────────────────────────────────
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, f1_score

    class_counts = y.value_counts()
    stratify_arg = y if not class_counts.empty and class_counts.min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify_arg
    )

    # ── Modelo ───────────────────────────────────────────────────────────────
    try:
        from xgboost import XGBClassifier
        model = XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            use_label_encoder=False,
            eval_metric="mlogloss",
        )
        model_name = "xgboost_alerta_climatica"
    except ImportError:
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        model_name = "random_forest_alerta_climatica"

    model.fit(X_train, y_train)
    pred_test = model.predict(X_test)

    inv_label_map = {v: k for k, v in label_map.items()}
    labels_present = sorted(set(y_test.tolist()) | set(pred_test.tolist()))
    metrics = {
        "f1_weighted": float(f1_score(y_test, pred_test, average="weighted")),
        "report": classification_report(
            y_test,
            pred_test,
            labels=labels_present,
            target_names=[inv_label_map[label] for label in labels_present],
            output_dict=True,
            zero_division=0,
        ),
        "n_train": int(len(X_train)),
        "n_test":  int(len(X_test)),
    }
    logger.info("Modelo %s — F1 ponderado: %.4f", model_name, metrics["f1_weighted"])

    # ── Registrar versión en model_version ───────────────────────────────────
    id_version = _registrar_version(engine, model_name, metrics)

    # ── Generar predicciones para todos los registros ────────────────────────
    pred_todas = model.predict(X)
    score_todas = model.predict_proba(X)

    df_pred = df[["id_municipio", "id_tiempo"]].copy()
    df_pred["nivel_riesgo"]      = [inv_label_map[p] for p in pred_todas]
    df_pred["tipo_evento"]       = df.apply(_clasificar_tipo_evento, axis=1).values
    df_pred["score_probabilidad"] = score_todas.max(axis=1)
    df_pred["descripcion_generada"] = df_pred.apply(
        lambda r: (
            f"Alerta {r['nivel_riesgo']} — {r['tipo_evento']}. "
            f"Probabilidad estimada: {r['score_probabilidad']:.0%}."
        ),
        axis=1,
    )
    df_pred["activa"]     = True
    df_pred["id_version"] = id_version

    _guardar_predicciones(engine, df_pred)

    return {"model_name": model_name, "metrics": metrics, "n_predicciones": len(df_pred)}


# ── Helpers BD ───────────────────────────────────────────────────────────────

def _registrar_version(engine, model_name: str, metrics: dict) -> int | None:
    from sqlalchemy import text
    # Desactivar versiones anteriores del mismo modelo
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE model_version SET activo = FALSE WHERE nombre_modelo = :nm"),
            {"nm": model_name},
        )
    with engine.begin() as conn:
        from sqlalchemy import text as sqltext
        result = conn.execute(
            sqltext(
                "INSERT INTO model_version (nombre_modelo, fecha_entrenamiento, metricas_json, activo) "
                "VALUES (:nombre_modelo, :fecha_entrenamiento, :metricas_json, :activo) "
                "RETURNING id_version"
            ),
            {
                "nombre_modelo": model_name,
                "fecha_entrenamiento": datetime.utcnow().isoformat(),
                "metricas_json": json.dumps(metrics, ensure_ascii=False),
                "activo": True,
            },
        )
        row = result.fetchone()
    id_version = int(row[0]) if row else None
    logger.info("model_version registrado: %s (id=%s)", model_name, id_version)
    return id_version


def _guardar_predicciones(engine, df_pred: pd.DataFrame) -> None:
    from load.db import upsert
    cols = [
        "id_municipio", "id_tiempo", "nivel_riesgo",
        "tipo_evento", "score_probabilidad",
        "descripcion_generada", "activa", "id_version",
    ]
    df_out = df_pred[cols].drop_duplicates(subset=["id_municipio", "id_tiempo"])
    upsert(engine, "pred_alerta_climatica", df_out, ["id_municipio", "id_tiempo"])
    logger.info("pred_alerta_climatica: %s predicciones guardadas", len(df_out))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    result = train_and_report()
    print(json.dumps(
        {k: v for k, v in result.items() if k != "metrics"},
        indent=2, ensure_ascii=False,
    ))
    print(f"\nF1 ponderado: {result['metrics']['f1_weighted']:.4f}")
