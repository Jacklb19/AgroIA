"""
audit_sources.py — Auditoría consolidada de fuentes de datos.

Lee los reportes JSON emitidos por `utils.extraction_quality.standardize`
durante cada extracción y genera un Markdown con:
- estado de cada fuente (✅ / ⚠ / ❌)
- filas, columnas, completitud media
- duplicados detectados por clave natural
- columnas con baja completitud (< 80%)
- timestamps de la última corrida

Uso:
    python -m validate.audit_sources
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from config.settings import DATA_RAW

logger = logging.getLogger(__name__)

REPORTS_DIR = DATA_RAW.parent / "quality_reports"
OUTPUT_MD   = REPORTS_DIR / "AUDIT.md"

UMBRAL_BUENO  = 95.0
UMBRAL_MEDIO  = 80.0


def _load_reports() -> list[dict]:
    if not REPORTS_DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in REPORTS_DIR.glob("*.json")]


def _status(comp_media: float, filas: int, dup: int) -> str:
    if filas == 0:                      return "❌ SIN DATOS"
    if dup > filas * 0.05:              return "⚠ DUPLICADOS"
    if comp_media < UMBRAL_MEDIO:       return "⚠ BAJA COMPLETITUD"
    if comp_media < UMBRAL_BUENO:       return "🟡 ACEPTABLE"
    return "✅ OK"


def build_audit() -> str:
    reportes = _load_reports()
    if not reportes:
        return "# Auditoría de fuentes\n\n⚠ Sin reportes generados aún. Corre el pipeline de extracción primero.\n"

    lines = [
        "# Auditoría de fuentes de datos · AgroIA Colombia",
        "",
        f"_Generado: {datetime.utcnow().isoformat(timespec='seconds')}Z_",
        "",
        "| Fuente | Estado | Filas | Cols | Completitud media | Duplicados | Última extracción |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in sorted(reportes, key=lambda x: x["fuente"]):
        comp = r.get("completitud_pct", {}) or {}
        comp_media = sum(comp.values()) / max(1, len(comp))
        lines.append(
            f"| `{r['fuente']}` | {_status(comp_media, r['filas'], r['duplicados_por_clave'])} "
            f"| {r['filas']:,} | {r['columnas']} | {comp_media:.1f}% "
            f"| {r['duplicados_por_clave']} | {r['extraido_at']} |"
        )

    lines += ["", "## Columnas con baja completitud (<80%)", ""]
    flagged_any = False
    for r in sorted(reportes, key=lambda x: x["fuente"]):
        comp = r.get("completitud_pct", {}) or {}
        bajas = [(c, v) for c, v in comp.items() if v < UMBRAL_MEDIO]
        if not bajas:
            continue
        flagged_any = True
        lines.append(f"### `{r['fuente']}`")
        lines.append("")
        lines.append("| Columna | Completitud |")
        lines.append("|---|---:|")
        for c, v in sorted(bajas, key=lambda kv: kv[1]):
            lines.append(f"| `{c}` | {v:.1f}% |")
        lines.append("")
    if not flagged_any:
        lines.append("✅ Todas las columnas tienen ≥80% de completitud.")
        lines.append("")

    lines += [
        "## Próximas acciones recomendadas",
        "",
        "- Si una fuente está en ⚠ DUPLICADOS, revisar la clave natural de upsert.",
        "- Si está en ⚠ BAJA COMPLETITUD, evaluar imputación o cambiar la fuente.",
        "- Si está ❌ SIN DATOS, verificar la URL del endpoint y la red.",
        "",
        "---",
        "_Reportes individuales en JSON: `data/quality_reports/*.json`_",
    ]
    return "\n".join(lines)


def main() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    md = build_audit()
    OUTPUT_MD.write_text(md, encoding="utf-8")
    # Forzar utf-8 al stdout (Windows cp1252 no soporta emojis)
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        print(md)
    except UnicodeEncodeError:
        print(md.encode("utf-8", errors="replace").decode("utf-8"))
    print(f"\n-> Auditoria guardada en {OUTPUT_MD}")
    return OUTPUT_MD


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    main()
