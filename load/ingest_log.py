"""
ingest_log.py — Bitácora única de ejecuciones (tabla ingest_run).

Todas las etapas (pipeline core/extended/models y los jobs de precios) registran aquí: alimenta
/api/precios/estado y /api/estado, y permite avisar cuando algo falla o los datos se atrasan.

Uso:
    with registrar_etapa(engine, "pipeline_core") as run:
        ...
        run.filas = 1234
Si el bloque lanza una excepción se cierra como 'error' y se envía la alerta (si hay webhook); la excepción se relanza.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import numpy as np
from sqlalchemy import text

from utils.alertas import enviar_alerta

logger = logging.getLogger(__name__)

# Frescura esperada. La ingesta de precios es diaria (días hábiles); el pipeline completo corre cada semana.
MAX_ATRASO_PRECIOS_HABILES = 3
MAX_ATRASO_PIPELINE = timedelta(days=10)
HORAS_ENTRE_ALERTAS = 12


# ── Filas de ingest_run ──────────────────────────────────────────────────
def iniciar_run(engine, fuente: str, source_ref: str | None = None) -> int:
    with engine.begin() as conn:
        res = conn.execute(
            text("INSERT INTO ingest_run (fuente, source_ref) VALUES (:f, :r) RETURNING id"),
            {"f": fuente, "r": source_ref},
        )
        return int(res.scalar_one())


def cerrar_run(
    engine,
    id_run: int,
    status: str,
    filas_nuevas: int | None = None,
    fecha_dato_max: date | None = None,
    source_last_modified: datetime | None = None,
    error: str | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE ingest_run
                SET finished_at = NOW(), status = :status, filas_nuevas = :filas,
                    fecha_dato_max = :fdm, source_last_modified = :slm, error = :err
                WHERE id = :id
            """),
            {
                "status": status, "filas": filas_nuevas, "fdm": fecha_dato_max,
                "slm": source_last_modified, "err": error[:2000] if error else None, "id": id_run,
            },
        )


def ultimo_run(engine, fuente: str, status: str | None = None, source_ref: str | None = None) -> dict | None:
    """Última ingesta de una fuente (opcionalmente solo con cierto estado y/o referencia)."""
    sql = "SELECT * FROM ingest_run WHERE fuente = :f"
    params: dict = {"f": fuente}
    if status:
        sql += " AND status = :s"
        params["s"] = status
    if source_ref:
        sql += " AND source_ref = :r"
        params["r"] = source_ref
    sql += " ORDER BY started_at DESC LIMIT 1"
    with engine.connect() as conn:
        fila = conn.execute(text(sql), params).mappings().first()
    return dict(fila) if fila else None


# ── Etapas ───────────────────────────────────────────────────────────────
@dataclass
class EtapaRun:
    """Datos que el bloque `with` puede dejar para el cierre de la corrida."""
    id: int | None = None
    fuente: str = ""
    status: str = "ok"
    filas: int | None = None
    fecha_dato_max: date | None = None
    nota: str | None = None


@contextmanager
def registrar_etapa(engine, fuente: str, source_ref: str | None = None, alertar: bool = True):
    """Registra una etapa en ingest_run. Si la bitácora misma falla (p. ej. sin migrar) la etapa sigue igual."""
    run = EtapaRun(fuente=fuente)
    try:
        run.id = iniciar_run(engine, fuente, source_ref)
    except Exception as exc:  # la bitácora nunca debe impedir el trabajo real
        logger.warning("No se pudo abrir la bitácora de %s: %s", fuente, exc)
    try:
        yield run
    except BaseException as exc:
        detalle = f"{type(exc).__name__}: {exc}"
        _cerrar_seguro(engine, run, "error", detalle)
        if alertar and not isinstance(exc, (KeyboardInterrupt, SystemExit)):
            enviar_alerta(f"Falló la etapa {fuente}", detalle)
        raise
    else:
        _cerrar_seguro(engine, run, run.status, run.nota)


def _cerrar_seguro(engine, run: EtapaRun, status: str, error: str | None) -> None:
    if run.id is None:
        return
    try:
        cerrar_run(engine, run.id, status, filas_nuevas=run.filas, fecha_dato_max=run.fecha_dato_max, error=error)
    except Exception as exc:
        logger.warning("No se pudo cerrar la bitácora de %s: %s", run.fuente, exc)


# ── Frescura ─────────────────────────────────────────────────────────────
def _dias_habiles(desde: date, hasta: date) -> int:
    return int(np.busday_count(desde, hasta)) if hasta > desde else 0


def revisar_frescura(engine, hoy: date | None = None, ahora: datetime | None = None) -> list[dict]:
    """
    Problemas de frescura detectados: [{'clave', 'titulo', 'detalle'}]. Lista vacía = todo al día.
    No comprueba lo que aún no existe (una base recién creada no genera alertas).
    """
    hoy = hoy or datetime.now(timezone.utc).date()
    ahora = ahora or datetime.now(timezone.utc)
    problemas: list[dict] = []

    with engine.connect() as conn:
        fecha_max = conn.execute(text("SELECT MAX(fecha) FROM fact_precio_diario")).scalar()
    if fecha_max is not None:
        atraso = _dias_habiles(fecha_max, hoy)
        if atraso > MAX_ATRASO_PRECIOS_HABILES:
            problemas.append({
                "clave": "precios_atraso",
                "titulo": "Precios desactualizados",
                "detalle": f"El último precio cargado es del {fecha_max} ({atraso} días hábiles de atraso).",
            })

    for fuente in ("pipeline_core", "pipeline_extended", "pipeline_models"):
        ult = ultimo_run(engine, fuente, status="ok")
        if ult is None:
            continue
        fin = ult["finished_at"] or ult["started_at"]
        if ahora - fin > MAX_ATRASO_PIPELINE:
            problemas.append({
                "clave": f"{fuente}_atraso",
                "titulo": f"{fuente} sin ejecutarse",
                "detalle": f"La última ejecución correcta fue el {fin:%Y-%m-%d}.",
            })
    return problemas


def avisar_frescura(engine, hoy: date | None = None, ahora: datetime | None = None) -> list[str]:
    """Envía una alerta por cada problema de frescura (una vez cada HORAS_ENTRE_ALERTAS). Devuelve las claves avisadas."""
    avisadas: list[str] = []
    try:
        problemas = revisar_frescura(engine, hoy, ahora)
    except Exception as exc:
        logger.warning("No se pudo revisar la frescura: %s", exc)
        return avisadas
    for p in problemas:
        marca = f"alerta:{p['clave']}"[:30]
        ultimo = ultimo_run(engine, marca)
        if ultimo and (ahora or datetime.now(timezone.utc)) - ultimo["started_at"] < timedelta(hours=HORAS_ENTRE_ALERTAS):
            continue
        id_run = iniciar_run(engine, marca, None)
        cerrar_run(engine, id_run, "ok", error=p["detalle"])
        enviar_alerta(p["titulo"], p["detalle"], nivel="aviso")
        avisadas.append(p["clave"])
    return avisadas
