"""Tests de clean_produccion: acepta las columnas crudas de Socrata y las ya renombradas por el extractor."""
import numpy as np
import pandas as pd
import pytest

from clean.clean_produccion import normalizar_produccion
from load.load_facts import _normalizar_nombre


def _crudo():
    """Columnas tal como salen de Socrata (uejq-wxrr)."""
    return pd.DataFrame({
        "a_o": ["2022", "2023"], "cultivo": ["CAFÉ", "PLÁTANO"],
        "rea_sembrada": ["10", "abc"], "rea_cosechada": ["9", "5"],
        "producci_n": ["18", "10"], "rendimiento": ["2.0", "2.0"],
        "grupo_cultivo": ["CAFE", "PLATANO"], "ciclo_del_cultivo": ["PERMANENTE", "PERMANENTE"],
        "c_digo_dane_municipio": ["5001", "73001"],
    })


def _renombrado():
    """Columnas tal como las deja extract_produccion (RENAME_MAP ya aplicado)."""
    return pd.DataFrame({
        "anio": [2022, 2023], "cultivo": ["CAFÉ", "PLÁTANO"],
        "area_sembrada_ha": [10.0, np.nan], "area_cosechada_ha": [9.0, 5.0],
        "produccion_t": [18.0, 10.0], "rendimiento_t_ha": [2.0, 2.0],
        "grupo_cultivo": ["CAFE", "PLATANO"], "ciclo_cultivo": ["PERMANENTE", "PERMANENTE"],
        "codigo_dane_municipio": ["05001", "73001"],
    })


@pytest.mark.parametrize("entrada", [_crudo, _renombrado], ids=["crudo", "ya_renombrado"])
def test_ambos_esquemas_producen_el_mismo_contrato(entrada):
    df = normalizar_produccion(entrada())
    for col in ("anio", "area_sembrada_ha", "area_cosechada_ha", "produccion_total_ton", "rendimiento_t_ha",
                "grupo_de_cultivo", "ciclo_de_cultivo", "id_municipio", "cultivo"):
        assert col in df.columns, col
    assert df["id_municipio"].tolist() == ["05001", "73001"]        # 5 dígitos
    assert df["produccion_total_ton"].tolist() == [18.0, 10.0]
    assert df["anio"].dtype.kind in "if"


def test_no_rellena_vacios_con_cero():
    df = normalizar_produccion(_crudo())
    assert np.isnan(df.loc[1, "area_sembrada_ha"])                   # 'abc' -> NaN, no 0


def test_columna_faltante_se_crea_vacia_y_las_obligatorias_fallan_claro():
    df = _renombrado().drop(columns=["area_cosechada_ha", "grupo_cultivo"])
    out = normalizar_produccion(df)
    assert out["area_cosechada_ha"].isna().all() and out["grupo_de_cultivo"].isna().all()
    with pytest.raises(ValueError, match="faltan columnas obligatorias"):
        normalizar_produccion(_renombrado().drop(columns=["rendimiento_t_ha"]))


def test_cultivos_con_tilde_coinciden_con_la_llave_de_dim_cultivo():
    """Regresión: dim_cultivo se cargaba con upper() y la producción con normalización sin tildes,
    por lo que Café, Plátano, Maíz... nunca coincidían y se perdían al cargar los hechos."""
    assert _normalizar_nombre("Café") == _normalizar_nombre("CAFÉ") == "CAFE"
    assert _normalizar_nombre("  Plátano  hartón ") == "PLATANO HARTON"
