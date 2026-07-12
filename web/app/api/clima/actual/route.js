import pool from "@/lib/db";

const OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast";

/* Cache simple en memoria del proceso (15 min). */
const CACHE = new Map();
const TTL_MS = 15 * 60 * 1000;

async function coordsMunicipio(nombre) {
  const { rows } = await pool.query(
    `SELECT latitud_centroide  AS lat,
            longitud_centroide AS lon,
            nombre_municipio,
            nombre_departamento
     FROM dim_municipio
     WHERE nombre_municipio ILIKE $1
       AND latitud_centroide IS NOT NULL
     LIMIT 1`,
    [`%${nombre}%`],
  );
  if (rows.length === 0) return null;
  return {
    lat:  parseFloat(rows[0].lat),
    lon:  parseFloat(rows[0].lon),
    municipio:    rows[0].nombre_municipio,
    departamento: rows[0].nombre_departamento,
  };
}

export async function GET(request) {
  const url       = new URL(request.url);
  const muni      = url.searchParams.get("municipio") || "Bogotá";
  const cacheKey  = muni.toLowerCase().trim();
  const cached    = CACHE.get(cacheKey);
  if (cached && (Date.now() - cached.ts) < TTL_MS) {
    return Response.json({ ...cached.data, cached: true });
  }

  try {
    const coords = await coordsMunicipio(muni);
    if (!coords) {
      return Response.json({ error: "Municipio no encontrado en dim_municipio" }, { status: 404 });
    }

    const params = new URLSearchParams({
      latitude:        String(coords.lat),
      longitude:       String(coords.lon),
      current:         "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,is_day",
      daily:           "temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration",
      timezone:        "America/Bogota",
      forecast_days:   "3",
    });
    const res = await fetch(`${OPENMETEO_URL}?${params}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`Open-Meteo HTTP ${res.status}`);
    const om = await res.json();

    const data = {
      municipio:    coords.municipio,
      departamento: coords.departamento,
      coords:       { lat: coords.lat, lon: coords.lon },
      actual: {
        temperatura_c:    om.current?.temperature_2m,
        humedad_pct:      om.current?.relative_humidity_2m,
        precipitacion_mm: om.current?.precipitation,
        viento_kmh:       om.current?.wind_speed_10m,
        es_de_dia:        om.current?.is_day === 1,
        timestamp:        om.current?.time,
      },
      pronostico_3d: (om.daily?.time || []).map((fecha, i) => ({
        fecha,
        temp_max_c:        om.daily.temperature_2m_max?.[i],
        temp_min_c:        om.daily.temperature_2m_min?.[i],
        lluvia_mm:         om.daily.precipitation_sum?.[i],
        sol_horas:         om.daily.sunshine_duration?.[i] != null
          ? +(om.daily.sunshine_duration[i] / 3600).toFixed(1)
          : null,
      })),
      fuente: "Open-Meteo Forecast API",
      actualizado_at: new Date().toISOString(),
    };

    CACHE.set(cacheKey, { data, ts: Date.now() });
    return Response.json(data);
  } catch (err) {
    console.error("[clima/actual]", err.message);
    return Response.json({ error: err.message }, { status: 500 });
  }
}
