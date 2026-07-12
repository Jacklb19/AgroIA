"""
anova_tests.py — Pruebas ANOVA sobre datos reales de AgroIA Colombia
=====================================================================
Ejecuta 3 pruebas ANOVA con datos reales del pipeline:

  1. Precipitación mensual  vs  Fase ENSO  (El Niño / La Niña / Neutro)
  2. Precio de insumos      vs  Tipo       (fertilizante / agroquimico / semilla / …)
  3. Precipitación mensual  vs  Trimestre  (Q1 ene-mar / Q2 abr-jun / Q3 jul-sep / Q4 oct-dic)

Cada prueba sigue el protocolo estadístico completo:
  Step 1 — Levene  (homogeneidad de varianzas)
  Step 2 — ANOVA   (scipy.stats.f_oneway)
  Step 3 — Tukey HSD post-hoc si p < 0.05

Genera boxplots en data/quality_reports/anova_*.png y una tabla resumen.

Uso:
    python -m validate.anova_tests
    python -m validate.anova_tests --verbose
"""
import argparse
import io
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import scipy.stats as stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DATA_RAW, DATA_PROCESSED

REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "quality_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PALETTE = {
    "El Niño":        "#E8604C",
    "La Niña":        "#4C9BE8",
    "Neutro":         "#6DBF67",
    "fertilizante":   "#F4A261",
    "agroquimico":    "#E76F51",
    "semilla":        "#2A9D8F",
    "combustible":    "#E9C46A",
    "mano_de_obra":   "#264653",
    "Q1 (Ene-Mar)":   "#A8DADC",
    "Q2 (Abr-Jun)":   "#457B9D",
    "Q3 (Jul-Sep)":   "#1D3557",
    "Q4 (Oct-Dic)":   "#E63946",
    "Ibagué":         "#7B2D8B",
    "Pasto":          "#F4A261",
    "Villavicencio":  "#2A9D8F",
}
DEFAULT_COLOR = "#888888"


# ─────────────────────────────────────────────────────────────────────
#  Resultado de cada prueba
# ─────────────────────────────────────────────────────────────────────

@dataclass
class AnovaResult:
    nombre: str
    variable: str
    factor: str
    grupos: list[str]
    n_por_grupo: dict
    levene_p: float
    f_stat: float
    p_valor: float
    significativa: bool
    tukey_df: pd.DataFrame | None = None
    nota: str = ""


results: list[AnovaResult] = []


# ─────────────────────────────────────────────────────────────────────
#  Utilidades estadísticas
# ─────────────────────────────────────────────────────────────────────

def _sig_label(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def _run_anova(grupos_data: dict[str, np.ndarray]) -> tuple[float, float, float]:
    arrays = list(grupos_data.values())
    lev_stat, lev_p = stats.levene(*arrays)
    f, p = stats.f_oneway(*arrays)
    return lev_p, f, p


def _tukey(series_list: list[np.ndarray], labels: list[str]) -> pd.DataFrame:
    all_vals = np.concatenate(series_list)
    all_labs = np.concatenate([np.full(len(s), l) for s, l in zip(series_list, labels)])
    result = pairwise_tukeyhsd(all_vals, all_labs, alpha=0.05)
    df = pd.DataFrame(
        data=result._results_table.data[1:],
        columns=result._results_table.data[0],
    )
    return df


# ─────────────────────────────────────────────────────────────────────
#  Formateo de ejes según tipo de dato
# ─────────────────────────────────────────────────────────────────────

def _fmt_cop(val, _pos=None):
    """Formatea valores COP: 1 500 000 → $ 1.5 M  |  85 000 → $ 85 K"""
    if val >= 1_000_000:
        return f"$ {val/1_000_000:.1f} M"
    if val >= 1_000:
        return f"$ {int(val/1_000)} K"
    return f"$ {int(val)}"


def _fmt_mm(val, _pos=None):
    return f"{val:,.0f} mm"


def _fmt_mm_dia(val, _pos=None):
    return f"{val:.1f} mm/día"


# ─────────────────────────────────────────────────────────────────────
#  Gráficas
# ─────────────────────────────────────────────────────────────────────

def _boxplot(grupos_data: dict[str, np.ndarray], title: str,
             ylabel: str, filename: str, p_valor: float,
             fmt: str = "default", log_scale: bool = False,
             clip_pct: int | None = None):
    """
    fmt: "default" | "cop" | "mm" | "mm_dia"
    log_scale: usar escala logarítmica en Y (útil cuando hay grupos con rangos muy distintos)
    """
    import matplotlib.ticker as ticker

    labels = list(grupos_data.keys())
    data   = [grupos_data[l] for l in labels]
    colors = [PALETTE.get(l, DEFAULT_COLOR) for l in labels]

    fig_w = max(8, len(labels) * 2.2)
    fig, ax = plt.subplots(figsize=(fig_w, 6))
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")

    bp = ax.boxplot(
        data,
        patch_artist=True,
        notch=False,
        medianprops=dict(color="white", linewidth=2.5),
        whiskerprops=dict(color="#666", linewidth=1.3, linestyle="--"),
        capprops=dict(color="#666", linewidth=1.5),
        flierprops=dict(marker="o", markersize=3.5, alpha=0.25, markeredgewidth=0),
        boxprops=dict(linewidth=0),
        widths=0.55,
    )

    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.88)

    # Media como diamante blanco
    means = [np.mean(d) for d in data]
    for i, mean_val in enumerate(means, 1):
        ax.plot(i, mean_val, marker="D", color="white", markersize=6,
                markeredgecolor="#333", markeredgewidth=1.2, zorder=5)

    # Anotar mediana encima de cada caja
    for i, (lbl, arr) in enumerate(grupos_data.items(), 1):
        median = np.median(arr)
        if fmt == "cop":
            med_txt = _fmt_cop(median)
        elif fmt in ("mm", "mm_dia"):
            med_txt = f"{median:.1f}"
        else:
            med_txt = f"{median:.1f}"

        ymax_box = np.percentile(arr, 75)
        ax.annotate(
            med_txt,
            xy=(i, median), xytext=(i, ymax_box),
            ha="center", va="bottom", fontsize=9, fontweight="600",
            color="#222",
            arrowprops=dict(arrowstyle="-", color="#aaa", lw=0.8),
        )

    # Escala Y y formato de ticks
    if log_scale:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt_cop))
        ax.annotate("Escala logarítmica — cada división multiplica por 10",
                    xy=(0.5, 1.01), xycoords="axes fraction",
                    ha="center", fontsize=8, color="#888", style="italic")
    else:
        if fmt == "cop":
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt_cop))
        elif fmt == "mm":
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt_mm))
        elif fmt == "mm_dia":
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt_mm_dia))

    # Etiquetas eje X: nombre del grupo + n
    xlabels = [f"{lbl}\n(n = {len(grupos_data[lbl]):,})".replace(",", ".") for lbl in labels]
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(xlabels, fontsize=10.5)
    ax.set_ylabel(ylabel, fontsize=11, labelpad=10)

    # Recortar eje Y si hay outliers extremos
    if clip_pct is not None and not log_scale:
        all_vals = np.concatenate(list(grupos_data.values()))
        ymax = np.percentile(all_vals, clip_pct)
        ymin = max(0, np.percentile(all_vals, 1))
        ax.set_ylim(ymin, ymax * 1.05)
        n_clip = int(np.sum(all_vals > ymax))
        if n_clip > 0:
            ax.annotate(
                f"↑ {n_clip} valores extremos fuera de vista (máx: {_fmt_mm(all_vals.max())})",
                xy=(0.5, 0.98), xycoords="axes fraction",
                ha="center", va="top", fontsize=8, color="#888", style="italic",
            )

    # Grid horizontal limpio
    ax.grid(axis="y", linestyle="--", linewidth=0.7, alpha=0.5, color="#ccc")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#ddd")
    ax.spines["bottom"].set_color("#ddd")

    # Título principal + resultado ANOVA
    sig = _sig_label(p_valor)
    sig_color = {"***": "#155436", "**": "#1a7a4a", "*": "#d97706", "ns": "#888"}.get(sig, "#333")
    ax.set_title(title, fontsize=13, fontweight="700", pad=14, loc="left")

    resultado_txt = (
        f"ANOVA: F significativo ({sig})  ·  p = {p_valor:.2e}  →  "
        f"{'las diferencias entre grupos son reales' if sig != 'ns' else 'sin diferencia significativa'}"
        if sig != "ns" else f"ANOVA p = {p_valor:.4f} — sin diferencia significativa"
    )
    fig.text(0.02, 0.01,
             f"◆ = media del grupo   ━ = mediana   {resultado_txt}",
             fontsize=8, color="#555")

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    out = REPORT_DIR / filename
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="#fafafa")
    plt.close(fig)
    print(f"  Gráfica guardada: {out}")


# ─────────────────────────────────────────────────────────────────────
#  PRUEBA 1 — Precipitación vs Fase ENSO
# ─────────────────────────────────────────────────────────────────────

def prueba1_precipitacion_enso(verbose: bool = False):
    print("\n" + "═" * 60)
    print("  PRUEBA 1 — Precipitación mensual vs Fase ENSO")
    print("═" * 60)

    clima = pd.read_parquet(DATA_PROCESSED / "clima_mensual.parquet")
    enso  = pd.read_csv(DATA_RAW / "enso_noaa_raw.csv", encoding="utf-8")

    # Alinear dtypes para el merge (clima usa Int64 nullable)
    clima = clima.copy()
    clima["anio"] = clima["anio"].astype("int64")
    clima["mes"]  = clima["mes"].astype("int64")

    # Merge por anio + mes
    df = clima.merge(enso[["anio", "mes", "fase_enso"]], on=["anio", "mes"], how="inner")
    df = df.dropna(subset=["precipitacion_mm", "fase_enso"])
    df = df[df["precipitacion_mm"] >= 0]

    orden_grupos = ["El Niño", "La Niña", "Neutro"]
    grupos_data: dict[str, np.ndarray] = {}
    for fase in orden_grupos:
        sub = df[df["fase_enso"] == fase]["precipitacion_mm"].values
        if len(sub) >= 3:
            grupos_data[fase] = sub

    if len(grupos_data) < 2:
        print("  [SKIP] Datos insuficientes para ANOVA.")
        return

    n_por_grupo = {k: len(v) for k, v in grupos_data.items()}
    print(f"  Registros por grupo: {n_por_grupo}")

    lev_p, f, p = _run_anova(grupos_data)
    sig = p < 0.05

    print(f"  Levene p = {lev_p:.4f}  ({'varianzas heterogéneas' if lev_p < 0.05 else 'varianzas OK'})")
    print(f"  ANOVA   F = {f:.3f},  p = {p:.6f}  {_sig_label(p)}")
    print(f"  Conclusión: {'Diferencias SIGNIFICATIVAS entre fases ENSO' if sig else 'Sin diferencias significativas'}")

    tukey_df = None
    if sig and verbose:
        tukey_df = _tukey(list(grupos_data.values()), list(grupos_data.keys()))
        print("\n  Post-hoc Tukey HSD:")
        print(tukey_df.to_string(index=False))

    _boxplot(grupos_data,
             title="Precipitación mensual por Fase ENSO\n(El Niño · La Niña · Neutro)",
             ylabel="Precipitación mensual (mm)",
             filename="anova_precipitacion_enso.png",
             p_valor=p,
             fmt="mm",
             clip_pct=95)

    results.append(AnovaResult(
        nombre="Precipitación vs Fase ENSO",
        variable="precipitacion_mm",
        factor="fase_enso",
        grupos=list(grupos_data.keys()),
        n_por_grupo=n_por_grupo,
        levene_p=lev_p,
        f_stat=f,
        p_valor=p,
        significativa=sig,
        tukey_df=tukey_df,
        nota="Join clima_mensual + enso_noaa por anio/mes",
    ))


# ─────────────────────────────────────────────────────────────────────
#  PRUEBA 2 — Precio de insumos vs Tipo de insumo
# ─────────────────────────────────────────────────────────────────────

def prueba2_precio_tipo_insumo(verbose: bool = False):
    print("\n" + "═" * 60)
    print("  PRUEBA 2 — Precio de insumos vs Tipo de insumo")
    print("═" * 60)

    df = pd.read_parquet(DATA_PROCESSED / "insumos_clean.parquet")
    df = df.dropna(subset=["precio_cop_unidad", "tipo_insumo"])
    df = df[df["precio_cop_unidad"] > 0]

    # Excluir 'indice' (no es un insumo físico con precio real)
    df = df[df["tipo_insumo"] != "indice"]

    # Solo grupos con >= 10 observaciones
    conteos = df["tipo_insumo"].value_counts()
    grupos_validos = conteos[conteos >= 10].index.tolist()
    df = df[df["tipo_insumo"].isin(grupos_validos)]

    grupos_data: dict[str, np.ndarray] = {}
    for tipo in sorted(grupos_validos):
        sub = df[df["tipo_insumo"] == tipo]["precio_cop_unidad"].values
        grupos_data[tipo] = sub

    if len(grupos_data) < 2:
        print("  [SKIP] Datos insuficientes para ANOVA.")
        return

    n_por_grupo = {k: len(v) for k, v in grupos_data.items()}
    print(f"  Registros por grupo: {n_por_grupo}")

    lev_p, f, p = _run_anova(grupos_data)
    sig = p < 0.05

    print(f"  Levene p = {lev_p:.4f}  ({'varianzas heterogéneas' if lev_p < 0.05 else 'varianzas OK'})")
    print(f"  ANOVA   F = {f:.3f},  p = {p:.6f}  {_sig_label(p)}")
    print(f"  Conclusión: {'Diferencias SIGNIFICATIVAS entre tipos de insumo' if sig else 'Sin diferencias significativas'}")

    tukey_df = None
    if sig and verbose:
        tukey_df = _tukey(list(grupos_data.values()), list(grupos_data.keys()))
        print("\n  Post-hoc Tukey HSD:")
        print(tukey_df.to_string(index=False))

    _boxplot(grupos_data,
             title="Precio de insumos agrícolas por tipo\n(fertilizante · agroquímico · semilla · combustible · mano de obra)",
             ylabel="Precio por unidad (pesos colombianos)",
             filename="anova_precio_tipo_insumo.png",
             p_valor=p,
             fmt="cop",
             log_scale=True)

    results.append(AnovaResult(
        nombre="Precio insumos vs Tipo",
        variable="precio_cop_unidad",
        factor="tipo_insumo",
        grupos=list(grupos_data.keys()),
        n_por_grupo=n_por_grupo,
        levene_p=lev_p,
        f_stat=f,
        p_valor=p,
        significativa=sig,
        tukey_df=tukey_df,
        nota="Excluye tipo='indice'. Solo grupos con n>=10.",
    ))


# ─────────────────────────────────────────────────────────────────────
#  PRUEBA 3 — Precipitación vs Trimestre (estacionalidad Colombia)
# ─────────────────────────────────────────────────────────────────────

def prueba3_precipitacion_trimestre(verbose: bool = False):
    print("\n" + "═" * 60)
    print("  PRUEBA 3 — Precipitación mensual vs Trimestre")
    print("═" * 60)

    clima = pd.read_parquet(DATA_PROCESSED / "clima_mensual.parquet")
    df = clima.dropna(subset=["precipitacion_mm", "mes"])
    df = df[df["precipitacion_mm"] >= 0]

    def asignar_trimestre(m):
        if m in [1, 2, 3]:
            return "Q1 (Ene-Mar)"
        if m in [4, 5, 6]:
            return "Q2 (Abr-Jun)"
        if m in [7, 8, 9]:
            return "Q3 (Jul-Sep)"
        return "Q4 (Oct-Dic)"

    df["trimestre"] = df["mes"].apply(asignar_trimestre)

    orden = ["Q1 (Ene-Mar)", "Q2 (Abr-Jun)", "Q3 (Jul-Sep)", "Q4 (Oct-Dic)"]
    grupos_data: dict[str, np.ndarray] = {}
    for q in orden:
        sub = df[df["trimestre"] == q]["precipitacion_mm"].values
        if len(sub) >= 3:
            grupos_data[q] = sub

    if len(grupos_data) < 2:
        print("  [SKIP] Datos insuficientes para ANOVA.")
        return

    n_por_grupo = {k: len(v) for k, v in grupos_data.items()}
    print(f"  Registros por grupo: {n_por_grupo}")

    lev_p, f, p = _run_anova(grupos_data)
    sig = p < 0.05

    print(f"  Levene p = {lev_p:.4f}  ({'varianzas heterogéneas' if lev_p < 0.05 else 'varianzas OK'})")
    print(f"  ANOVA   F = {f:.3f},  p = {p:.6f}  {_sig_label(p)}")
    print(f"  Conclusión: {'Estacionalidad SIGNIFICATIVA en precipitación' if sig else 'Sin variación estacional significativa'}")

    tukey_df = None
    if sig and verbose:
        tukey_df = _tukey(list(grupos_data.values()), list(grupos_data.keys()))
        print("\n  Post-hoc Tukey HSD:")
        print(tukey_df.to_string(index=False))

    _boxplot(grupos_data,
             title="Precipitación mensual por trimestre\n(Estacionalidad bimodal de Colombia)",
             ylabel="Precipitación mensual (mm)",
             filename="anova_precipitacion_trimestre.png",
             p_valor=p,
             fmt="mm",
             clip_pct=95)

    results.append(AnovaResult(
        nombre="Precipitación vs Trimestre",
        variable="precipitacion_mm",
        factor="trimestre",
        grupos=list(grupos_data.keys()),
        n_por_grupo=n_por_grupo,
        levene_p=lev_p,
        f_stat=f,
        p_valor=p,
        significativa=sig,
        tukey_df=tukey_df,
        nota="Trimestres del calendario civil. Captura bimodalidad lluvias Colombia.",
    ))


# ─────────────────────────────────────────────────────────────────────
#  PRUEBA 4 — Precipitación diaria NASA POWER por municipio (otra fuente)
# ─────────────────────────────────────────────────────────────────────

def prueba4_precipitacion_nasa_municipios(verbose: bool = False):
    print("\n" + "═" * 60)
    print("  PRUEBA 4 — Precipitación diaria NASA POWER por municipio")
    print("  (Ibagué / Pasto / Villavicencio — 2024)")
    print("═" * 60)

    nasa_path = Path(__file__).resolve().parent.parent / "data" / "raw" / "nasa_power" / "clima_diario.parquet"
    if not nasa_path.exists():
        print("  [SKIP] No se encontró data/raw/nasa_power/clima_diario.parquet")
        return

    df = pd.read_parquet(nasa_path)
    df = df.dropna(subset=["precipitacion_mm", "nombre_municipio"])
    df = df[df["precipitacion_mm"] >= 0]

    municipios = ["Ibagué", "Pasto", "Villavicencio"]
    grupos_data: dict[str, np.ndarray] = {}
    for muni in municipios:
        sub = df[df["nombre_municipio"] == muni]["precipitacion_mm"].values
        if len(sub) >= 3:
            grupos_data[muni] = sub

    if len(grupos_data) < 2:
        print("  [SKIP] Datos insuficientes para ANOVA.")
        return

    n_por_grupo = {k: len(v) for k, v in grupos_data.items()}
    print(f"  Registros por grupo: {n_por_grupo}")
    print(f"  Fuente: NASA POWER reanalysis MERRA-2 (precipitación diaria mm)")

    lev_p, f, p = _run_anova(grupos_data)
    sig = p < 0.05

    print(f"  Levene p = {lev_p:.4f}  ({'varianzas heterogéneas' if lev_p < 0.05 else 'varianzas OK'})")
    print(f"  ANOVA   F = {f:.3f},  p = {p:.6f}  {_sig_label(p)}")
    print(f"  Conclusión: {'Diferencias SIGNIFICATIVAS entre municipios (NASA POWER)' if sig else 'Sin diferencias significativas'}")

    tukey_df = None
    if sig and verbose:
        tukey_df = _tukey(list(grupos_data.values()), list(grupos_data.keys()))
        print("\n  Post-hoc Tukey HSD:")
        print(tukey_df.to_string(index=False))

    _boxplot(grupos_data,
             title="Precipitación diaria por municipio — NASA POWER 2024\n(Reanálisis satelital MERRA-2)",
             ylabel="Precipitación diaria (mm/día)",
             filename="anova_precipitacion_nasa_municipios.png",
             p_valor=p,
             fmt="mm_dia",
             clip_pct=98)

    results.append(AnovaResult(
        nombre="Precip. diaria NASA POWER por municipio",
        variable="precipitacion_mm",
        factor="municipio (NASA POWER)",
        grupos=list(grupos_data.keys()),
        n_por_grupo=n_por_grupo,
        levene_p=lev_p,
        f_stat=f,
        p_valor=p,
        significativa=sig,
        tukey_df=tukey_df,
        nota="Fuente externa: NASA POWER reanalysis MERRA-2. Contrasta con pruebas 1-3 basadas en IDEAM.",
    ))


# ─────────────────────────────────────────────────────────────────────
#  Resumen final
# ─────────────────────────────────────────────────────────────────────

def print_summary():
    print("\n" + "=" * 80)
    print("   RESUMEN — Pruebas ANOVA  |  AgroIA Colombia")
    print("=" * 80)

    rows = []
    for r in results:
        n_total = sum(r.n_por_grupo.values())
        rows.append({
            "Prueba":        r.nombre,
            "Variable":      r.variable,
            "Factor":        r.factor,
            "Grupos":        len(r.grupos),
            "N total":       n_total,
            "Levene p":      f"{r.levene_p:.4f}",
            "F":             f"{r.f_stat:.3f}",
            "p-valor":       f"{r.p_valor:.6f}",
            "Sig.":          _sig_label(r.p_valor),
            "Conclusión":    "SIGNIFICATIVA" if r.significativa else "No significativa",
        })

    df = pd.DataFrame(rows)

    col_widths = {c: max(len(c), df[c].astype(str).str.len().max()) for c in df.columns}
    header = "  ".join(c.ljust(col_widths[c]) for c in df.columns)
    sep    = "  ".join("-" * col_widths[c] for c in df.columns)
    print(header)
    print(sep)
    for _, row in df.iterrows():
        print("  ".join(str(row[c]).ljust(col_widths[c]) for c in df.columns))

    out_csv = REPORT_DIR / "anova_resumen.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\nTabla guardada en: {out_csv}")
    print("=" * 80)


# ─────────────────────────────────────────────────────────────────────
#  Entrypoint
# ─────────────────────────────────────────────────────────────────────

def run_all(verbose: bool = False):
    pruebas = [prueba1_precipitacion_enso, prueba2_precio_tipo_insumo, prueba3_precipitacion_trimestre, prueba4_precipitacion_nasa_municipios]
    for fn in pruebas:
        try:
            fn(verbose=verbose)
        except Exception as e:
            print(f"  [ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pruebas ANOVA — AgroIA Colombia")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Mostrar tablas Tukey HSD post-hoc")
    args = parser.parse_args()
    run_all(verbose=args.verbose)
