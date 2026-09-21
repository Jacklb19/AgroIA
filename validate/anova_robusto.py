"""
anova_robusto.py — Comparación de grupos con supuestos realistas (funciones puras, sin gráficos).

Por qué existe: las pruebas ANOVA originales comparaban miles de lecturas estación-mes como si fueran
observaciones independientes (no lo son: las estaciones de un mismo mes comparten el clima), usaban el
ANOVA clásico aunque Levene mostraba varianzas muy distintas, y con miles de datos cualquier diferencia
minúscula sale "significativa". Aquí:
  - se agrega a UNIDADES INDEPENDIENTES antes de comparar (p. ej. un valor por mes calendario);
  - se usa el ANOVA de Welch (no exige varianzas iguales) y Kruskal-Wallis (no exige normalidad);
  - se reporta el TAMAÑO DE EFECTO (eta²), que dice cuánto pesa la diferencia, no solo si existe;
  - el post-hoc es Mann-Whitney por pares con corrección de Holm (el Tukey clásico exige varianzas iguales).
"""
import itertools

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.oneway import anova_oneway

MIN_POR_GRUPO = 3


def agregar_unidades_independientes(df: pd.DataFrame, valor: str, claves: list[str]) -> pd.DataFrame:
    """Promedia `valor` dentro de cada combinación de `claves` (p. ej. anio, mes, fase): una fila por unidad independiente."""
    return df.dropna(subset=[valor]).groupby(claves, as_index=False)[valor].mean()


def comparar_grupos(grupos: dict[str, np.ndarray]) -> dict:
    """
    grupos: {nombre: valores}. Retorna Levene (mediana), ANOVA de Welch, Kruskal-Wallis y tamaños de efecto.
    Lanza ValueError si hay menos de 2 grupos con al menos MIN_POR_GRUPO datos.
    """
    validos = {k: np.asarray(v, float) for k, v in grupos.items() if len(v) >= MIN_POR_GRUPO}
    if len(validos) < 2:
        raise ValueError("Se necesitan al menos 2 grupos con datos suficientes")
    arrays = list(validos.values())
    todos = np.concatenate(arrays)
    n = len(todos)

    welch = anova_oneway(arrays, use_var="unequal", welch_correction=True)
    kw_h, kw_p = stats.kruskal(*arrays)
    _, lev_p = stats.levene(*arrays, center="median")

    ss_total = float(((todos - todos.mean()) ** 2).sum())
    ss_entre = float(sum(len(a) * (a.mean() - todos.mean()) ** 2 for a in arrays))
    return {
        "grupos": list(validos),
        "n_por_grupo": {k: int(len(v)) for k, v in validos.items()},
        "n_total": int(n),
        "levene_p": float(lev_p),
        "welch_f": float(welch.statistic),
        "welch_p": float(welch.pvalue),
        "kruskal_h": float(kw_h),
        "kruskal_p": float(kw_p),
        "eta2": ss_entre / ss_total if ss_total > 0 else float("nan"),                 # fracción de varianza explicada
        "epsilon2_kw": float(kw_h * (n + 1) / (n ** 2 - 1)),                            # tamaño de efecto de Kruskal-Wallis
    }


def etiqueta_efecto(eta2: float) -> str:
    """Interpretación convencional de eta²: <0,01 insignificante, <0,06 pequeño, <0,14 mediano, ≥0,14 grande."""
    if not np.isfinite(eta2):
        return "n/d"
    return "insignificante" if eta2 < 0.01 else "pequeño" if eta2 < 0.06 else "mediano" if eta2 < 0.14 else "grande"


def posthoc_holm(grupos: dict[str, np.ndarray]) -> pd.DataFrame:
    """Mann-Whitney U por pares con corrección de Holm. Columnas: grupo1, grupo2, p_ajustado, significativo."""
    validos = {k: np.asarray(v, float) for k, v in grupos.items() if len(v) >= MIN_POR_GRUPO}
    pares = list(itertools.combinations(validos, 2))
    if not pares:
        return pd.DataFrame(columns=["grupo1", "grupo2", "p_ajustado", "significativo"])
    p = [stats.mannwhitneyu(validos[a], validos[b], alternative="two-sided").pvalue for a, b in pares]
    rechaza, p_aj, _, _ = multipletests(p, alpha=0.05, method="holm")
    return pd.DataFrame({
        "grupo1": [a for a, _ in pares], "grupo2": [b for _, b in pares],
        "p_ajustado": p_aj, "significativo": rechaza,
    })
