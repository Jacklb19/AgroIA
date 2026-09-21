# Contribuir a AgroIA

## Empezar

```powershell
.\scripts\tasks.ps1 setup   # una sola vez: dependencias, Postgres local (Docker), migraciones y datos de ejemplo
.\scripts\tasks.ps1 dev     # web en http://localhost:3000
.\scripts\tasks.ps1 test    # ruff + pytest (incluye pruebas contra Postgres)
.\scripts\tasks.ps1 e2e     # build + humo E2E con Playwright
```

Sin Docker puedes correr `pytest` (las pruebas con marca `db` se omiten) y `ruff check .`.

## Reglas del proyecto

1. **Nada inventado.** Si no hay dato, la interfaz muestra un estado vacío y la API responde 503/404; no hay valores de respaldo.
   Los datos sintéticos solo existen en `scripts/seed_dev.py` y están rotulados.
2. **Cada cifra visible** debe poder rastrearse a una tabla y una fecha (usa `DataStamp` y las rutas de `web/lib/api.js`).
3. **Esquema con migraciones.** No edites una migración aplicada: crea `migrations/NNN_nombre.sql` idempotente y corre `python -m load.migrate`.
4. **Sin `fillna(0)`** en variables del modelo (un dato faltante no es un cero) y sin evaluar el modelo con datos vistos al entrenar.
5. **Errores internos no salen al cliente**: usa `errorBD()` (503 genérico con `request_id`) y registra con `log()`.
6. **Pruebas**: cada corrección de un bug lleva una prueba que habría fallado antes. Las pruebas con base de datos llevan `@pytest.mark.db`.

## Antes de abrir un PR

- `.\scripts\tasks.ps1 test` en verde y `cd web; npm run lint; npm run build`.
- Si tocas la web: `.\scripts\tasks.ps1 e2e`.
- Si tocas dependencias: cambia las versiones fijadas en `requirements*.txt` y describe por qué.
- Un PR por tema y con su verificación descrita.
