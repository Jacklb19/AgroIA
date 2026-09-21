"""
migrate.py — Migraciones versionadas de la base de datos.

Reglas:
  · `migrations/NNN_nombre.sql` se aplican UNA vez, en orden, y quedan registradas en `schema_migrations`.
    Una migración ya aplicada no se edita (se detecta por checksum): los cambios van en una migración nueva.
  · Las migraciones son idempotentes (IF NOT EXISTS, ADD COLUMN IF NOT EXISTS...), así que sobre una base que
    ya tenía las tablas (creadas antes con schema.sql) simplemente no cambian nada y quedan registradas.
  · `migrations/R__*.sql` son repetibles (vistas, RLS/roles): se reaplican cuando cambia el archivo o cuando
    se aplica alguna migración versionada nueva.
  · Todo lo pendiente se aplica en UNA transacción con un candado consultivo: si algo falla no queda a medias,
    y dos procesos a la vez (el cron de precios y un despliegue) no se pisan.

Uso:
  python -m load.migrate                 # aplica lo pendiente
  python -m load.migrate --status        # lista aplicadas y pendientes sin cambiar nada
  python -m load.migrate --web-password  # fija la contraseña del rol agroia_web (variable WEB_DB_PASSWORD)
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
LOCK_ID = 7_240_601            # clave arbitraria del candado consultivo de migraciones
_VERSIONADA = re.compile(r"^(\d{3})_[\w\-]+\.sql$")
_REPETIBLE = re.compile(r"^R__[\w\-]+\.sql$")


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migracion:
    clave: str          # "001" para versionadas, "R__1_vistas" para repetibles
    archivo: str
    sql: str
    checksum: str
    repetible: bool


def _checksum(sql: str) -> str:
    normal = sql.replace("\r\n", "\n").strip()
    return hashlib.sha256(normal.encode("utf-8")).hexdigest()


def descubrir(directorio: Path = MIGRATIONS_DIR) -> list[Migracion]:
    """Lee las migraciones del disco: versionadas ordenadas por número y luego las repetibles por nombre."""
    if not directorio.is_dir():
        raise MigrationError(f"No existe la carpeta de migraciones: {directorio}")
    versionadas, repetibles = [], []
    for ruta in sorted(directorio.glob("*.sql")):
        sql = ruta.read_text(encoding="utf-8")
        if _VERSIONADA.match(ruta.name):
            versionadas.append(Migracion(ruta.name[:3], ruta.name, sql, _checksum(sql), False))
        elif _REPETIBLE.match(ruta.name):
            repetibles.append(Migracion(ruta.stem, ruta.name, sql, _checksum(sql), True))
        else:
            raise MigrationError(f"Nombre de migración inválido: {ruta.name} (usa NNN_nombre.sql o R__nombre.sql)")
    claves = [m.clave for m in versionadas]
    if len(claves) != len(set(claves)):
        raise MigrationError(f"Números de migración repetidos: {sorted(claves)}")
    return versionadas + repetibles


_CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    archivo     TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    repetible   BOOLEAN NOT NULL DEFAULT FALSE,
    aplicada_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def _aplicadas(conn) -> dict[str, str]:
    existe = conn.execute(text("SELECT to_regclass('schema_migrations') IS NOT NULL")).scalar()
    if not existe:
        return {}
    return {r[0]: r[1] for r in conn.execute(text("SELECT version, checksum FROM schema_migrations"))}


def _pendientes(migraciones: list[Migracion], aplicadas: dict[str, str], forzar: bool = False) -> list[Migracion]:
    pendientes: list[Migracion] = []
    hay_versionada_nueva = False
    for m in migraciones:
        if m.repetible:
            continue
        previo = aplicadas.get(m.clave)
        if previo is None:
            pendientes.append(m)
            hay_versionada_nueva = True
        elif previo != m.checksum:
            raise MigrationError(
                f"La migración {m.archivo} ya estaba aplicada y su contenido cambió. "
                "No se editan migraciones aplicadas: crea una nueva (NNN_...sql) con el cambio."
            )
    for m in migraciones:
        if m.repetible and (forzar or hay_versionada_nueva or aplicadas.get(m.clave) != m.checksum):
            pendientes.append(m)
    return pendientes


def estado(engine, directorio: Path = MIGRATIONS_DIR) -> dict:
    """{'aplicadas': [claves], 'pendientes': [archivos]} sin modificar la base."""
    migraciones = descubrir(directorio)
    with engine.connect() as conn:
        aplicadas = _aplicadas(conn)
    pend = _pendientes(migraciones, aplicadas)
    return {
        "aplicadas": sorted(aplicadas),
        "pendientes": [m.archivo for m in pend],
    }


def aplicar(engine, directorio: Path = MIGRATIONS_DIR, forzar_repetibles: bool = False) -> list[str]:
    """Aplica lo pendiente y devuelve los archivos aplicados ([] si la base ya estaba al día)."""
    migraciones = descubrir(directorio)

    # Camino rápido (el job horario pasa por aquí): sin nada pendiente no se toma ningún candado.
    with engine.connect() as conn:
        pend = _pendientes(migraciones, _aplicadas(conn), forzar_repetibles)
    if not pend:
        return []

    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": LOCK_ID})
        conn.execute(text(_CREAR_TABLA))
        # Otro proceso pudo aplicar lo mismo mientras esperábamos el candado: se recalcula.
        pend = _pendientes(migraciones, _aplicadas(conn), forzar_repetibles)
        hechas: list[str] = []
        for m in pend:
            logger.info("Aplicando migración %s", m.archivo)
            try:
                conn.execute(text(m.sql))
            except Exception as exc:
                raise MigrationError(f"Falló {m.archivo}: {exc}") from exc
            conn.execute(
                text(
                    """INSERT INTO schema_migrations (version, archivo, checksum, repetible)
                       VALUES (:v, :a, :c, :r)
                       ON CONFLICT (version) DO UPDATE
                       SET archivo = EXCLUDED.archivo, checksum = EXCLUDED.checksum, aplicada_at = NOW()"""
                ),
                {"v": m.clave, "a": m.archivo, "c": m.checksum, "r": m.repetible},
            )
            hechas.append(m.archivo)
    return hechas


def fijar_password_web(engine, password: str) -> None:
    """Fija la contraseña del rol agroia_web (creado sin contraseña por R__2_seguridad.sql)."""
    if not password or len(password) < 12:
        raise MigrationError("WEB_DB_PASSWORD debe tener al menos 12 caracteres.")
    with engine.connect() as conn:
        existe = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'agroia_web'")).scalar()
        if not existe:
            raise MigrationError("El rol agroia_web no existe: aplica primero las migraciones (python -m load.migrate).")
        # ALTER ROLE no admite parámetros: se arma el literal con format(%L) del servidor.
        sentencia = conn.execute(text("SELECT format('ALTER ROLE agroia_web WITH PASSWORD %L', CAST(:p AS text))"), {"p": password}).scalar()
    crudo = engine.raw_connection()
    try:
        cur = crudo.cursor()
        cur.execute(sentencia)
        crudo.commit()
    finally:
        crudo.close()
    logger.info("Contraseña del rol agroia_web actualizada")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migraciones de la base de AgroIA")
    parser.add_argument("--status", action="store_true", help="Muestra aplicadas y pendientes sin cambiar nada")
    parser.add_argument("--force-repeatable", action="store_true", help="Reaplica también las migraciones repetibles (vistas, seguridad)")
    parser.add_argument("--web-password", action="store_true", help="Fija la contraseña del rol agroia_web con WEB_DB_PASSWORD")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from config.settings import ConfigError
    from load.db import get_engine

    try:
        engine = get_engine()
        if args.web_password:
            fijar_password_web(engine, os.getenv("WEB_DB_PASSWORD", ""))
            return 0
        if args.status:
            e = estado(engine)
            print("Aplicadas :", ", ".join(e["aplicadas"]) or "(ninguna)")
            print("Pendientes:", ", ".join(e["pendientes"]) or "(ninguna)")
            return 0
        hechas = aplicar(engine, forzar_repetibles=args.force_repeatable)
        print("Aplicadas ahora:", ", ".join(hechas) if hechas else "nada (la base ya estaba al día)")
        return 0
    except (ConfigError, MigrationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
