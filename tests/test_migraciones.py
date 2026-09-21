"""Migraciones versionadas (load/migrate.py). Las pruebas `db` corren contra un Postgres desechable (ver conftest)."""
import re
import shutil

import pytest
from sqlalchemy import text

from load import migrate
from load.migrate import MIGRATIONS_DIR, MigrationError, aplicar, descubrir, estado


# ── Sin base de datos: la carpeta migrations/ está bien formada ─────────
def test_las_migraciones_estan_numeradas_sin_huecos():
    versionadas = [m for m in descubrir() if not m.repetible]
    numeros = [int(m.clave) for m in versionadas]
    assert numeros == list(range(1, len(numeros) + 1))


def test_las_repetibles_van_despues_de_las_versionadas():
    orden = [m.repetible for m in descubrir()]
    assert orden == sorted(orden)


def test_ninguna_migracion_borra_vistas_en_cascada():
    """Antes cada corrida hacía DROP VIEW ... CASCADE y podía llevarse por delante objetos dependientes."""
    for ruta in MIGRATIONS_DIR.glob("*.sql"):
        assert not re.search(r"DROP\s+VIEW[^;]*CASCADE", ruta.read_text(encoding="utf-8"), re.I), ruta.name


def test_el_checksum_ignora_los_saltos_de_linea():
    assert migrate._checksum("a\r\nb\r\n") == migrate._checksum("a\nb")


def test_nombre_invalido_se_rechaza(tmp_path):
    (tmp_path / "uno.sql").write_text("SELECT 1")
    with pytest.raises(MigrationError):
        descubrir(tmp_path)


def test_numero_repetido_se_rechaza(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1")
    (tmp_path / "001_b.sql").write_text("SELECT 2")
    with pytest.raises(MigrationError):
        descubrir(tmp_path)


def test_migracion_aplicada_y_editada_se_detecta():
    m = descubrir()[0]
    with pytest.raises(MigrationError, match="ya estaba aplicada"):
        migrate._pendientes([m], {m.clave: "otro-checksum"})


def test_repetibles_se_reaplican_solo_si_cambian_o_hay_migracion_nueva(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1")
    (tmp_path / "R__v.sql").write_text("SELECT 2")
    ms = descubrir(tmp_path)
    al_dia = {m.clave: m.checksum for m in ms}
    assert migrate._pendientes(ms, al_dia) == []
    assert [m.archivo for m in migrate._pendientes(ms, {**al_dia, "R__v": "viejo"})] == ["R__v.sql"]
    assert [m.archivo for m in migrate._pendientes(ms, {"R__v": ms[1].checksum})] == ["001_a.sql", "R__v.sql"]
    assert [m.archivo for m in migrate._pendientes(ms, al_dia, forzar=True)] == ["R__v.sql"]


# ── Con Postgres ────────────────────────────────────────────────────────
TABLAS_ESPERADAS = {
    "dim_municipio", "dim_cultivo", "dim_tiempo", "fact_produccion_agricola", "fact_clima_mensual",
    "pred_rendimiento", "pred_alerta_climatica", "model_version", "chat_session", "chat_message",
    "dim_producto_precio", "fact_precio_diario", "pred_precio", "informe_precio_diario", "ingest_run",
    "chat_rate", "quality_check_run", "extraction_report", "schema_migrations",
}
VISTAS_ESPERADAS = {"v_dashboard_agro", "v_monitor_climatico", "v_predicciones_modelo", "v_alertas_climaticas", "v_precio_actual"}


@pytest.mark.db
def test_aplicar_crea_todo_y_es_idempotente(engine_limpio):
    hechas = aplicar(engine_limpio)
    assert hechas[0] == "001_base.sql" and "R__2_seguridad.sql" in hechas
    with engine_limpio.connect() as conn:
        tablas = {r[0] for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
        vistas = {r[0] for r in conn.execute(text("SELECT viewname FROM pg_views WHERE schemaname='public'"))}
    assert TABLAS_ESPERADAS <= tablas
    assert VISTAS_ESPERADAS <= vistas
    assert aplicar(engine_limpio) == []                       # segunda vez: nada que hacer
    assert estado(engine_limpio)["pendientes"] == []


@pytest.mark.db
def test_las_vistas_de_power_bi_se_pueden_consultar(engine_migrado):
    with engine_migrado.connect() as conn:
        for vista in VISTAS_ESPERADAS:
            conn.execute(text(f"SELECT * FROM {vista} LIMIT 1"))


@pytest.mark.db
def test_base_preexistente_sin_registro_se_adopta_sin_error(engine_limpio):
    """Una base creada antes con schema.sql tiene las tablas pero no `schema_migrations`."""
    base = (MIGRATIONS_DIR / "001_base.sql").read_text(encoding="utf-8")
    with engine_limpio.begin() as conn:
        conn.execute(text(base))
    hechas = aplicar(engine_limpio)
    assert "001_base.sql" in hechas
    assert aplicar(engine_limpio) == []


@pytest.mark.db
def test_migracion_editada_despues_de_aplicarse_falla(engine_limpio, tmp_path):
    for ruta in MIGRATIONS_DIR.glob("*.sql"):
        shutil.copy(ruta, tmp_path / ruta.name)
    aplicar(engine_limpio, tmp_path)
    (tmp_path / "003_chat_rate.sql").write_text("-- editada\nSELECT 1;\n")
    with pytest.raises(MigrationError, match="003_chat_rate.sql"):
        aplicar(engine_limpio, tmp_path)


@pytest.mark.db
def test_un_fallo_deja_la_base_sin_cambios_a_medias(engine_limpio, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE prueba_ok (a int);")
    (tmp_path / "002_rota.sql").write_text("CREATE TABLE prueba_rota (a int); SELECT * FROM tabla_que_no_existe;")
    with pytest.raises(MigrationError, match="002_rota.sql"):
        aplicar(engine_limpio, tmp_path)
    with engine_limpio.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('prueba_ok')")).scalar() is None      # se revirtió todo
        assert conn.execute(text("SELECT to_regclass('schema_migrations')")).scalar() is None


@pytest.mark.db
def test_nueva_migracion_reaplica_las_repetibles(engine_limpio, tmp_path):
    for ruta in MIGRATIONS_DIR.glob("*.sql"):
        shutil.copy(ruta, tmp_path / ruta.name)
    aplicar(engine_limpio, tmp_path)
    (tmp_path / "005_nueva.sql").write_text("CREATE TABLE IF NOT EXISTS dim_prueba_nueva (id int);")
    hechas = aplicar(engine_limpio, tmp_path)
    assert hechas == ["005_nueva.sql", "R__1_vistas.sql", "R__2_seguridad.sql"]
    with engine_limpio.connect() as conn:       # la repetible de seguridad cubrió la tabla nueva
        assert conn.execute(text("SELECT relrowsecurity FROM pg_class WHERE relname='dim_prueba_nueva'")).scalar() is True


@pytest.mark.db
def test_rls_activo_en_todas_las_tablas_de_agroia(engine_migrado):
    with engine_migrado.connect() as conn:
        sin_rls = [r[0] for r in conn.execute(text(
            "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity"))]
    assert sin_rls == []


def _como_web(engine, sql):
    """Ejecuta `sql` como el rol agroia_web; devuelve True si se permitió, False si fue denegado."""
    from sqlalchemy.exc import DBAPIError

    with engine.connect() as conn:
        conn.execute(text("SET ROLE agroia_web"))
        try:
            conn.execute(text(sql))
            return True
        except DBAPIError:
            return False
        finally:
            conn.rollback()


@pytest.mark.db
def test_el_rol_web_solo_lee_y_escribe_en_chat(engine_migrado):
    assert _como_web(engine_migrado, "SELECT count(*) FROM dim_municipio")
    assert _como_web(engine_migrado, "SELECT count(*) FROM v_precio_actual")
    assert _como_web(engine_migrado, "INSERT INTO chat_rate (clave, dia, n) VALUES ('t', CURRENT_DATE, 1)")
    assert not _como_web(engine_migrado, "INSERT INTO dim_region_natural (id_region, nombre_region) VALUES (99, 'x')")
    assert not _como_web(engine_migrado, "DELETE FROM fact_precio_diario")
    assert not _como_web(engine_migrado, "CREATE TABLE no_deberia (a int)")
    assert not _como_web(engine_migrado, "SELECT * FROM pg_authid")
