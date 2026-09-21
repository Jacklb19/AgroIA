"""Flujos completos contra Postgres real (marca `db`): siembra sintética → precios → informe → modelo."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import seed_dev  # noqa: E402


@pytest.fixture()
def base_sembrada(engine_limpio):
    seed_dev.sembrar(engine_limpio)
    return engine_limpio


@pytest.mark.db
def test_la_siembra_deja_datos_coherentes(base_sembrada):
    with base_sembrada.connect() as conn:
        n_muni = conn.execute(text("SELECT COUNT(*) FROM dim_municipio")).scalar()
        n_prod = conn.execute(text("SELECT COUNT(*) FROM fact_produccion_agricola")).scalar()
        rend_malos = conn.execute(text(
            "SELECT COUNT(*) FROM fact_produccion_agricola WHERE rendimiento_t_ha IS NULL OR rendimiento_t_ha <= 0")).scalar()
        marca = conn.execute(text("SELECT status FROM ingest_run WHERE fuente = 'seed_dev'")).scalar()
    assert n_muni == len(seed_dev.MUNICIPIOS) and n_prod > 100 and rend_malos == 0 and marca == "ok"


@pytest.mark.db
def test_no_se_mezcla_ejemplo_con_datos_ya_cargados(base_sembrada):
    with pytest.raises(seed_dev.SiembraError, match="ya tiene datos"):
        seed_dev.sembrar(base_sembrada)


@pytest.mark.db
def test_la_siembra_es_reproducible(engine_limpio):
    a = seed_dev.sembrar(engine_limpio, semilla=7)
    with engine_limpio.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    b = seed_dev.sembrar(engine_limpio, semilla=7)
    assert a["produccion"] == b["produccion"]


@pytest.mark.db
def test_precios_llegan_a_la_vista_y_reingestar_no_cambia_nada(base_sembrada):
    from load.load_precios import cargar_precios  # noqa: F401  (el flujo ya lo usó la siembra)

    with base_sembrada.connect() as conn:
        filas = conn.execute(text("SELECT COUNT(*) FROM v_precio_actual")).scalar()
        sin_var = conn.execute(text("SELECT COUNT(*) FROM v_precio_actual WHERE var_dia_pct IS NULL")).scalar()
    assert filas == len(seed_dev.MERCADOS) * len(seed_dev.PRODUCTOS)
    assert sin_var == 0            # todas las series tienen día anterior con qué comparar


@pytest.mark.db
def test_el_informe_diario_se_genera_desde_los_precios_sembrados(base_sembrada):
    from models.informe_precios import generar_informe

    informe = generar_informe(base_sembrada)
    assert informe and informe["fecha"]
    with base_sembrada.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM informe_precio_diario")).scalar() == 1


@pytest.mark.db
def test_el_modelo_se_entrena_y_guarda_predicciones_fuera_de_muestra(engine_limpio, monkeypatch):
    monkeypatch.setenv("OPTUNA_TRIALS", "3")
    seed_dev.sembrar(engine_limpio, modelo=True)
    with engine_limpio.connect() as conn:
        activos = conn.execute(text("SELECT COUNT(*) FROM model_version WHERE activo")).scalar()
        preds = conn.execute(text("SELECT COUNT(*) FROM pred_rendimiento")).scalar()
        no_holdout = conn.execute(text("SELECT COUNT(*) FROM pred_rendimiento WHERE NOT es_holdout")).scalar()
    assert activos >= 1 and preds > 0
    assert no_holdout == 0        # nunca se guardan predicciones sobre datos con los que se entrenó
