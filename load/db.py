import os
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

import urllib.parse

def get_engine():
    password = os.getenv('SUPABASE_DB_PASSWORD') or os.getenv('SUPABASE_DB_PASS', '')
    encoded_password = urllib.parse.quote_plus(password)
    host = os.getenv('SUPABASE_DB_HOST', 'localhost')
    url = (
        f"postgresql+psycopg2://{os.getenv('SUPABASE_DB_USER')}:"
        f"{encoded_password}@"
        f"{host}:"
        f"{os.getenv('SUPABASE_DB_PORT', 5432)}/"
        f"{os.getenv('SUPABASE_DB_NAME', 'postgres')}"
    )
    ssl_mode = "disable" if host in ["localhost", "127.0.0.1"] else "require"
    return create_engine(url, connect_args={"sslmode": ssl_mode}, pool_pre_ping=True)


def init_schema(engine):
    """Ejecuta schema.sql para crear todas las tablas si no existen."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    with engine.begin() as conn:
        conn.execute(text(sql))
    logger.info("Schema inicializado correctamente")


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
