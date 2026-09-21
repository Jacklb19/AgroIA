import pandas as pd
import logging
from sqlalchemy import text
from config.settings import CLIMA_YEAR_START, YEAR_END

logger = logging.getLogger(__name__)

CHECKS = [
    {
        "nombre": "municipios_con_cobertura_climatica",
        "sql": """
            SELECT
                COUNT(DISTINCT m.id_municipio) FILTER (WHERE e.id_municipio IS NOT NULL)::FLOAT
                / NULLIF(COUNT(DISTINCT m.id_municipio), 0) * 100 AS pct
            FROM dim_municipio m
            LEFT JOIN dim_estacion_ideam e ON e.id_municipio = m.id_municipio
        """,
        "umbral_min": 80,
        "mensaje": "% municipios con estación climática asignada",
    },
    {
        "nombre": "registros_sin_municipio",
        "sql": "SELECT COUNT(*) FILTER (WHERE id_municipio IS NULL)::FLOAT / NULLIF(COUNT(*), 0) * 100 AS pct FROM fact_produccion_agricola",
        "umbral_max": 0,
        "mensaje": "% registros de producción sin id_municipio",
    },
    {
        "nombre": "municipios_rendimiento_nulo",
        "sql": "SELECT COUNT(*) FILTER (WHERE rendimiento_t_ha IS NULL OR rendimiento_t_ha = 0)::FLOAT / NULLIF(COUNT(*), 0) * 100 AS pct FROM fact_produccion_agricola",
        "umbral_max": 5,
        "mensaje": "% registros de producción con rendimiento 0 o NULL",
    },
    {
        "nombre": "modelos_activos_duplicados",
        "sql": """
            SELECT COALESCE(SUM(GREATEST(cnt - 1, 0)), 0)::FLOAT AS pct
            FROM (
                SELECT nombre_modelo, COUNT(*) AS cnt
                FROM model_version
                WHERE activo = TRUE
                GROUP BY nombre_modelo
            ) t
        """,
        "umbral_max": 0,
        "mensaje": "Número de modelos activos en producción (debe ser <= 1)",
    },
    {
        "nombre": "estaciones_sin_municipio",
        "sql": """
            SELECT COUNT(*) FILTER (WHERE id_municipio IS NULL)::FLOAT
            / NULLIF(COUNT(*), 0) * 100 AS pct
            FROM dim_estacion_ideam
        """,
        "umbral_max": 5,
        "mensaje": "% estaciones IDEAM sin municipio asignado",
    },
    {
        "nombre": "duplicados_clima_mensual",
        "sql": """
            SELECT COALESCE(SUM(duplicados), 0)::FLOAT AS pct
            FROM (
                SELECT GREATEST(COUNT(*) - 1, 0) AS duplicados
                FROM fact_clima_mensual
                GROUP BY id_estacion, id_tiempo
            ) t
        """,
        "umbral_max": 0,
        "mensaje": "Duplicados en fact_clima_mensual por (id_estacion, id_tiempo)",
    },
    {
        "nombre": "cobertura_temporal_clima_anios",
        "sql": """
            SELECT COUNT(DISTINCT dt.anio)::FLOAT AS pct
            FROM fact_clima_mensual fc
            JOIN dim_tiempo dt ON dt.id_tiempo = fc.id_tiempo
        """,
        "umbral_min": max(1, YEAR_END - CLIMA_YEAR_START + 1),
        "mensaje": "Años distintos cubiertos por fact_clima_mensual",
    },
    {
        "nombre": "trimestres_enso_faltantes",
        "sql": f"""
            WITH fact_count AS (
                SELECT COUNT(*) AS total FROM fact_alerta_enso
            ),
            periodos AS (
                SELECT DISTINCT anio, trimestre
                FROM dim_tiempo
                WHERE anio BETWEEN {CLIMA_YEAR_START} AND {YEAR_END}
            ),
            enso AS (
                SELECT DISTINCT dt.anio, dt.trimestre
                FROM fact_alerta_enso fe
                JOIN dim_tiempo dt ON dt.id_tiempo = fe.id_tiempo
            )
            SELECT CASE
                WHEN (SELECT total FROM fact_count) = 0 THEN NULL
                ELSE (
                    SELECT COUNT(*)::FLOAT
                    FROM periodos p
                    LEFT JOIN enso e ON e.anio = p.anio AND e.trimestre = p.trimestre
                    WHERE e.anio IS NULL
                )
            END AS pct
        """,
        "umbral_max": 0,
        "mensaje": "Trimestres faltantes en fact_alerta_enso",
    },
]

def run_quality_report(engine) -> pd.DataFrame:
    resultados = []
    with engine.connect() as conn:
        for check in CHECKS:
            try:
                row = conn.execute(text(check["sql"])).fetchone()
                valor = float(row[0]) if row and row[0] is not None else None
                umbral_min = check.get("umbral_min")
                umbral_max = check.get("umbral_max")
                if valor is None:
                    estado = "SIN_DATOS"
                elif umbral_min is not None and valor < umbral_min:
                    estado = "ALERTA"
                elif umbral_max is not None and valor > umbral_max:
                    estado = "ALERTA"
                else:
                    estado = "OK"
                resultados.append({
                    "indicador": check["nombre"],
                    "descripcion": check["mensaje"],
                    "valor": valor,
                    "estado": estado,
                })
                if estado == "ALERTA":
                    val_str = f"{valor:.2f}" if valor is not None else "N/A"
                    logger.warning(f"CALIDAD ALERTA — {check['mensaje']}: {val_str}")
                else:
                    val_str = f"{valor:.2f}" if valor is not None else "N/A"
                    logger.info(f"CALIDAD OK — {check['mensaje']}: {val_str}")
            except Exception as e:
                # Sin rollback, un check que falla deja abortada la transacción y rompe todos los siguientes.
                conn.rollback()
                logger.error(f"Error en check {check['nombre']}: {e}")
                resultados.append({
                    "indicador": check["nombre"], "descripcion": check["mensaje"],
                    "valor": None, "estado": "SIN_DATOS",
                })
    df = pd.DataFrame(resultados)
    _guardar_resultados(engine, df)
    return df


def _guardar_resultados(engine, df: pd.DataFrame) -> None:
    """Guarda cada corrida en quality_check_run (para /api/calidad y /api/estado) y avisa si hay alertas."""
    if df.empty:
        return
    try:
        filas = [
            {"i": r["indicador"], "d": r["descripcion"], "v": None if pd.isna(r["valor"]) else float(r["valor"]), "e": r["estado"]}
            for r in df.to_dict("records")
        ]
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO quality_check_run (indicador, descripcion, valor, estado) VALUES (:i, :d, :v, :e)"),
                filas,
            )
            conn.execute(text("DELETE FROM quality_check_run WHERE ejecutado_at < NOW() - INTERVAL '90 days'"))
    except Exception as exc:  # p. ej. migración 004 sin aplicar: el reporte sigue siendo válido
        logger.warning("No se pudo guardar el reporte de calidad en la BD: %s", exc)

    en_alerta = df[df["estado"] == "ALERTA"]
    if not en_alerta.empty:
        from utils.alertas import enviar_alerta

        detalle = "\n".join(f"· {r['descripcion']}: {r['valor']:.2f}" for r in en_alerta.to_dict("records"))
        enviar_alerta(f"Calidad de datos: {len(en_alerta)} indicador(es) en alerta", detalle, nivel="aviso")
