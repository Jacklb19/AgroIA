"""Tests sobre módulos clean: contratos básicos sin BD."""
import importlib

import pandas as pd
import pytest


CLEAN_MODULES = [
    "clean.clean_clima",
    "clean.clean_insumos",
    "clean.clean_municipios",
    "clean.clean_precios",
    "clean.clean_suelo",
]


@pytest.mark.parametrize("mod_path", CLEAN_MODULES)
def test_clean_module_imports(mod_path):
    """Cada módulo de clean debe importar sin errores."""
    mod = importlib.import_module(mod_path)
    # Al menos una función pública (no _privada)
    publicas = [name for name in dir(mod) if not name.startswith("_") and callable(getattr(mod, name))]
    assert len(publicas) > 0, f"{mod_path} no expone funciones públicas"


def test_pandas_available():
    """Sanity check: dependencias core instaladas."""
    df = pd.DataFrame({"a": [1, 2, 3]})
    assert df.shape == (3, 1)
