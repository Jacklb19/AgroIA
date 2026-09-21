"""Tests sin red ni BD del flujo de precios diarios SIPSA (extract/clean/orquestación)."""
import io
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from clean.clean_precios_diarios import (
    COLUMNAS_SALIDA,
    canon_grupo,
    canon_mercado,
    canon_producto,
    canon_titulo,
    normalizar_excel,
    normalizar_soap,
)
from extract.extract_sipsa_diario import parse_boletin, token_fecha, url_boletin
from extract.extract_sipsa_soap import iter_filas


# ── Canonicalización ─────────────────────────────────────────────────────
def test_canon_producto_quita_asterisco_y_unifica_variantes():
    assert canon_producto("Papa negra*") == ("Papa negra", "PAPA NEGRA")
    assert canon_producto("Piña *")[1] == "PINA"
    assert canon_producto("Papa  criolla")[0] == "Papa criolla"
    # SOAP y Excel escriben distinto: deben coincidir en la llave
    assert canon_producto("Fríjol verde*")[1] == canon_producto("Frijol Verde")[1]
    assert canon_producto("Limón Común")[1] == canon_producto("Limón común")[1]


def test_canon_mercado_alias_y_espacios():
    assert canon_mercado("Bogotá, D.C., Corabastos") == "Bogotá, Corabastos"
    assert canon_mercado("Cali, Santa Helena") == "Cali, Santa Elena"
    assert canon_mercado("Ibagué, \nLa 21") == "Ibagué, La 21"        # celda de Excel con salto de línea
    assert canon_mercado("Pasto, El Potrerillo") == "Pasto, El Potrerillo"


def test_canon_titulo_departamentos():
    assert canon_titulo("NORTE DE SANTANDER") == "Norte de Santander"
    assert canon_titulo("VALLE DEL CAUCA") == "Valle del Cauca"
    assert canon_titulo("ATLÁNTICO") == "Atlántico"
    assert canon_titulo("BOGOTÁ, D. C.") == canon_titulo("BOGOTÁ, D.C.") == "Bogotá D.C."


def test_canon_grupo():
    assert canon_grupo("TUBERCULOS, RAICES Y PLATANOS") == "Tubérculos, raíces y plátanos"
    assert canon_grupo("FRUTAS") == "Frutas"
    assert canon_grupo(None) is None


# ── URL del boletín ──────────────────────────────────────────────────────
def test_token_y_url_boletin():
    assert token_fecha(date(2026, 9, 18)) == "18sep2026"
    assert token_fecha(date(2026, 1, 5)) == "05ene2026"     # día con dos dígitos
    assert url_boletin(date(2026, 9, 18)).endswith("/anex-SIPSADiario-18sep2026.xlsx")


# ── SOAP: parseo en streaming ────────────────────────────────────────────
_SOAP_XML = """<?xml version='1.0' encoding='UTF-8'?>
<S:Envelope xmlns:S="http://www.w3.org/2003/05/soap-envelope"><S:Body>
<ns2:promediosSipsaParcialResponse xmlns:ns2="http://servicios.sipsa.co.gov.dane/">
<return><artiNombre>Papa criolla</artiNombre><deptNombre>NARIÑO</deptNombre><enmaFecha>2026-09-17T00:00:00-05:00</enmaFecha><fuenNombre>Pasto, El Potrerillo</fuenNombre><grupNombre>TUBERCULOS, RAICES Y PLATANOS</grupNombre><maximoKg>2400</maximoKg><minimoKg>2000</minimoKg><muniId>52001</muniId><muniNombre>PASTO</muniNombre><promedioKg>2200</promedioKg></return>
<return><artiNombre>Papa criolla</artiNombre><deptNombre>NARIÑO</deptNombre><enmaFecha>2020-02-01T00:00:00-05:00</enmaFecha><fuenNombre>Pasto, El Potrerillo</fuenNombre><grupNombre>TUBERCULOS, RAICES Y PLATANOS</grupNombre><maximoKg>900</maximoKg><minimoKg>800</minimoKg><muniId>52001</muniId><muniNombre>PASTO</muniNombre><promedioKg>850</promedioKg></return>
</ns2:promediosSipsaParcialResponse></S:Body></S:Envelope>"""


def test_iter_filas_lee_y_filtra_por_fecha(tmp_path):
    ruta = tmp_path / "resp.xml"
    ruta.write_text(_SOAP_XML, encoding="utf-8")

    todas = list(iter_filas(ruta))
    assert len(todas) == 2
    assert todas[0]["fuenNombre"] == "Pasto, El Potrerillo" and todas[0]["promedioKg"] == "2200"

    recientes = list(iter_filas(ruta, desde=date(2026, 9, 1)))
    assert [f["enmaFecha"][:10] for f in recientes] == ["2026-09-17"]


def _fila(**kw):
    base = {
        "artiNombre": "Papa negra*", "grupNombre": "TUBERCULOS, RAICES Y PLATANOS",
        "deptNombre": "NARIÑO", "muniId": "52001", "muniNombre": "PASTO",
        "fuenNombre": "Pasto, El Potrerillo", "enmaFecha": "2026-09-17T00:00:00-05:00",
        "minimoKg": "1000", "maximoKg": "1200", "promedioKg": "1100",
    }
    base.update(kw)
    return base


def test_normalizar_soap_valida_y_normaliza():
    df = normalizar_soap(pd.DataFrame([_fila()]))
    assert list(df.columns) == COLUMNAS_SALIDA
    r = df.iloc[0]
    assert (r.producto, r.producto_norm) == ("Papa negra", "PAPA NEGRA")
    assert r.departamento == "Nariño" and r.ciudad == "Pasto"
    assert r.id_municipio == "52001" and r.id_departamento == "52"
    assert r.grupo == "Tubérculos, raíces y plátanos" and r.fuente == "soap"
    assert r.precio_prom_kg == 1100


def test_normalizar_soap_descarta_invalidos_y_limpia_min_max():
    filas = pd.DataFrame([
        _fila(promedioKg="0"),                                   # precio 0 -> se descarta
        _fila(artiNombre="Zanahoria", promedioKg="abc"),         # no numérico -> se descarta
        _fila(artiNombre="Yuca*", promedioKg="9999999"),         # fuera de rango -> se descarta
        _fila(artiNombre="Tomate*", minimoKg="1500", maximoKg="1000", promedioKg="1100"),  # min/max incoherentes
        _fila(artiNombre="Lulo", muniId="5"),                    # municipio inválido -> queda sin código
    ])
    df = normalizar_soap(filas).set_index("producto")
    assert set(df.index) == {"Tomate", "Lulo"}
    assert pd.isna(df.loc["Tomate", "precio_min_kg"]) and pd.isna(df.loc["Tomate", "precio_max_kg"])
    assert df.loc["Tomate", "precio_prom_kg"] == 1100          # el promedio se conserva
    assert pd.isna(df.loc["Lulo", "id_municipio"])


def test_normalizar_soap_fusiona_alias_de_mercado():
    filas = pd.DataFrame([
        _fila(fuenNombre="Cali, Santa Elena", minimoKg="900", maximoKg="1100", promedioKg="1000"),
        _fila(fuenNombre="Cali, Santa Helena", minimoKg="1000", maximoKg="1300", promedioKg="1200"),
    ])
    df = normalizar_soap(filas)
    assert len(df) == 1
    r = df.iloc[0]
    assert r.mercado == "Cali, Santa Elena"
    assert r.precio_prom_kg == 1100 and r.precio_min_kg == 900 and r.precio_max_kg == 1300


# ── Excel diario ─────────────────────────────────────────────────────────
def _excel_bytes() -> bytes:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([None])
    ws.append(["Viernes 18 de septiembre de 2026"])
    ws.append(["Precio $/Kg", "Barranquilla", None, "Bogotá, Corabastos", None, "Ibagué, \nLa 21", None])
    ws.append([None, "Precio", "Var %", "Precio", "Var %", "Precio", "Var %"])
    ws.append(["Verduras y hortalizas"])                                   # fila de categoría
    ws.append(["Ahuyama", "n.d.", "n.d.", 2275, 0.03, 1350, 0])
    ws.append(["Papa  criolla", 4000, 0.01, 3500, -0.02, "n.d.", "n.d."])
    ws.append(["*Variedad predominante en el mercado"])                    # nota
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_boletin_formato_largo():
    df = parse_boletin(_excel_bytes())
    assert set(df.columns) == {"fecha", "mercado", "producto", "precio_prom_kg"}
    assert (df["fecha"] == pd.Timestamp("2026-09-18")).all()
    # 'n.d.' no genera fila; categorías y notas tampoco
    assert len(df) == 4
    ahuyama = df[df.producto == "Ahuyama"].set_index("mercado").precio_prom_kg
    assert ahuyama["Bogotá, Corabastos"] == 2275 and "Barranquilla" not in ahuyama.index


def test_normalizar_excel_omite_ciudades_agregadas_y_marca_fuente():
    df = normalizar_excel(parse_boletin(_excel_bytes()))
    assert "Barranquilla" not in set(df.mercado)                 # es promedio de sus mercados, no un mercado
    assert set(df.mercado) == {"Bogotá, Corabastos", "Ibagué, La 21"}
    assert set(df.fuente) == {"excel"}
    assert df[df.producto_norm == "PAPA CRIOLLA"].precio_prom_kg.tolist() == [3500]
    assert df.precio_min_kg.isna().all()                        # el Excel no trae mín/máx


# ── Orquestación: cuándo consultar el SOAP ──────────────────────────────
class _Motor:
    """Los pasos reciben `engine` pero los accesos a BD se sustituyen con monkeypatch."""


@pytest.fixture
def orquestador(monkeypatch):
    import load.load_precios as lp
    import run_prices as rp

    estado = {"max_soap": date(2026, 9, 17), "full": None, "ultimo": None, "llamadas": []}
    monkeypatch.setattr(lp, "fecha_max_precios", lambda engine, fuente=None: estado["max_soap"])

    def _ultimo_run(engine, fuente, status=None, source_ref=None):
        return estado["full"] if source_ref == "full" else estado["ultimo"]

    monkeypatch.setattr(lp, "ultimo_run", _ultimo_run)
    monkeypatch.setattr(rp, "run_soap", lambda engine, desde: estado["llamadas"].append(desde) or {"status": "ok"})
    return rp, estado


AHORA = datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc)


def test_soap_sin_backfill_se_omite(orquestador):
    rp, estado = orquestador
    estado["max_soap"] = None
    assert rp.run_soap_si_corresponde(_Motor(), date(2026, 9, 18), AHORA)["motivo"] == "sin_backfill"
    assert estado["llamadas"] == []


def test_soap_reconciliacion_semanal(orquestador):
    rp, estado = orquestador
    estado["full"] = {"finished_at": AHORA - timedelta(days=8)}
    rp.run_soap_si_corresponde(_Motor(), date(2026, 9, 17), AHORA)
    assert estado["llamadas"] == [None]                         # None = historial completo


def test_soap_atrasado_carga_incremental_una_vez_cada_2_horas(orquestador):
    rp, estado = orquestador
    estado["full"] = {"finished_at": AHORA - timedelta(days=1)}

    estado["ultimo"] = {"started_at": AHORA - timedelta(hours=3)}
    rp.run_soap_si_corresponde(_Motor(), date(2026, 9, 18), AHORA)
    assert estado["llamadas"] == [date(2026, 9, 17) - timedelta(days=rp.SOAP_VENTANA_DIAS)]

    estado["llamadas"].clear()
    estado["ultimo"] = {"started_at": AHORA - timedelta(minutes=30)}
    assert rp.run_soap_si_corresponde(_Motor(), date(2026, 9, 18), AHORA)["status"] == "espera"
    assert estado["llamadas"] == []


def test_soap_al_dia_no_descarga(orquestador):
    rp, estado = orquestador
    estado["full"] = {"finished_at": AHORA - timedelta(days=1)}
    estado["max_soap"] = date(2026, 9, 18)
    assert rp.run_soap_si_corresponde(_Motor(), date(2026, 9, 18), AHORA)["status"] == "al_dia"
    assert estado["llamadas"] == []
