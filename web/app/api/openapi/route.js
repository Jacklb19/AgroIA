export const dynamic = "force-dynamic";

const SPEC = {
  openapi: "3.1.0",
  info: {
    title:       "AgroIA Colombia API",
    description: "API pública sobre datos abiertos colombianos para inteligencia agroclimática. Predicciones XGBoost con SHAP, alertas IsolationForest, asistente Claude con tool-use.",
    version:     "1.0.0",
    contact:     { name: "AgroIA Colombia · Hackathon" },
    license:     { name: "MIT" },
  },
  servers: [{ url: "/api", description: "Servidor actual" }],
  tags: [
    { name: "Predicción", description: "Endpoints de inferencia y explicabilidad" },
    { name: "Datos",      description: "Catálogo, mapa, dashboards" },
    { name: "Precios",    description: "Precios mayoristas diarios por mercado y departamento (DANE - SIPSA)" },
    { name: "Asistente",  description: "Chat conversacional con Claude" },
    { name: "Sistema",    description: "Salud y metadatos" },
  ],
  paths: {
    "/health": {
      get: {
        tags: ["Sistema"], summary: "Healthcheck (sin detalles internos)",
        responses: { "200": { description: "{ ok: true, latencia_ms }" }, "503": { description: "{ ok: false }" } },
      },
    },
    "/municipios": {
      get: {
        tags: ["Datos"], summary: "Lista de municipios disponibles",
        responses: { "200": { description: "Array de strings 'Municipio, Departamento'" } },
      },
    },
    "/cultivos": {
      get: {
        tags: ["Datos"], summary: "Lista de cultivos en dim_cultivo",
        responses: { "200": { description: "Array de strings" } },
      },
    },
    "/mapa": {
      get: {
        tags: ["Datos"], summary: "Hasta 120 municipios con alerta activa, coordenadas y nivel de riesgo",
        responses: { "200": { description: "Array de puntos { municipio, departamento, lat, lon, riesgo }" }, "503": { description: "Datos no disponibles" } },
      },
    },
    "/modelo/metricas": {
      get: {
        tags: ["Datos"], summary: "Métricas reales de los modelos activos (model_version)",
        responses: { "200": { description: "{ rendimiento, alerta, precios } (null si no hay modelo entrenado)" } },
      },
    },
    "/comparativo": {
      get: {
        tags: ["Predicción"], summary: "Comparativo regional: otros municipios del mismo departamento con predicción del mismo cultivo",
        parameters: [
          { name: "muni",    in: "query", required: true, schema: { type: "string" } },
          { name: "cultivo", in: "query", required: true, schema: { type: "string" } },
          { name: "anio",    in: "query", schema: { type: "integer" } },
        ],
        responses: { "200": { description: "{ vecinos[] }" } },
      },
    },
    "/catalogo": {
      get: {
        tags: ["Datos"], summary: "Catálogo de fuentes datos.gov.co integradas",
        responses: { "200": { description: "Array { id, titulo, entidad, uri, tabla, estrategico, filas }" } },
      },
    },
    "/dashboards": {
      get: {
        tags: ["Datos"], summary: "Datos agregados para dashboards (modo offline)",
        responses: { "200": { description: "Series, top municipios, alertas, anomalías" } },
      },
    },
    "/impacto": {
      get: {
        tags: ["Datos"], summary: "KPIs reales calculados sobre el star schema",
        responses: { "200": { description: "Cobertura, beneficiarios, alertas" } },
      },
    },
    "/clima/actual": {
      get: {
        tags: ["Datos"], summary: "Clima en vivo del municipio (Open-Meteo)",
        parameters: [{ name: "municipio", in: "query", required: true, schema: { type: "string" } }],
        responses: { "200": { description: "Actual + pronóstico 3 días" } },
      },
    },
    "/prediccion": {
      post: {
        tags: ["Predicción"], summary: "Predicción XGBoost con SHAP",
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  muni:     { type: "string" },
                  cultivo:  { type: "string" },
                  year:     { type: "string", description: "Año pedido; si no hay predicción se usa la más reciente ('anio' en la respuesta)" },
                  enso:     { type: "string", enum: ["Neutral", "El Niño", "La Niña"], description: "Ajuste por regla orientativa, no del modelo" },
                  lluvia:   { type: "string", enum: ["Normal", "Déficit", "Exceso"], description: "Ajuste por regla orientativa, no del modelo" },
                },
                required: ["muni", "cultivo"],
              },
            },
          },
        },
        responses: {
          "200": { description: "yhat, yhat_modelo, low, high, risk, hist, shap[], modelo{error_tipico_t_ha,r2}, escenario{ajuste_t_ha}" },
          "404": { description: "El modelo no tiene predicciones para esa combinación" },
          "503": { description: "Datos no disponibles" },
        },
      },
    },
    "/recomendacion": {
      post: {
        tags: ["Predicción"], summary: "Recomendación accionable (calendario + dosis + plagas + agua)",
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  muni:    { type: "string" },
                  cultivo: { type: "string" },
                  enso:    { type: "string" },
                  lluvia:  { type: "string" },
                },
                required: ["muni", "cultivo"],
              },
            },
          },
        },
        responses: { "200": { description: "4 recomendaciones agronómicas" } },
      },
    },
    "/precios": {
      get: {
        tags: ["Precios"], summary: "Último precio mayorista por mercado y producto ($/kg)",
        description: "Incluye variación vs dato anterior y vs 7 días, y los últimos 30 datos. Por defecto solo series con dato en los últimos 30 días.",
        parameters: [
          { name: "departamento", in: "query", schema: { type: "string" }, description: "Nombre exacto (ver /precios/filtros)" },
          { name: "producto",     in: "query", schema: { type: "integer" }, description: "id_producto" },
          { name: "mercado",      in: "query", schema: { type: "integer" }, description: "id_central" },
          { name: "grupo",        in: "query", schema: { type: "string" } },
          { name: "max_atraso",   in: "query", schema: { type: "integer", default: 30 }, description: "Días máximos desde el último dato" },
        ],
        responses: { "200": { description: "{ fromDB, total, precios[] }" }, "503": { description: "Datos no disponibles" } },
      },
    },
    "/precios/filtros": {
      get: {
        tags: ["Precios"], summary: "Departamentos, mercados y productos con dato reciente",
        responses: { "200": { description: "{ departamentos[], mercados[], productos[] }" } },
      },
    },
    "/precios/serie": {
      get: {
        tags: ["Precios"], summary: "Historial de un producto en un mercado, con pronóstico si existe",
        parameters: [
          { name: "producto", in: "query", required: true, schema: { type: "integer" } },
          { name: "mercado",  in: "query", required: true, schema: { type: "integer" } },
          { name: "dias",     in: "query", schema: { type: "integer", default: 90, minimum: 7, maximum: 2200 } },
        ],
        responses: { "200": { description: "{ serie[], prediccion[] }; el horizonte del pronóstico está en días hábiles" }, "404": { description: "No existe" } },
      },
    },
    "/precios/informe": {
      get: {
        tags: ["Precios"], summary: "Informe diario (subidas, bajadas, brecha entre mercados, atípicos)",
        parameters: [{ name: "fecha", in: "query", schema: { type: "string", format: "date" }, description: "YYYY-MM-DD; por defecto el más reciente" }],
        responses: { "200": { description: "{ fecha, informe, fechas[] }" }, "404": { description: "Sin informe" } },
      },
    },
    "/precios/estado": {
      get: {
        tags: ["Precios"], summary: "Frescura de los datos y última revisión",
        description: "DANE publica una vez por día hábil; la app revisa cada hora si hay datos nuevos.",
        responses: { "200": { description: "{ estado, fecha_dato_max, datos_actualizados_at, ultima_revision_at, publicado_dane_at }" } },
      },
    },
    "/chat": {
      post: {
        tags: ["Asistente"], summary: "Chat con Claude (tool-use SQL)",
        description: "Límite por IP y por día (CHAT_LIMIT_IP_DIA) y tope global diario (CHAT_LIMIT_GLOBAL_DIA). Mensajes de hasta 2.000 caracteres; se usan los últimos 12.",
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  messages:   { type: "array", items: { type: "object", properties: { role: { type: "string" }, content: { type: "string" } } } },
                  sessionId:  { type: "string", description: "UUID opcional para persistir la conversación" },
                },
                required: ["messages"],
              },
            },
          },
        },
        responses: {
          "200": { description: "{ reply, sessionId }" },
          "400": { description: "Cuerpo inválido o mensaje demasiado largo" },
          "429": { description: "Límite diario alcanzado" },
          "502": { description: "El proveedor del modelo no respondió" },
        },
      },
    },
  },
};

export async function GET() {
  return Response.json(SPEC);
}
