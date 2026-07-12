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
    { name: "Asistente",  description: "Chat conversacional con Claude" },
    { name: "Sistema",    description: "Salud y metadatos" },
  ],
  paths: {
    "/health": {
      get: {
        tags: ["Sistema"], summary: "Healthcheck",
        responses: { "200": { description: "Servicio OK" } },
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
        tags: ["Datos"], summary: "Top 80 municipios con coordenadas y nivel de riesgo",
        responses: { "200": { description: "Array de puntos { municipio, lat, lon, riesgo }" } },
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
                  year:     { type: "string" },
                  semester: { type: "string", enum: ["A", "B"] },
                  enso:     { type: "string", enum: ["Neutral", "El Niño", "La Niña"] },
                  lluvia:   { type: "string", enum: ["Normal", "Déficit", "Exceso"] },
                },
                required: ["muni", "cultivo"],
              },
            },
          },
        },
        responses: { "200": { description: "yhat, low, high, risk, shap[]" } },
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
    "/chat": {
      post: {
        tags: ["Asistente"], summary: "Chat con Claude Sonnet 4.6 (tool-use SQL)",
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
        responses: { "200": { description: "{ reply, sessionId }" } },
      },
    },
  },
};

export async function GET() {
  return Response.json(SPEC);
}
