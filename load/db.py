import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from psycopg2.extras import execute_values
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

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
    connect_args = {
        "sslmode": cfg["sslmode"],
        "connect_timeout": 15,
        # keepalives_idle/interval/count no los respeta libpq en Windows (solo Linux/Mac),
        # así que no bastan por sí solos para detectar una conexión muerta en este equipo:
        # el timeout real está en el watchdog de hilo de upsert() más abajo.
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        # idle_in_transaction_session_timeout corto: si una transacción queda abandonada
        # (conexión muerta a medias), el servidor la mata rápido y libera los bloqueos de
        # fila — si no, un reintento sobre las mismas filas se queda esperando ese bloqueo
        # y parece un segundo colgado en vez de una consulta normal.
        "options": "-c statement_timeout=120000 -c idle_in_transaction_session_timeout=15000 -c lock_timeout=10000",
    }
    if os.getenv("DB_SSL_CA"):
        connect_args["sslrootcert"] = os.environ["DB_SSL_CA"]
    # NullPool: cada checkout abre una conexión física nueva (y la cierra al terminar), sin
    # reusar nada del pool. Se vio repetidas veces que una conexión que quedó abierta pero
    # inactiva durante la fase de extracción (que no toca la BD, solo red HTTP) llegaba muerta
    # o "negra" (el proxy de Railway la corta sin avisar) al primer INSERT posterior, y ni
    # pool_pre_ping ni las keepalives (no soportadas en Windows) lo detectaban a tiempo. El
    # costo es una reconexión (~2-3s) por lote en vez de reusar una conexión cacheada.
    return create_engine(url, connect_args=connect_args, poolclass=NullPool)


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


UPSERT_BATCH_SIZE = 2000


def upsert(engine, table: str, df, conflict_cols: list):
    """
    Inserta filas de un DataFrame en `table`, por lotes de UPSERT_BATCH_SIZE.
    Si ya existe el registro (por conflict_cols), lo actualiza (ON CONFLICT DO UPDATE).

    Se hace en lotes (no en una sola sentencia con todas las filas) porque un INSERT
    con decenas de miles de sets de parámetros puede tumbar la conexión en proveedores
    con poca memoria (visto con Postgres free de Railway al cargar fact_produccion_agricola
    completa en una sola sentencia).
    """
    if df.empty:
        logger.warning(f"DataFrame vacío para tabla {table}, se omite")
        return

    cols = list(df.columns)
    update_set = ", ".join([
        f"{c} = EXCLUDED.{c}" for c in cols if c not in conflict_cols
    ])
    conflict_str = ", ".join(conflict_cols)

    # Plantilla para execute_values: "VALUES %s" es el marcador que psycopg2 reemplaza por
    # (v1,v2,...),(v1,v2,...),... de TODO el lote en una sola sentencia/round-trip. Con el
    # %(name)s de SQLAlchemy (executemany fila por fila) 240 filas tardaban ~44s porque manda
    # una sentencia por fila; con execute_values el mismo lote tarda menos de 1s.
    if update_set:
        stmt = f"""
            INSERT INTO {table} ({', '.join(cols)})
            VALUES %s
            ON CONFLICT ({conflict_str})
            DO UPDATE SET {update_set}
        """
    else:
        stmt = f"""
            INSERT INTO {table} ({', '.join(cols)})
            VALUES %s
            ON CONFLICT ({conflict_str})
            DO NOTHING
        """
    import math
    # Tuplas en el mismo orden que `cols` (execute_values es posicional, no por nombre) y
    # NaN/float nan -> None para que psycopg2 envíe NULL correctamente.
    def _limpiar(v):
        return None if (v is not None and isinstance(v, float) and math.isnan(v)) else v

    registros = df[cols].to_dict(orient="records")
    clean_records = [tuple(_limpiar(row[c]) for c in cols) for row in registros]

    total = len(clean_records)
    n_lotes = math.ceil(total / UPSERT_BATCH_SIZE)
    LOTE_TIMEOUT_S = 60

    def _ejecutar_lote(lote):
        with engine.begin() as conn:
            raw = conn.connection.driver_connection  # conexión psycopg2 cruda bajo SQLAlchemy
            with raw.cursor() as cur:
                execute_values(cur, stmt, lote, page_size=len(lote))

    for i, inicio in enumerate(range(0, total, UPSERT_BATCH_SIZE), start=1):
        lote = clean_records[inicio:inicio + UPSERT_BATCH_SIZE]
        for intento in range(1, 4):
            # Se ejecuta en un hilo aparte con timeout duro: en Windows, libpq ignora
            # keepalives_idle/interval/count, así que una conexión que el proxy corta a
            # medias (visto con Railway) puede quedar "idle in transaction" sin que el
            # cliente ni el SO lo detecten nunca. Si el hilo no vuelve a tiempo, se abandona
            # esa conexión colgada (el pool la reemplaza sola) y se reintenta con otra.
            # OJO: no usar ThreadPoolExecutor como context manager aquí — su __exit__
            # espera (shutdown(wait=True)) a que el hilo termine, lo que anularía el
            # timeout si el hilo quedó colgado. Se crea suelto y, si hay timeout, se
            # abandona con shutdown(wait=False) (el hilo colgado se filtra pero no bloquea).
            ex = ThreadPoolExecutor(max_workers=1)
            try:
                ex.submit(_ejecutar_lote, lote).result(timeout=LOTE_TIMEOUT_S)
                ex.shutdown(wait=False)
                break
            except FutureTimeoutError:
                ex.shutdown(wait=False)
                if intento == 3:
                    raise TimeoutError(
                        f"{table}: lote {i}/{n_lotes} colgado más de {LOTE_TIMEOUT_S}s tras 3 intentos"
                    )
                logger.warning(f"{table}: lote {i}/{n_lotes} colgado, reintento {intento}/3 con conexión nueva")
                engine.dispose()  # descarta conexiones del pool (incluida la colgada) sin esperarlas
            except OperationalError as e:
                if intento == 3:
                    raise
                # Se reintenta tanto si la conexión se cayó (connection_invalidated) como si
                # el statement_timeout/lock_timeout del servidor canceló la consulta (p. ej.
                # LockNotAvailable esperando un bloqueo de fila que dejó una transacción
                # zombie de un intento anterior, ya limpiada por idle_in_transaction_session_timeout).
                # Ambos son transitorios; un error de datos real (IntegrityError, etc.) no es
                # OperationalError y sigue propagándose sin reintento.
                logger.warning(
                    f"{table}: lote {i}/{n_lotes} falló ({type(e.orig).__name__ if e.orig else type(e).__name__}), "
                    f"reintento {intento}/3"
                )
                time.sleep(2 * intento)
        if i % 10 == 0 or i == n_lotes:
            logger.info(f"{table}: lote {i}/{n_lotes} ({min(inicio + UPSERT_BATCH_SIZE, total)}/{total} filas)")
    logger.info(f"{table}: {total} filas insertadas/actualizadas ({n_lotes} lotes)")
