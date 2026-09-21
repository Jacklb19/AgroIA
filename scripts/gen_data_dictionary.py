"""
gen_data_dictionary.py — Genera docs/DICCIONARIO_DATOS.md desde el esquema REAL de Postgres (tras aplicar las migraciones).

  python scripts/gen_data_dictionary.py           # escribe docs/DICCIONARIO_DATOS.md
  python scripts/gen_data_dictionary.py --check   # falla si el archivo está desactualizado (lo usa el CI)

Lee columnas, tipos y restricciones de information_schema / pg_constraint, así que no puede desalinearse del esquema.
El propósito de cada tabla vive en DESCRIPCIONES; una tabla nueva sin descripción hace fallar la generación
(así nadie agrega una tabla sin documentarla).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

DESTINO = Path(__file__).resolve().parent.parent / "docs" / "DICCIONARIO_DATOS.md"

DESCRIPCIONES = {
    # Dimensiones
    "dim_region_natural": "Regiones naturales de Colombia (Andina, Caribe, Pacífico, Orinoquía, Amazonía).",
    "dim_municipio": "Municipios (código DIVIPOLA de 5 dígitos), con departamento, región y centroide.",
    "dim_tiempo": "Un registro por mes (primer día); marca los años El Niño derivados del ONI.",
    "dim_cultivo": "Cultivos de la Evaluación Agropecuaria Municipal (nombre normalizado sin tildes).",
    "dim_estacion_ideam": "Estaciones meteorológicas del IDEAM asignadas a un municipio.",
    "dim_central_abastos": "Mercados mayoristas (centrales de abasto) con su departamento.",
    "dim_producto_precio": "Productos con precio mayorista SIPSA; `id_cultivo` los enlaza con la EVA cuando hay equivalencia clara.",
    # Hechos
    "fact_produccion_agricola": "Producción anual por municipio × cultivo: áreas, toneladas y rendimiento (t/ha). Fuente: EVA (datos.gov.co).",
    "fact_clima_mensual": "Clima mensual por estación IDEAM: lluvia, temperatura, humedad, brillo solar.",
    "fact_precios_mayoristas": "Precios mayoristas mensuales por mercado × cultivo (tabla histórica anterior a la diaria).",
    "fact_precio_diario": "Precio mayorista diario por mercado × producto (SIPSA): promedio, mínimo y máximo por kilo.",
    "fact_aptitud_suelo": "Clase de aptitud de suelo por municipio × cultivo (UPRA/SIPRA; hoy sin fuente activa).",
    "fact_censo_agropecuario": "Uso del suelo por municipio del Censo Nacional Agropecuario (DANE).",
    "fact_alerta_enso": "Fase ENSO por trimestre y región, con ONI, SPI y anomalía de precipitación.",
    "fact_precios_insumos": "Precios de insumos agrícolas (IPIA, DANE).",
    # Modelos
    "model_version": "Versiones de modelos entrenados, con métricas en JSON; `activo` marca la vigente.",
    "pred_rendimiento": "Predicciones de rendimiento fuera de muestra por municipio × cultivo × año, con intervalo p10–p90 y SHAP.",
    "pred_alerta_climatica": "Nivel de riesgo climático del mes siguiente por municipio (índice por reglas + modelo).",
    "pred_precio": "Pronóstico de precios a 1–10 días hábiles con su confianza.",
    "informe_precio_diario": "Informe diario de precios (JSON) generado tras cada carga.",
    # Operación
    "ingest_run": "Bitácora de ejecuciones: cada etapa del pipeline y cada job de precios (estado, filas, fecha del dato).",
    "schema_migrations": "Migraciones de esquema aplicadas y su checksum.",
    "quality_check_run": "Resultados históricos de los controles de calidad de datos.",
    "extraction_report": "Último reporte de completitud de cada fuente al extraerla.",
    "chat_session": "Sesiones del asistente conversacional.",
    "chat_message": "Mensajes de cada sesión del asistente.",
    "chat_rate": "Contadores diarios del asistente (por IP con hash y global) para limitar el gasto.",
    # Vistas
    "v_dashboard_agro": "Vista para Power BI: producción anual con clima anual del municipio.",
    "v_monitor_climatico": "Vista para Power BI: clima mensual con fase ENSO.",
    "v_predicciones_modelo": "Vista para Power BI: predicciones frente a rendimiento real y metadatos del modelo.",
    "v_alertas_climaticas": "Vista para Power BI: alertas climáticas activas.",
    "v_precio_actual": "Último precio por mercado × producto con variación diaria y de 7 días (la usa la pestaña Precios).",
}

TIPOS = {
    "character varying": "varchar", "character": "char", "timestamp with time zone": "timestamptz",
    "timestamp without time zone": "timestamp", "double precision": "double", "integer": "int", "smallint": "smallint",
    "bigint": "bigint", "boolean": "bool", "jsonb": "jsonb", "date": "date", "text": "text", "numeric": "numeric", "uuid": "uuid",
}


class DiccionarioError(RuntimeError):
    pass


def _tipo(fila) -> str:
    base = TIPOS.get(fila["data_type"], fila["data_type"])
    if fila["character_maximum_length"]:
        return f"{base}({fila['character_maximum_length']})"
    return base


def _celda(texto) -> str:
    return str(texto).replace("|", "\\|").replace("\n", " ") if texto is not None else ""


def generar(engine) -> str:
    with engine.connect() as conn:
        objetos = {r[0]: r[1] for r in conn.execute(text(
            "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"))}
        columnas = conn.execute(text(
            """SELECT table_name, column_name, data_type, character_maximum_length, is_nullable, column_default
               FROM information_schema.columns WHERE table_schema = 'public' ORDER BY table_name, ordinal_position""")).mappings().all()
        restricciones = conn.execute(text(
            """SELECT c.relname AS tabla, con.contype AS tipo, pg_get_constraintdef(con.oid) AS definicion
               FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid
               JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname = 'public' AND con.contype IN ('p', 'u', 'f')
               ORDER BY c.relname, con.contype DESC, con.conname""")).mappings().all()

    sin_descripcion = sorted(set(objetos) - set(DESCRIPCIONES))
    if sin_descripcion:
        raise DiccionarioError(
            "Tablas/vistas sin descripción en scripts/gen_data_dictionary.py: " + ", ".join(sin_descripcion))

    por_tabla: dict[str, list] = {}
    for c in columnas:
        por_tabla.setdefault(c["table_name"], []).append(c)
    rest_tabla: dict[str, list] = {}
    for r in restricciones:
        rest_tabla.setdefault(r["tabla"], []).append(r)

    def seccion(nombre: str) -> list[str]:
        out = [f"### `{nombre}`", "", DESCRIPCIONES[nombre], "",
               "| Columna | Tipo | Nulo | Por defecto |", "|---|---|---|---|"]
        for c in por_tabla.get(nombre, []):
            defecto = c["column_default"]
            if defecto and defecto.startswith("nextval("):
                defecto = "autoincremental"
            out.append(f"| `{c['column_name']}` | {_tipo(c)} | {'sí' if c['is_nullable'] == 'YES' else 'no'} | {_celda(defecto)} |")
        etiquetas = {"p": "Clave primaria", "u": "Único", "f": "Clave foránea"}
        if rest_tabla.get(nombre):
            out += ["", "Restricciones:"] + [f"- {etiquetas[r['tipo']]}: `{r['definicion']}`" for r in rest_tabla[nombre]]
        return out + [""]

    grupos = [
        ("Dimensiones", lambda n: n.startswith("dim_")),
        ("Hechos", lambda n: n.startswith("fact_")),
        ("Modelos y predicciones", lambda n: n.startswith(("pred_", "model_", "informe_"))),
        ("Operación y observabilidad", lambda n: n in {"ingest_run", "schema_migrations", "quality_check_run", "extraction_report"}
                                                    or n.startswith("chat_")),
    ]
    tablas = [n for n, t in objetos.items() if t == "BASE TABLE"]
    vistas = [n for n, t in objetos.items() if t == "VIEW"]

    md = [
        "# Diccionario de datos",
        "",
        "> **Archivo generado** por `python scripts/gen_data_dictionary.py` a partir del esquema real (migraciones aplicadas).",
        "> No lo edites a mano: cambia las migraciones o las descripciones del script y vuelve a generarlo.",
        "",
        f"{len(tablas)} tablas y {len(vistas)} vistas. Convenciones: `dim_*` dimensiones, `fact_*` hechos, `pred_*` salidas de modelos, "
        "`v_*` vistas para Power BI y la web.",
        "",
        "| Objeto | Propósito |",
        "|---|---|",
    ]
    md += [f"| `{n}` | {_celda(DESCRIPCIONES[n])} |" for n in sorted(objetos)]
    md.append("")
    usadas: set[str] = set()
    for titulo, pertenece in grupos:
        nombres = [n for n in tablas if pertenece(n) and n not in usadas]
        usadas.update(nombres)
        if nombres:
            md += [f"## {titulo}", ""]
            for n in nombres:
                md += seccion(n)
    restantes = [n for n in tablas if n not in usadas]
    if restantes:
        md += ["## Otras tablas", ""]
        for n in restantes:
            md += seccion(n)
    md += ["## Vistas", ""]
    for n in vistas:
        md += seccion(n)
    return "\n".join(md).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera docs/DICCIONARIO_DATOS.md desde el esquema real")
    parser.add_argument("--check", action="store_true", help="No escribe: falla si el archivo está desactualizado")
    args = parser.parse_args(argv)

    from config.settings import ConfigError
    from load.db import get_engine
    from load.migrate import aplicar

    try:
        engine = get_engine()
        aplicar(engine)                # el diccionario describe el esquema tras las migraciones
        contenido = generar(engine)
    except (ConfigError, DiccionarioError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    actual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
    if args.check:
        if actual.replace("\r\n", "\n") != contenido:
            print("docs/DICCIONARIO_DATOS.md está desactualizado: corre `python scripts/gen_data_dictionary.py` y súbelo.", file=sys.stderr)
            return 1
        print("Diccionario de datos al día.")
        return 0
    DESTINO.parent.mkdir(exist_ok=True)
    DESTINO.write_text(contenido, encoding="utf-8", newline="\n")
    print(f"Escrito {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
