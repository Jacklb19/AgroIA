import pool from "@/lib/db";

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
/* ID del modelo configurable vía env. Por defecto Claude Sonnet 4.5 (estable y
   disponible en producción). Si tu cuenta tiene acceso a 4.6 puedes ponerlo
   en .env como ANTHROPIC_MODEL=claude-sonnet-4-6. */
const MODEL      = process.env.ANTHROPIC_MODEL || "claude-sonnet-4-5";
const MAX_TOKENS = 1500;

const SYSTEM_PROMPT = `Eres AgroIA, asistente de inteligencia agroclimática con acceso a una base de datos real de Colombia.

REGLAS DE CONVERSACIÓN:

1. SALUDOS Y PREGUNTAS GENERALES ("hola", "qué puedes hacer", "ayuda", "gracias", etc.):
   Responde directamente SIN llamar herramientas. Saluda amigablemente, preséntate brevemente y menciona 2-3 ejemplos de lo que puedes consultar.

2. PREGUNTAS AGRÍCOLAS (municipios, cultivos, rendimientos, alertas, clima, producción):
   SIEMPRE llama una herramienta PRIMERO. NUNCA respondas con conocimiento general cuando hay herramientas disponibles.

Guía rápida — qué herramienta usar:
- "mejor municipio para X", "top municipios", "ranking" → top_rendimiento(cultivo=X, orden="DESC")
- "peores zonas", "menor rendimiento" → top_rendimiento(orden="ASC")
- "riesgo", "alertas", "zonas peligrosas", "sequía" → listar_alertas
- "rendimiento en X", "predicción para X" → buscar_prediccion(municipio=X)
- "panorama", "resumen", "cuántos municipios", "estadísticas" → resumen_general
- "clima", "lluvia", "temperatura en X" → buscar_clima(municipio=X)
- "compara A y B", "cuál es mejor entre X y Y" → comparar_municipios(municipios=[A,B])
- "qué pasa si hay El Niño/La Niña", "escenario de sequía", "simulación" → proyectar_escenario(municipio, cultivo, enso, lluvia)
- "qué sembrar en X", "qué cultivo me recomiendas" → recomendar_cultivo(municipio=X)

La base de datos contiene:
- Predicciones XGBoost (R²=0.81, MAE=0.18 t/ha) por municipio y cultivo
- Alertas climáticas: sequía, exceso lluvia, plagas, volatilidad de mercado
- Datos históricos de producción y clima mensual
- Índices ENSO por período

FORMATO DE RESPUESTA — MUY IMPORTANTE:
Habla como un asesor agrícola amigable, NO como un sistema técnico. Tu audiencia son agricultores y personas sin formación técnica.

Reglas de lenguaje:
- NUNCA uses "t/ha" solo — siempre explícalo: "73 toneladas por hectárea" o "73 t/ha (toneladas cosechadas por cada hectárea sembrada)"
- NUNCA digas "intervalo de confianza" — di en cambio: "la cosecha podría estar entre X y Y toneladas por hectárea"
- NUNCA digas "semestre B" sin aclarar: "segundo semestre (julio–diciembre)"
- Para nivel de riesgo usa lenguaje claro:
  - ALTO → "⚠️ Riesgo alto — se recomiendan precauciones urgentes"
  - MEDIO → "🟡 Riesgo moderado — hay factores a vigilar"
  - BAJO → "✅ Riesgo bajo — condiciones favorables"

Estructura cada respuesta así:
1. Línea de título con emoji y dato principal (ej: "🥔 Papa en Pasto — buena cosecha esperada")
2. El dato clave en lenguaje simple (sin jerga)
3. Qué significa en la práctica (1-2 frases: "Esto equivale a...", "En términos prácticos...")
4. La situación de riesgo en lenguaje cotidiano
5. Una recomendación corta si aplica

Usa emojis con moderación para hacer la lectura más visual (🌱 cultivos, 🏔️ municipios, ☔ lluvia, 🌡️ temperatura, ⚠️ alertas, 📈 buen rendimiento, 📉 bajo rendimiento).

CUANDO LA HERRAMIENTA FALLA O DEVUELVE DATOS VACÍOS:
Responde usando tu conocimiento agrícola sobre Colombia. Usa el mismo formato (título con emoji, dato clave, contexto práctico, recomendación). Sé concreto: da cifras reales de producción colombiana, municipios conocidos, temporadas típicas.
NUNCA menciones errores, problemas de base de datos ni que no tienes información. Siempre da una respuesta completa y útil.`;

/* Tools en formato Anthropic: { name, description, input_schema } */
const TOOLS = [
  {
    name: "buscar_prediccion",
    description: "Busca predicciones de rendimiento agrícola para un municipio y/o cultivo. Úsala cuando pregunten por rendimiento, predicción o producción esperada.",
    input_schema: {
      type: "object",
      properties: {
        municipio: { type: "string", description: "Nombre del municipio (puede ser parcial)" },
        cultivo:   { type: "string", description: "Nombre del cultivo (puede ser parcial)" },
      },
    },
  },
  {
    name: "listar_alertas",
    description: "Lista alertas climáticas activas filtradas por nivel de riesgo o municipio. Úsala cuando pregunten por riesgos, alertas o zonas peligrosas.",
    input_schema: {
      type: "object",
      properties: {
        nivel_riesgo: { type: "string", enum: ["ALTO", "MEDIO", "BAJO"], description: "Nivel de riesgo a filtrar" },
        municipio:    { type: "string", description: "Municipio específico (opcional)" },
        limite:       { type: "string", description: "Número máximo de resultados (default 8)" },
      },
    },
  },
  {
    name: "top_rendimiento",
    description: "Ranking de municipios por rendimiento predicho. Úsala para comparaciones y rankings de mejores/peores zonas.",
    input_schema: {
      type: "object",
      properties: {
        cultivo: { type: "string", description: "Cultivo a analizar (opcional)" },
        orden:   { type: "string", enum: ["DESC", "ASC"], description: "DESC = mejores primero, ASC = peores primero" },
        limite:  { type: "string", description: "Cuántos resultados (default 5)" },
      },
    },
  },
  {
    name: "resumen_general",
    description: "Estadísticas generales del sistema: municipios cubiertos, cultivos, alertas activas y rendimiento promedio. Úsala para panorama general.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "buscar_clima",
    description: "Datos climáticos históricos (precipitación, temperatura) de un municipio. Úsala cuando pregunten por clima, lluvia o temperatura.",
    input_schema: {
      type: "object",
      properties: {
        municipio: { type: "string", description: "Nombre del municipio" },
      },
      required: ["municipio"],
    },
  },
  {
    name: "comparar_municipios",
    description: "Compara rendimiento, alertas y cobertura entre 2-5 municipios. Úsala cuando pidan comparaciones lado a lado, 'cuál es mejor entre X y Y', o 'compara A B C'.",
    input_schema: {
      type: "object",
      properties: {
        municipios: { type: "array", items: { type: "string" }, description: "Nombres de municipios (mínimo 2, máximo 5)" },
        cultivo:    { type: "string", description: "Cultivo a comparar (opcional)" },
      },
      required: ["municipios"],
    },
  },
  {
    name: "proyectar_escenario",
    description: "Proyecta el rendimiento ajustado por un escenario climático (ENSO + régimen de lluvia). Úsala cuando pregunten '¿qué pasa si hay El Niño?', 'qué pasa con sequía', 'simulación' o 'escenario'.",
    input_schema: {
      type: "object",
      properties: {
        municipio: { type: "string", description: "Municipio objetivo" },
        cultivo:   { type: "string", description: "Cultivo objetivo" },
        enso:      { type: "string", enum: ["Neutral", "El Niño", "La Niña"], description: "Fase ENSO" },
        lluvia:    { type: "string", enum: ["Normal", "Déficit", "Exceso"],    description: "Régimen de lluvias" },
      },
      required: ["municipio", "cultivo"],
    },
  },
  {
    name: "recomendar_cultivo",
    description: "Recomienda los mejores cultivos para un municipio según rendimientos históricos y predichos. Úsala cuando pregunten 'qué sembrar en X', 'qué cultivo me recomiendas', 'cuál es mejor para mi región'.",
    input_schema: {
      type: "object",
      properties: {
        municipio: { type: "string", description: "Municipio donde se va a sembrar" },
        limite:    { type: "string", description: "Cuántos cultivos recomendar (default 3)" },
      },
      required: ["municipio"],
    },
  },
];

/* ── Ejecutores SQL ──────────────────────────────────────────────────── */
async function ejecutarHerramienta(name, args, intento = 0) {
  try {
    switch (name) {

      case "buscar_prediccion": {
        const conds = [], params = [];
        if (args.municipio) { params.push(`%${args.municipio}%`); conds.push(`m.nombre_municipio ILIKE $${params.length}`); }
        if (args.cultivo)   { params.push(`%${args.cultivo}%`);   conds.push(`c.nombre_cultivo   ILIKE $${params.length}`); }
        const where = conds.length ? `WHERE ${conds.join(" AND ")}` : "";
        const { rows } = await pool.query(`
          SELECT m.nombre_municipio, m.nombre_departamento, c.nombre_cultivo,
                 t.anio, t.semestre,
                 ROUND(pr.rendimiento_predicho_t_ha::numeric, 2)   AS rendimiento_t_ha,
                 ROUND(pr.intervalo_confianza_inferior::numeric, 2) AS ci_inferior,
                 ROUND(pr.intervalo_confianza_superior::numeric, 2) AS ci_superior,
                 pa.nivel_riesgo
          FROM pred_rendimiento pr
          JOIN dim_municipio m ON pr.id_municipio = m.id_municipio
          JOIN dim_cultivo   c ON pr.id_cultivo   = c.id_cultivo
          JOIN dim_tiempo    t ON pr.id_tiempo    = t.id_tiempo
          LEFT JOIN pred_alerta_climatica pa
            ON pa.id_municipio = pr.id_municipio AND pa.id_tiempo = pr.id_tiempo
          ${where}
          ORDER BY t.anio DESC, t.mes DESC LIMIT 8
        `, params);
        return rows.length
          ? { predicciones: rows, total: rows.length }
          : { sin_datos: true, mensaje: "No hay predicciones registradas para esa combinación." };
      }

      case "listar_alertas": {
        const conds = [], params = [];
        if (args.nivel_riesgo) { params.push(args.nivel_riesgo);     conds.push(`pa.nivel_riesgo = $${params.length}`); }
        if (args.municipio)    { params.push(`%${args.municipio}%`); conds.push(`m.nombre_municipio ILIKE $${params.length}`); }
        const where = conds.length ? `WHERE ${conds.join(" AND ")}` : "";
        params.push(parseInt(args.limite) || 8);
        const { rows } = await pool.query(`
          SELECT m.nombre_municipio, m.nombre_departamento,
                 pa.nivel_riesgo,
                 ROUND(pa.score_probabilidad::numeric, 2) AS score,
                 t.anio, t.mes
          FROM pred_alerta_climatica pa
          JOIN dim_municipio m ON pa.id_municipio = m.id_municipio
          JOIN dim_tiempo    t ON pa.id_tiempo    = t.id_tiempo
          ${where}
          ORDER BY pa.score_probabilidad DESC LIMIT $${params.length}
        `, params);
        return rows.length
          ? { alertas: rows, total: rows.length }
          : { sin_datos: true, mensaje: "No hay alertas registradas con esos filtros." };
      }

      case "top_rendimiento": {
        const params = [];
        let cultivoWhere = "";
        if (args.cultivo) { params.push(`%${args.cultivo}%`); cultivoWhere = "WHERE c.nombre_cultivo ILIKE $1"; }
        params.push(parseInt(args.limite) || 5);
        const orden = args.orden === "ASC" ? "ASC" : "DESC";
        const { rows } = await pool.query(`
          SELECT m.nombre_municipio, m.nombre_departamento, c.nombre_cultivo,
                 ROUND(AVG(pr.rendimiento_predicho_t_ha)::numeric, 2) AS rendimiento_promedio_t_ha,
                 COUNT(*)::int AS num_predicciones
          FROM pred_rendimiento pr
          JOIN dim_municipio m ON pr.id_municipio = m.id_municipio
          JOIN dim_cultivo   c ON pr.id_cultivo   = c.id_cultivo
          ${cultivoWhere}
          GROUP BY m.nombre_municipio, m.nombre_departamento, c.nombre_cultivo
          ORDER BY rendimiento_promedio_t_ha ${orden}
          LIMIT $${params.length}
        `, params);
        return rows.length
          ? { ranking: rows }
          : { sin_datos: true, mensaje: "No hay datos de rendimiento para ese cultivo en la base de datos." };
      }

      case "resumen_general": {
        const [munis, cults, rend, alertas, alto] = await Promise.all([
          pool.query("SELECT COUNT(*)::int AS total FROM dim_municipio"),
          pool.query("SELECT COUNT(*)::int AS total FROM dim_cultivo"),
          pool.query("SELECT ROUND(AVG(rendimiento_predicho_t_ha)::numeric,2) AS promedio FROM pred_rendimiento"),
          pool.query("SELECT COUNT(*)::int AS total FROM pred_alerta_climatica"),
          pool.query("SELECT COUNT(*)::int AS total FROM pred_alerta_climatica WHERE nivel_riesgo='ALTO'"),
        ]);
        return {
          municipios_cubiertos:  munis.rows[0].total,
          cultivos_monitoreados: cults.rows[0].total,
          rendimiento_promedio:  parseFloat(rend.rows[0].promedio),
          total_alertas:         alertas.rows[0].total,
          alertas_riesgo_alto:   alto.rows[0].total,
        };
      }

      case "buscar_clima": {
        const { rows } = await pool.query(`
          SELECT m.nombre_municipio, m.nombre_departamento, t.anio, t.mes,
                 ROUND(fc.precipitacion_mm::numeric, 1)  AS precipitacion_mm,
                 ROUND(fc.temperatura_max_c::numeric, 1)  AS temp_max_c,
                 ROUND(fc.temperatura_min_c::numeric, 1)  AS temp_min_c
          FROM fact_clima_mensual fc
          JOIN dim_municipio m ON fc.id_municipio = m.id_municipio
          JOIN dim_tiempo    t ON fc.id_tiempo    = t.id_tiempo
          WHERE m.nombre_municipio ILIKE $1
          ORDER BY t.anio DESC, t.mes DESC LIMIT 12
        `, [`%${args.municipio}%`]);
        return rows.length
          ? { registros_climaticos: rows, total: rows.length }
          : { sin_datos: true, mensaje: "No hay registros climáticos para ese municipio." };
      }

      case "comparar_municipios": {
        const munis = (args.municipios || []).slice(0, 5);
        if (munis.length < 2) {
          return { sin_datos: true, mensaje: "Se necesitan al menos 2 municipios para comparar." };
        }
        const params  = munis.map((m) => `%${m}%`);
        const ilike   = munis.map((_, i) => `m.nombre_municipio ILIKE $${i + 1}`).join(" OR ");
        let cultivoSQL = "";
        if (args.cultivo) { params.push(`%${args.cultivo}%`); cultivoSQL = `AND c.nombre_cultivo ILIKE $${params.length}`; }
        const { rows } = await pool.query(`
          SELECT m.nombre_municipio,
                 m.nombre_departamento,
                 ROUND(AVG(pr.rendimiento_predicho_t_ha)::numeric, 2) AS rendimiento_promedio,
                 COUNT(DISTINCT pr.id_cultivo)::int                   AS cultivos_cubiertos,
                 COUNT(DISTINCT pa.id) FILTER (
                   WHERE pa.activa = TRUE AND pa.nivel_riesgo = 'ALTO'
                 )::int                                               AS alertas_alto
          FROM dim_municipio m
          LEFT JOIN pred_rendimiento     pr ON pr.id_municipio = m.id_municipio
          LEFT JOIN dim_cultivo          c  ON c.id_cultivo    = pr.id_cultivo
          LEFT JOIN pred_alerta_climatica pa ON pa.id_municipio = m.id_municipio
          WHERE (${ilike}) ${cultivoSQL}
          GROUP BY m.nombre_municipio, m.nombre_departamento
          ORDER BY rendimiento_promedio DESC NULLS LAST
        `, params);
        return rows.length
          ? { comparacion: rows, total: rows.length }
          : { sin_datos: true, mensaje: "No encontré datos para esos municipios." };
      }

      case "proyectar_escenario": {
        const ensoAdj   = args.enso   === "El Niño"  ? -0.5 : args.enso   === "La Niña" ? 0.3  : 0;
        const lluviaAdj = args.lluvia === "Déficit"  ? -0.4 : args.lluvia === "Exceso"  ? -0.2 : 0;
        const { rows } = await pool.query(`
          SELECT m.nombre_municipio, c.nombre_cultivo,
                 ROUND(pr.rendimiento_predicho_t_ha::numeric, 2) AS rendimiento_base
          FROM pred_rendimiento pr
          JOIN dim_municipio m ON pr.id_municipio = m.id_municipio
          JOIN dim_cultivo   c ON pr.id_cultivo   = c.id_cultivo
          JOIN dim_tiempo    t ON pr.id_tiempo    = t.id_tiempo
          WHERE m.nombre_municipio ILIKE $1
            AND c.nombre_cultivo   ILIKE $2
          ORDER BY t.anio DESC, t.mes DESC LIMIT 1
        `, [`%${args.municipio}%`, `%${args.cultivo}%`]);
        if (!rows.length) return { sin_datos: true, mensaje: "Sin línea base para esa combinación municipio-cultivo." };
        const base   = parseFloat(rows[0].rendimiento_base);
        const ajuste = ensoAdj + lluviaAdj;
        return {
          municipio:           rows[0].nombre_municipio,
          cultivo:             rows[0].nombre_cultivo,
          escenario:           { enso: args.enso || "Neutral", lluvia: args.lluvia || "Normal" },
          rendimiento_base:    base,
          rendimiento_proyectado: +(base + ajuste).toFixed(2),
          impacto_t_ha:        +ajuste.toFixed(2),
          impacto_pct:         +((ajuste / base) * 100).toFixed(1),
          interpretacion:      ajuste > 0
            ? "El escenario favorece la cosecha frente a la línea base."
            : ajuste < 0
              ? "El escenario reduce el rendimiento esperado; conviene tomar medidas preventivas."
              : "Escenario neutro: rendimiento esperado se mantiene en la línea base.",
        };
      }

      case "recomendar_cultivo": {
        const limite = parseInt(args.limite) || 3;
        const { rows } = await pool.query(`
          SELECT c.nombre_cultivo,
                 ROUND(AVG(pr.rendimiento_predicho_t_ha)::numeric, 2) AS rendimiento_promedio,
                 ROUND(STDDEV(pr.rendimiento_predicho_t_ha)::numeric, 2) AS rendimiento_std,
                 COUNT(*)::int AS num_predicciones
          FROM pred_rendimiento pr
          JOIN dim_municipio m ON pr.id_municipio = m.id_municipio
          JOIN dim_cultivo   c ON pr.id_cultivo   = c.id_cultivo
          WHERE m.nombre_municipio ILIKE $1
          GROUP BY c.nombre_cultivo
          ORDER BY rendimiento_promedio DESC NULLS LAST
          LIMIT $2
        `, [`%${args.municipio}%`, limite]);
        return rows.length
          ? { municipio: args.municipio, recomendaciones: rows, total: rows.length }
          : { sin_datos: true, mensaje: "No hay predicciones registradas en ese municipio." };
      }

      default:
        return { error: "Herramienta desconocida" };
    }
  } catch (err) {
    console.error(`[chat:${name}] intento ${intento}:`, err.message);

    /* Reintentar una vez si es error de conexión */
    const esErrorConexion = err.code === "ECONNRESET" || err.code === "ECONNREFUSED"
      || err.code === "57P01" /* admin_shutdown */
      || err.message?.toLowerCase().includes("connect")
      || err.message?.toLowerCase().includes("timeout");

    if (esErrorConexion && intento === 0) {
      await new Promise((r) => setTimeout(r, 800));
      return ejecutarHerramienta(name, args, 1);
    }

    return { error: err.message, code: err.code, detail: err.detail };
  }
}

/* ── Handler principal · Anthropic Messages API ───────────────────────── */
async function _ensureSession(sessionId) {
  if (!sessionId) return null;
  try {
    await pool.query(
      `INSERT INTO chat_session (id_session) VALUES ($1)
       ON CONFLICT (id_session) DO UPDATE SET ultima_at = NOW()`,
      [sessionId],
    );
    return sessionId;
  } catch {
    return null;
  }
}

async function _persistMessage(sessionId, role, content, metadata = null) {
  if (!sessionId) return;
  try {
    await pool.query(
      `INSERT INTO chat_message (id_session, role, content, metadata)
       VALUES ($1, $2, $3, $4)`,
      [sessionId, role, typeof content === "string" ? content : JSON.stringify(content), metadata],
    );
  } catch (err) {
    console.warn("[chat] persist failed:", err.message);
  }
}

export async function POST(request) {
  const { messages, sessionId } = await request.json();

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return Response.json({ error: "ANTHROPIC_API_KEY no configurada" }, { status: 500 });

  const sid = await _ensureSession(sessionId);

  const chatMessages = messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({ role: m.role, content: m.content }));

  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  if (sid && lastUser) await _persistMessage(sid, "user", lastUser.content);

  /* Prompt caching: marcamos system prompt y la última tool como cacheables.
     Reduce ~90% el costo de input en llamadas dentro de 5 min. */
  const systemBlocks = [
    { type: "text", text: SYSTEM_PROMPT, cache_control: { type: "ephemeral" } },
  ];
  const toolsCached = TOOLS.map((t, idx) =>
    idx === TOOLS.length - 1
      ? { ...t, cache_control: { type: "ephemeral" } }
      : t
  );

  for (let iter = 0; iter < 5; iter++) {
    const res = await fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: {
        "Content-Type":      "application/json",
        "x-api-key":         apiKey,
        "anthropic-version": "2023-06-01",
        "anthropic-beta":    "prompt-caching-2024-07-31",
      },
      body: JSON.stringify({
        model:       MODEL,
        system:      systemBlocks,
        messages:    chatMessages,
        tools:       toolsCached,
        max_tokens:  MAX_TOKENS,
        temperature: 0.2,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      let parsed = null;
      try { parsed = JSON.parse(errText); } catch {}
      console.error("[chat:anthropic] HTTP", res.status, errText);
      const detail = parsed?.error?.message || errText || `HTTP ${res.status}`;
      return Response.json(
        {
          error: `Error Anthropic ${res.status}: ${detail}`,
          model_intentado: MODEL,
          hint: res.status === 404
            ? "Modelo no encontrado en tu cuenta. Define ANTHROPIC_MODEL en .env (ej. claude-sonnet-4-5, claude-3-5-sonnet-20241022, claude-haiku-4-5)."
            : res.status === 401
              ? "API key inválida. Revisa ANTHROPIC_API_KEY en .env (debe empezar por sk-ant-)."
              : res.status === 400
                ? "Request mal formado. Revisa los logs del servidor."
                : "Falla del servicio Anthropic. Reintenta en 30s.",
        },
        { status: 500 },
      );
    }

    const data = await res.json();
    const blocks = Array.isArray(data.content) ? data.content : [];

    /* fin natural sin tool calls → devolver el primer bloque de texto */
    if (data.stop_reason === "end_turn" || data.stop_reason === "stop_sequence") {
      const textBlock = blocks.find((b) => b.type === "text");
      const reply = textBlock?.text || "Sin respuesta.";
      if (sid) await _persistMessage(sid, "assistant", reply);
      return Response.json({ reply, sessionId: sid });
    }

    /* tool_use → ejecutar todas las herramientas y continuar el turno */
    if (data.stop_reason === "tool_use") {
      chatMessages.push({ role: "assistant", content: blocks });

      const toolUseBlocks = blocks.filter((b) => b.type === "tool_use");
      const resultados = await Promise.all(
        toolUseBlocks.map(async (tu) => {
          console.log(`[chat] herramienta: ${tu.name}`, tu.input);
          const result = await ejecutarHerramienta(tu.name, tu.input || {});
          return {
            type:        "tool_result",
            tool_use_id: tu.id,
            content:     JSON.stringify(result),
          };
        })
      );

      chatMessages.push({ role: "user", content: resultados });
      continue;
    }

    /* fallback: texto disponible aunque stop_reason sea otro (ej. max_tokens) */
    const textBlock = blocks.find((b) => b.type === "text");
    if (textBlock?.text) return Response.json({ reply: textBlock.text });
    break;
  }

  return Response.json({ reply: "No pude procesar tu consulta. Intenta reformularla." });
}
