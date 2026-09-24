-- 005 · fact_precios_insumos.unidad_medida quedó demasiado corta (VARCHAR(20)): el extractor
-- real de insumos DANE SIPSA-I (extract/extract_insumos.py) usa la descripción completa
-- "Precio promedio de mercado (COP)" (33 caracteres), que nunca se probó contra Postgres real
-- hasta la primera carga end-to-end (2026-09-23) y truncaba con StringDataRightTruncation.
-- Se amplía en vez de acortar el texto: es más informativo para quien consuma la tabla/vista.
ALTER TABLE fact_precios_insumos
    ALTER COLUMN unidad_medida TYPE VARCHAR(50);
