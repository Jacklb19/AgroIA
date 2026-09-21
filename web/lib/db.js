import { Pool } from "pg";

/* SSL (variable DB_SSL):
     disable      sin SSL (solo desarrollo local)
     require      cifrado sin verificar el certificado (por defecto: compatible con el pooler de Supabase)
     verify-full  cifrado + verificación; el certificado de la CA va en DB_SSL_CA (contenido PEM; admite "\n" literales)
   Se recomienda verify-full en producción cuando se dispone de la CA del proveedor. */
function configSsl() {
  const modo = (process.env.DB_SSL || "").toLowerCase();
  if (modo === "disable") return false;
  if (modo === "verify-full" || modo === "verify") {
    const ca = process.env.DB_SSL_CA;
    return { rejectUnauthorized: true, ...(ca ? { ca: ca.replace(/\\n/g, "\n") } : {}) };
  }
  return { rejectUnauthorized: false };
}

function makePool() {
  const statementTimeout = Number(process.env.DB_STATEMENT_TIMEOUT_MS) || 0;   // opcional; algunos poolers no aceptan el parámetro
  return new Pool({
    host:     process.env.DB_HOST,
    port:     parseInt(process.env.DB_PORT || "5432"),
    database: process.env.DB_NAME,
    user:     process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    ssl: configSsl(),
    max: 3,
    idleTimeoutMillis:       60000,
    connectionTimeoutMillis: 8000,
    query_timeout:           20000,    // una consulta colgada no debe mantener viva la función serverless
    ...(statementTimeout ? { statement_timeout: statementTimeout } : {}),
  });
}

/* Reutilizar el pool entre hot-reloads de Next.js dev */
if (!global._pgPool) global._pgPool = makePool();

export default global._pgPool;
