import { Pool } from "pg";

function makePool() {
  return new Pool({
    host:     process.env.DB_HOST,
    port:     parseInt(process.env.DB_PORT || "5432"),
    database: process.env.DB_NAME,
    user:     process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    ssl: { rejectUnauthorized: false },
    max: 3,
    idleTimeoutMillis:       60000,
    connectionTimeoutMillis: 8000,
  });
}

/* Reutilizar el pool entre hot-reloads de Next.js dev */
if (!global._pgPool) global._pgPool = makePool();

export default global._pgPool;
