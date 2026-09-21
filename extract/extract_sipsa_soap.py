"""
extract_sipsa_soap.py — Precios mayoristas diarios SIPSA (DANE) vía servicio SOAP.

`promediosSipsaParcial` no acepta filtros: devuelve TODO el historial diario
(2020-02 en adelante, ~700k filas, ~300 MB de XML) con producto, mercado,
departamento, código DIVIPOLA del municipio y precio mínimo/máximo/promedio
en $/kg. Por eso:
  - se descarga en streaming a disco y se parsea con iterparse (sin cargar el XML);
  - `desde` permite quedarse solo con los últimos días (carga incremental);
  - no sirve para sondeo horario (para eso está el Excel diario).

El servicio solo responde a SOAP 1.2 (application/soap+xml).
"""
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Iterator

import pandas as pd
import requests

from clean.clean_precios_diarios import COLUMNAS_SALIDA, normalizar_soap, validar_y_deduplicar
from config.precios import SIPSA_SOAP_NS, SIPSA_SOAP_URL
from config.settings import DATA_RAW

logger = logging.getLogger(__name__)

OPERACION = "promediosSipsaParcial"
CAMPOS = (
    "artiNombre", "grupNombre", "deptNombre", "muniId", "muniNombre",
    "fuenNombre", "enmaFecha", "minimoKg", "maximoKg", "promedioKg",
)
CHUNK_FILAS = 100_000
MAX_INTENTOS = 3
TIMEOUT = (30, 900)  # (conexión, lectura): la respuesta completa tarda ~1-2 min


class SipsaSoapError(RuntimeError):
    pass


def _envelope(operacion: str) -> bytes:
    return (
        '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
        f'xmlns:ws="{SIPSA_SOAP_NS}"><soap:Header/><soap:Body><ws:{operacion}/></soap:Body></soap:Envelope>'
    ).encode("utf-8")


def _validar_respuesta(path: Path) -> None:
    """Falla si el archivo no es la respuesta SOAP esperada (Fault, HTML de error, vacío)."""
    with open(path, "rb") as f:
        cabecera = f.read(4096).decode("utf-8", errors="replace")
    if f"{OPERACION}Response" not in cabecera:
        raise SipsaSoapError(f"Respuesta SOAP inesperada: {cabecera[:200]!r}")


def descargar_parcial(destino: Path | None = None) -> Path:
    """Descarga la respuesta completa a disco (streaming) con reintentos."""
    destino = destino or DATA_RAW / "sipsa" / "soap_parcial.xml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".part")

    ultimo_error: Exception | None = None
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            logger.info("SIPSA SOAP: descargando %s (intento %s/%s)...", OPERACION, intento, MAX_INTENTOS)
            with requests.post(
                SIPSA_SOAP_URL,
                data=_envelope(OPERACION),
                headers={"Content-Type": "application/soap+xml; charset=utf-8"},
                stream=True,
                timeout=TIMEOUT,
            ) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for bloque in r.iter_content(chunk_size=1 << 20):
                        f.write(bloque)
            _validar_respuesta(tmp)
            tmp.replace(destino)
            logger.info("SIPSA SOAP: %.0f MB -> %s", destino.stat().st_size / 1e6, destino)
            return destino
        except (requests.RequestException, SipsaSoapError, OSError) as exc:
            ultimo_error = exc
            logger.warning("SIPSA SOAP: intento %s falló: %s", intento, exc)
            if intento < MAX_INTENTOS:
                time.sleep(5 * intento)
    tmp.unlink(missing_ok=True)
    raise SipsaSoapError(f"No fue posible descargar SIPSA SOAP: {ultimo_error}")


def iter_filas(path: Path, desde: date | None = None) -> Iterator[dict]:
    """Recorre el XML en streaming y emite un dict por <return>, opcionalmente filtrado por fecha."""
    corte = desde.isoformat() if desde else None
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "return":
            continue
        fila = {hijo.tag: hijo.text for hijo in elem}
        elem.clear()
        if corte and (fila.get("enmaFecha") or "")[:10] < corte:
            continue
        yield fila


def iter_chunks(path: Path, desde: date | None = None, tam: int = CHUNK_FILAS) -> Iterator[pd.DataFrame]:
    """Emite DataFrames crudos (texto) de hasta `tam` filas."""
    buffer: list[dict] = []
    for fila in iter_filas(path, desde):
        buffer.append({c: fila.get(c) for c in CAMPOS})
        if len(buffer) >= tam:
            yield pd.DataFrame(buffer)
            buffer = []
    if buffer:
        yield pd.DataFrame(buffer)


def extract_sipsa_soap(desde: date | None = None, path: Path | None = None) -> pd.DataFrame:
    """
    Descarga (o reutiliza `path`), parsea y normaliza. Retorna el DataFrame limpio
    (ver clean_precios_diarios.COLUMNAS_SALIDA), listo para cargar.
    """
    descargado = path is None
    if descargado:
        path = descargar_parcial()
    else:
        _validar_respuesta(path)

    try:
        partes = [normalizar_soap(chunk) for chunk in iter_chunks(path, desde)]
    finally:
        if descargado:
            path.unlink(missing_ok=True)   # ~300 MB: no se conserva (disco efímero en Railway)
    partes = [p for p in partes if not p.empty]
    if not partes:
        logger.warning("SIPSA SOAP: sin filas%s.", f" desde {desde}" if desde else "")
        return pd.DataFrame(columns=COLUMNAS_SALIDA)

    df = pd.concat(partes, ignore_index=True)
    # Un mismo (mercado, producto, fecha) puede haber quedado repartido entre chunks
    df = validar_y_deduplicar(df)
    logger.info(
        "SIPSA SOAP: %s filas, %s a %s, %s productos, %s mercados",
        len(df), df["fecha"].min().date(), df["fecha"].max().date(),
        df["producto_norm"].nunique(), df["mercado"].nunique(),
    )
    return df
