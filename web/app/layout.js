import { Inter, Inter_Tight, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import "./styles.css";

/* Fuentes autoalojadas por Next (sin pedir nada a Google en el navegador, sin salto de texto al cargar). */
const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--f-inter", display: "swap" });
const interTight = Inter_Tight({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--f-inter-tight", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "600", "700"], variable: "--f-mono", display: "swap" });

const sitio =
  process.env.NEXT_PUBLIC_SITE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "http://localhost:3000");

const DESCRIPCION =
  "Datos abiertos del agro colombiano en un solo lugar: precios mayoristas diarios por mercado, predicción de rendimiento por municipio y alertas climáticas, con la fuente y la fecha de cada cifra.";

export const metadata = {
  metadataBase: new URL(sitio),
  title: "AgroIA Colombia — Inteligencia Agroclimática",
  description: DESCRIPCION,
  openGraph: {
    title: "AgroIA Colombia — Inteligencia Agroclimática",
    description: DESCRIPCION,
    type: "website",
    locale: "es_CO",
    siteName: "AgroIA Colombia",
  },
  twitter: { card: "summary_large_image", title: "AgroIA Colombia", description: DESCRIPCION },
};

export const viewport = { width: "device-width", initialScale: 1, themeColor: "#155436" };

export default function RootLayout({ children }) {
  return (
    <html lang="es" className={`${inter.variable} ${interTight.variable} ${mono.variable}`}>
      <body>
        <a href="#main" className="skip-link">Saltar al contenido principal</a>
        <div className="app">{children}</div>
      </body>
    </html>
  );
}
