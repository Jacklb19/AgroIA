import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from config.settings import db_config  # carga .env y valida las variables

logger = logging.getLogger(__name__)


def get_engine():
    """Engine de SQLAlchemy con la configuración validada de config.settings.db_config()."""
    cfg = db_config()
    url = URL.create(
        "postgresql+psycopg2",
        username=cfg["user"], password=cfg["password"],   # URL.create escapa los caracteres especiales
        host=cfg["host"], port=cfg["port"], database=cfg["dbname"],
    )
    connect_args = {"sslmode": cfg["sslmode"], "connect_timeout": 15}
    if os.getenv("DB_SSL_CA"):
        connect_args["sslrootcert"] = os.environ["DB_SSL_CA"]
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def init_schema(engine):
    """Aplica las migraciones pendientes (migrations/). Idempotente: si la base está al día no hace nada."""
    from load.migrate import aplicar

    hechas = aplicar(engine)
    if hechas:
        logger.info("Migraciones aplicadas: %s", ", ".join(hechas))


def init_schema_precios(engine, force: bool = False):
    """
    Antes creaba aparte las tablas de precios para que el job horario no recreara las vistas de Power BI.
    Con migraciones versionadas eso ya no es un problema (las vistas solo se reaplican si cambia su archivo),
    así que es un alias de init_schema. force=True reaplica también las migraciones repetibles (vistas, seguridad).
    """
    from load.migrate import aplicar

    hechas = aplicar(engine, forzar_repetibles=force)
    if hechas:
        logger.info("Migraciones aplicadas: %s", ", ".join(hechas))


def upsert(engine, table: str, df, conflict_cols: list):
    """
    Inserta filas de un DataFrame en `table`.
    Si ya existe el registro (por conflict_cols), lo actualiza (ON CONFLICT DO UPDATE).
    """
    if df.empty:
        logger.warning(f"DataFrame vacío para tabla {table}, se omite")
        return

    cols = list(df.columns)
    placeholders = ", ".join([f":{c}" for c in cols])
    update_set = ", ".join([
        f"{c} = EXCLUDED.{c}" for c in cols if c not in conflict_cols
    ])
    conflict_str = ", ".join(conflict_cols)

    if update_set:
        stmt = f"""
            INSERT INTO {table} ({', '.join(cols)})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_str})
            DO UPDATE SET {update_set}
        """
    else:
        stmt = f"""
            INSERT INTO {table} ({', '.join(cols)})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_str})
            DO NOTHING
        """
    import math
    records = df.to_dict(orient="records")
    # Reemplazar NaN/float nan con None para que psycopg2 envíe NULL correctamente
    clean_records = []
    for row in records:
        clean_row = {
            k: (None if (v is not None and isinstance(v, float) and math.isnan(v)) else v)
            for k, v in row.items()
        }
        clean_records.append(clean_row)
    with engine.begin() as conn:
        conn.execute(text(stmt), clean_records)
    logger.info(f"{table}: {len(clean_records)} filas insertadas/actualizadas")
