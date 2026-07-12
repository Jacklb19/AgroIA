"""
train_rendimiento.py — Entrenamiento del modelo de rendimiento agrícola.

- XGBoost con tuning bayesiano (Optuna) y validación temporal.
- SHAP global + top-features por predicción persistidos en BD.
- Versionado en model_version.metricas_json.
"""
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from load.db import get_engine
from models.build_features import build_ml_features

logger = logging.getLogger(__name__)


# ── Configuración del modelo (alineada con informe) ────────────────────
N_TRIALS_OPTUNA   = 200
N_ESTIMATORS_FINAL = 1500
MAX_DEPTH_DEFAULT  = 8
TIME_SPLITS        = 5
RANDOM_SEED        = 42

_DROP_COLS = [
    "id_municipio", "id_cultivo", "id_tiempo", "anio",
    "id_departamento", "clase_aptitud", "es_anio_nino",
    "rendimiento_t_ha", "produccion_total_ton",
]


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


def _ensure_shap_column(engine) -> bool:
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE pred_rendimiento ADD COLUMN IF NOT EXISTS shap_top JSONB")
            )
        return True
    except Exception as e:
        logger.warning("No se pudo asegurar columna shap_top: %s", e)
        return False


def _guardar_predicciones(engine, df_pred: pd.DataFrame, id_version: int | None, tiene_shap: bool) -> None:
    from load.db import upsert

    df_pred = df_pred.copy()
    df_pred["id_version"] = id_version
    df_pred = df_pred.replace({np.nan: None})

    cols = [
        "id_municipio",
        "id_cultivo",
        "id_tiempo",
        "rendimiento_predicho_t_ha",
        "intervalo_confianza_inferior",
        "intervalo_confianza_superior",
        "id_version",
    ]
    if tiene_shap and "shap_top" in df_pred.columns:
        cols.append("shap_top")

    for c in cols:
        if c not in df_pred.columns:
            df_pred[c] = None

    df_out = df_pred[cols].drop_duplicates(subset=["id_municipio", "id_cultivo", "id_tiempo"])
    upsert(engine, "pred_rendimiento", df_out, ["id_municipio", "id_cultivo", "id_tiempo"])
    logger.info("pred_rendimiento: %s predicciones guardadas", len(df_out))


def _split_features(df: pd.DataFrame):
    df = df.dropna(subset=["rendimiento_t_ha"]).copy()
    feature_cols = [c for c in df.columns if c not in _DROP_COLS]
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    y = df["rendimiento_t_ha"].astype(float)
    return df, X, y, feature_cols


def _tune_with_optuna(X, y, n_trials: int, n_splits: int) -> dict:
    """Tuning bayesiano con TimeSeriesSplit. Retorna mejores hiperparámetros."""
    try:
        import optuna
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import mean_absolute_error
        from xgboost import XGBRegressor

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial):
            params = {
                "n_estimators":      trial.suggest_int("n_estimators", 400, 1500, step=100),
                "max_depth":         trial.suggest_int("max_depth", 4, 10),
                "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                "subsample":         trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight":  trial.suggest_int("min_child_weight", 1, 10),
                "reg_alpha":         trial.suggest_float("reg_alpha", 1e-3, 5.0, log=True),
                "reg_lambda":        trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
                "random_state":      RANDOM_SEED,
                "n_jobs":            -1,
                "tree_method":       "hist",
            }
            tscv = TimeSeriesSplit(n_splits=n_splits)
            errs = []
            for tr_idx, va_idx in tscv.split(X):
                m = XGBRegressor(**params)
                m.fit(X.iloc[tr_idx], y.iloc[tr_idx], verbose=False)
                pred = m.predict(X.iloc[va_idx])
                errs.append(mean_absolute_error(y.iloc[va_idx], pred))
            return float(np.mean(errs))

        study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED))
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
        logger.info("Optuna best params: %s | MAE CV=%.4f", study.best_params, study.best_value)
        return {**study.best_params, "cv_mae": float(study.best_value), "n_trials": n_trials}
    except Exception as e:
        logger.warning("Optuna tuning falló (%s). Uso defaults.", e)
        return {
            "n_estimators":     N_ESTIMATORS_FINAL,
            "max_depth":        MAX_DEPTH_DEFAULT,
            "learning_rate":    0.05,
            "subsample":        0.9,
            "colsample_bytree": 0.9,
            "min_child_weight": 1,
            "reg_alpha":        0.1,
            "reg_lambda":       1.0,
            "n_trials":         0,
        }


def _compute_shap(model, X, feature_cols, sample_size: int = 1000):
    """SHAP global (top-10) + por fila (top-3 con signo). Devuelve dicts/listas."""
    try:
        import shap
        sample = X.sample(min(sample_size, len(X)), random_state=RANDOM_SEED)
        explainer   = shap.TreeExplainer(model)
        shap_sample = explainer.shap_values(sample)
        importance  = np.abs(shap_sample).mean(axis=0)
        top_global  = sorted(
            zip(feature_cols, importance.tolist()),
            key=lambda kv: kv[1],
            reverse=True,
        )[:10]
        top_global_payload = [{"feature": f, "shap_abs_mean": float(v)} for f, v in top_global]

        # SHAP por predicción sobre todo el dataset
        shap_all = explainer.shap_values(X)
        per_row = []
        for i in range(shap_all.shape[0]):
            idx_top = np.argsort(np.abs(shap_all[i]))[::-1][:3]
            per_row.append([
                {
                    "feature": feature_cols[j],
                    "shap":    float(shap_all[i, j]),
                    "value":   float(X.iloc[i, j]) if pd.notna(X.iloc[i, j]) else None,
                }
                for j in idx_top
            ])
        return top_global_payload, per_row
    except Exception as e:
        logger.warning("SHAP falló: %s", e)
        return [], None


def train_and_report(engine=None) -> dict:
    """Entrena modelo, registra versión, persiste predicciones + SHAP."""
    if engine is None:
        engine = get_engine()

    df = build_ml_features(engine)
    if df.empty:
        raise ValueError("No hay datos suficientes para entrenar el modelo")

    df, X, y, feature_cols = _split_features(df)
    n_features = len(feature_cols)
    logger.info("Entrenando con %s filas y %s features", len(df), n_features)

    # Hiperparámetros
    best_params = _tune_with_optuna(X, y, N_TRIALS_OPTUNA, TIME_SPLITS)
    extra = {k: best_params.pop(k, None) for k in ("cv_mae", "n_trials")}

    try:
        from xgboost import XGBRegressor
        model = XGBRegressor(
            **best_params,
            random_state=RANDOM_SEED,
            n_jobs=-1,
            tree_method="hist",
        )
        model_name = "xgboost_rendimiento"
    except ImportError:
        from sklearn.ensemble import GradientBoostingRegressor
        model = GradientBoostingRegressor(random_state=RANDOM_SEED)
        model_name = "gradient_boosting_rendimiento"
        best_params = {}

    # Hold-out temporal: últimos 20% de años para test final
    anios_orden = sorted(df["anio"].unique())
    cut = anios_orden[int(len(anios_orden) * 0.8)] if len(anios_orden) > 4 else anios_orden[-1]
    mask_train = df["anio"] < cut
    X_train, X_test = X[mask_train], X[~mask_train]
    y_train, y_test = y[mask_train], y[~mask_train]

    if len(X_test) == 0 or len(X_train) == 0:
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_SEED)

    model.fit(X_train, y_train)

    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    pred_test = model.predict(X_test)
    mae   = float(mean_absolute_error(y_test, pred_test))
    rmse  = float(mean_squared_error(y_test, pred_test) ** 0.5)
    r2    = float(r2_score(y_test, pred_test))

    # SHAP
    top_global, shap_per_row = _compute_shap(model, X, feature_cols)

    metrics = {
        "mae":            mae,
        "rmse":           rmse,
        "r2":             r2,
        "n_train":        int(len(X_train)),
        "n_test":         int(len(X_test)),
        "n_features":     n_features,
        "feature_cols":   feature_cols,
        "best_params":    best_params,
        "optuna_trials":  extra.get("n_trials", 0),
        "cv_mae":         extra.get("cv_mae"),
        "split_year":     int(cut),
        "shap_top_global": top_global,
    }
    logger.info("Modelo %s entrenado | R²=%.3f MAE=%.3f RMSE=%.3f", model_name, r2, mae, rmse)

    id_version = _registrar_version(engine, model_name, metrics)
    tiene_shap = _ensure_shap_column(engine)

    # Predicciones sobre todo el dataset
    pred_todas = model.predict(X)
    df_pred = df[["id_municipio", "id_cultivo", "anio"]].copy()

    df_tiempo = pd.read_sql("SELECT id_tiempo, anio FROM dim_tiempo WHERE mes = 12", engine)
    df_pred = df_pred.merge(df_tiempo, on="anio", how="left")

    df_pred["rendimiento_predicho_t_ha"]    = pred_todas
    df_pred["intervalo_confianza_inferior"] = pred_todas - mae
    df_pred["intervalo_confianza_superior"] = pred_todas + mae
    if tiene_shap and shap_per_row is not None:
        df_pred["shap_top"] = [json.dumps(r, ensure_ascii=False) for r in shap_per_row]

    _guardar_predicciones(engine, df_pred, id_version, tiene_shap)

    return {"model_name": model_name, "metrics": metrics}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    result = train_and_report()
    print(json.dumps({"model_name": result["model_name"], "metrics": {
        k: v for k, v in result["metrics"].items() if k != "shap_top_global"
    }}, indent=2, ensure_ascii=False, default=str))
