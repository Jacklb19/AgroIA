/* "¿Cómo se calcula?": explicación en una capa plegable (details: accesible y sin JavaScript). */
export default function InfoPanel({ titulo = "¿Cómo se calcula?", children }) {
  return (
    <details className="info-panel">
      <summary>{titulo}</summary>
      <div className="info-panel-body">{children}</div>
    </details>
  );
}
