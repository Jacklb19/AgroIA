"""
load_precios.py — Carga de precios mayoristas diarios (SIPSA) a Postgres.

- Dimensiones: dim_producto_precio y dim_central_abastos (mercado).
- Hecho: fact_precio_diario, upsert masivo con execute_values (700k filas
  con executemany fila a fila tardaría demasiado sobre Supabase).
- Precedencia: una fila 'soap' (trae mín/máx) nunca es sobrescrita por una 'excel'.
- Bitácora: ingest_run alimenta /api/precios/estado y la lógica de "sin cambios".
"""
import logging
from datetime import date

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

logger = logging.getLogger(__name__)

PAGE_SIZE = 5_000

_SQL_FACT = """
    INSERT INTO fact_precio_diario
        (id_central, id_producto, fecha, precio_min_kg, precio_max_kg, precio_prom_kg, fuente)
    VALUES %s
    ON CONFLICT (id_central, id_producto, fecha) DO UPDATE SET
        precio_prom_kg = EXCLUDED.precio_prom_kg,
        precio_min_kg  = COALESCE(EXCLUDED.precio_min_kg, fact_precio_diario.precio_min_kg),
        precio_max_kg  = COALESCE(EXCLUDED.precio_max_kg, fact_precio_diario.precio_max_kg),
        fuente         = EXCLUDED.fuente,
        ingested_at    = NOW()
    WHERE (EXCLUDED.fuente = 'soap' OR fact_precio_diario.fuente <> 'soap')
      AND (   fact_precio_diario.precio_prom_kg IS DISTINCT FROM EXCLUDED.precio_prom_kg
           OR fact_precio_diario.precio_min_kg  IS DISTINCT FROM COALESCE(EXCLUDED.precio_min_kg, fact_precio_diario.precio_min_kg)
           OR fact_precio_diario.precio_max_kg  IS DISTINCT FROM COALESCE(EXCLUDED.precio_max_kg, fact_precio_diario.precio_max_kg)
           OR fact_precio_diario.fuente         IS DISTINCT FROM EXCLUDED.fuente)
    RETURNING 1
"""


def _nulo(valor):
    """NaN/NaT/pd.NA -> None para que psycopg2 envíe NULL."""
    return None if pd.isna(valor) else valor


# ── Dimensiones ──────────────────────────────────────────────────────────
def asegurar_productos(engine, df: pd.DataFrame) -> dict[str, int]:
    """Inserta productos nuevos (no pisa el nombre visible de los existentes). Retorna {producto_norm: id}."""
    prods = (
        df[["producto", "producto_norm", "grupo"]]
        .drop_duplicates(subset=["producto_norm"])
        .to_dict("records")
    )
    filas = [
        {"nombre": p["producto"], "norm": p["producto_norm"], "grupo": _nulo(p["grupo"])}
        for p in prods
    ]
    with engine.begin() as conn:
        if filas:
            conn.execute(
                text("""
                    INSERT INTO dim_producto_precio (nombre, nombre_normalizado, grupo)
                    VALUES (:nombre, :norm, :grupo)
                    ON CONFLICT (nombre_normalizado) DO UPDATE
                    SET grupo = COALESCE(dim_producto_precio.grupo, EXCLUDED.grupo)
                """),
                filas,
            )
        res = conn.execute(text("SELECT id_producto, nombre_normalizado FROM dim_producto_precio"))
        return {norm: idp for idp, norm in res.fetchall()}


def vincular_productos_cultivos(engine) -> int:
    """
    Enlaza dim_producto_precio con dim_cultivo (columna id_cultivo) según config.precios.PRODUCTO_A_CULTIVO.
    Permite usar los precios diarios como rasgo del modelo de rendimiento. Idempotente; si dim_cultivo
    está vacío (todavía no se cargó la producción) no hace nada. Retorna cuántos productos quedaron enlazados.
    """
    from config.precios import PRODUCTO_A_CULTIVO

    with engine.begin() as conn:
        cultivos = {n: i for i, n in conn.execute(text("SELECT id_cultivo, nombre_normalizado FROM dim_cultivo")).fetchall()}
        filas = [
            {"prod": p, "cult": cultivos[c]}
            for p, c in PRODUCTO_A_CULTIVO.items() if c in cultivos
        ]
        if filas:
            conn.execute(
                text("UPDATE dim_producto_precio SET id_cultivo = :cult WHERE nombre_normalizado = :prod"),
                filas,
            )
        n = conn.execute(text("SELECT COUNT(*) FROM dim_producto_precio WHERE id_cultivo IS NOT NULL")).scalar()
    return int(n)


def asegurar_mercados(engine, df: pd.DataFrame) -> dict[str, int]:
    """
    Inserta/actualiza mercados en dim_central_abastos. Retorna {mercado: id_central}.
    id_municipio solo se asigna si el municipio existe en dim_municipio (FK).
    """
    # La identidad del mercado es su nombre canónico. El nombre del municipio que trae
    # el SOAP cambia con el tiempo (p. ej. 'Cúcuta' -> 'San José de Cúcuta'), así que
    # se toma el más reciente y nunca se usa para distinguir mercados.
    if "fecha" in df.columns:
        df = df.sort_values("fecha")
    mercados = (
        df[["mercado", "ciudad", "id_municipio", "id_departamento", "departamento"]]
        .drop_duplicates(subset=["mercado"], keep="last")
        .to_dict("records")
    )
    with engine.begin() as conn:
        validos = {r[0] for r in conn.execute(text("SELECT id_municipio FROM dim_municipio")).fetchall()}
        for m in mercados:
            id_muni = _nulo(m["id_municipio"])
            p = {
                "central": m["mercado"],
                "ciudad": _nulo(m["ciudad"]) or m["mercado"].split(",")[0],
                "muni": id_muni if id_muni in validos else None,
                "dep": _nulo(m["id_departamento"]),
                "dep_nombre": _nulo(m["departamento"]),
            }
            existente = conn.execute(
                text("SELECT MIN(id_central) FROM dim_central_abastos WHERE nombre_central = :central"), p
            ).scalar()
            if existente is None:
                conn.execute(
                    text("""
                        INSERT INTO dim_central_abastos
                            (nombre_central, ciudad, id_municipio, id_departamento, nombre_departamento)
                        VALUES (:central, :ciudad, :muni, :dep, :dep_nombre)
                    """),
                    p,
                )
            else:
                conn.execute(
                    text("""
                        UPDATE dim_central_abastos SET
                            id_municipio        = COALESCE(:muni, id_municipio),
                            id_departamento     = COALESCE(:dep, id_departamento),
                            nombre_departamento = COALESCE(:dep_nombre, nombre_departamento)
                        WHERE id_central = :id
                    """),
                    {**p, "id": existente},
                )
    return _mapa_mercados(engine)


# ── Hecho ────────────────────────────────────────────────────────────────
def _mapa_mercados(engine) -> dict[str, int]:
    """{nombre canónico: id_central}. Si hubiera filas duplicadas por ciudad, gana la más antigua."""
    with engine.connect() as conn:
        filas = conn.execute(
            text("SELECT nombre_central, MIN(id_central) FROM dim_central_abastos GROUP BY nombre_central")
        ).fetchall()
    return {nombre: idc for nombre, idc in filas}


def cargar_precios(engine, df: pd.DataFrame, fuente: str, crear_mercados: bool = True) -> int:
    """
    Upsert de precios normalizados (ver clean_precios_diarios.COLUMNAS_SALIDA).
    Retorna cuántas filas se insertaron o cambiaron (las idénticas se omiten).

    crear_mercados=False (Excel): el boletín no trae municipio ni departamento, así que
    solo se aceptan mercados ya registrados por el SOAP; el resto se descarta con aviso.
    """
    if df.empty:
        logger.info("Sin precios para cargar (%s)", fuente)
        return 0

    df = df.copy()
    df["fuente"] = fuente
    mapa_prod = asegurar_productos(engine, df)
    vincular_productos_cultivos(engine)
    mapa_merc = asegurar_mercados(engine, df) if crear_mercados else _mapa_mercados(engine)

    df["id_producto"] = df["producto_norm"].map(mapa_prod)
    df["id_central"] = df["mercado"].map(mapa_merc)
    if not crear_mercados:
        desconocidos = sorted(df.loc[df["id_central"].isna(), "mercado"].unique())
        if desconocidos:
            logger.warning("Mercados sin registrar (se cargan con el SOAP): %s", desconocidos)
    sin_id = df["id_producto"].isna() | df["id_central"].isna()
    if sin_id.any():
        logger.warning("Precios sin producto/mercado en dimensiones: %s filas descartadas", int(sin_id.sum()))
        df = df[~sin_id]

    filas = [
        (
            int(r.id_central), int(r.id_producto), r.fecha.date(),
            _nulo(r.precio_min_kg), _nulo(r.precio_max_kg), float(r.precio_prom_kg), fuente,
        )
        for r in df.itertuples(index=False)
    ]

    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            devueltas = execute_values(cur, _SQL_FACT, filas, page_size=PAGE_SIZE, fetch=True)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

    cambiadas = len(devueltas)
    logger.info("fact_precio_diario (%s): %s filas leidas, %s nuevas o cambiadas", fuente, len(filas), cambiadas)
    return cambiadas


# ── Bitácora de ingestas ─────────────────────────────────────────────────
# Vive en load/ingest_log.py (la usan también las etapas del pipeline); se reexporta aquí por compatibilidad.
from load.ingest_log import cerrar_run, iniciar_run, ultimo_run  # noqa: E402,F401


def fecha_max_precios(engine, fuente: str | None = None) -> date | None:
    sql = "SELECT MAX(fecha) FROM fact_precio_diario"
    params: dict = {}
    if fuente:
        sql += " WHERE fuente = :f"
        params["f"] = fuente
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()
