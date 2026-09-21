"""
extract_sipsa_diario.py — Boletín diario SIPSA (DANE) en Excel.

Archivo pequeño (~340 KB) publicado cada día hábil hacia el mediodía:
  https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSADiario-18sep2026.xlsx
Trae un resumen de ~16 mercados x 36 productos (solo precio promedio $/kg).
NO incluye Pasto ni otros mercados que sí están en el SOAP, ni mín/máx.

Sirve como sondeo horario barato: un HEAD dice si hay archivo nuevo (Last-Modified)
sin descargar nada. El SOAP (extract_sipsa_soap) completa el resto.
"""
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

from clean.clean_precios_diarios import normalizar_excel
from config.precios import MESES_ABREV, SIPSA_EXCEL_URL
from extract.extract_sipsa import _parse_spanish_date

logger = logging.getLogger(__name__)

TIMEOUT = 60
MAX_DIAS_ATRAS = 7          # cuántos días hacia atrás buscar el último boletín publicado
TAM_MINIMO_BYTES = 50_000   # un boletín real pesa ~340 KB; menos es una página de error


@dataclass
class BoletinMeta:
    fecha: date
    url: str
    last_modified: datetime | None
    tamano: int | None


def token_fecha(d: date) -> str:
    """18 de septiembre de 2026 -> '18sep2026' (día con dos dígitos)."""
    return f"{d.day:02d}{MESES_ABREV[d.month - 1]}{d.year}"


def url_boletin(d: date) -> str:
    return SIPSA_EXCEL_URL.format(token=token_fecha(d))


def _meta_desde_headers(d: date, r: requests.Response) -> BoletinMeta | None:
    if r.status_code != 200:
        return None
    if "html" in r.headers.get("Content-Type", "").lower():
        return None
    tamano = int(r.headers["Content-Length"]) if r.headers.get("Content-Length", "").isdigit() else None
    if tamano is not None and tamano < TAM_MINIMO_BYTES:
        return None
    lm = None
    if r.headers.get("Last-Modified"):
        try:
            lm = parsedate_to_datetime(r.headers["Last-Modified"]).astimezone(timezone.utc)
        except (TypeError, ValueError):
            lm = None
    return BoletinMeta(fecha=d, url=url_boletin(d), last_modified=lm, tamano=tamano)


def head_boletin(d: date) -> BoletinMeta | None:
    """HEAD del boletín de un día. None si no existe (fin de semana, festivo o aún sin publicar)."""
    try:
        r = requests.head(url_boletin(d), timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        logger.warning("SIPSA Excel: HEAD %s falló: %s", d, exc)
        return None
    return _meta_desde_headers(d, r)


def buscar_ultimo_boletin(hoy: date | None = None, max_dias_atras: int = MAX_DIAS_ATRAS) -> BoletinMeta | None:
    """Recorre desde hoy hacia atrás (saltando fines de semana) hasta hallar un boletín publicado."""
    hoy = hoy or datetime.now(timezone(timedelta(hours=-5))).date()  # Colombia = UTC-5
    for atras in range(max_dias_atras + 1):
        d = hoy - timedelta(days=atras)
        if d.weekday() >= 5:
            continue
        meta = head_boletin(d)
        if meta:
            return meta
    return None


def descargar_boletin(meta: BoletinMeta) -> bytes:
    r = requests.get(meta.url, timeout=TIMEOUT)
    r.raise_for_status()
    if len(r.content) < TAM_MINIMO_BYTES:
        raise ValueError(f"Boletin {meta.url} demasiado pequeño ({len(r.content)} bytes)")
    return r.content


def parse_boletin(contenido: bytes) -> pd.DataFrame:
    """
    Tabla cruzada -> formato largo (fecha, mercado, producto, precio_prom_kg) SIN normalizar.

    Fila 1: fecha en texto. Fila 2: nombres de mercado en las columnas 1, 3, 5...
    (cada mercado ocupa dos columnas: Precio y Var %). Fila 3: encabezados Precio/Var %.
    Desde la fila 4: productos (las filas de categoría y las notas no tienen precios).
    """
    raw = pd.read_excel(io.BytesIO(contenido), header=None)
    fecha_iso = _parse_spanish_date(str(raw.iloc[1, 0]))
    fecha = pd.to_datetime(fecha_iso, errors="coerce")
    if pd.isna(fecha):
        raise ValueError(f"No se pudo leer la fecha del boletín: {raw.iloc[1, 0]!r}")

    mercados = {
        col: str(raw.iloc[2, col])
        for col in range(1, raw.shape[1], 2)
        if pd.notna(raw.iloc[2, col])
    }

    filas = []
    for i in range(4, len(raw)):
        producto = raw.iloc[i, 0]
        if pd.isna(producto):
            continue
        for col, mercado in mercados.items():
            precio = pd.to_numeric(raw.iloc[i, col], errors="coerce")  # 'n.d.' -> NaN
            if pd.notna(precio):
                filas.append({
                    "fecha": fecha,
                    "mercado": mercado,
                    "producto": str(producto),
                    "precio_prom_kg": float(precio),
                })
    return pd.DataFrame(filas, columns=["fecha", "mercado", "producto", "precio_prom_kg"])


def extract_sipsa_diario(meta: BoletinMeta) -> pd.DataFrame:
    """Descarga, parsea y normaliza el boletín. Retorna filas listas para cargar (fuente='excel')."""
    contenido = descargar_boletin(meta)
    largo = parse_boletin(contenido)
    if largo.empty:
        logger.warning("SIPSA Excel %s: sin precios legibles", meta.fecha)
    df = normalizar_excel(largo)
    if not df.empty and df["fecha"].max().date() != meta.fecha:
        logger.warning(
            "SIPSA Excel: la fecha interna (%s) no coincide con la del archivo (%s)",
            df["fecha"].max().date(), meta.fecha,
        )
    return df
