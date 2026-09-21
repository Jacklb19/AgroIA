"""Todos los módulos del proyecto deben poder importarse y los símbolos que otros usan deben existir.
Habría detectado: SOCRATA_TOKEN inexistente en config.settings y fill_fact_clima_from_openmeteo faltante."""
import importlib
import pkgutil

import pytest

PAQUETES = ["config", "extract", "clean", "load", "utils", "validate"]
MODULOS_SUELTOS = ["models.build_features", "models.train_rendimiento", "models.train_alerta_climatica",
                   "models.train_clima_forecast", "models.detect_anomalies", "models.informe_precios",
                   "models.train_precio_forecast", "run_pipeline", "run_prices"]


def _modulos_de(paquete: str):
    pkg = importlib.import_module(paquete)
    for m in pkgutil.iter_modules(pkg.__path__, prefix=f"{paquete}."):
        yield m.name


TODOS = [m for p in PAQUETES for m in _modulos_de(p)] + MODULOS_SUELTOS


@pytest.mark.parametrize("modulo", TODOS)
def test_el_modulo_se_importa(modulo):
    if modulo == "validate.anova_tests":
        pytest.importorskip("matplotlib")
    importlib.import_module(modulo)


def test_settings_define_lo_que_importan_los_extractores():
    from config import settings
    for nombre in ("SOURCES", "DATA_RAW", "CLIMA_YEAR_START", "YEAR_END", "SOCRATA_TOKEN"):
        assert hasattr(settings, nombre), nombre


def test_load_facts_expone_las_funciones_que_usa_run_openmeteo_fill():
    from load import load_facts
    assert callable(load_facts.fill_fact_clima_from_openmeteo)
