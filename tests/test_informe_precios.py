"""Tests sin BD del informe diario de precios (función pura calcular_informe)."""
from datetime import date, timedelta

import pandas as pd
import pytest

from models.informe_precios import calcular_informe

HOY = date(2026, 9, 18)


def _serie(id_central, mercado, dep, id_producto, producto, precios_por_dia):
    """precios_por_dia: {dias_antes_de_hoy: precio}"""
    return [
        {
            "id_central": id_central, "mercado": mercado, "departamento": dep,
            "id_producto": id_producto, "producto": producto, "grupo": "Frutas",
            "fecha": pd.Timestamp(HOY - timedelta(days=dias)), "precio_prom_kg": precio,
        }
        for dias, precio in precios_por_dia.items()
    ]


@pytest.fixture
def df():
    filas = []
    # Papa: sube 10% en el día, baja 20% en 7 días, en dos mercados; un tercero más caro
    filas += _serie(1, "Pasto, El Potrerillo", "Nariño", 10, "Papa criolla", {0: 2200, 1: 2000, 7: 2750})
    filas += _serie(2, "Bogotá, Corabastos", "Bogotá D.C.", 10, "Papa criolla", {0: 3000, 1: 3000, 7: 3000})
    filas += _serie(3, "Cali, Cavasa", "Valle del Cauca", 10, "Papa criolla", {0: 4000, 1: 4000, 7: 4000})
    # Tomate: baja 25% en el día
    filas += _serie(1, "Pasto, El Potrerillo", "Nariño", 20, "Tomate", {0: 1500, 1: 2000})
    # Serie con un pico atípico hoy (30 días estables ~1000 y hoy 5000)
    estable = {d: 1000 + (d % 3) * 10 for d in range(1, 31)}
    filas += _serie(2, "Bogotá, Corabastos", "Bogotá D.C.", 30, "Lulo", {0: 5000, **estable})
    # Serie inactiva hoy (último dato hace 3 días): cuenta como activa pero sin dato
    filas += _serie(3, "Cali, Cavasa", "Valle del Cauca", 40, "Yuca", {3: 800, 4: 800})
    # Dato viejo (> 30 días): no es serie activa
    filas += _serie(3, "Cali, Cavasa", "Valle del Cauca", 50, "Coco", {90: 3000})
    return pd.DataFrame(filas)


def test_cobertura_distingue_series_activas_y_con_dato(df):
    inf = calcular_informe(df, HOY)
    c = inf["cobertura"]
    assert c["series_con_dato"] == 5          # 3 de papa + tomate + lulo
    assert c["series_activas"] == 6           # + yuca (último dato hace 3 días); coco (90 días) no cuenta
    assert c["mercados_con_dato"] == 3


def test_subidas_y_bajadas_del_dia(df):
    inf = calcular_informe(df, HOY)
    subidas = {f["producto"]: f["var_pct"] for f in inf["mayores_subidas_dia"]}
    bajadas = {f["producto"]: f["var_pct"] for f in inf["mayores_bajadas_dia"]}
    assert subidas["Lulo"] == pytest.approx(395.0, abs=0.1)                 # 1010 (dato de ayer) -> 5000
    assert subidas["Papa criolla"] == pytest.approx(10.0, abs=0.1)          # Pasto 2000 -> 2200
    assert bajadas == {"Tomate": -25.0}
    # el primero de la lista es el mayor
    assert inf["mayores_subidas_dia"][0]["producto"] == "Lulo"


def test_variacion_7_dias_usa_dato_de_hace_una_semana(df):
    inf = calcular_informe(df, HOY)
    bajadas7 = inf["mayores_bajadas_7d"]
    assert bajadas7[0]["producto"] == "Papa criolla" and bajadas7[0]["mercado"].startswith("Pasto")
    assert bajadas7[0]["var_pct"] == pytest.approx(-20.0, abs=0.1)         # 2750 -> 2200


def test_brecha_entre_mercados_exige_minimo_de_mercados(df):
    inf = calcular_informe(df, HOY)
    productos = {b["producto"]: b for b in inf["brecha_entre_mercados"]}
    assert set(productos) == {"Papa criolla"}                               # los demás tienen < 3 mercados
    p = productos["Papa criolla"]
    assert p["mas_barato"]["mercado"].startswith("Pasto") and p["mas_barato"]["precio"] == 2200
    assert p["mas_caro"]["mercado"].startswith("Cali") and p["mas_caro"]["precio"] == 4000
    assert p["brecha_pct"] == pytest.approx((4000 - 2200) / 2200 * 100, abs=0.1)


def test_atipicos_detecta_pico_y_reporta_z(df):
    inf = calcular_informe(df, HOY)
    assert [a["producto"] for a in inf["atipicos"]] == ["Lulo"]
    assert inf["atipicos"][0]["z"] > 3 and inf["atipicos"][0]["promedio_30d"] == pytest.approx(1010, abs=15)


def test_resumen_por_departamento(df):
    inf = calcular_informe(df, HOY)
    dep = {d["departamento"]: d for d in inf["por_departamento"]}
    assert dep["Nariño"]["series"] == 2
    assert dep["Nariño"]["suben_dia"] == 1 and dep["Nariño"]["bajan_dia"] == 1


def test_dia_sin_datos_devuelve_listas_vacias(df):
    inf = calcular_informe(df, HOY + timedelta(days=30))
    assert inf["cobertura"]["series_con_dato"] == 0
    assert inf["mayores_subidas_dia"] == [] and inf["atipicos"] == [] and inf["por_departamento"] == []


def test_dato_anterior_muy_viejo_no_cuenta_como_variacion_diaria():
    # Único dato previo hace 20 días: no se puede hablar de "variación del día"
    filas = _serie(1, "Pasto, El Potrerillo", "Nariño", 10, "Papa criolla", {0: 2000, 20: 1000})
    inf = calcular_informe(pd.DataFrame(filas), HOY)
    assert inf["mayores_subidas_dia"] == [] and inf["mayores_subidas_7d"] == []
