"""
train_alerta_climatica.py — Alerta climática ANTICIPADA (riesgo del mes siguiente) por municipio.

Qué cambió y por qué
- Antes: el "riesgo" se etiquetaba con una regla y el clasificador aprendía esa misma regla desde las mismas
  columnas (evaluación circular: F1 alto no significaba nada) con split aleatorio y vacíos rellenados con 0.
- Ahora:
    * `_etiquetar_riesgo` es un ÍNDICE DE RIESGO POR REGLAS del mes observado (documentado, no un modelo).
    * El modelo predice el índice del MES SIGUIENTE a partir de lo observado hasta el mes actual:
      es un pronóstico real, evaluado con corte TEMPORAL (últimos meses fuera del entrenamiento) y
      comparado con la línea base "el mes siguiente repetirá el nivel actual" (persistencia).
    * Los vacíos se quedan como NaN (nunca 0) y solo se puntúan las reglas con datos disponibles.
- pred_alerta_climatica: `activa` = TRUE solo para el pronóstico vigente del mes siguiente al último mes
  con datos; los meses de prueba se guardan como historial fuera de muestra (activa = FALSE).

Uso:  python -m models.train_alerta_climatica
"""
import json
import logging

import numpy as np
import pandas as pd

from load.db import get_engine

logger = logging.getLogger(__name__)

MESES_PRUEBA = 6
ETIQUETAS = {0: "BAJO", 1: "MEDIO", 2: "ALTO"}
NOMBRE_MODELO = "xgboost_alerta_anticipada"
NOMBRE_BASE = "persistencia_alerta"

# Un solo registro por municipio y mes: promedio entre estaciones
TRAIN_SQL = """
SELECT fc.id_municipio, fc.id_tiempo, dt.anio, dt.mes,
       AVG(fc.precipitacion_mm)       AS precipitacion_mm,
       AVG(fc.temperatura_media_c)    AS temperatura_media_c,
       MAX(fc.temperatura_max_c)      AS temperatura_max_c,
       MIN(fc.temperatura_min_c)      AS temperatura_min_c,
       AVG(fc.humedad_relativa_pct)   AS humedad_relativa_pct,
       AVG(fc.brillo_solar_horas_dia) AS brillo_solar_horas_dia,
       MAX(ae.fase_enso)              AS fase_enso,
       AVG(ae.indice_oni)             AS indice_oni,
       AVG(ae.indice_spi)             AS indice_spi,
       AVG(ae.anomalia_precipitacion_pct) AS anomalia_precipitacion_pct
FROM fact_clima_mensual fc
JOIN dim_tiempo dt   ON dt.id_tiempo = fc.id_tiempo
JOIN dim_municipio m ON m.id_municipio = fc.id_municipio
LEFT JOIN fact_alerta_enso ae ON ae.id_tiempo = fc.id_tiempo AND ae.id_region = m.id_region
GROUP BY fc.id_municipio, fc.id_tiempo, dt.anio, dt.mes
"""

# Tipos de evento que la regla SÍ puede determinar con las variables disponibles.
# (Se quitó "Volatilidad de mercado", que nunca se asignaba, y "Plagas" pasa a ser una condición, no un evento.)
TIPOS_EVENTO = {
    "SEQUIA":         "Sequía severa",
    "EXCESO_LLUVIA":  "Exceso de lluvias",
    "ESTRES_TERMICO": "Estrés térmico",
    "PLAGAS":         "Condiciones propicias para plagas (regla)",
    "NORMAL":         "Sin evento crítico",
}


def _val(row, clave):
    """Valor numérico o None si falta (NaN ≠ 0)."""
    v = row.get(clave)
    return None if v is None or pd.isna(v) else float(v)


def _clasificar_tipo_evento(row) -> str:
    """Evento predominante del mes observado según las señales disponibles; sin datos no se asume nada."""
    spi, anom = _val(row, "indice_spi"), _val(row, "anomalia_precipitacion_pct")
    tmax, tmin = _val(row, "temperatura_max_c"), _val(row, "temperatura_min_c")
    hum = _val(row, "humedad_relativa_pct")
    if (spi is not None and spi < -1.0) or (anom is not None and anom < -40):
        return TIPOS_EVENTO["SEQUIA"]
    if (spi is not None and spi > 1.0) or (anom is not None and anom > 50):
        return TIPOS_EVENTO["EXCESO_LLUVIA"]
    if (tmax is not None and tmax > 36) or (tmin is not None and tmin < 4):
        return TIPOS_EVENTO["ESTRES_TERMICO"]
    if hum is not None and tmax is not None and hum > 80 and 22 <= tmax <= 32:
        return TIPOS_EVENTO["PLAGAS"]
    return TIPOS_EVENTO["NORMAL"]


def _etiquetar_riesgo(row) -> int:
    """
    Índice de riesgo por REGLAS (0 bajo, 1 medio, 2 alto) del mes observado. No es un modelo: es una
    definición documentada. Solo suma las reglas cuyas variables existen.
    """
    score = 0
    spi = _val(row, "indice_spi")
    if spi is not None:
        score += 3 if spi < -1.5 else 2 if spi < -1.0 else 1 if spi < -0.5 else 0
        score += 2 if spi > 1.5 else 1 if spi > 1.0 else 0
    anom = _val(row, "anomalia_precipitacion_pct")
    if anom is not None:
        score += 2 if abs(anom) > 50 else 1 if abs(anom) > 25 else 0
    tmax = _val(row, "temperatura_max_c")
    if tmax is not None:
        score += 2 if tmax > 38 else 1 if tmax > 35 else 0
    if str(row.get("fase_enso")) in ("El Niño", "La Niña"):
        score += 1
    return 2 if score >= 5 else 1 if score >= 2 else 0


# ── Dataset: rasgos del mes actual -> riesgo del mes siguiente ───────────
def construir_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    df: una fila por municipio-mes (ver TRAIN_SQL). Agrega el índice observado, rezagos y el OBJETIVO
    `y` = índice de riesgo del mes calendario siguiente (NaN si ese mes no existe: no se inventa).
    """
    df = df.sort_values(["id_municipio", "anio", "mes"]).reset_index(drop=True).copy()
    df["periodo"] = df["anio"].astype(int) * 12 + df["mes"].astype(int)
    df["riesgo_obs"] = [_etiquetar_riesgo(r) for r in df.to_dict("records")]

    siguiente = df[["id_municipio", "periodo", "riesgo_obs"]].copy()
    siguiente["periodo"] -= 1                         # el mes t+1 aporta su valor a la fila del mes t
    df = df.merge(siguiente.rename(columns={"riesgo_obs": "y"}), on=["id_municipio", "periodo"], how="left")

    previo = df[["id_municipio", "periodo", "precipitacion_mm", "anomalia_precipitacion_pct", "riesgo_obs"]].copy()
    previo["periodo"] += 1                            # el mes t-1 aporta su valor a la fila del mes t
    previo = previo.rename(columns={c: f"{c}_lag1" for c in ("precipitacion_mm", "anomalia_precipitacion_pct", "riesgo_obs")})
    df = df.merge(previo, on=["id_municipio", "periodo"], how="left")

    df["mes_sin"] = np.sin(2 * np.pi * df["mes"] / 12)
    df["mes_cos"] = np.cos(2 * np.pi * df["mes"] / 12)
    return df


FEATURES = [
    "precipitacion_mm", "temperatura_media_c", "temperatura_max_c", "temperatura_min_c",
    "humedad_relativa_pct", "brillo_solar_horas_dia", "indice_oni", "indice_spi", "anomalia_precipitacion_pct",
    "precipitacion_mm_lag1", "anomalia_precipitacion_pct_lag1", "riesgo_obs", "riesgo_obs_lag1",
    "mes_sin", "mes_cos",
]


def dividir_temporal(df: pd.DataFrame, meses_prueba: int = MESES_PRUEBA):
    """
    Corte temporal: los últimos `meses_prueba` meses con objetivo conocido son prueba; el entrenamiento solo
    usa filas cuyo mes objetivo (periodo + 1) ocurrió ANTES del inicio de la prueba.
    """
    con_y = df.dropna(subset=["y"])
    if con_y.empty:
        raise ValueError("Ningún mes tiene un mes siguiente con datos: no hay objetivo para entrenar")
    inicio_prueba = int(con_y["periodo"].max()) - meses_prueba + 1
    train = con_y[con_y["periodo"] + 1 < inicio_prueba]
    test = con_y[con_y["periodo"] >= inicio_prueba]
    return train, test


def metricas_clasificacion(y_real, y_pred) -> dict:
    from sklearn.metrics import accuracy_score, f1_score
    return {
        "f1_ponderado": float(f1_score(y_real, y_pred, average="weighted", zero_division=0)),
        "exactitud": float(accuracy_score(y_real, y_pred)),
        "n": int(len(y_real)),
    }


# ── Persistencia ─────────────────────────────────────────────────────────
def _guardar_predicciones(engine, df_pred: pd.DataFrame) -> None:
    from load.db import upsert
    from sqlalchemy import text

    cols = ["id_municipio", "id_tiempo", "nivel_riesgo", "tipo_evento", "score_probabilidad",
            "descripcion_generada", "activa", "id_version"]
    df_out = df_pred[cols].drop_duplicates(subset=["id_municipio", "id_tiempo"]).astype(object)
    df_out = df_out.where(df_out.notna(), None)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM pred_alerta_climatica"))       # las anteriores eran ajustes sobre el entrenamiento
    upsert(engine, "pred_alerta_climatica", df_out, ["id_municipio", "id_tiempo"])
    logger.info("pred_alerta_climatica: %s predicciones guardadas (%s vigentes)", len(df_out), int(df_out["activa"].sum()))


def train_and_report(engine=None) -> dict:
    """Entrena el pronóstico de riesgo del mes siguiente, lo evalúa fuera de muestra y guarda alertas."""
    from models.train_rendimiento import _registrar_version

    engine = engine or get_engine()
    df = pd.read_sql(TRAIN_SQL, engine)
    if df.empty:
        raise ValueError("No hay datos climáticos suficientes para entrenar el modelo de alertas. "
                         "Ejecuta primero el ETL core con datos IDEAM.")

    df = construir_dataset(df)
    train, test = dividir_temporal(df)
    X = lambda d: d[FEATURES].astype("float32")      # NaN se conserva
    logger.info("Alertas: %s filas de entrenamiento, %s de prueba (últimos %s meses)", len(train), len(test), MESES_PRUEBA)

    base_test = metricas_clasificacion(test["y"].astype(int), test["riesgo_obs"].astype(int))
    tiene_modelo = train["y"].nunique() >= 2
    if tiene_modelo:
        from xgboost import XGBClassifier
        modelo = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05, subsample=0.85,
                               colsample_bytree=0.85, random_state=42, eval_metric="mlogloss")
        clases = sorted(train["y"].astype(int).unique())
        idx = {c: i for i, c in enumerate(clases)}
        modelo.fit(X(train), train["y"].astype(int).map(idx))
        predecir = lambda d: np.array(clases)[modelo.predict(X(d))]
        probas = lambda d: modelo.predict_proba(X(d)).max(axis=1)
        m_test = metricas_clasificacion(test["y"].astype(int), predecir(test))
        nombre = NOMBRE_MODELO
    else:
        logger.warning("Una sola clase en el entrenamiento: se usa la persistencia como pronóstico")
        predecir = lambda d: d["riesgo_obs"].astype(int).to_numpy()
        probas = lambda d: np.full(len(d), np.nan)
        m_test, nombre = base_test, NOMBRE_BASE

    metrics = {
        "evaluacion": f"Fuera de muestra: últimos {MESES_PRUEBA} meses con objetivo conocido; el modelo predice el riesgo del mes siguiente",
        "tipo": "pronostico_mes_siguiente",
        "f1_weighted": m_test["f1_ponderado"], "exactitud": m_test["exactitud"], "n_test": m_test["n"], "n_train": int(len(train)),
        "linea_base": {"descripcion": "el mes siguiente repite el nivel de riesgo actual (persistencia)", **base_test},
        "distribucion_y_test": {ETIQUETAS[int(k)]: int(v) for k, v in test["y"].astype(int).value_counts().items()},
        "nota_etiqueta": "El riesgo se define con un índice por reglas (no hay etiquetas históricas validadas por expertos)",
        "n_features": len(FEATURES),
    }
    logger.info("Alertas %s | F1=%.3f (persistencia %.3f) sobre %s filas de prueba",
                nombre, m_test["f1_ponderado"], base_test["f1_ponderado"], m_test["n"])
    id_version = _registrar_version(engine, nombre, metrics)

    # Historial fuera de muestra (activa=False) + pronóstico vigente del mes siguiente al último mes con datos (activa=True)
    tiempos = pd.read_sql("SELECT id_tiempo, anio, mes FROM dim_tiempo", engine)
    ult = df[df["periodo"] == df["periodo"].max()].copy()
    ult["periodo"] += 1                                   # el pronóstico vigente es del mes siguiente
    ult["anio_obj"], ult["mes_obj"] = (ult["periodo"] - 1) // 12, (ult["periodo"] - 1) % 12 + 1
    ult = ult.merge(tiempos, left_on=["anio_obj", "mes_obj"], right_on=["anio", "mes"], how="inner", suffixes=("_obs", ""))
    historial = test.copy()

    def _armar(d, activa, id_t):
        pred = predecir(d)
        p = probas(d)
        out = pd.DataFrame({
            "id_municipio": d["id_municipio"].to_numpy(),
            "id_tiempo": id_t,
            "nivel_riesgo": [ETIQUETAS[int(c)] for c in pred],
            "tipo_evento": [_clasificar_tipo_evento(r) for r in d.to_dict("records")],
            "score_probabilidad": p,
            "activa": activa,
            "id_version": id_version,
        })
        out["descripcion_generada"] = [
            f"Riesgo previsto {r.nivel_riesgo} para el mes siguiente"
            + ("" if np.isnan(r.score_probabilidad) else f" (probabilidad {r.score_probabilidad:.0%})")
            + f". Condición del último mes observado: {r.tipo_evento}."
            for r in out.itertuples()
        ]
        return out

    partes = [_armar(historial, False, historial["id_tiempo"].to_numpy())]     # id_tiempo = mes observado
    if not ult.empty:
        partes.append(_armar(ult, True, ult["id_tiempo"].to_numpy()))          # id_tiempo = mes previsto
    pred_all = pd.concat(partes, ignore_index=True)
    # Si un municipio-mes aparece en ambos grupos, gana el pronóstico vigente
    pred_all = pred_all.sort_values("activa").drop_duplicates(subset=["id_municipio", "id_tiempo"], keep="last")
    _guardar_predicciones(engine, pred_all)

    return {"model_name": nombre, "metrics": metrics, "n_predicciones": int(len(pred_all))}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    result = train_and_report()
    print(json.dumps({k: v for k, v in result.items() if k != "metrics"}, indent=2, ensure_ascii=False))
    print(f"\nF1 ponderado (fuera de muestra): {result['metrics']['f1_weighted']:.4f}")
