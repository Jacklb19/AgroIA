import "./globals.css";

export const metadata = {
  title: "AgroIA Colombia — Inteligencia Agroclimática",
  description:
    "Plataforma de inteligencia agroclimática con datos abiertos del sector agropecuario colombiano.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap"
          rel="stylesheet"
        />
        <link rel="stylesheet" href="/styles.css" />
      </head>
      <body>
        <a href="#main" className="skip-link">Saltar al contenido principal</a>
        <div className="app">{children}</div>
      </body>
    </html>
  );
}
