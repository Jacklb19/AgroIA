"""
train_precio_forecast.py — Pronóstico de precios mayoristas diarios (SIPSA), 1-10 días hábiles.

Enfoque
- Un modelo global XGBoost sobre TODAS las series (mercado x producto). Objetivo: el
  cambio logarítmico del precio a h días hábiles, log(P[t+h] / P[t]), con pérdida
  absoluta (mediana). Rasgos: retornos y volatilidad recientes, desvío frente a
  medias móviles, momentum del producto en los demás mercados, calendario y h.
- Línea base: "el precio de hoy no cambia" (naive). Un pronóstico solo se publica como
  modelo si en el backtest supera a la línea base para ese producto; si no, se
  publica la línea base marcada con confianza 'baja'.
- Backtest de origen rodante ORDENADO POR FECHA: para cada corte C solo se entrena con
  filas cuyo objetivo cae en o antes de C, y se prueba con orígenes posteriores a C.
- Intervalos p10-p90 a partir de los residuos del backtest (por producto y horizonte).
- Solo se guardan predicciones futuras, nunca valores ajustados sobre el histórico.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import text

from load.db import upsert

logger = logging.getLogger(__name__)

NOMBRE_MODELO = "xgboost_precio_diario"
H = 10                      # horizonte máximo (días hábiles)
LAGS = (1, 2, 3, 5, 10, 20)
MIN_OBS_SERIE = 180         # observaciones mínimas para modelar una serie
FFILL_MAX = 3               # se rellenan huecos de hasta 3 días hábiles
LOOKBACK_ORIGENES = 750     # ~3 años de orígenes para entrenar
STRIDE_ENTRENAMIENTO = 2
FOLDS = 4
VENTANA_TEST = 20           # días hábiles por fold (4 folds = últimos ~4 meses)
BACKTEST_MAX_EDAD = timedelta(days=7)
MIN_RESIDUOS = 40           # mínimo de residuos para usar cuantiles propios de un producto/horizonte
UMBRAL_ALTA = 0.10          # error <= 90 % del de la línea base -> confianza alta
UMBRAL_MEDIA = 0.05         # mejora >= 5 % -> media; menos -> se publica la línea base con confianza baja
MIN_FILAS_PH = 100          # mínimo de filas de prueba por (producto, horizonte) para decidir con datos propios

XGB_PARAMS = dict(
    n_estimators=250, max_depth=6, learning_rate=0.08, subsample=0.8, colsample_bytree=0.8,
    min_child_weight=20, objective="reg:absoluteerror", tree_method="hist",
    enable_categorical=True, n_jobs=-1, random_state=42,
)


# ── Datos y rasgos ───────────────────────────────────────────────────────
def cargar_historia(engine) -> pd.DataFrame:
    df = pd.read_sql(
        text("SELECT id_central, id_producto, fecha, precio_prom_kg FROM fact_precio_diario"), engine
    )
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def construir_panel(df: pd.DataFrame, min_obs: int = MIN_OBS_SERIE) -> pd.DataFrame:
    """Matriz días hábiles x series (columnas MultiIndex id_central, id_producto) con NaN en los huecos."""
    df = df[df["fecha"].dt.dayofweek < 5]
    cuenta = df.groupby(["id_central", "id_producto"]).size()
    validas = cuenta[cuenta >= min_obs].index
    df = df.set_index(["id_central", "id_producto"]).loc[validas].reset_index()
    ancho = df.pivot_table(index="fecha", columns=["id_central", "id_producto"], values="precio_prom_kg", aggfunc="mean")
    return ancho.reindex(pd.bdate_range(ancho.index.min(), ancho.index.max()))


def calcular_rasgos(L: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """L = log(precio) con huecos rellenados. Cada rasgo es una matriz con la forma de L."""
    F = {f"r{k}": L - L.shift(k) for k in LAGS}
    d1 = L.diff()
    F["vol5"] = d1.rolling(5, min_periods=3).std()
    F["vol20"] = d1.rolling(20, min_periods=10).std()
    F["dev20"] = L - L.rolling(20, min_periods=10).mean()
    F["dev90"] = L - L.rolling(90, min_periods=30).mean()
    for k in (5, 20):  # momentum promedio del producto en todos los mercados
        F[f"prod_r{k}"] = F[f"r{k}"].T.groupby(level=1).transform("mean").T
    return F


def construir_muestras(L, F, origenes: np.ndarray, con_objetivo: bool) -> pd.DataFrame:
    """Filas (origen, serie, h). Con objetivo: solo donde existe el precio futuro (entrenamiento/backtest)."""
    T, S = L.shape
    Lv = L.values
    idx_ext = L.index.append(pd.bdate_range(L.index[-1] + pd.offsets.BDay(1), periods=H))
    cols_c = L.columns.get_level_values(0).to_numpy()
    cols_p = L.columns.get_level_values(1).to_numpy()
    Fv = {k: v.values for k, v in F.items()}

    partes = []
    for h in range(1, H + 1):
        o = origenes[origenes + h < T] if con_objetivo else origenes
        if len(o) == 0:
            continue
        base = Lv[o]
        ok = np.isfinite(base)
        if con_objetivo:
            y = Lv[o + h] - base
            ok &= np.isfinite(y)
        oi, si = np.nonzero(ok)
        datos = {
            "orig": o[oi], "serie": si, "h": h, "base": base[oi, si],
            "id_central": cols_c[si], "id_producto": cols_p[si],
            "dow": idx_ext.dayofweek.to_numpy()[o[oi] + h].astype(np.int8),
            "doy_sin": np.sin(2 * np.pi * idx_ext.dayofyear.to_numpy()[o[oi] + h] / 365.25).astype(np.float32),
            "doy_cos": np.cos(2 * np.pi * idx_ext.dayofyear.to_numpy()[o[oi] + h] / 365.25).astype(np.float32),
        }
        if con_objetivo:
            datos["y"] = y[oi, si].astype(np.float32)
        for nombre, m in Fv.items():
            datos[nombre] = m[o[oi], si].astype(np.float32)
        partes.append(pd.DataFrame(datos))
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def _X(muestras: pd.DataFrame, categorias: dict) -> pd.DataFrame:
    X = muestras.drop(columns=["orig", "serie", "base", "y"], errors="ignore").copy()
    for c in ("id_central", "id_producto"):
        X[c] = pd.Categorical(X[c], categories=categorias[c])
    return X


def _modelo():
    from xgboost import XGBRegressor
    return XGBRegressor(**XGB_PARAMS)


# ── Backtest ─────────────────────────────────────────────────────────────
def _cuantiles(residuos: pd.DataFrame) -> dict:
    """{'global': {h: [q10, q90]}, 'producto': {id: {h: [q10, q90]}}} con los residuos (y - pred)."""
    def q(v):
        return [float(np.quantile(v, 0.10)), float(np.quantile(v, 0.90))]
    out = {"global": {int(h): q(g["res"]) for h, g in residuos.groupby("h")}, "producto": {}}
    for (pid, h), g in residuos.groupby(["id_producto", "h"]):
        if len(g) >= MIN_RESIDUOS:
            out["producto"].setdefault(str(int(pid)), {})[int(h)] = q(g["res"])
    return out


def clasificar(mejora: float | None) -> str:
    if mejora is None:
        return "baja"
    return "alta" if mejora >= UMBRAL_ALTA else "media" if mejora >= UMBRAL_MEDIA else "baja"


def mejora_esperada(calidad: dict, pid: int, h: int) -> float | None:
    """Mejora del modelo frente a la línea base en el backtest: la del (producto, horizonte) si hay
    filas suficientes; si no, la del producto. None si el producto no estuvo en el backtest."""
    q = calidad.get(str(pid))
    if not q:
        return None
    return q.get("mejora_por_h", {}).get(str(h), q.get("mejora"))


def backtest(L, F, categorias) -> dict:
    """Origen rodante. Retorna métricas + reglas de calidad + cuantiles de residuos."""
    T = L.shape[0]
    orig_train = np.arange(max(20, T - LOOKBACK_ORIGENES), T - 1, STRIDE_ENTRENAMIENTO)
    orig_test = np.arange(T - FOLDS * VENTANA_TEST, T - 1)
    train = construir_muestras(L, F, orig_train, True)
    test = construir_muestras(L, F, orig_test, True)

    resultados = []
    for k in range(FOLDS):
        corte = T - FOLDS * VENTANA_TEST + k * VENTANA_TEST - 1        # último índice "conocido" en este fold
        tr = train[train["orig"] + train["h"] <= corte]                 # el objetivo ya había ocurrido
        te = test[(test["orig"] > corte) & (test["orig"] <= corte + VENTANA_TEST)]
        if tr.empty or te.empty:
            continue
        m = _modelo()
        m.fit(_X(tr, categorias), tr["y"])
        pred = m.predict(_X(te, categorias))
        resultados.append(te[["orig", "h", "id_central", "id_producto", "y"]].assign(pred=pred))
        logger.info("Backtest fold %s/%s: corte=%s train=%s test=%s", k + 1, FOLDS, L.index[corte].date(), len(tr), len(te))

    if not resultados:
        raise RuntimeError("Backtest sin resultados: historia insuficiente")
    r = pd.concat(resultados, ignore_index=True)
    r["res"] = r["y"] - r["pred"]
    r["err_m"] = r["res"].abs()
    r["err_n"] = r["y"].abs()

    por_prod = r.groupby("id_producto").agg(n=("y", "size"), mae_m=("err_m", "mean"), mae_n=("err_n", "mean"))
    por_prod["mejora"] = 1 - por_prod["mae_m"] / por_prod["mae_n"]
    por_prod["confianza"] = por_prod["mejora"].map(clasificar)
    por_h = r.groupby("h").agg(mae_modelo=("err_m", "mean"), mae_naive=("err_n", "mean")).reset_index()
    por_ph = r.groupby(["id_producto", "h"]).agg(n=("y", "size"), mae_m=("err_m", "mean"), mae_n=("err_n", "mean")).reset_index()
    por_ph = por_ph[por_ph["n"] >= MIN_FILAS_PH]
    mejora_h: dict[str, dict[str, float]] = {}
    for x in por_ph.itertuples():
        mejora_h.setdefault(str(int(x.id_producto)), {})[str(int(x.h))] = float(1 - x.mae_m / x.mae_n)

    naive = r[["h", "id_producto"]].assign(res=r["y"])                 # residuo de la línea base = y
    return {
        "folds": FOLDS, "ventana_bdays": VENTANA_TEST, "n_test": int(len(r)),
        "mae_log_modelo": float(r["err_m"].mean()), "mae_log_naive": float(r["err_n"].mean()),
        "mejora_global": float(1 - r["err_m"].mean() / r["err_n"].mean()),
        "por_horizonte": [{"h": int(x.h), "mae_modelo": float(x.mae_modelo), "mae_naive": float(x.mae_naive)} for x in por_h.itertuples()],
        "por_producto": {
            str(int(pid)): {"n": int(x.n), "mae_modelo": float(x.mae_m), "mae_naive": float(x.mae_n),
                            "mejora": float(x.mejora), "confianza": x.confianza,
                            "mejora_por_h": mejora_h.get(str(int(pid)), {})}
            for pid, x in por_prod.iterrows()
        },
        "cuantiles_modelo": _cuantiles(r),
        "cuantiles_naive": _cuantiles(naive),
    }


# ── Predicción final ─────────────────────────────────────────────────────
def _cuantil(cuantiles: dict, pid: int, h: int) -> list[float]:
    propio = cuantiles.get("producto", {}).get(str(pid), {}).get(str(h))
    return propio or cuantiles["global"].get(str(h)) or [-0.1, 0.1]


def predecir(L, F, categorias, metricas: dict) -> pd.DataFrame:
    """Ajusta con todo el histórico disponible y predice desde el último día con datos."""
    T = L.shape[0]
    orig_train = np.arange(max(20, T - LOOKBACK_ORIGENES), T - 1, STRIDE_ENTRENAMIENTO)
    train = construir_muestras(L, F, orig_train, True)
    modelo = _modelo()
    modelo.fit(_X(train, categorias), train["y"])

    futuro = construir_muestras(L, F, np.array([T - 1]), False)
    futuro["pred_log"] = modelo.predict(_X(futuro, categorias))
    calidad = metricas["por_producto"]

    filas = []
    fechas = pd.bdate_range(L.index[-1] + pd.offsets.BDay(1), periods=H)
    for r in futuro.itertuples(index=False):
        pid, h = int(r.id_producto), int(r.h)
        conf = clasificar(mejora_esperada(calidad, pid, h))
        usa_modelo = conf in ("alta", "media")
        pred = r.pred_log if usa_modelo else 0.0
        q10, q90 = _cuantil(metricas["cuantiles_modelo" if usa_modelo else "cuantiles_naive"], pid, h)
        base = float(np.exp(r.base))
        filas.append({
            "id_central": int(r.id_central), "id_producto": pid,
            "fecha_objetivo": fechas[h - 1].date(), "horizonte_dias": h,
            "precio_pred_kg": base * float(np.exp(pred)),
            "p10_kg": base * float(np.exp(pred + q10)), "p90_kg": base * float(np.exp(pred + q90)),
            "metodo": "xgboost" if usa_modelo else "naive", "confianza": conf,
        })
    return pd.DataFrame(filas)


# ── Orquestación ─────────────────────────────────────────────────────────
def _ultimo_backtest(engine) -> dict | None:
    with engine.connect() as conn:
        fila = conn.execute(text("""
            SELECT id_version, fecha_entrenamiento, metricas_json FROM model_version
            WHERE nombre_modelo = :n AND activo ORDER BY id_version DESC LIMIT 1
        """), {"n": NOMBRE_MODELO}).first()
    if not fila:
        return None
    m = fila[2] if isinstance(fila[2], dict) else json.loads(fila[2])
    return {"id_version": fila[0], "fecha": fila[1], "metricas": m}


def forecast_y_guardar(engine, forzar_backtest: bool = False) -> dict:
    from models.train_rendimiento import _registrar_version

    df = cargar_historia(engine)
    if df.empty:
        return {"status": "sin_datos"}
    panel = construir_panel(df)
    L = np.log(panel.ffill(limit=FFILL_MAX))
    F = calcular_rasgos(L)
    categorias = {
        "id_central": sorted(set(L.columns.get_level_values(0))),
        "id_producto": sorted(set(L.columns.get_level_values(1))),
    }
    logger.info("Panel de precios: %s días hábiles x %s series", L.shape[0], L.shape[1])

    previo = _ultimo_backtest(engine)
    vigente = (
        previo is not None and not forzar_backtest
        and datetime.now(timezone.utc) - previo["fecha"] < BACKTEST_MAX_EDAD
    )
    if vigente:
        metricas, id_version = previo["metricas"], previo["id_version"]
    else:
        bt = backtest(L, F, categorias)
        metricas = {
            "backtest": {k: v for k, v in bt.items() if not k.startswith("cuantiles") and k != "por_producto"},
            "por_producto": bt["por_producto"],
            "cuantiles_modelo": bt["cuantiles_modelo"], "cuantiles_naive": bt["cuantiles_naive"],
            "horizonte_max": H, "unidad_horizonte": "dias_habiles",
            "entrenado_hasta": L.index[-1].date().isoformat(),
        }
        metricas = json.loads(json.dumps(metricas))       # mismas claves (texto) que al leerlas de la BD
        id_version = _registrar_version(engine, NOMBRE_MODELO, metricas)
        logger.info(
            "Backtest: MAE(log) modelo=%.4f naive=%.4f mejora=%.1f %%",
            bt["mae_log_modelo"], bt["mae_log_naive"], 100 * bt["mejora_global"],
        )

    pred = predecir(L, F, categorias, metricas)
    pred["id_version"] = id_version
    upsert(engine, "pred_precio", pred, ["id_central", "id_producto", "fecha_objetivo"])
    resumen = pred.groupby("confianza").size().to_dict()
    logger.info("pred_precio: %s predicciones (%s)", len(pred), resumen)
    return {
        "status": "ok", "predicciones": int(len(pred)), "confianza": resumen,
        "backtest_reutilizado": bool(vigente), "id_version": id_version,
        "fecha_dato_max": L.index[-1].date(),
    }


if __name__ == "__main__":
    from load.db import get_engine
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    print(forecast_y_guardar(get_engine(), forzar_backtest=True))
