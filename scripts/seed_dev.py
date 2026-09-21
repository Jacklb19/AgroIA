"""
seed_dev.py — Datos SINTÉTICOS mínimos para desarrollar y probar sin descargar las fuentes reales.

  python scripts/seed_dev.py                 # aplica migraciones y siembra (base local vacía)
  python scripts/seed_dev.py --reset         # borra el esquema public y vuelve a sembrar
  python scripts/seed_dev.py --modelo        # además entrena el modelo de rendimiento (pocas pruebas Optuna)

Por seguridad solo corre contra una base LOCAL (localhost / 127.0.0.1) y se niega a mezclar datos de ejemplo
con datos reales: si ya hay producción cargada, falla. La siembra queda anotada en ingest_run (fuente 'seed_dev'),
que /api/estado usa para rotular la web como "datos de ejemplo".

Las cifras son inventadas a propósito (municipios y cultivos reales, valores aleatorios con semilla fija):
sirven para ver la interfaz y correr pruebas, NUNCA como información agrícola.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

SEMILLA = 20260918
ANIOS = range(2019, 2026)

# (código DIVIPOLA, municipio, cód. depto, departamento, región, lat, lon)
MUNICIPIOS = [
    ("52001", "Pasto", "52", "Nariño", "Andina", 1.214, -77.281),
    ("73001", "Ibagué", "73", "Tolima", "Andina", 4.438, -75.232),
    ("50001", "Villavicencio", "50", "Meta", "Orinoquía", 4.142, -73.627),
    ("05001", "Medellín", "05", "Antioquia", "Andina", 6.244, -75.581),
    ("76001", "Cali", "76", "Valle del Cauca", "Pacífico", 3.452, -76.532),
    ("11001", "Bogotá D.C.", "11", "Bogotá D.C.", "Andina", 4.711, -74.072),
    ("15001", "Tunja", "15", "Boyacá", "Andina", 5.535, -73.367),
    ("19001", "Popayán", "19", "Cauca", "Pacífico", 2.444, -76.614),
    ("23001", "Montería", "23", "Córdoba", "Caribe", 8.750, -75.881),
    ("20001", "Valledupar", "20", "Cesar", "Caribe", 10.463, -73.253),
    ("41001", "Neiva", "41", "Huila", "Andina", 2.927, -75.281),
    ("54001", "Cúcuta", "54", "Norte de Santander", "Andina", 7.894, -72.508),
]
# (nombre, normalizado, ciclo, rendimiento típico t/ha)
CULTIVOS = [
    ("Papa", "PAPA", "transitorio", 20.0),
    ("Maíz", "MAIZ", "transitorio", 3.5),
    ("Arroz", "ARROZ", "transitorio", 5.5),
    ("Café", "CAFE", "permanente", 1.1),
    ("Plátano", "PLATANO", "permanente", 9.0),
    ("Cebolla", "CEBOLLA", "transitorio", 22.0),
]
# (mercado canónico, ciudad, cód. municipio, cód. depto, departamento)
MERCADOS = [
    ("Bogotá, Corabastos", "Bogotá D.C.", "11001", "11", "Bogotá D.C."),
    ("Pasto, El Potrerillo", "Pasto", "52001", "52", "Nariño"),
    ("Ibagué, La 21", "Ibagué", "73001", "73", "Tolima"),
    ("Medellín, Central Mayorista de Antioquia", "Medellín", "05001", "05", "Antioquia"),
]
# (producto, normalizado, grupo, precio base COP/kg)
PRODUCTOS = [
    ("Papa negra", "PAPA NEGRA", "Tubérculos", 1800.0),
    ("Cebolla cabezona blanca", "CEBOLLA CABEZONA BLANCA", "Verduras y hortalizas", 2200.0),
    ("Plátano hartón verde", "PLATANO HARTON VERDE", "Frutas", 2500.0),
    ("Tomate", "TOMATE", "Verduras y hortalizas", 2900.0),
]
DIAS_PRECIOS = 75


class SiembraError(RuntimeError):
    pass


def _sembrar_dimensiones(engine, rng) -> None:
    from load.load_dimensions import load_dim_region_natural, load_dim_tiempo

    load_dim_region_natural(engine)
    load_dim_tiempo(engine)
    with engine.begin() as conn:
        regiones = {n: i for i, n in conn.execute(text("SELECT id_region, nombre_region FROM dim_region_natural"))}
        for cod, nombre, dep, nombre_dep, region, lat, lon in MUNICIPIOS:
            conn.execute(
                text("""INSERT INTO dim_municipio (id_municipio, nombre_municipio, id_departamento, nombre_departamento,
                                                   id_region, latitud_centroide, longitud_centroide)
                        VALUES (:c, :n, :d, :nd, :r, :la, :lo) ON CONFLICT (id_municipio) DO NOTHING"""),
                {"c": cod, "n": nombre, "d": dep, "nd": nombre_dep, "r": regiones[region], "la": lat, "lo": lon},
            )
        for nombre, norm, ciclo, _ in CULTIVOS:
            conn.execute(
                text("""INSERT INTO dim_cultivo (nombre_cultivo, nombre_normalizado, tipo_ciclo)
                        VALUES (:n, :nn, :c) ON CONFLICT (nombre_normalizado) DO NOTHING"""),
                {"n": nombre, "nn": norm, "c": ciclo},
            )


def _sembrar_produccion(engine, rng) -> int:
    with engine.begin() as conn:
        base_por_norm = {c[1]: c[3] for c in CULTIVOS}
        cultivos = {
            norm: (id_cultivo, base_por_norm[norm])
            for id_cultivo, norm in conn.execute(text("SELECT id_cultivo, nombre_normalizado FROM dim_cultivo"))
        }
        tiempos = {a: i for i, a in conn.execute(text("SELECT id_tiempo, anio FROM dim_tiempo WHERE mes = 1"))}
        filas = []
        for cod, *_ in MUNICIPIOS:
            factor_muni = rng.uniform(0.75, 1.25)
            for _, norm, _, _ in CULTIVOS:
                if rng.random() > 0.75:          # no todos los municipios siembran todo
                    continue
                id_cultivo, base = cultivos[norm]
                area = rng.uniform(40, 900)
                for k, anio in enumerate(ANIOS):
                    rend = max(0.1, base * factor_muni * (1 + 0.015 * k) * rng.normal(1.0, 0.09))
                    cosechada = area * rng.uniform(0.85, 1.0)
                    filas.append({
                        "m": cod, "c": id_cultivo, "t": tiempos[anio], "sem": round(area, 1), "cos": round(cosechada, 1),
                        "prod": round(cosechada * rend, 1), "rend": round(rend, 3),
                    })
        conn.execute(
            text("""INSERT INTO fact_produccion_agricola (id_municipio, id_cultivo, id_tiempo, area_sembrada_ha,
                        area_cosechada_ha, produccion_total_ton, rendimiento_t_ha, fuente_origen)
                    VALUES (:m, :c, :t, :sem, :cos, :prod, :rend, 'seed_dev') ON CONFLICT DO NOTHING"""),
            filas,
        )
    return len(filas)


def _sembrar_enso(engine) -> None:
    """Fase ENSO sintética por año (marcada es_sintetico) para que las pantallas de clima tengan algo que mostrar."""
    fases = {2019: "El Niño", 2020: "La Niña", 2021: "La Niña", 2022: "La Niña", 2023: "El Niño", 2024: "Neutro", 2025: "Neutro"}
    with engine.begin() as conn:
        tiempos = list(conn.execute(text("SELECT id_tiempo, anio FROM dim_tiempo WHERE anio BETWEEN 2019 AND 2025")))
        regiones = [r[0] for r in conn.execute(text("SELECT id_region FROM dim_region_natural"))]
        filas = [
            {"t": t, "r": r, "f": fases[a], "oni": {"El Niño": 0.9, "La Niña": -0.9}.get(fases[a], 0.0)}
            for t, a in tiempos for r in regiones
        ]
        conn.execute(
            text("""INSERT INTO fact_alerta_enso (id_tiempo, id_region, fase_enso, indice_oni, fuente_origen, es_sintetico)
                    VALUES (:t, :r, :f, :oni, 'seed_dev', TRUE) ON CONFLICT DO NOTHING"""),
            filas,
        )


def _sembrar_precios(engine, rng) -> int:
    """Precios diarios por el cargador real (load_precios.cargar_precios): también sirve de prueba de humo del flujo."""
    from clean.clean_precios_diarios import COLUMNAS_SALIDA
    from load.load_precios import cargar_precios

    fin = date.today() - timedelta(days=1)
    dias = [fin - timedelta(days=i) for i in range(DIAS_PRECIOS)]
    dias = [d for d in reversed(dias) if d.weekday() < 5]     # DANE publica días hábiles
    filas = []
    for mercado, ciudad, muni, dep, dep_nombre in MERCADOS:
        for producto, norm, grupo, base in PRODUCTOS:
            nivel = base * rng.uniform(0.85, 1.2)
            for d in dias:
                nivel = max(base * 0.4, nivel * (1 + rng.normal(0.0, 0.025)))
                filas.append({
                    "fecha": pd.Timestamp(d), "mercado": mercado, "ciudad": ciudad, "id_municipio": muni,
                    "id_departamento": dep, "departamento": dep_nombre, "producto": producto, "producto_norm": norm,
                    "grupo": grupo, "precio_min_kg": round(nivel * 0.93, 1), "precio_max_kg": round(nivel * 1.07, 1),
                    "precio_prom_kg": round(nivel, 1), "fuente": "soap",
                })
    return cargar_precios(engine, pd.DataFrame(filas, columns=COLUMNAS_SALIDA), "soap")


def _entrenar_modelo(engine) -> None:
    os.environ.setdefault("OPTUNA_TRIALS", "5")
    from models.build_features import build_ml_features
    from models.train_rendimiento import train_and_report

    if build_ml_features(engine).empty:
        raise SiembraError("No se pudo construir el feature store con los datos sembrados")
    train_and_report(engine=engine)


def sembrar(engine, modelo: bool = False, semilla: int = SEMILLA) -> dict:
    """Aplica migraciones y siembra. Falla si la base ya tiene producción (no mezcla ejemplo con datos reales)."""
    from load.db import init_schema

    init_schema(engine)
    with engine.connect() as conn:
        if conn.execute(text("SELECT COUNT(*) FROM fact_produccion_agricola")).scalar():
            raise SiembraError("La base ya tiene datos de producción: no se mezclan con los de ejemplo (usa --reset en una base local).")

    rng = np.random.default_rng(semilla)
    _sembrar_dimensiones(engine, rng)
    n_prod = _sembrar_produccion(engine, rng)
    _sembrar_enso(engine)
    n_precios = _sembrar_precios(engine, rng)
    from models.informe_precios import generar_informe

    generar_informe(engine)          # la portada muestra el informe del último día
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO ingest_run (fuente, finished_at, status, filas_nuevas, source_ref) "
            "VALUES ('seed_dev', NOW(), 'ok', :n, 'datos sinteticos de desarrollo')"), {"n": n_prod + n_precios})
    if modelo:
        _entrenar_modelo(engine)
    return {"produccion": n_prod, "precios": n_precios, "municipios": len(MUNICIPIOS), "cultivos": len(CULTIVOS)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Siembra datos sintéticos de desarrollo (solo bases locales)")
    parser.add_argument("--reset", action="store_true", help="Borra el esquema public antes de sembrar")
    parser.add_argument("--modelo", action="store_true", help="Entrena también el modelo de rendimiento (rápido, 5 pruebas)")
    args = parser.parse_args(argv)

    from config.settings import ConfigError, db_config
    from load.db import get_engine

    try:
        cfg = db_config()
        if not cfg["local"]:
            print(f"ERROR: la base apunta a {cfg['host']!r}. Este script solo siembra bases locales (localhost/127.0.0.1).", file=sys.stderr)
            return 2
        engine = get_engine()
        if args.reset:
            with engine.begin() as conn:
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
        resumen = sembrar(engine, modelo=args.modelo)
    except (ConfigError, SiembraError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Datos de EJEMPLO sembrados:", resumen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
