"""
extraction_quality.py — Toolkit reusable para extractores AgroIA.

Garantiza que cada fuente entre al pipeline con:
- Reintentos exponenciales y timeouts coherentes
- Validación de schema (columnas requeridas + tipos)
- Detección de NULL y reporte de completitud
- Coerción de tipos numéricos sin perder filas válidas
- Deduplicación por clave natural (mantiene la más reciente)
- Trazabilidad: columnas `_source_uri`, `_extracted_at`, `_row_hash`
- Reporte JSON de calidad por fuente (input para `validate/audit_sources.py`)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# ── HTTP con reintentos ─────────────────────────────────────────────────
class FetchError(RuntimeError):
    pass


def fetch_json(
    url: str,
    params: dict | None = None,
    timeout: int = 60,
    max_retries: int = 4,
    backoff_base: float = 1.5,
    headers: dict | None = None,
) -> list | dict:
    """GET con reintentos exponenciales. Lanza FetchError si todos fallan."""
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=timeout, headers=headers)
            if r.status_code == 429:
                wait = backoff_base ** (attempt + 2)
                logger.warning("HTTP 429 en %s — esperando %ss", url, wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last_err = exc
            wait = backoff_base ** attempt
            logger.warning("intento %s/%s falló (%s) — reintentando en %.1fs",
                           attempt + 1, max_retries, exc, wait)
            time.sleep(wait)
    raise FetchError(f"agotados {max_retries} reintentos contra {url}: {last_err}")


def paginate_socrata(
    url: str,
    extra_params: dict | None = None,
    page_size: int = 50_000,
    max_rows: int | None = None,
    timeout: int = 60,
) -> list[dict]:
    """Pagina Socrata con $limit / $offset hasta agotar resultados."""
    rows: list[dict] = []
    offset = 0
    while True:
        params = {"$limit": page_size, "$offset": offset, **(extra_params or {})}
        batch = fetch_json(url, params=params, timeout=timeout)
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(batch)
        if max_rows and len(rows) >= max_rows:
            return rows[:max_rows]
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


# ── Validación + limpieza ───────────────────────────────────────────────
def validate_required_columns(df: pd.DataFrame, required: Iterable[str], fuente: str) -> pd.DataFrame:
    """Lanza ValueError si faltan columnas críticas."""
    faltantes = [c for c in required if c not in df.columns]
    if faltantes:
        raise ValueError(f"[{fuente}] faltan columnas requeridas: {faltantes}")
    return df


def coerce_numeric(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Convierte columnas a numérico; valores no parseables → NaN."""
    df = df.copy()
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def coerce_str(df: pd.DataFrame, columns: Iterable[str], strip: bool = True, upper: bool = False) -> pd.DataFrame:
    df = df.copy()
    for c in columns:
        if c in df.columns:
            s = df[c].astype("string")
            if strip: s = s.str.strip()
            if upper: s = s.str.upper()
            df[c] = s
    return df


def drop_critical_nulls(df: pd.DataFrame, critical: Iterable[str], fuente: str) -> pd.DataFrame:
    """
    Elimina filas con NULL en columnas críticas. Logea cuántas se descartan.
    A diferencia de imputar con 0/'desconocido', NO inventa datos.
    """
    antes = len(df)
    out = df.dropna(subset=list(critical))
    perdidas = antes - len(out)
    if perdidas > 0:
        logger.info("[%s] descartadas %s/%s filas con NULL en %s",
                    fuente, perdidas, antes, list(critical))
    return out


def filter_range(df: pd.DataFrame, column: str, low: float | None = None, high: float | None = None) -> pd.DataFrame:
    """Descarta filas con valores fuera del rango esperado (ej. años, lat/lon)."""
    if column not in df.columns:
        return df
    mask = pd.Series(True, index=df.index)
    if low  is not None: mask &= df[column] >= low
    if high is not None: mask &= df[column] <= high
    out = df[mask]
    descartadas = len(df) - len(out)
    if descartadas > 0:
        logger.info("filter_range %s [%s, %s]: descartadas %s filas", column, low, high, descartadas)
    return out


def dedupe_keep_latest(df: pd.DataFrame, key_cols: list[str], order_col: str | None = None) -> pd.DataFrame:
    """Deduplica por `key_cols`. Si hay `order_col`, mantiene la fila con valor más alto."""
    if order_col and order_col in df.columns:
        df = df.sort_values(order_col).drop_duplicates(subset=key_cols, keep="last")
    else:
        df = df.drop_duplicates(subset=key_cols, keep="last")
    return df


def add_provenance(df: pd.DataFrame, source_uri: str) -> pd.DataFrame:
    """Agrega columnas de trazabilidad."""
    df = df.copy()
    df["_source_uri"]   = source_uri
    df["_extracted_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return df


def row_hash(df: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    """Hash determinista por fila sobre `columns` — útil para idempotencia."""
    cols = [c for c in columns if c in df.columns]
    if not cols:
        return pd.Series([""] * len(df), index=df.index)
    concat = df[cols].astype(str).agg("||".join, axis=1)
    return concat.map(lambda s: hashlib.md5(s.encode("utf-8")).hexdigest())


# ── Reporte de calidad ──────────────────────────────────────────────────
def quality_report(df: pd.DataFrame, fuente: str, source_uri: str, key_cols: list[str] | None = None) -> dict:
    """Reporte agregado de completitud por columna + duplicados."""
    n = len(df)
    completitud = {
        c: round(100 * df[c].notna().sum() / n, 2) if n else 0.0
        for c in df.columns
        if not c.startswith("_")
    }
    duplicados = 0
    if key_cols and all(c in df.columns for c in key_cols):
        duplicados = int(df.duplicated(subset=key_cols).sum())
    return {
        "fuente":              fuente,
        "uri":                 source_uri,
        "filas":               int(n),
        "columnas":            int(df.shape[1]),
        "completitud_pct":     completitud,
        "duplicados_por_clave": duplicados,
        "extraido_at":         datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def save_quality_report(report: dict, base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in report["fuente"])
    out  = base_dir / f"{safe}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Reporte de calidad: %s", out)
    return out


# ── Pipeline estándar para un extractor ─────────────────────────────────
def standardize(
    df: pd.DataFrame,
    fuente: str,
    source_uri: str,
    required: list[str],
    numeric: list[str] | None = None,
    string_strip: list[str] | None = None,
    critical_nulls: list[str] | None = None,
    key_cols: list[str] | None = None,
    range_filters: dict[str, tuple[float | None, float | None]] | None = None,
    reports_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Pipeline estándar: valida schema, coacciona tipos, descarta NULL críticos,
    aplica rangos, deduplica, agrega provenance y emite reporte de calidad.
    """
    if df.empty:
        logger.warning("[%s] DataFrame vacío al entrar a standardize", fuente)

    df = validate_required_columns(df, required, fuente)
    if numeric:        df = coerce_numeric(df, numeric)
    if string_strip:   df = coerce_str(df, string_strip, strip=True)
    if critical_nulls: df = drop_critical_nulls(df, critical_nulls, fuente)
    if range_filters:
        for col, (lo, hi) in range_filters.items():
            df = filter_range(df, col, lo, hi)
    if key_cols:       df = dedupe_keep_latest(df, key_cols)
    df = add_provenance(df, source_uri)

    report = quality_report(df, fuente, source_uri, key_cols)
    if reports_dir:
        save_quality_report(report, reports_dir)
    return df, report
