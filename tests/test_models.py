"""Smoke tests para módulos de modelos: importan correctamente."""
import importlib


def test_train_rendimiento_imports():
    mod = importlib.import_module("models.train_rendimiento")
    assert callable(mod.train_and_report)
    assert mod.N_TRIALS_OPTUNA >= 100
    assert mod.RANDOM_SEED == 42


def test_detect_anomalies_imports():
    mod = importlib.import_module("models.detect_anomalies")
    assert callable(mod.detect_and_persist)


def test_train_clima_forecast_imports():
    mod = importlib.import_module("models.train_clima_forecast")
    assert callable(mod.forecast_and_persist)
