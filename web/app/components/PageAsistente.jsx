"use client";
import { useState, useRef, useEffect } from "react";
import { Icon } from "./icons";

const SUGERENCIAS = [
  "¿Cuál es el panorama general del sistema?",
  "¿Cuál es el mejor municipio para arroz?",
  "Muéstrame las alertas de riesgo ALTO",
  "Compara Espinal y Saldaña en rendimiento",
  "¿Qué pasa si hay El Niño en Pasto con maíz?",
  "¿Qué cultivo me recomiendas para Manizales?",
  "¿Cómo está el clima en Ibagué?",
  "Proyecta café en Armenia con sequía",
];

function BotIcon() {
  return (
    <div className="chat-avatar bot">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        <line x1="12" y1="3" x2="12" y2="7"/>
        <circle cx="8.5" cy="16" r="1.5" fill="currentColor" stroke="none"/>
        <circle cx="15.5" cy="16" r="1.5" fill="currentColor" stroke="none"/>
      </svg>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="chat-bubble ai">
      <BotIcon />
      <div className="bubble-body typing-dots">
        <span /><span /><span />
      </div>
    </div>
  );
}

function Mensaje({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div className={`chat-bubble ${isUser ? "user" : "ai"}`}>
      {!isUser && <BotIcon />}
      <div className="bubble-body">
        {msg.content.split("\n").map((line, i) => (
          <span key={i}>
            {line}
            {i < msg.content.split("\n").length - 1 && <br />}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function PageAsistente() {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const messagesRef = useRef(null);
  const inputRef    = useRef(null);

  /* ── Sesión persistente (memoria en BD) ─────────────────────────── */
  const [sessionId, setSessionId] = useState(null);
  useEffect(() => {
    if (typeof window === "undefined") return;
    let sid = localStorage.getItem("agroia_chat_session");
    if (!sid) {
      sid = (crypto.randomUUID && crypto.randomUUID()) ||
            `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem("agroia_chat_session", sid);
    }
    setSessionId(sid);
  }, []);

  /* ── Reconocimiento de voz (Web Speech API) ─────────────────────── */
  const [escuchando,   setEscuchando]   = useState(false);
  const [vozDisponible, setVozDisponible] = useState(false);
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    setVozDisponible(true);
    const rec = new SR();
    rec.lang           = "es-CO";
    rec.continuous     = false;
    rec.interimResults = true;
    rec.onresult = (e) => {
      const txt = Array.from(e.results).map((r) => r[0].transcript).join("");
      setInput(txt);
    };
    rec.onend   = () => setEscuchando(false);
    rec.onerror = () => setEscuchando(false);
    recognitionRef.current = rec;
    return () => { try { rec.abort(); } catch {} };
  }, []);

  const toggleVoz = () => {
    const rec = recognitionRef.current;
    if (!rec) return;
    if (escuchando) { rec.stop(); return; }
    try { rec.start(); setEscuchando(true); } catch {}
  };

  const hablar = (texto) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const limpio = String(texto || "").replace(/[*_`>#]/g, "").slice(0, 600);
    const u = new SpeechSynthesisUtterance(limpio);
    u.lang  = "es-CO";
    u.rate  = 1.05;
    u.pitch = 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  };

  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  const enviar = async (texto) => {
    const txt = (texto || input).trim();
    if (!txt || loading) return;

    const userMsg  = { role: "user", content: txt };
    const newMsgs  = [...messages, userMsg];
    setMessages(newMsgs);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ messages: newMsgs, sessionId }),
      });
      const data = await res.json();
      let reply;
      if (data.reply) {
        reply = data.reply;
      } else if (data.error) {
        reply = `⚠ ${data.error}${data.hint ? `\n\n💡 ${data.hint}` : ""}${data.model_intentado ? `\n\nModelo intentado: ${data.model_intentado}` : ""}`;
      } else {
        reply = "Sin respuesta del servidor.";
      }
      setMessages([...newMsgs, { role: "assistant", content: reply }]);
      if (vozDisponible && reply && data.reply) hablar(reply);
    } catch {
      setMessages([...newMsgs, {
        role:    "assistant",
        content: "Error de conexión. Verifica que el servidor esté activo.",
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(); }
  };

  const vaciar = () => { if (!loading) setMessages([]); };

  return (
    <section className="section">
      <div className="container">

        {/* Encabezado */}
        <div className="section-head">
          <span className="eyebrow blue">Asistente · Claude Sonnet 4.6 </span>
          <h2>Consulta la base de datos en lenguaje natural</h2>
          <p>Pregunta sobre predicciones, alertas climáticas, ranking de municipios o estadísticas generales. El asistente consulta la BD real y responde con datos concretos.</p>
        </div>

        <div className="chat-layout">

          {/* Panel lateral de info */}
          <aside className="chat-sidebar">
            <div className="chat-sidebar-card">
              <div className="cs-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                Qué puedes preguntar
              </div>
              <ul className="cs-list">
                <li>Rendimiento predicho (XGBoost) por municipio y cultivo</li>
                <li>Comparar 2–5 municipios lado a lado</li>
                <li>Proyectar escenarios El Niño / La Niña / sequía</li>
                <li>Recomendar cultivos óptimos para una zona</li>
                <li>Alertas climáticas y ranking por riesgo</li>
                <li>Datos climáticos históricos (lluvia, temperatura)</li>
                <li>Panorama general del sistema</li>
              </ul>
            </div>

            <div className="chat-sidebar-card">
              <div className="cs-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                </svg>
                Tablas disponibles
              </div>
              <ul className="cs-list mono">
                <li>pred_rendimiento</li>
                <li>pred_alerta_climatica</li>
                <li>fact_produccion_agricola</li>
                <li>fact_clima_mensual</li>
                <li>dim_municipio · dim_cultivo</li>
              </ul>
            </div>
          </aside>

          {/* Área principal del chat */}
          <div className="chat-main">

            <div className="chat-messages" ref={messagesRef}>
              {/* Estado vacío con sugerencias */}
              {messages.length === 0 && !loading && (
                <div className="chat-empty">
                  <div className="chat-empty-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                      <circle cx="8.5" cy="16" r="1.5" fill="currentColor" stroke="none"/>
                      <circle cx="15.5" cy="16" r="1.5" fill="currentColor" stroke="none"/>
                    </svg>
                  </div>
                  <p className="chat-empty-title">¿En qué te ayudo hoy?</p>
                  <p className="chat-empty-sub">Puedes usar una sugerencia o escribir tu propia pregunta.</p>
                  <div className="chat-chips">
                    {SUGERENCIAS.map((s) => (
                      <button key={s} className="chat-chip" onClick={() => enviar(s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Mensajes */}
              {messages.map((m, i) => <Mensaje key={i} msg={m} />)}
              {loading && <TypingDots />}
            </div>

            {/* Input */}
            <div className="chat-input-wrap">
              {messages.length > 0 && (
                <button className="chat-clear" onClick={vaciar} title="Nueva conversación">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/>
                  </svg>
                  Nueva conversación
                </button>
              )}
              <div className="chat-input-row">
                <textarea
                  ref={inputRef}
                  className="chat-input"
                  rows={1}
                  placeholder={escuchando ? "Escuchando…" : "Escribe o pulsa el micrófono…"}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKey}
                  disabled={loading}
                />
                {vozDisponible && (
                  <button
                    type="button"
                    onClick={toggleVoz}
                    title={escuchando ? "Detener" : "Hablar"}
                    aria-label={escuchando ? "Detener escucha" : "Iniciar escucha"}
                    className="chat-send"
                    style={{
                      background: escuchando ? "#dc2626" : "#1e4d7b",
                      animation: escuchando ? "pulse 1.2s infinite" : "none",
                    }}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
                      <path d="M19 11a7 7 0 0 1-14 0"/>
                      <line x1="12" y1="18" x2="12" y2="22"/>
                      <line x1="8"  y1="22" x2="16" y2="22"/>
                    </svg>
                  </button>
                )}
                <button
                  className="chat-send"
                  onClick={() => enviar()}
                  disabled={!input.trim() || loading}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                  </svg>
                </button>
              </div>
              <p className="chat-hint">
                Enter para enviar · Shift+Enter para nueva línea · {vozDisponible ? "🎤 voz disponible (es-CO)" : "consulta la BD real"}
              </p>
            </div>

          </div>
        </div>
      </div>
    </section>
  );
}
