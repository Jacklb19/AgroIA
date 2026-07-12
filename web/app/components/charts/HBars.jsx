"use client";

export default function HBars({ items, color = "#1a7a4a", max }) {
  const peak = max || Math.max(...items.map((i) => i.v));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {items.map((it, i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "120px 1fr 56px", gap: 12, alignItems: "center" }}>
          <span style={{ fontSize: 12.5, color: "#374151" }}>{it.l}</span>
          <div style={{ height: 8, background: "#f3f4f6", borderRadius: 4, overflow: "hidden" }}>
            <span style={{ display: "block", height: "100%", width: `${(it.v / peak) * 100}%`, background: color, borderRadius: 4 }} />
          </div>
          <span style={{ fontSize: 12.5, fontFamily: "ui-monospace, monospace", color: "#111827", textAlign: "right", fontWeight: 600 }}>
            {it.v.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}
