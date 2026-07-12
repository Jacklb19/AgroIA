import pool from "@/lib/db";

const FALLBACK = [
  { lat:  4.43, lon: -75.23, riesgo: "MEDIO" },
  { lat:  4.16, lon: -74.88, riesgo: "BAJO"  },
  { lat:  4.07, lon: -73.63, riesgo: "BAJO"  },
  { lat:  1.21, lon: -77.27, riesgo: "ALTO"  },
  { lat: 11.24, lon: -74.21, riesgo: "MEDIO" },
  { lat:  5.07, lon: -75.52, riesgo: "BAJO"  },
  { lat:  8.75, lon: -75.88, riesgo: "ALTO"  },
];

export async function GET() {
  try {
    const { rows } = await pool.query(`
      SELECT m.nombre_municipio,
             m.nombre_departamento,
             m.latitud_centroide  AS lat,
             m.longitud_centroide AS lon,
             COALESCE(
               (SELECT pa.nivel_riesgo
                FROM pred_alerta_climatica pa
                WHERE pa.id_municipio = m.id_municipio AND pa.activa = TRUE
                ORDER BY pa.score_probabilidad DESC LIMIT 1),
               'BAJO'
             ) AS riesgo
      FROM dim_municipio m
      WHERE m.latitud_centroide IS NOT NULL AND m.longitud_centroide IS NOT NULL
      ORDER BY random()
      LIMIT 80
    `);
    return Response.json(rows.map((r) => ({
      municipio:    r.nombre_municipio,
      departamento: r.nombre_departamento,
      lat:          parseFloat(r.lat),
      lon:          parseFloat(r.lon),
      riesgo:       r.riesgo,
    })));
  } catch (err) {
    console.error("[mapa] DB error:", err.message);
    return Response.json(FALLBACK);
  }
}
