# Cómo conectar dashboards de Power BI a la página web AgroIA

## Requisitos previos
- Tener los 5 dashboards construidos en Power BI Desktop (.pbix)
- Tener una cuenta de Microsoft (puede ser cuenta universitaria o personal)
- Tener acceso a Power BI Service (powerbi.com) — el plan gratuito funciona para embebido público

---

## PASO 1 — Publicar el reporte desde Power BI Desktop

1. Abre tu archivo `.pbix` en Power BI Desktop
2. En la barra superior ve a **Inicio → Publicar**
3. Si te pide iniciar sesión, usa tu cuenta de Microsoft
4. Selecciona el workspace de destino — si es la primera vez, usa **"Mi área de trabajo"**
5. Haz clic en **Publicar**
6. Espera el mensaje de confirmación: *"Publicación correcta"*
7. Repite este proceso para cada uno de los 5 dashboards

---

## PASO 2 — Obtener el enlace de inserción (embed URL)

Para cada reporte publicado:

1. Ve a **powerbi.com** e inicia sesión
2. En el panel izquierdo abre **"Mi área de trabajo"**
3. Haz clic en el nombre del reporte que acabas de publicar
4. El reporte se abre en el navegador — copia la URL que aparece en la barra de direcciones, la necesitarás después
5. Ahora en la barra superior del reporte haz clic en **Archivo → Insertar informe → Sitio web o portal**
6. Se abre una ventana con un bloque de código `<iframe>` — copia ese bloque completo, se ve así:

```html
<iframe title="NombreReporte"
  width="1140"
  height="541.25"
  src="https://app.powerbi.com/reportEmbed?reportId=XXXXXXXX&autoAuth=true&ctid=XXXXXXXX"
  frameborder="0"
  allowFullScreen="true">
</iframe>
```

7. Guarda ese `src="..."` de cada dashboard — son las 5 URLs que necesitas

> **Nota importante:** La opción "Sitio web o portal" solo aparece si el reporte tiene permisos públicos o si tu organización lo permite. Si no aparece, ve al Paso 2B.

### PASO 2B — Si no aparece la opción de insertar (alternativa)

1. En el reporte abierto en powerbi.com, haz clic en los **tres puntos (...)** arriba a la derecha
2. Selecciona **Compartir**
3. Activa **"Cualquier persona con el vínculo puede ver"**
4. Copia el enlace que genera
5. Para convertirlo en embed URL, cambia la URL de:
   `https://app.powerbi.com/view?r=XXXXXXXX`
   a:
   `https://app.powerbi.com/reportEmbed?reportId=XXXXXXXX&autoAuth=true`

---

## PASO 3 — Agregar las URLs al código

Abre el archivo:
```
AgroH/web/app/components/PageDashboards.jsx
```

Busca el objeto `PLACEHOLDERS` cerca de la línea 60. Verás que cada dashboard tiene una propiedad `embedNote`. Agrega una propiedad `embedUrl` con la URL que copiaste en el paso anterior:

```js
const PLACEHOLDERS = {
  produccion: {
    // ... lo que ya existe ...
    embedUrl: "https://app.powerbi.com/reportEmbed?reportId=TU_ID_AQUI&autoAuth=true&ctid=TU_CTID",
  },
  clima: {
    // ...
    embedUrl: "https://app.powerbi.com/reportEmbed?reportId=TU_ID_AQUI&autoAuth=true&ctid=TU_CTID",
  },
  calidad: {
    // ...
    embedUrl: "https://app.powerbi.com/reportEmbed?reportId=TU_ID_AQUI&autoAuth=true&ctid=TU_CTID",
  },
  modelos: {
    // ...
    embedUrl: "https://app.powerbi.com/reportEmbed?reportId=TU_ID_AQUI&autoAuth=true&ctid=TU_CTID",
  },
};
```

---

## PASO 4 — Reemplazar los placeholders por iframes reales

En el mismo archivo `PageDashboards.jsx`, busca el componente `DashPlaceholder` y reemplázalo completamente por este:

```jsx
function DashPlaceholder({ tabId }) {
  const cfg = PLACEHOLDERS[tabId];

  // Si tiene URL de Power BI, muestra el iframe
  if (cfg.embedUrl) {
    return (
      <div className="fade-in" style={{ marginTop: 16 }}>
        <div style={{
          background: "white",
          border: "1px solid var(--ink-200)",
          borderRadius: "var(--radius-lg)",
          overflow: "hidden",
          boxShadow: "var(--shadow-sm)"
        }}>
          <div style={{
            padding: "16px 22px",
            borderBottom: "1px solid var(--ink-200)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 600 }}>{cfg.title}</h3>
              <p style={{ fontSize: 12.5, color: "var(--ink-500)", margin: "4px 0 0" }}>{cfg.embedNote}</p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {cfg.badges.map((b) => (
                <span key={b} className="src-badge">{b}</span>
              ))}
            </div>
          </div>
          <iframe
            title={cfg.title}
            src={cfg.embedUrl}
            width="100%"
            height="600"
            frameBorder="0"
            allowFullScreen={true}
            style={{ display: "block" }}
          />
        </div>
      </div>
    );
  }

  // Si no tiene URL todavía, muestra el placeholder original
  return (
    <div className="dash-placeholder fade-in">
      <div className="icon-wrap">{cfg.icon}</div>
      <h3>{cfg.title}</h3>
      <p>{cfg.desc}</p>
      <div className="badges">
        {cfg.badges.map((b) => <span key={b} className="src-badge">{b}</span>)}
      </div>
      <div><div className="footer-strip">{cfg.filter}</div></div>
    </div>
  );
}
```

---

## PASO 5 — Conectar el dashboard "Panorama Ejecutivo" (tab 1)

El Panorama Ejecutivo ya tiene gráficas nativas con datos reales de PostgreSQL. Si también quieres reemplazarlo con un iframe de Power BI:

1. En `PageDashboards.jsx` busca la línea:
   ```jsx
   {tab === "panorama" ? <PanoramaPanel /> : <DashPlaceholder tabId={tab} />}
   ```

2. Agrega la URL del panorama en una constante arriba:
   ```jsx
   const PANORAMA_EMBED_URL = "https://app.powerbi.com/reportEmbed?reportId=TU_ID&autoAuth=true&ctid=TU_CTID";
   ```

3. Cambia la línea por:
   ```jsx
   {tab === "panorama"
     ? (PANORAMA_EMBED_URL
         ? <iframe title="Panorama Ejecutivo" src={PANORAMA_EMBED_URL} width="100%" height="700" frameBorder="0" allowFullScreen style={{display:"block", borderRadius:"var(--radius-lg)"}} />
         : <PanoramaPanel />)
     : <DashPlaceholder tabId={tab} />}
   ```

---

## PASO 6 — Verificar que el embed funciona

1. Guarda todos los cambios
2. Corre `npm run dev` en la carpeta `web/`
3. Abre `http://localhost:3000`
4. Ve a la sección **Dashboards** y cambia entre tabs
5. Deberías ver el iframe de Power BI cargando dentro de la página

### Problemas comunes

| Problema | Causa | Solución |
|----------|-------|----------|
| El iframe muestra error de permisos | El reporte no es público | Activar "Cualquier persona con el vínculo" en Power BI Service |
| El iframe muestra pantalla en blanco | URL incorrecta o token expirado | Volver a generar el enlace desde powerbi.com |
| Se ve muy pequeño | Altura del iframe | Cambiar `height="600"` a `height="800"` o más |
| No carga en producción (Railway/Vercel) | CORS o política de iframes | Asegurarse de que el reporte sea público, no organizacional |
| El reporte pide login dentro del iframe | Modo de autenticación | Usar embed con `autoAuth=true` o cambiar a enlace público |

---

## Resultado final esperado

Cuando todo esté conectado, la página de Dashboards mostrará:

- **Tab Panorama Ejecutivo** → Gráficas nativas con datos reales de PostgreSQL (o iframe de PBI si prefieres)
- **Tab Producción** → iframe Power BI Dashboard 2
- **Tab Clima & Alertas** → iframe Power BI Dashboard 3
- **Tab Calidad de Datos** → iframe Power BI Dashboard 4
- **Tab Modelos y Evidencia** → iframe Power BI Dashboard 5

Cada iframe es interactivo — los filtros, slicers y drill-through de Power BI funcionan dentro de la página web exactamente igual que en Power BI Service.
