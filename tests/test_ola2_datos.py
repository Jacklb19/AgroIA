"""Tests de la Ola 2: alertas con objetivo predictivo, índices ENSO/precipitación, ANOVA robusto y fuentes corregidas."""
import numpy as np
import pandas as pd
import pytest

import models.train_alerta_climatica as al
from clean.clean_suelo import _resumir_por_codigo
from extract.extract_cna import parsear_cuadro_uso_suelo
from load.derive_clima_indices import anios_nino, indices_precipitacion
from validate.anova_robusto import agregar_unidades_independientes, comparar_grupos, etiqueta_efecto, posthoc_holm


# ── Alertas: el objetivo es el mes SIGUIENTE, no una regla sobre las mismas columnas ──────────
def _clima(meses=30, municipios=("a", "b"), seed=1):
    rng = np.random.default_rng(seed)
    filas = []
    for m in municipios:
        for k in range(meses):
            anio, mes = 2020 + k // 12, k % 12 + 1
            filas.append({
                "id_municipio": m, "id_tiempo": k + 1, "anio": anio, "mes": mes,
                "precipitacion_mm": rng.uniform(20, 300), "temperatura_media_c": 24.0, "temperatura_max_c": rng.uniform(28, 40),
                "temperatura_min_c": 15.0, "humedad_relativa_pct": 70.0, "brillo_solar_horas_dia": 5.0,
                "fase_enso": "Neutro", "indice_oni": 0.0,
                "indice_spi": rng.normal(0, 1.2), "anomalia_precipitacion_pct": rng.normal(0, 40),
            })
    return pd.DataFrame(filas)


def test_el_objetivo_es_el_riesgo_del_mes_siguiente():
    ds = al.construir_dataset(_clima())
    a = ds[ds["id_municipio"] == "a"].set_index("periodo")
    # y del mes t == riesgo observado del mes t+1
    assert (a["y"].iloc[:-1].to_numpy() == a["riesgo_obs"].iloc[1:].to_numpy()).all()
    assert np.isnan(a["y"].iloc[-1])                      # el último mes no tiene "mes siguiente": no se inventa
    # el rezago usa el mes anterior
    assert a["riesgo_obs_lag1"].iloc[5] == a["riesgo_obs"].iloc[4]


def test_una_laguna_de_meses_no_conecta_meses_no_consecutivos():
    df = _clima(meses=6, municipios=("a",))
    df = df[df["mes"] != 3]                               # falta marzo
    ds = al.construir_dataset(df).set_index("mes")
    assert np.isnan(ds.loc[2, "y"])                       # febrero no tiene marzo: y = NaN, no abril


def test_el_corte_temporal_no_mezcla_futuro_en_el_entrenamiento():
    ds = al.construir_dataset(_clima())
    train, test = al.dividir_temporal(ds, meses_prueba=6)
    assert train["periodo"].max() + 1 < test["periodo"].min()     # el objetivo del entrenamiento ocurre antes de la prueba
    assert test["y"].notna().all() and train["y"].notna().all()
    assert len(test["periodo"].unique()) == 6


def test_las_reglas_ignoran_lo_que_falta_y_no_lo_convierten_en_cero():
    fila_vacia = {"fase_enso": "Neutro"}
    assert al._etiquetar_riesgo(fila_vacia) == 0
    assert al._clasificar_tipo_evento(fila_vacia) == al.TIPOS_EVENTO["NORMAL"]
    sequia = {"indice_spi": -2.0, "anomalia_precipitacion_pct": -60.0, "temperatura_max_c": 39.0, "fase_enso": "El Niño"}
    assert al._etiquetar_riesgo(sequia) == 2
    assert al._clasificar_tipo_evento(sequia) == al.TIPOS_EVENTO["SEQUIA"]
    assert "MERCADO" not in al.TIPOS_EVENTO                        # tipo que nunca se calculaba


# ── Índices derivados de datos reales ────────────────────────────────────
def test_anomalia_y_spi_solo_con_suficientes_anios():
    filas = [{"id_region": 1, "anio": 2018 + i, "mes": 1, "precip": p} for i, p in enumerate([100, 100, 100, 200, 0])]
    filas += [{"id_region": 1, "anio": 2018, "mes": 2, "precip": 50}]          # un solo año para febrero
    out = indices_precipitacion(pd.DataFrame(filas)).set_index(["mes", "anio"])
    assert out.loc[(1, 2021), "anomalia_pct"] == pytest.approx(100.0)          # media enero = 100 -> 200 es +100 %
    assert out.loc[(1, 2021), "spi_z"] > 0 > out.loc[(1, 2022), "spi_z"]
    assert np.isnan(out.loc[(2, 2018), "spi_z"])                                # 1 año: sin referencia, NaN


def test_anio_nino_se_deriva_del_oni_no_de_una_lista_fija():
    oni = pd.DataFrame({"anio": [2023] * 12 + [2024] * 12,
                        "indice_oni": [0.6] * 6 + [0.0] * 6 + [0.2] * 12})
    assert anios_nino(oni) == {2023: True, 2024: False}


# ── ANOVA con supuestos realistas ────────────────────────────────────────
def test_agregar_unidades_independientes_colapsa_estaciones_del_mismo_mes():
    df = pd.DataFrame({"anio": [2020] * 4, "mes": [1, 1, 2, 2], "fase": ["N"] * 4, "precipitacion_mm": [10.0, 30.0, 5.0, 15.0]})
    out = agregar_unidades_independientes(df, "precipitacion_mm", ["anio", "mes", "fase"])
    assert out["precipitacion_mm"].tolist() == [20.0, 10.0]


def test_comparar_grupos_detecta_efecto_grande_y_no_inventa_efecto_nulo():
    rng = np.random.default_rng(0)
    con_efecto = comparar_grupos({"a": rng.normal(0, 1, 40), "b": rng.normal(2, 1, 40), "c": rng.normal(4, 1, 40)})
    assert con_efecto["welch_p"] < 1e-6 and con_efecto["kruskal_p"] < 1e-6
    assert con_efecto["eta2"] > 0.5 and etiqueta_efecto(con_efecto["eta2"]) == "grande"
    sin_efecto = comparar_grupos({k: rng.normal(0, 1, 40) for k in "abc"})
    assert sin_efecto["welch_p"] > 0.01 and sin_efecto["eta2"] < 0.06


def test_comparar_grupos_exige_grupos_con_datos():
    with pytest.raises(ValueError):
        comparar_grupos({"a": np.array([1.0, 2.0, 3.0]), "b": np.array([1.0])})


def test_posthoc_holm_marca_solo_los_pares_distintos():
    rng = np.random.default_rng(1)
    ph = posthoc_holm({"a": rng.normal(0, 1, 50), "b": rng.normal(0.05, 1, 50), "c": rng.normal(5, 1, 50)}).set_index(["grupo1", "grupo2"])
    assert not ph.loc[("a", "b"), "significativo"]
    assert ph.loc[("a", "c"), "significativo"] and ph.loc[("b", "c"), "significativo"]


# ── Fuentes corregidas ───────────────────────────────────────────────────
def test_cna_lee_columnas_reales_y_no_fabrica_permanentes_transitorios():
    raw = pd.DataFrame([
        ["Cuadro 2."] + [None] * 7,
        ["05", "Antioquia", "05001", "Medellín", 4055.6, 2933.9, 4494.2, 147.8],
        ["05", "Antioquia", "05002", "Abejorral", 15615.8, 8648.7, 7755.3, 59.6],
        [None, "Total Nacional", None, None, 24797932.9, 9628688.6, 8476711.2, 121406.9],   # fila de totales: se descarta
    ])
    df = parsear_cuadro_uso_suelo(raw)
    assert df["id_municipio"].tolist() == ["05001", "05002"]
    assert df.loc[0, "area_agricola_ha"] == 4494.2 and df.loc[0, "area_pastos_ha"] == 4055.6
    assert "area_cultivos_permanentes_ha" not in df.columns and "area_cultivos_transitorios_ha" not in df.columns


def test_aptitud_toma_la_clase_mas_frecuente_no_la_primera_fila():
    gdf = pd.DataFrame({
        "id_municipio": ["5001"] * 5, "producto": ["PAPA"] * 5,
        "aptitud": ["Baja", "Alta", "Alta", "Alta", "Media"],       # la primera es 'Baja' pero domina 'Alta'
    })
    out = _resumir_por_codigo(gdf, "id_municipio")
    assert out["clase_aptitud"].tolist() == ["Alta"]
    assert out["id_municipio"].tolist() == ["05001"]
