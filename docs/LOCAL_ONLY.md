# Arquitectura estrictamente local

## Regla no negociable

Financito se ejecuta íntegramente en el Mac del usuario. No existe infraestructura propia remota para frontend, backend, base de datos, documentos, embeddings, RAG, LLM, logs, métricas, backups, sesiones, configuración ni cachés.

No se desplegará Financito en Vercel, AWS, Azure, GCP, Supabase, Firebase, Cloudflare Workers, Railway, Render ni servicios equivalentes.

## Topología de producción

Browser → loopback local → WebApp estática + FastAPI → SQLite cifrada / workers / RAG / LLM / Vault.

Solo se escucha en 127.0.0.1 o ::1. Nunca en interfaces LAN o WAN.

## Frontend en producción

Next.js se usa para desarrollo y build. La producción debe generar assets estáticos. FastAPI sirve tanto la WebApp como /api bajo el mismo origen local.

No debe existir un runtime Node obligatorio en producción.

Ventajas:
- menor consumo;
- menos procesos;
- sin CORS entre UI y API;
- CSP más sencilla;
- menor superficie de ataque;
- operación local reproducible.

## Internet

Todo local no significa sin Internet. Financito puede realizar conexiones salientes estrictamente necesarias hacia proveedores configurados por el usuario: Open Banking, cotizaciones, fundamentales, cripto, noticias, macro y comparadores.

Esas conexiones salen directamente desde el Mac. No pasan por servidores propios de Financito.

## IA

Obligatorio:
- LLM local;
- embeddings locales;
- reranker local;
- vector DB local;
- prompts locales.

Prohibido para contenido privado:
- OpenAI API;
- Anthropic API;
- Gemini API;
- otros LLM cloud.

## Frontend sin dependencias remotas en runtime

No cargar Google Fonts, CDN de JavaScript, iconos remotos, estilos remotos, trackers, píxeles, analytics ni embeds innecesarios.

Fuentes, iconos y assets se empaquetan localmente.

## Telemetría

Cero telemetría remota, cero crash reporting remoto, cero analytics remoto y cero logs remotos. Toda observabilidad es local.

## Backups

Solo backup local cifrado y export manual cifrado. No activar iCloud, Dropbox, Google Drive u otro cloud automáticamente.

Si el usuario coloca voluntariamente un backup o Vault en una carpeta sincronizada, Financito debe advertir que deja de ser estrictamente local.

## Política de red

Default deny conceptual:
- frontend: solo self;
- backend: outbound solo a providers habilitados;
- bind: loopback;
- sin descubrimiento LAN;
- sin UPnP;
- sin túneles;
- sin acceso remoto.

## Desarrollo

En desarrollo pueden ejecutarse Next dev y FastAPI por separado. Los entornos de desarrollo no deben usar datos financieros reales.


## Subida de documentos desde la WebApp

Seleccionar o arrastrar un archivo en la WebApp no lo envía a Internet.

Flujo:
Browser local → FastAPI loopback → `~/.financito/vault/uploads` → extracción/OCR → SQLite/RAG → Ollama local.

Los ficheros subidos, texto extraído, embeddings, propuestas y conclusiones permanecen en el Mac. El análisis automático del Vault se ejecuta en un thread de fondo para no bloquear el arranque de Financito.
