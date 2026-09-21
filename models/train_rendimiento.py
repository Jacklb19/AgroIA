"""
train_rendimiento.py — Modelo de rendimiento agrícola (t/ha) por municipio × cultivo × año.

Diseño (honesto por construcción):
- Validación TEMPORAL POR AÑO: en cada fold se entrena solo con años anteriores al año validado.
  (Antes se usaba TimeSeriesSplit sobre filas ordenadas por municipio, que no es temporal.)
- Año de PRUEBA reservado: el último año con datos no se usa ni para entrenar ni para ajustar hiperparámetros.
  Las métricas que se publican (R², MAE, RMSE) son de ese año, junto con una línea base
  ("el promedio histórico del municipio × cultivo").
- Solo se guardan predicciones FUERA DE MUESTRA (cada fila se predice con un modelo que no vio su año):
  pred_rendimiento.es_holdout = TRUE. Nunca se guardan ajustes sobre el propio entrenamiento.
- Intervalos p10–p90 calibrados con los residuos reales de la validación (por cultivo cuando hay
  suficientes datos), no ±MAE. Se reporta su cobertura en el año de prueba.
- Los vacíos se quedan como NaN (XGBoost los maneja): jamás se rellenan con 0.
"""
import json
import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd

from load.db import get_engine
from models.build_features import build_ml_features

logger = logging.getLogger(__name__)

N_TRIALS_OPTUNA = int(os.getenv("OPTUNA_TRIALS", "60"))
CV_FOLDS = 3
MIN_TRAIN_YEARS = 3          # años mínimos de entrenamiento en el primer fold
RANDOM_SEED = 42
MIN_RESIDUOS_CULTIVO = 30    # mínimo de residuos para calibrar intervalos por cultivo
NOMBRE_MODELO_XGB = "xgboost_rendimiento"

# Columnas que NO son rasgos: identificadores, objetivo y variables que no se conocen al sembrar.
# area_cosechada_ha solo se conoce después de cosechar y determina el rendimiento (producción / área
# cosechada): usarla como rasgo sería fuga de información.
_DROP_COLS = [
    "id_municipio", "id_cultivo", "id_tiempo", "anio",
    "id_departamento", "clase_aptitud", "es_anio_nino",
    "rendimiento_t_ha", "produccion_total_ton", "area_cosechada_ha",
]


# ── Utilidades puras (testeadas sin BD) ──────────────────────────────────
def year_splits(anios, n_splits: int = CV_FOLDS, min_train: int = MIN_TRAIN_YEARS):
    """
    Folds temporales por año (ventana creciente): entrena con años < y y valida en y.
    Retorna [(años_entrenamiento, año_validación), ...] con los últimos `n_splits` años validables.
    """
    anios = sorted(set(int(a) for a in anios))
    validables = anios[min_train:]
    if not validables:
        raise ValueError(f"Historia insuficiente: {len(anios)} años, se necesitan al menos {min_train + 1}")
    return [([a for a in anios if a < y], y) for y in validables[-n_splits:]]


def metricas_regresion(y_real, y_pred) -> dict:
    y_real, y_pred = np.asarray(y_real, float), np.asarray(y_pred, float)
    err = y_real - y_pred
    ss_tot = float(((y_real - y_real.mean()) ** 2).sum())
    return {
        "mae": float(np.abs(err).mean()),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "r2": float(1 - (err ** 2).sum() / ss_tot) if ss_tot > 0 else float("nan"),
        "n": int(len(y_real)),
    }


def _cuantiles(res) -> tuple[float, float]:
    return float(np.quantile(res, 0.10)), float(np.quantile(res, 0.90))


def calibrar_intervalos(oof: pd.DataFrame, anio_prueba: int) -> pd.DataFrame:
    """
    Agrega `lo` y `hi` (p10 y p90 de la predicción) a las filas fuera de muestra.
    Los cuantiles salen de los residuos de la validación de OTROS años (el residuo de una fila nunca
    calibra su propio intervalo) y los residuos del año de prueba no calibran a nadie.
    Por cultivo si hay >= MIN_RESIDUOS_CULTIVO residuos; si no, globales.
    """
    oof = oof.copy()
    oof["res"] = oof["y"] - oof["yhat"]
    calibracion = oof[oof["anio"] != anio_prueba]
    lo = np.full(len(oof), np.nan)
    hi = np.full(len(oof), np.nan)
    for anio in oof["anio"].unique():
        base = calibracion[calibracion["anio"] != anio]
        if base.empty:
            continue
        g_lo, g_hi = _cuantiles(base["res"])
        por_cultivo = {
            c: _cuantiles(g["res"]) for c, g in base.groupby("id_cultivo") if len(g) >= MIN_RESIDUOS_CULTIVO
        }
        filas = np.flatnonzero((oof["anio"] == anio).to_numpy())
        for i in filas:
            q = por_cultivo.get(oof["id_cultivo"].iat[i], (g_lo, g_hi))
            lo[i], hi[i] = oof["yhat"].iat[i] + q[0], oof["yhat"].iat[i] + q[1]
    oof["lo"], oof["hi"] = np.maximum(lo, 0), hi     # un rendimiento no puede ser negativo
    return oof


# ── Persistencia ─────────────────────────────────────────────────────────
def _registrar_version(engine, model_name: str, metrics: dict) -> int:
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE model_version SET activo = FALSE WHERE nombre_modelo = :nm"),
            {"nm": model_name},
        )
        result = conn.execute(
            text(
                "INSERT INTO model_version "
                "(nombre_modelo, fecha_entrenamiento, metricas_json, activo) "
                "VALUES (:nombre_modelo, :fecha_entrenamiento, :metricas_json, :activo) "
                "RETURNING id_version"
            ),
            {
                "nombre_modelo":       model_name,
                "fecha_entrenamiento": datetime.utcnow().isoformat(),
                "metricas_json":       json.dumps(metrics, ensure_ascii=False),
                "activo":              True,
            },
        )
        row = result.fetchone()
    id_version = int(row[0]) if row else None
    logger.info("model_version: id=%s (%s) registrado", id_version, model_name)
    return id_version


def _ensure_columns(engine) -> None:
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE pred_rendimiento ADD COLUMN IF NOT EXISTS shap_top JSONB"))
        conn.execute(text("ALTER TABLE pred_rendimiento ADD COLUMN IF NOT EXISTS es_holdout BOOLEAN NOT NULL DEFAULT FALSE"))


def _guardar_predicciones(engine, df_pred: pd.DataFrame, id_version: int | None) -> None:
    """Reemplaza TODAS las predicciones anteriores (eran ajustes sobre el entrenamiento) por las honestas."""
    from sqlalchemy import text
    from load.db import upsert

    df_pred = df_pred.copy()
    df_pred["id_version"] = id_version
    df_pred["es_holdout"] = True
    df_pred = df_pred.astype(object).where(df_pred.notna(), None)
    cols = ["id_municipio", "id_cultivo", "id_tiempo", "rendimiento_predicho_t_ha",
            "intervalo_confianza_inferior", "intervalo_confianza_superior", "id_version", "shap_top", "es_holdout"]
    for c in cols:
        if c not in df_pred.columns:
            df_pred[c] = None
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM pred_rendimiento"))
    upsert(engine, "pred_rendimiento", df_pred[cols], ["id_municipio", "id_cultivo", "id_tiempo"])
    logger.info("pred_rendimiento: %s predicciones fuera de muestra guardadas", len(df_pred))


# ── Modelo ───────────────────────────────────────────────────────────────
def _split_features(df: pd.DataFrame):
    df = df.dropna(subset=["rendimiento_t_ha"]).copy()
    feature_cols = [c for c in df.columns if c not in _DROP_COLS]
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").astype("float32")     # NaN se conserva
    y = df["rendimiento_t_ha"].astype(float)
    return df, X, y, feature_cols


def _crear_modelo(params: dict):
    try:
        from xgboost import XGBRegressor
        return XGBRegressor(**params, objective="reg:absoluteerror", random_state=RANDOM_SEED, n_jobs=-1, tree_method="hist"), "xgboost"
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor       # también acepta NaN
        return HistGradientBoostingRegressor(random_state=RANDOM_SEED), "hist_gradient_boosting"


_PARAMS_POR_DEFECTO = {
    "n_estimators": 400, "max_depth": 6, "learning_rate": 0.05, "subsample": 0.9,
    "colsample_bytree": 0.9, "min_child_weight": 3, "reg_alpha": 0.1, "reg_lambda": 1.0,
}


def _tune_with_optuna(df, X, y, n_trials: int) -> dict:
    """Ajuste bayesiano con la validación temporal por año (solo años de desarrollo, sin el año de prueba)."""
    splits = year_splits(df["anio"].unique())
    try:
        import optuna
        from xgboost import XGBRegressor

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial):
            params = {
                "n_estimators":     trial.suggest_int("n_estimators", 150, 600, step=50),
                "max_depth":        trial.suggest_int("max_depth", 4, 8),
                "learning_rate":    trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
                "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "reg_alpha":        trial.suggest_float("reg_alpha", 1e-3, 5.0, log=True),
                "reg_lambda":       trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
            }
            maes = []
            for anios_tr, anio_val in splits:
                tr, va = df["anio"].isin(anios_tr).to_numpy(), (df["anio"] == anio_val).to_numpy()
                base = _bases(df, tr)
                m = XGBRegressor(**params, objective="reg:absoluteerror", random_state=RANDOM_SEED, n_jobs=-1, tree_method="hist")
                m.fit(X[tr], (y - base)[tr], verbose=False)
                maes.append(float(np.abs(y[va] - (base[va] + m.predict(X[va]))).mean()))
            return float(np.mean(maes))

        study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
        logger.info("Optuna best params: %s | MAE CV=%.4f", study.best_params, study.best_value)
        return {**study.best_params, "cv_mae": float(study.best_value), "n_trials": n_trials}
    except Exception as e:
        logger.warning("Optuna tuning falló (%s). Uso parámetros por defecto.", e)
        return {**_PARAMS_POR_DEFECTO, "n_trials": 0}


def _bases(df: pd.DataFrame, entrenamiento) -> np.ndarray:
    """
    Línea base por fila: promedio histórico municipio×cultivo de años ANTERIORES; si el municipio no tiene
    historia, el promedio del cultivo calculado SOLO con las filas de entrenamiento (nunca con el año evaluado).
    """
    entrenamiento = np.asarray(entrenamiento, bool)
    base = df["rendimiento_t_ha_hist_avg"].to_numpy(dtype=float) if "rendimiento_t_ha_hist_avg" in df else np.full(len(df), np.nan)
    por_cultivo = df.loc[entrenamiento].groupby("id_cultivo")["rendimiento_t_ha"].mean()
    respaldo = df["id_cultivo"].map(por_cultivo).to_numpy(dtype=float)
    base = np.where(np.isnan(base), respaldo, base)
    return np.where(np.isnan(base), float(df.loc[entrenamiento, "rendimiento_t_ha"].mean()), base)


def _shap(modelo, X_test: pd.DataFrame, feature_cols: list[str], muestra: int = 1000):
    """SHAP global (top-10) y por fila (top-3 con signo) sobre el año de prueba."""
    try:
        import shap
        explainer = shap.TreeExplainer(modelo)
        idx = X_test.sample(min(muestra, len(X_test)), random_state=RANDOM_SEED).index
        vals = explainer.shap_values(X_test.loc[idx])
        importancia = np.abs(vals).mean(axis=0)
        top_global = [{"feature": f, "shap_abs_mean": float(v)}
                      for f, v in sorted(zip(feature_cols, importancia.tolist()), key=lambda kv: kv[1], reverse=True)[:10]]
        todo = explainer.shap_values(X_test)
        por_fila = []
        for i in range(todo.shape[0]):
            top = np.argsort(np.abs(todo[i]))[::-1][:3]
            por_fila.append(json.dumps([
                {"feature": feature_cols[j], "shap": float(todo[i, j]),
                 "value": None if pd.isna(X_test.iloc[i, j]) else float(X_test.iloc[i, j])}
                for j in top
            ], ensure_ascii=False))
        return top_global, por_fila
    except Exception as e:
        logger.warning("SHAP falló: %s", e)
        return [], None


def train_and_report(engine=None, n_trials: int | None = None) -> dict:
    """Entrena, evalúa en el año de prueba, guarda predicciones fuera de muestra y registra la versión."""
    engine = engine or get_engine()
    df = build_ml_features(engine)
    if df.empty:
        raise ValueError("No hay datos suficientes para entrenar el modelo")

    df, X, y, feature_cols = _split_features(df)
    df = df.reset_index(drop=True); X = X.reset_index(drop=True); y = y.reset_index(drop=True)
    anios = sorted(df["anio"].unique())
    anio_prueba = int(anios[-1])
    dev = (df["anio"] < anio_prueba).to_numpy()
    test = ~dev
    if len(set(anios[:-1])) <= MIN_TRAIN_YEARS:
        raise ValueError(f"Historia insuficiente: {len(anios)} años con datos (se necesitan al menos {MIN_TRAIN_YEARS + 2})")
    logger.info("Entrenamiento: %s filas de desarrollo (años %s-%s), %s de prueba (año %s), %s rasgos",
                int(dev.sum()), anios[0], anios[-2], int(test.sum()), anio_prueba, len(feature_cols))

    # 1) Hiperparámetros con validación temporal por año, solo con años de desarrollo
    best = _tune_with_optuna(df[dev], X[dev], y[dev], n_trials if n_trials is not None else N_TRIALS_OPTUNA)
    extra = {k: best.pop(k, None) for k in ("cv_mae", "n_trials")}

    # 2) Predicciones fuera de muestra de los años de validación (cada fila con un modelo que no vio su año)
    oof, cv_detalle = [], []
    for anios_tr, anio_val in year_splits(df.loc[dev, "anio"].unique()):
        tr, va = df["anio"].isin(anios_tr).to_numpy(), (df["anio"] == anio_val).to_numpy()
        base = _bases(df, tr)
        m, _ = _crear_modelo(best)
        m.fit(X[tr], (y - base)[tr])
        pred = base[va] + m.predict(X[va])
        oof.append(df.loc[va, ["id_municipio", "id_cultivo", "id_tiempo", "anio"]].assign(y=y[va].to_numpy(), yhat=pred))
        cv_detalle.append({"anio_validacion": int(anio_val), "n_train": int(tr.sum()), **metricas_regresion(y[va], pred)})

    # 3) Modelo final con todos los años de desarrollo -> año de prueba
    base_final = _bases(df, dev)
    modelo, nombre = _crear_modelo(best)
    modelo.fit(X[dev], (y - base_final)[dev])
    pred_test = base_final[test] + modelo.predict(X[test])
    oof.append(df.loc[test, ["id_municipio", "id_cultivo", "id_tiempo", "anio"]].assign(y=y[test].to_numpy(), yhat=pred_test))
    oof = calibrar_intervalos(pd.concat(oof, ignore_index=True), anio_prueba)

    m_test = metricas_regresion(y[test], pred_test)
    m_base = metricas_regresion(y[test], base_final[test])
    en_test = oof[oof["anio"] == anio_prueba]
    cobertura = float(((en_test["y"] >= en_test["lo"]) & (en_test["y"] <= en_test["hi"])).mean())

    top_global, shap_test = _shap(modelo, X[test], feature_cols)     # explica la desviación respecto a la línea base

    metrics = {
        "evaluacion": f"Fuera de muestra: el año {anio_prueba} no se usó para entrenar ni para ajustar hiperparámetros",
        "mae": m_test["mae"], "rmse": m_test["rmse"], "r2": m_test["r2"],
        "n_train": int(dev.sum()), "n_test": m_test["n"], "split_year": anio_prueba,
        "linea_base": {"descripcion": "promedio histórico municipio×cultivo", **m_base},
        "mejora_mae_vs_base_pct": float(100 * (1 - m_test["mae"] / m_base["mae"])) if m_base["mae"] else None,
        "cv_mae": extra.get("cv_mae"), "cv_folds": cv_detalle,
        "cobertura_p10_p90": cobertura,
        "n_features": len(feature_cols), "feature_cols": feature_cols,
        "best_params": best, "optuna_trials": extra.get("n_trials", 0),
        "shap_top_global": top_global,
        "anios_con_datos": [int(a) for a in anios],
    }
    logger.info("Modelo %s | año de prueba %s | R²=%.3f MAE=%.3f (línea base MAE=%.3f, mejora %.1f %%) | cobertura p10-p90=%.0f %%",
                nombre, anio_prueba, m_test["r2"], m_test["mae"], m_base["mae"], metrics["mejora_mae_vs_base_pct"] or 0, 100 * cobertura)

    id_version = _registrar_version(engine, NOMBRE_MODELO_XGB if nombre == "xgboost" else f"{nombre}_rendimiento", metrics)
    _ensure_columns(engine)

    # 4) Guardar SOLO predicciones fuera de muestra, con SHAP para el año de prueba
    df_pred = oof.rename(columns={"yhat": "rendimiento_predicho_t_ha", "lo": "intervalo_confianza_inferior", "hi": "intervalo_confianza_superior"})
    df_pred["shap_top"] = None
    if shap_test is not None:
        idx_test = df_pred.index[df_pred["anio"] == anio_prueba]
        df_pred.loc[idx_test, "shap_top"] = shap_test
    _guardar_predicciones(engine, df_pred, id_version)

    return {"model_name": NOMBRE_MODELO_XGB if nombre == "xgboost" else nombre, "metrics": metrics}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    result = train_and_report()
    print(json.dumps({"model_name": result["model_name"], "metrics": {
        k: v for k, v in result["metrics"].items() if k not in ("shap_top_global", "feature_cols")
    }}, indent=2, ensure_ascii=False, default=str))
