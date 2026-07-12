import pool from "@/lib/db";

const FUENTES = [
  { id: "uejq-wxrr", titulo: "Producción Agrícola Municipal A04/A05", entidad: "MinAgricultura", uri: "https://www.datos.gov.co/resource/uejq-wxrr.json", tabla: "fact_produccion_agricola", estrategico: true },
  { id: "y5zy-x4ky", titulo: "Precios de Insumos Agrícolas (IPIA)",   entidad: "DANE / UPRA",     uri: "https://www.datos.gov.co/resource/y5zy-x4ky.json", tabla: "fact_precios_insumos",   estrategico: true },
  { id: "hp9r-jxuu", titulo: "Catálogo Estaciones IDEAM",              entidad: "IDEAM",           uri: "https://www.datos.gov.co/resource/hp9r-jxuu.json", tabla: "dim_estacion_ideam",     estrategico: true },
  { id: "s54a-sgyg", titulo: "Precipitación IDEAM (cada 10 min)",      entidad: "IDEAM",           uri: "https://www.datos.gov.co/resource/s54a-sgyg.json", tabla: "fact_clima_mensual",     estrategico: true },
  { id: "57sv-p2fu", titulo: "Variables climáticas combinadas IDEAM",   entidad: "IDEAM",           uri: "https://www.datos.gov.co/resource/57sv-p2fu.json", tabla: "fact_clima_mensual",     estrategico: true },
  { id: "gdxc-w37w", titulo: "DIVIPOLA — Codificación municipal",      entidad: "DANE",            uri: "https://www.datos.gov.co/resource/gdxc-w37w.json", tabla: "dim_municipio",           estrategico: false },
  { id: "SIPRA",      titulo: "Aptitud de suelo agrícola SIPRA",         entidad: "UPRA",            uri: "https://sipra.upra.gov.co/geoserver/ows",         tabla: "fact_aptitud_suelo",     estrategico: true },
  { id: "SIPSA",      titulo: "Precios mayoristas (microdatos SIPSA)",   entidad: "DANE",            uri: "https://microdatos.dane.gov.co/index.php/catalog/776", tabla: "fact_precios_mayoristas", estrategico: true },
  { id: "ENSO-NOAA",  titulo: "Índice ENSO (El Niño / La Niña)",         entidad: "NOAA",            uri: "https://www.cpc.ncep.noaa.gov/",                  tabla: "fact_alerta_enso",        estrategico: false },
  { id: "ckwx-9gr5",   titulo: "Tierras formalizadas ANT",          entidad: "ANT",         uri: "https://www.datos.gov.co/resource/ckwx-9gr5.json", tabla: "fact_tierras_ant",        estrategico: true },
  { id: "8e8j-2x86",   titulo: "Crédito agropecuario Finagro",      entidad: "Finagro",     uri: "https://www.datos.gov.co/resource/8e8j-2x86.json", tabla: "fact_credito_finagro",    estrategico: true },
  { id: "NASA-POWER",  titulo: "Clima diario MERRA-2",               entidad: "NASA",        uri: "https://power.larc.nasa.gov/api/temporal/daily/point", tabla: "fact_clima_diario_nasa", estrategico: false },
  { id: "WB-OPENDATA", titulo: "Indicadores macro-agrícolas Colombia", entidad: "World Bank", uri: "https://api.worldbank.org/v2/country/COL/indicator", tabla: "fact_indicadores_wb",      estrategico: false },
  { id: "FAOSTAT-QCL", titulo: "Producción agrícola FAO Colombia",   entidad: "FAO/ONU",     uri: "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL", tabla: "fact_produccion_fao",   estrategico: false },
];

async function safeCount(query) {
  try {
    const { rows } = await pool.query(query);
    return Number(rows[0].n) || 0;
  } catch {
    return null;
  }
}

export async function GET() {
  const counts = await Promise.all([
    safeCount("SELECT COUNT(*)::int AS n FROM fact_produccion_agricola"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_precios_insumos"),
    safeCount("SELECT COUNT(*)::int AS n FROM dim_estacion_ideam"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_clima_mensual"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_clima_mensual"),
    safeCount("SELECT COUNT(*)::int AS n FROM dim_municipio"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_aptitud_suelo"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_precios_mayoristas"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_alerta_enso"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_tierras_ant"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_credito_finagro"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_clima_diario_nasa"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_indicadores_wb"),
    safeCount("SELECT COUNT(*)::int AS n FROM fact_produccion_fao"),
  ]);

  return Response.json(FUENTES.map((f, i) => ({ ...f, filas: counts[i] })));
}
