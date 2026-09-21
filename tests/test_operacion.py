"""Configuración validada, alertas por webhook, bitácora única de ejecuciones y persistencia de calidad."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest
import requests
from sqlalchemy import text

from config import settings
from config.settings import ConfigError

VARIABLES_DB = [
    "SUPABASE_DB_HOST", "SUPABASE_DB_PORT", "SUPABASE_DB_NAME", "SUPABASE_DB_USER", "SUPABASE_DB_PASSWORD",
    "SUPABASE_DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSL",
]


@pytest.fixture()
def sin_variables_db(monkeypatch):
    for v in VARIABLES_DB:
        monkeypatch.delenv(v, raising=False)
    return monkeypatch


# ── config.settings.db_config ───────────────────────────────────────────
def test_db_config_dice_exactamente_que_falta(sin_variables_db):
    with pytest.raises(ConfigError) as exc:
        settings.db_config()
    msg = str(exc.value)
    assert "SUPABASE_DB_HOST" in msg and "SUPABASE_DB_USER" in msg and "SUPABASE_DB_PASSWORD" in msg


def test_db_config_solo_menciona_lo_que_falta(sin_variables_db):
    sin_variables_db.setenv("SUPABASE_DB_HOST", "db.ejemplo.co")
    sin_variables_db.setenv("SUPABASE_DB_USER", "u")
    with pytest.raises(ConfigError) as exc:
        settings.db_config()
    assert "SUPABASE_DB_PASSWORD" in str(exc.value) and "SUPABASE_DB_HOST" not in str(exc.value)


def test_db_config_acepta_los_alias_de_la_web(sin_variables_db):
    for k, v in {"DB_HOST": "h", "DB_USER": "u", "DB_PASSWORD": "p", "DB_PORT": "6543", "DB_NAME": "n"}.items():
        sin_variables_db.setenv(k, v)
    cfg = settings.db_config()
    assert (cfg["host"], cfg["user"], cfg["password"], cfg["port"], cfg["dbname"]) == ("h", "u", "p", 6543, "n")


def test_el_nombre_oficial_gana_al_alias(sin_variables_db):
    sin_variables_db.setenv("SUPABASE_DB_HOST", "oficial")
    sin_variables_db.setenv("DB_HOST", "alias")
    sin_variables_db.setenv("SUPABASE_DB_USER", "u")
    sin_variables_db.setenv("SUPABASE_DB_PASSWORD", "p")
    assert settings.db_config()["host"] == "oficial"


def test_ssl_por_defecto_segun_el_host(sin_variables_db):
    sin_variables_db.setenv("SUPABASE_DB_USER", "u")
    sin_variables_db.setenv("SUPABASE_DB_PASSWORD", "p")
    sin_variables_db.setenv("SUPABASE_DB_HOST", "localhost")
    assert settings.db_config()["sslmode"] == "disable"
    sin_variables_db.setenv("SUPABASE_DB_HOST", "db.supabase.co")
    assert settings.db_config()["sslmode"] == "require"
    sin_variables_db.setenv("DB_SSL", "verify-full")
    assert settings.db_config()["sslmode"] == "verify-full"


def test_ssl_invalido_o_puerto_no_numerico_se_rechazan(sin_variables_db):
    sin_variables_db.setenv("SUPABASE_DB_HOST", "h")
    sin_variables_db.setenv("SUPABASE_DB_USER", "u")
    sin_variables_db.setenv("SUPABASE_DB_PASSWORD", "p")
    sin_variables_db.setenv("DB_SSL", "quizas")
    with pytest.raises(ConfigError, match="DB_SSL"):
        settings.db_config()
    sin_variables_db.delenv("DB_SSL")
    sin_variables_db.setenv("SUPABASE_DB_PORT", "abc")
    with pytest.raises(ConfigError, match="SUPABASE_DB_PORT"):
        settings.db_config()


def test_get_engine_escapa_la_contrasena(sin_variables_db):
    from load.db import get_engine

    for k, v in {"SUPABASE_DB_HOST": "localhost", "SUPABASE_DB_USER": "u", "SUPABASE_DB_PASSWORD": "p@ss:/w#rd"}.items():
        sin_variables_db.setenv(k, v)
    engine = get_engine()
    assert engine.url.password == "p@ss:/w#rd" and engine.url.host == "localhost"


# ── utils.alertas ───────────────────────────────────────────────────────
def test_alerta_sin_webhook_no_hace_nada(monkeypatch):
    from utils import alertas

    monkeypatch.setattr(alertas, "ALERT_WEBHOOK_URL", None)
    monkeypatch.setattr(alertas.requests, "post", lambda *a, **k: pytest.fail("no debe enviar"))
    assert alertas.enviar_alerta("t", "d") is False


def test_alerta_envia_json_compatible_con_slack_y_discord(monkeypatch):
    from utils import alertas

    enviado = {}

    class Resp:
        def raise_for_status(self):
            pass

    def falso_post(url, json=None, timeout=None):
        enviado.update(url=url, json=json, timeout=timeout)
        return Resp()

    monkeypatch.setattr(alertas.requests, "post", falso_post)
    assert alertas.enviar_alerta("Falló X", "detalle", url="https://hooks.ejemplo/abc") is True
    assert enviado["url"] == "https://hooks.ejemplo/abc" and enviado["timeout"] == 10
    assert "Falló X" in enviado["json"]["text"] and enviado["json"]["content"] == enviado["json"]["text"]


def test_alerta_que_falla_no_lanza_excepcion(monkeypatch):
    from utils import alertas

    def roto(*a, **k):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(alertas.requests, "post", roto)
    assert alertas.enviar_alerta("t", url="https://hooks.ejemplo/abc") is False


# ── load.ingest_log ─────────────────────────────────────────────────────
@pytest.fixture()
def alertas_enviadas(monkeypatch):
    from load import ingest_log

    lista = []
    monkeypatch.setattr(ingest_log, "enviar_alerta", lambda titulo, detalle="", nivel="error", url=None: lista.append((titulo, detalle, nivel)) or True)
    return lista


@pytest.mark.db
def test_etapa_correcta_queda_registrada(engine_migrado, alertas_enviadas):
    from load.ingest_log import registrar_etapa, ultimo_run

    with registrar_etapa(engine_migrado, "pipeline_core") as run:
        run.filas = 42
        run.fecha_dato_max = date(2026, 9, 1)
    fila = ultimo_run(engine_migrado, "pipeline_core")
    assert fila["status"] == "ok" and fila["filas_nuevas"] == 42 and fila["finished_at"] is not None
    assert alertas_enviadas == []


@pytest.mark.db
def test_etapa_que_falla_queda_en_error_avisa_y_relanza(engine_migrado, alertas_enviadas):
    from load.ingest_log import registrar_etapa, ultimo_run

    with pytest.raises(ValueError, match="boom"):
        with registrar_etapa(engine_migrado, "pipeline_models"):
            raise ValueError("boom")
    fila = ultimo_run(engine_migrado, "pipeline_models")
    assert fila["status"] == "error" and "boom" in fila["error"]
    assert len(alertas_enviadas) == 1 and "pipeline_models" in alertas_enviadas[0][0]


def test_etapa_sigue_funcionando_si_la_bitacora_no_esta_disponible(alertas_enviadas):
    """Sin migrar (tabla inexistente) o sin conexión, la bitácora falla pero el trabajo real no debe verse afectado."""
    from sqlalchemy import create_engine

    from load.ingest_log import registrar_etapa

    engine = create_engine("sqlite://")       # no tiene ingest_run
    ejecutado = []
    with registrar_etapa(engine, "pipeline_core"):
        ejecutado.append(True)
    assert ejecutado == [True]


@pytest.mark.db
def test_frescura_detecta_precios_atrasados_y_no_repite_la_alerta(engine_migrado, alertas_enviadas):
    from load.ingest_log import avisar_frescura, revisar_frescura

    with engine_migrado.begin() as conn:
        conn.execute(text("INSERT INTO dim_central_abastos (id_central, nombre_central, ciudad) VALUES (1, 'M', 'C')"))
        conn.execute(text("INSERT INTO dim_producto_precio (id_producto, nombre, nombre_normalizado) VALUES (1, 'Papa', 'PAPA')"))
        conn.execute(text("INSERT INTO fact_precio_diario (id_central, id_producto, fecha, precio_prom_kg) VALUES (1, 1, '2026-09-01', 1500)"))

    assert revisar_frescura(engine_migrado, hoy=date(2026, 9, 2)) == []                   # 1 día hábil: al día
    problemas = revisar_frescura(engine_migrado, hoy=date(2026, 9, 18))
    assert [p["clave"] for p in problemas] == ["precios_atraso"] and "2026-09-01" in problemas[0]["detalle"]

    ahora = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    assert avisar_frescura(engine_migrado, hoy=date(2026, 9, 18), ahora=ahora) == ["precios_atraso"]
    assert avisar_frescura(engine_migrado, hoy=date(2026, 9, 18), ahora=ahora) == []      # dentro de 12 h no se repite
    assert len(alertas_enviadas) == 1 and alertas_enviadas[0][2] == "aviso"


@pytest.mark.db
def test_frescura_base_vacia_no_genera_alertas(engine_migrado, alertas_enviadas):
    from load.ingest_log import avisar_frescura

    assert avisar_frescura(engine_migrado) == [] and alertas_enviadas == []


@pytest.mark.db
def test_pipeline_sin_ejecutarse_hace_dias_genera_aviso(engine_migrado, alertas_enviadas):
    from load.ingest_log import revisar_frescura

    with engine_migrado.begin() as conn:
        conn.execute(text(
            "INSERT INTO ingest_run (fuente, started_at, finished_at, status) "
            "VALUES ('pipeline_core', NOW() - INTERVAL '30 days', NOW() - INTERVAL '30 days', 'ok')"))
    assert [p["clave"] for p in revisar_frescura(engine_migrado)] == ["pipeline_core_atraso"]


# ── Calidad y reportes de extracción en la BD ───────────────────────────
@pytest.mark.db
def test_reporte_de_calidad_se_guarda_en_la_bd(engine_migrado, monkeypatch):
    from utils import alertas
    from validate.quality_report import run_quality_report

    avisos = []
    monkeypatch.setattr(alertas, "enviar_alerta", lambda *a, **k: avisos.append(a) or True)
    df = run_quality_report(engine_migrado)
    with engine_migrado.connect() as conn:
        n = conn.execute(text("SELECT count(*) FROM quality_check_run")).scalar()
    assert n == len(df) > 0


@pytest.mark.db
def test_sincronizar_reportes_de_extraccion(engine_migrado, tmp_path):
    from utils.extraction_quality import sincronizar_reportes

    reporte = {"fuente": "produccion", "uri": "https://x", "filas": 10, "columnas": 3,
               "completitud_pct": {"a": 100.0, "b": 50.0}, "duplicados_por_clave": 0, "extraido_at": "2026-09-01T10:00:00Z"}
    (tmp_path / "produccion.json").write_text(json.dumps(reporte), encoding="utf-8")
    (tmp_path / "anova_data.json").write_text(json.dumps({"otra": "cosa"}), encoding="utf-8")   # se ignora
    (tmp_path / "roto.json").write_text("{no es json", encoding="utf-8")                        # se ignora
    assert sincronizar_reportes(engine_migrado, tmp_path) == 1
    assert sincronizar_reportes(engine_migrado, tmp_path) == 1                                  # idempotente
    with engine_migrado.connect() as conn:
        fila = conn.execute(text("SELECT filas, completitud_pct->>'b' FROM extraction_report WHERE fuente='produccion'")).one()
    assert fila == (10, "50.0")
    assert sincronizar_reportes(engine_migrado, tmp_path / "no_existe") == 0


# ── Orquestador ─────────────────────────────────────────────────────────
def test_el_orquestador_expone_las_etapas_y_los_modos_nuevos():
    import run_pipeline

    assert set(run_pipeline.ETAPAS) == {"core", "extended", "models"}
    assert callable(run_pipeline.run_precios)


def test_timedelta_de_frescura_es_razonable():
    from load import ingest_log

    assert ingest_log.MAX_ATRASO_PIPELINE > timedelta(days=7)      # el pipeline corre cada semana
    assert ingest_log.MAX_ATRASO_PRECIOS_HABILES >= 2
