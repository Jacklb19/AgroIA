"""Tests de validez del modelo de rendimiento: validación temporal, ausencia de fuga y datos faltantes."""
import ast
import inspect

import numpy as np
import pandas as pd
import pytest

import models.build_features as bf
import models.train_rendimiento as tr
from load.load_facts import agregar_produccion_anual


# ── Validación temporal por año ──────────────────────────────────────────
def test_year_splits_solo_entrena_con_el_pasado():
    anios = list(range(2019, 2025))
    splits = tr.year_splits(anios, n_splits=3, min_train=3)
    assert [v for _, v in splits] == [2022, 2023, 2024]
    for entrenamiento, validacion in splits:
        assert max(entrenamiento) < validacion              # nunca se entrena con el futuro
        assert len(entrenamiento) >= 3


def test_year_splits_falla_con_poca_historia():
    with pytest.raises(ValueError, match="insuficiente"):
        tr.year_splits([2022, 2023, 2024], min_train=3)


def test_los_folds_no_dependen_del_orden_de_las_filas():
    """El error original: TimeSeriesSplit sobre filas ordenadas por municipio. Aquí el orden no importa."""
    a = tr.year_splits([2024, 2019, 2021, 2020, 2023, 2022])
    b = tr.year_splits(sorted([2024, 2019, 2021, 2020, 2023, 2022]))
    assert a == b


# ── Métricas e intervalos ────────────────────────────────────────────────
def test_metricas_regresion():
    m = tr.metricas_regresion([1, 2, 3, 4], [1, 2, 3, 4])
    assert m["mae"] == 0 and m["rmse"] == 0 and m["r2"] == pytest.approx(1.0)
    m = tr.metricas_regresion([1, 2, 3, 4], [2, 3, 4, 5])
    assert m["mae"] == pytest.approx(1.0) and m["n"] == 4


def _oof(seed=0):
    rng = np.random.default_rng(seed)
    filas = []
    for anio in (2021, 2022, 2023, 2024):
        for i in range(400):
            y = rng.uniform(1, 10)
            filas.append({"id_municipio": f"m{i}", "id_cultivo": i % 2, "id_tiempo": anio, "anio": anio,
                          "y": y, "yhat": y + rng.normal(0, 0.5)})
    return pd.DataFrame(filas)


def test_intervalos_calibrados_cubren_aprox_80_por_ciento_y_no_usan_el_propio_anio():
    out = tr.calibrar_intervalos(_oof(), anio_prueba=2024)
    prueba = out[out["anio"] == 2024]
    cobertura = ((prueba["y"] >= prueba["lo"]) & (prueba["y"] <= prueba["hi"])).mean()
    assert 0.70 <= cobertura <= 0.90                          # nominal 80 % (p10-p90)
    assert (out["lo"] <= out["hi"]).all() and (out["lo"] >= 0).all()   # rendimiento no negativo


def test_los_residuos_del_anio_de_prueba_no_calibran_ningun_intervalo():
    base = _oof()
    a = tr.calibrar_intervalos(base, anio_prueba=2024)
    alterado = base.copy()
    alterado.loc[alterado["anio"] == 2024, "yhat"] += 100     # destrozar el año de prueba
    b = tr.calibrar_intervalos(alterado, anio_prueba=2024)
    # Los anchos de banda de los años de validación no cambian: no usaron el año de prueba
    ancho = lambda d, anio: (d[d["anio"] == anio]["hi"] - d[d["anio"] == anio]["lo"]).mean()
    assert ancho(a, 2022) == pytest.approx(ancho(b, 2022))


# ── Datos faltantes y fuga ───────────────────────────────────────────────
def test_split_features_conserva_nan_y_excluye_fuga():
    df = pd.DataFrame({
        "id_municipio": ["a"] * 4, "id_cultivo": [1] * 4, "id_tiempo": [1, 2, 3, 4], "anio": [2020, 2021, 2022, 2023],
        "id_departamento": ["05"] * 4, "clase_aptitud": [None] * 4, "es_anio_nino": [None] * 4,
        "rendimiento_t_ha": [2.0, 3.0, np.nan, 4.0], "produccion_total_ton": [1, 2, 3, 4],
        "area_cosechada_ha": [1, 1, 1, 1], "area_sembrada_ha": [1, 1, 1, 1],
        "lluvia_acumulada_anual": [np.nan, 1200.0, 1100.0, np.nan],
    })
    _, X, y, cols = tr._split_features(df)
    assert "area_cosechada_ha" not in cols and "produccion_total_ton" not in cols     # fuga del objetivo
    assert "rendimiento_t_ha" not in cols
    assert X["lluvia_acumulada_anual"].isna().sum() == 2                               # los vacíos NO se volvieron 0
    assert len(y) == 3                                                                 # filas sin objetivo se descartan


def test_ningun_codigo_de_modelo_rellena_con_cero():
    """Guardia estática: las funciones que arman los rasgos no rellenan vacíos con fillna(0).
    (_add_municipio_history usa fillna(0) solo como paso auxiliar del cumsum, contando aparte los años con dato.)"""
    for funcion in (tr._split_features, tr.train_and_report, bf._encode_categoricals, bf.build_ml_features, bf._add_lags):
        arbol = ast.parse(inspect.getsource(funcion).lstrip())
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "fillna":
                assert not (nodo.args and isinstance(nodo.args[0], ast.Constant) and nodo.args[0].value == 0), \
                    f"fillna(0) en {funcion.__name__}"


# ── Rasgos: rezagos por año y promedio histórico ─────────────────────────
def test_lag_es_por_anio_calendario_no_por_fila():
    df = pd.DataFrame({
        "id_municipio": ["a"] * 3, "id_cultivo": [1] * 3, "anio": [2019, 2020, 2022],     # falta 2021
        "lluvia_acumulada_anual": [100.0, 200.0, 400.0], "temp_promedio_anual": [20.0] * 3,
        "spi_promedio": [0.0] * 3, "precio_promedio_cop_kg": [1.0] * 3,
    })
    out = bf._add_lags(df).set_index("anio")
    assert out.loc[2020, "lluvia_acumulada_anual_lag1"] == 100.0
    assert np.isnan(out.loc[2022, "lluvia_acumulada_anual_lag1"])       # no existe 2021: NO toma 2020
    assert out.loc[2022, "lluvia_acumulada_anual_lag3"] == 100.0        # 2022 - 3 = 2019


def test_promedio_historico_excluye_el_anio_actual_e_ignora_vacios():
    df = pd.DataFrame({
        "id_municipio": ["a"] * 4, "id_cultivo": [1] * 4, "anio": [2019, 2020, 2021, 2022],
        "rendimiento_t_ha": [2.0, np.nan, 4.0, 10.0], "produccion_total_ton": [1.0, 1.0, 1.0, 1.0],
    })
    out = bf._add_municipio_history(df).set_index("anio")["rendimiento_t_ha_hist_avg"]
    assert np.isnan(out[2019])
    assert out[2020] == 2.0 and out[2021] == 2.0        # el vacío de 2020 no cuenta
    assert out[2022] == pytest.approx(3.0)              # (2 + 4) / 2, sin usar el 10 del año actual


def test_categoricas_sin_dato_quedan_nan():
    df = pd.DataFrame({"id_municipio": ["a", "b"], "id_departamento": ["05", "05"], "id_region": [1, None],
                       "clase_aptitud": ["alta", None], "es_anio_nino": [True, None]})
    out = bf._encode_categoricals(df)
    assert out["clase_aptitud_score"].tolist()[0] == 3 and np.isnan(out["clase_aptitud_score"].iloc[1])
    assert out["es_anio_nino_int"].iloc[0] == 1.0 and np.isnan(out["es_anio_nino_int"].iloc[1])


# ── Carga de producción ──────────────────────────────────────────────────
def test_agregar_produccion_recalcula_rendimiento_y_no_convierte_vacios_en_cero():
    df = pd.DataFrame({
        "id_municipio": ["a", "a", "b"], "id_cultivo": [1, 1, 1], "id_tiempo": [10, 10, 10],
        "area_sembrada_ha": [10.0, 10.0, np.nan], "area_cosechada_ha": [10.0, 10.0, np.nan],
        "produccion_total_ton": [20.0, 40.0, np.nan], "rendimiento_t_ha": [2.0, 4.0, np.nan],
    })
    out = agregar_produccion_anual(df).set_index("id_municipio")
    assert out.loc["a", "produccion_total_ton"] == 60.0 and out.loc["a", "area_cosechada_ha"] == 20.0
    assert out.loc["a", "rendimiento_t_ha"] == pytest.approx(3.0)      # 60/20, NO 2+4=6 como sumaba antes
    assert np.isnan(out.loc["b", "produccion_total_ton"]) and np.isnan(out.loc["b", "rendimiento_t_ha"])


def test_agregar_produccion_usa_rendimiento_medio_si_no_hay_area_cosechada():
    df = pd.DataFrame({
        "id_municipio": ["a", "a"], "id_cultivo": [1, 1], "id_tiempo": [10, 10],
        "area_sembrada_ha": [1.0, 1.0], "area_cosechada_ha": [0.0, 0.0],
        "produccion_total_ton": [5.0, 5.0], "rendimiento_t_ha": [2.0, 4.0],
    })
    assert agregar_produccion_anual(df)["rendimiento_t_ha"].iloc[0] == pytest.approx(3.0)
