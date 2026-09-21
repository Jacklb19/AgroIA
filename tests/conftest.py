"""
Fixtures compartidas.

Las pruebas marcadas `db` necesitan un Postgres REAL y desechable. Se activan con la variable
TEST_DATABASE_URL (p. ej. postgresql+psycopg2://postgres:postgres@localhost:5432/agroia_test) y, como el fixture
recrea el esquema `public` desde cero, solo se ejecutan contra localhost / 127.0.0.1 (nunca contra Supabase).
Sin la variable se omiten (en CI el servicio Postgres la define).
"""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

HOSTS_SEGUROS = {"localhost", "127.0.0.1", "::1", "postgres"}   # "postgres" = nombre del servicio en docker/CI


def _url_de_pruebas():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Define TEST_DATABASE_URL (Postgres local desechable) para correr las pruebas de base de datos")
    if make_url(url).host not in HOSTS_SEGUROS:
        pytest.skip("TEST_DATABASE_URL debe apuntar a un Postgres local: estas pruebas recrean el esquema public")
    return url


@pytest.fixture()
def engine_limpio():
    """Engine sobre una base con el esquema `public` vacío."""
    engine = create_engine(_url_de_pruebas(), pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    yield engine
    engine.dispose()


@pytest.fixture()
def engine_migrado(engine_limpio):
    """Engine con todas las migraciones aplicadas."""
    from load.migrate import aplicar

    aplicar(engine_limpio)
    return engine_limpio
