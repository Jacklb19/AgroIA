"""Tests del pronóstico de precios sobre un panel sintético (sin BD ni red)."""
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("xgboost")

import models.train_precio_forecast as tf


def _historia(n_dias=320, series=((1, 10), (2, 10), (1, 20)), seed=0, huecos=True):
    """Caminata aleatoria log-normal por serie, solo días hábiles, con algunos huecos."""
    rng = np.random.default_rng(seed)
    fechas = pd.bdate_range("2024-01-01", periods=n_dias)
    filas = []
    for i, (c, p) in enumerate(series):
        precio = 2000 * (1 + i) * np.exp(np.cumsum(rng.normal(0, 0.02, n_dias)))
        for j, f in enumerate(fechas):
            if huecos and rng.random() < 0.05:
                continue
            filas.append({"id_central": c, "id_producto": p, "fecha": f, "precio_prom_kg": precio[j]})
    return pd.DataFrame(filas)


def test_construir_panel_descarta_series_cortas_y_fines_de_semana():
    df = _historia()
    corta = df[(df.id_central == 1) & (df.id_producto == 10)].head(50).assign(id_central=9)
    sabado = pd.DataFrame([{"id_central": 1, "id_producto": 10, "fecha": pd.Timestamp("2024-01-06"), "precio_prom_kg": 1.0}])
    panel = tf.construir_panel(pd.concat([df, corta, sabado], ignore_index=True))
    assert (9, 10) not in panel.columns                       # < MIN_OBS_SERIE
    assert panel.shape[1] == 3
    assert (panel.index.dayofweek < 5).all()                  # rejilla de días hábiles


def test_muestras_objetivo_es_cambio_logaritmico_y_rasgos_solo_usan_el_pasado():
    panel = tf.construir_panel(_historia(huecos=False))
    L = np.log(panel)
    F = tf.calcular_rasgos(L)
    o = np.array([100])
    m = tf.construir_muestras(L, F, o, con_objetivo=True)
    assert set(m["h"]) == set(range(1, tf.H + 1))

    fila = m[(m["h"] == 3) & (m["id_central"] == 1) & (m["id_producto"] == 10)].iloc[0]
    col = list(L.columns).index((1, 10))
    assert fila["y"] == pytest.approx(L.iloc[103, col] - L.iloc[100, col], abs=1e-5)
    assert fila["r1"] == pytest.approx(L.iloc[100, col] - L.iloc[99, col], abs=1e-5)

    # Alterar el futuro NO cambia los rasgos del origen (sin fuga)
    L2 = L.copy()
    L2.iloc[101:, :] = L2.iloc[101:, :] + 5
    m2 = tf.construir_muestras(L2, tf.calcular_rasgos(L2), o, con_objetivo=True)
    rasgos = [c for c in m.columns if c.startswith(("r", "vol", "dev", "prod_r")) and c != "orig"]
    pd.testing.assert_frame_equal(m[rasgos].reset_index(drop=True), m2[rasgos].reset_index(drop=True))


def test_muestras_futuras_no_exigen_objetivo():
    panel = tf.construir_panel(_historia(huecos=False))
    L = np.log(panel)
    fut = tf.construir_muestras(L, tf.calcular_rasgos(L), np.array([L.shape[0] - 1]), con_objetivo=False)
    assert "y" not in fut.columns and len(fut) == 3 * tf.H


def test_clasificar_y_cuantiles():
    assert tf.clasificar(0.15) == "alta" and tf.clasificar(0.06) == "media"
    assert tf.clasificar(0.03) == "baja" and tf.clasificar(-0.2) == "baja" and tf.clasificar(None) == "baja"
    calidad = {"10": {"mejora": 0.2, "mejora_por_h": {"1": -0.05}}}
    assert tf.mejora_esperada(calidad, 10, 1) == -0.05        # dato propio del horizonte
    assert tf.mejora_esperada(calidad, 10, 5) == 0.2          # cae a la del producto
    assert tf.mejora_esperada(calidad, 99, 1) is None         # producto sin backtest
    cuant = {"global": {"1": [-0.1, 0.1]}, "producto": {"10": {"1": [-0.02, 0.03]}}}
    assert tf._cuantil(cuant, 10, 1) == [-0.02, 0.03]        # propio del producto
    assert tf._cuantil(cuant, 99, 1) == [-0.1, 0.1]          # global
    assert tf._cuantil(cuant, 99, 7) == [-0.1, 0.1]          # último recurso


def test_backtest_entrena_solo_con_lo_conocido_en_cada_corte(monkeypatch):
    """Cada fold usa filas cuyo objetivo ya había ocurrido (orig + h <= corte) y prueba con orígenes posteriores."""
    monkeypatch.setattr(tf, "FOLDS", 2)
    monkeypatch.setattr(tf, "VENTANA_TEST", 15)
    monkeypatch.setattr(tf, "XGB_PARAMS", {**tf.XGB_PARAMS, "n_estimators": 15, "max_depth": 3})

    panel = tf.construir_panel(_historia(n_dias=320))
    L = np.log(panel.ffill(limit=tf.FFILL_MAX))
    F = tf.calcular_rasgos(L)
    cat = {"id_central": [1, 2], "id_producto": [10, 20]}

    vistos = []
    original = tf._modelo

    class _Espia:
        def __init__(self):
            self.m = original()

        def fit(self, X, y):
            vistos.append(len(X))
            return self.m.fit(X, y)

        def predict(self, X):
            return self.m.predict(X)

    monkeypatch.setattr(tf, "_modelo", lambda: _Espia())
    bt = tf.backtest(L, F, cat)
    assert bt["n_test"] > 0 and np.isfinite(bt["mae_log_modelo"]) and np.isfinite(bt["mae_log_naive"])
    assert len(vistos) == 2 and vistos[1] > vistos[0]        # el segundo fold conoce más historia
    assert set(bt["por_producto"]) == {"10", "20"}
    assert all(v["confianza"] in ("alta", "media", "baja") for v in bt["por_producto"].values())
    assert set(bt["cuantiles_modelo"]["global"]) == set(range(1, tf.H + 1))


def test_predecir_publica_naive_con_confianza_baja_si_no_supera_la_linea_base(monkeypatch):
    monkeypatch.setattr(tf, "XGB_PARAMS", {**tf.XGB_PARAMS, "n_estimators": 10, "max_depth": 3})
    panel = tf.construir_panel(_historia(n_dias=320, huecos=False))
    L = np.log(panel)
    F = tf.calcular_rasgos(L)
    cat = {"id_central": [1, 2], "id_producto": [10, 20]}
    cuant = {"global": {str(h): [-0.05, 0.05] for h in range(1, tf.H + 1)}, "producto": {}}
    metricas = {
        # producto 10 no supera a la línea base; producto 20 sí, salvo a 1 día
        "por_producto": {"10": {"mejora": -0.10}, "20": {"mejora": 0.20, "mejora_por_h": {"1": 0.0}}},
        "cuantiles_modelo": cuant, "cuantiles_naive": cuant,
    }
    pred = tf.predecir(L, F, cat, metricas)

    assert set(pred["metodo"]) == {"naive", "xgboost"}
    baja = pred[(pred["id_producto"] == 10) & (pred["id_central"] == 1)]
    ultimo = float(np.exp(L.iloc[-1][(1, 10)]))
    assert (baja["confianza"] == "baja").all() and baja["precio_pred_kg"].tolist() == pytest.approx([ultimo] * tf.H)
    p20 = pred[pred["id_producto"] == 20].set_index("horizonte_dias")
    assert p20.loc[1, "metodo"] == "naive" and p20.loc[1, "confianza"] == "baja"      # a 1 día no mejora
    assert (p20.loc[2:, "metodo"] == "xgboost").all() and (p20.loc[2:, "confianza"] == "alta").all()
    assert (pred["p10_kg"] < pred["precio_pred_kg"]).all() and (pred["p90_kg"] > pred["precio_pred_kg"]).all()
    assert pred["fecha_objetivo"].min() > L.index[-1].date()   # solo futuro
    assert sorted(pred["horizonte_dias"].unique()) == list(range(1, tf.H + 1))
