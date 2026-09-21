import crypto from "crypto";
import pool from "@/lib/db";
import { log } from "@/lib/log";

/* Límite de uso del asistente (/api/chat) para proteger la ANTHROPIC_API_KEY.
   Contadores diarios en Postgres (tabla chat_rate): sirve con varias instancias serverless, sin infraestructura extra.
   La IP nunca se guarda: solo un hash con sal. Si la BD falla se responde 503 (falla cerrado, para no gastar sin control). */

const LIMITE_IP = Number(process.env.CHAT_LIMIT_IP_DIA) || 20;
const LIMITE_GLOBAL = Number(process.env.CHAT_LIMIT_GLOBAL_DIA) || 500;

const DIA_BOGOTA = "(NOW() AT TIME ZONE 'America/Bogota')::date";

/* La tabla chat_rate la crea la migración 003 (python -m load.migrate). Ya no se crea en tiempo de ejecución:
   el rol de BD de la web puede ser de solo lectura salvo en las tablas chat_*. */

export function ipDe(request) {
  const xff = request.headers.get("x-forwarded-for");
  return (xff ? xff.split(",")[0] : request.headers.get("x-real-ip") || "desconocida").trim();
}

export function hashIp(ip) {
  return crypto.createHash("sha256").update(`${process.env.CHAT_HASH_SALT || "agroia"}:${ip}`).digest("hex").slice(0, 24);
}

async function contar(clave) {
  const { rows } = await pool.query(
    `INSERT INTO chat_rate (clave, dia, n) VALUES ($1, ${DIA_BOGOTA}, 1)
     ON CONFLICT (clave, dia) DO UPDATE SET n = chat_rate.n + 1
     RETURNING n`,
    [clave],
  );
  return rows[0].n;
}

/* Cuenta un mensaje. Retorna { ok:true } o { ok:false, status, mensaje }. */
export async function permitirChat(request) {
  try {
    const porIp = await contar(`ip:${hashIp(ipDe(request))}`);
    if (porIp > LIMITE_IP) {
      return { ok: false, status: 429, mensaje: `Llegaste al límite de ${LIMITE_IP} mensajes por día. Vuelve mañana o consulta los datos directamente en las demás pestañas.` };
    }
    const global = await contar("global");
    if (global > LIMITE_GLOBAL) {
      return { ok: false, status: 429, mensaje: "El asistente alcanzó su cupo diario de uso. Inténtalo de nuevo mañana." };
    }
    if (Math.random() < 0.01) {   // limpieza ocasional de contadores viejos
      pool.query(`DELETE FROM chat_rate WHERE dia < ${DIA_BOGOTA} - 7`).catch(() => {});
    }
    return { ok: true, restantes: Math.max(0, LIMITE_IP - porIp) };
  } catch (err) {
    log("error", "rate_limit", { mensaje: err?.message, codigo: err?.code });
    return { ok: false, status: 503, mensaje: "El asistente no está disponible en este momento." };
  }
}

/* Validación del cuerpo de /api/chat. Retorna { ok:true, messages, sessionId } o { ok:false, error }. */
export const MAX_MENSAJE = 2000;
export const MAX_HISTORIAL = 12;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function validarChat(body) {
  if (!body || typeof body !== "object" || !Array.isArray(body.messages) || body.messages.length === 0) {
    return { ok: false, error: "Se requiere un arreglo 'messages' con al menos un mensaje." };
  }
  const limpios = [];
  for (const m of body.messages) {
    if (!m || (m.role !== "user" && m.role !== "assistant") || typeof m.content !== "string") continue;
    if (m.role === "user" && m.content.length > MAX_MENSAJE) {
      return { ok: false, error: `Cada mensaje puede tener como máximo ${MAX_MENSAJE} caracteres.` };
    }
    limpios.push({ role: m.role, content: m.content.slice(0, 8000) });
  }
  const recientes = limpios.slice(-MAX_HISTORIAL);
  const primerUser = recientes.findIndex((m) => m.role === "user");
  const messages = primerUser === -1 ? [] : recientes.slice(primerUser);   // la API exige empezar con "user"
  if (!messages.length || messages[messages.length - 1].role !== "user") {
    return { ok: false, error: "El último mensaje debe ser del usuario." };
  }
  const sessionId = typeof body.sessionId === "string" && UUID.test(body.sessionId) ? body.sessionId : null;
  return { ok: true, messages, sessionId };
}
