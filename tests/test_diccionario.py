"""El diccionario de datos se genera del esquema real y obliga a documentar cada tabla nueva."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import gen_data_dictionary as gdd  # noqa: E402


@pytest.mark.db
def test_todas_las_tablas_y_vistas_tienen_descripcion(engine_migrado):
    md = gdd.generar(engine_migrado)          # lanza DiccionarioError si falta alguna
    assert "### `fact_precio_diario`" in md and "### `v_precio_actual`" in md
    assert "autoincremental" in md


@pytest.mark.db
def test_una_tabla_nueva_sin_descripcion_hace_fallar_la_generacion(engine_migrado):
    with engine_migrado.begin() as conn:
        conn.execute(text("CREATE TABLE fact_sin_documentar (a int)"))
    with pytest.raises(gdd.DiccionarioError, match="fact_sin_documentar"):
        gdd.generar(engine_migrado)


@pytest.mark.db
def test_la_generacion_es_determinista(engine_migrado):
    assert gdd.generar(engine_migrado) == gdd.generar(engine_migrado)
