"""
informe_precios.py — Informe diario de precios mayoristas (SIPSA).

Genera un JSON determinista por fecha (sin texto inventado) y lo guarda en
`informe_precio_diario`. Contenido: mayores subidas/bajadas (día y 7 días),
brecha de precio entre mercados por producto, resumen por departamento,
precios atípicos y cobertura (cuántas series reportaron ese día).
"""
import json
import logging
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

VENTANA_DIAS = 45          # historia que se consulta por serie
MAX_DIAS_ANTERIOR = 5      # el "dato anterior" debe ser de los últimos 5 días (fines de semana/festivos)
TOP = 8
UMBRAL_Z = 3.0
MIN_OBS_Z = 10
MIN_MERCADOS_BRECHA = 3
SERIE_ACTIVA_DIAS = 30

_KEY = ["id_central", "id_producto"]


def _r(v, d=1):
    return None if v is None or pd.isna(v) else round(float(v), d)


def _ultima_por_serie(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values("fecha").groupby(_KEY, as_index=False).tail(1)


def _fila(r, var_col=None, extra=None) -> dict:
    out = {
        "producto": r["producto"], "mercado": r["mercado"], "departamento": r["departamento"],
        "precio": _r(r["precio_prom_kg"], 0),
    }
    if var_col:
        out["anterior"] = _r(r["precio_ant"] if var_col == "var_dia_pct" else r["precio_7d"], 0)
        out["var_pct"] = _r(r[var_col])
    if extra:
        out.update(extra)
    return out


def calcular_informe(df: pd.DataFrame, fecha: date) -> dict:
    """
    df: historia reciente con columnas id_central, mercado, departamento, id_producto,
    producto, grupo, fecha (datetime64), precio_prom_kg. Función pura (sin BD).
    """
    d = pd.Timestamp(fecha)
    df = df[df["fecha"] <= d].copy()
    hoy = df[df["fecha"] == d].copy()

    activas = df[df["fecha"] >= d - pd.Timedelta(days=SERIE_ACTIVA_DIAS)][_KEY].drop_duplicates()
    cobertura = {
        "series_activas": int(len(activas)),
        "series_con_dato": int(len(hoy)),
        "mercados_activos": int(df[df["fecha"] >= d - pd.Timedelta(days=SERIE_ACTIVA_DIAS)]["id_central"].nunique()),
        "mercados_con_dato": int(hoy["id_central"].nunique()),
    }
    informe = {"fecha": d.date().isoformat(), "cobertura": cobertura, "fuente": "DANE - SIPSA (precios mayoristas, $/kg)"}
    if hoy.empty:
        informe.update({k: [] for k in (
            "mayores_subidas_dia", "mayores_bajadas_dia", "mayores_subidas_7d", "mayores_bajadas_7d",
            "brecha_entre_mercados", "por_departamento", "atipicos")})
        return informe

    # Dato anterior (≤ 5 días) y dato de hace ~7 días (entre 7 y 14 días) por serie
    ant = _ultima_por_serie(df[(df["fecha"] < d) & (df["fecha"] >= d - pd.Timedelta(days=MAX_DIAS_ANTERIOR))])
    sem = _ultima_por_serie(df[(df["fecha"] <= d - pd.Timedelta(days=7)) & (df["fecha"] >= d - pd.Timedelta(days=14))])
    base = hoy.merge(ant[_KEY + ["precio_prom_kg"]].rename(columns={"precio_prom_kg": "precio_ant"}), on=_KEY, how="left")
    base = base.merge(sem[_KEY + ["precio_prom_kg"]].rename(columns={"precio_prom_kg": "precio_7d"}), on=_KEY, how="left")
    base["var_dia_pct"] = (base["precio_prom_kg"] - base["precio_ant"]) / base["precio_ant"] * 100
    base["var_7d_pct"] = (base["precio_prom_kg"] - base["precio_7d"]) / base["precio_7d"] * 100

    def top(col, ascendente):
        v = base[base[col].notna() & (base[col] != 0)].sort_values(col, ascending=ascendente)
        v = v[v[col] < 0] if ascendente else v[v[col] > 0]
        return [_fila(r, col) for _, r in v.head(TOP).iterrows()]

    informe["mayores_subidas_dia"] = top("var_dia_pct", False)
    informe["mayores_bajadas_dia"] = top("var_dia_pct", True)
    informe["mayores_subidas_7d"] = top("var_7d_pct", False)
    informe["mayores_bajadas_7d"] = top("var_7d_pct", True)

    # Brecha de precio entre mercados por producto (solo mercados que reportaron hoy)
    brecha = []
    for _, g in hoy.groupby("id_producto"):
        if g["id_central"].nunique() < MIN_MERCADOS_BRECHA:
            continue
        barato, caro = g.loc[g["precio_prom_kg"].idxmin()], g.loc[g["precio_prom_kg"].idxmax()]
        brecha.append({
            "producto": barato["producto"],
            "n_mercados": int(g["id_central"].nunique()),
            "mediana": _r(g["precio_prom_kg"].median(), 0),
            "mas_barato": {"mercado": barato["mercado"], "departamento": barato["departamento"], "precio": _r(barato["precio_prom_kg"], 0)},
            "mas_caro": {"mercado": caro["mercado"], "departamento": caro["departamento"], "precio": _r(caro["precio_prom_kg"], 0)},
            "brecha_pct": _r((caro["precio_prom_kg"] - barato["precio_prom_kg"]) / barato["precio_prom_kg"] * 100),
        })
    informe["brecha_entre_mercados"] = sorted(brecha, key=lambda x: x["brecha_pct"] or 0, reverse=True)

    # Resumen por departamento
    deps = []
    for dep, g in base.groupby("departamento"):
        deps.append({
            "departamento": dep,
            "series": int(len(g)),
            "var_dia_mediana": _r(g["var_dia_pct"].median()),
            "var_7d_mediana": _r(g["var_7d_pct"].median()),
            "suben_dia": int((g["var_dia_pct"] > 0).sum()),
            "bajan_dia": int((g["var_dia_pct"] < 0).sum()),
        })
    informe["por_departamento"] = sorted(deps, key=lambda x: x["departamento"])

    # Atípicos: z-score contra las últimas 30 observaciones previas de la serie
    previo = df[df["fecha"] < d].sort_values("fecha").groupby(_KEY, as_index=False).tail(30)
    est = previo.groupby(_KEY)["precio_prom_kg"].agg(media="mean", desv="std", n="count").reset_index()
    z = base.merge(est, on=_KEY, how="inner")
    z = z[(z["n"] >= MIN_OBS_Z) & (z["desv"] > 0)].copy()
    z["z"] = (z["precio_prom_kg"] - z["media"]) / z["desv"]
    z = z[z["z"].abs() >= UMBRAL_Z]
    z = z.loc[z["z"].abs().sort_values(ascending=False).index].head(10)
    informe["atipicos"] = [
        _fila(r, None, {"z": _r(r["z"], 1), "promedio_30d": _r(r["media"], 0)}) for _, r in z.iterrows()
    ]
    return informe


def _cargar_ventana(engine, fecha: date) -> pd.DataFrame:
    sql = text("""
        SELECT f.id_central, ca.nombre_central AS mercado, ca.nombre_departamento AS departamento,
               f.id_producto, p.nombre AS producto, p.grupo,
               f.fecha, f.precio_prom_kg
        FROM fact_precio_diario f
        JOIN dim_central_abastos ca ON ca.id_central = f.id_central
        JOIN dim_producto_precio p  ON p.id_producto = f.id_producto
        WHERE f.fecha BETWEEN :desde AND :hasta
    """)
    desde = pd.Timestamp(fecha) - pd.Timedelta(days=VENTANA_DIAS)
    df = pd.read_sql(sql, engine, params={"desde": desde.date(), "hasta": fecha})
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def generar_informe(engine, fecha: date | None = None) -> dict | None:
    """Calcula y guarda el informe de `fecha` (por defecto, el último día con datos)."""
    if fecha is None:
        with engine.connect() as conn:
            fecha = conn.execute(text("SELECT MAX(fecha) FROM fact_precio_diario")).scalar()
    if fecha is None:
        logger.warning("Informe diario: no hay precios cargados")
        return None

    informe = calcular_informe(_cargar_ventana(engine, fecha), fecha)
    informe["generado_at"] = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO informe_precio_diario (fecha, payload) VALUES (:f, CAST(:p AS JSONB))
                ON CONFLICT (fecha) DO UPDATE SET payload = EXCLUDED.payload, generado_at = NOW()
            """),
            {"f": fecha, "p": json.dumps(informe, ensure_ascii=False)},
        )
    logger.info(
        "Informe diario %s: %s series con dato de %s activas",
        fecha, informe["cobertura"]["series_con_dato"], informe["cobertura"]["series_activas"],
    )
    return informe


def informe_pendiente(engine) -> bool:
    """True si el último día con datos no tiene informe, o el informe es anterior a la última carga con cambios."""
    with engine.connect() as conn:
        fila = conn.execute(text("""
            SELECT i.generado_at,
                   (SELECT MAX(finished_at) FROM ingest_run
                     WHERE status = 'ok' AND filas_nuevas > 0
                       AND fuente IN ('sipsa_excel', 'sipsa_soap')) AS ultimo_cambio
            FROM (SELECT MAX(fecha) AS f FROM fact_precio_diario) m
            LEFT JOIN informe_precio_diario i ON i.fecha = m.f
        """)).first()
    if fila is None or fila[0] is None:
        return True
    return fila[1] is not None and fila[1] > fila[0]
