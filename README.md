# Financito

**Financito** es una aplicación financiera personal 360º, local-first y orientada a privacidad. Centraliza cuentas, movimientos, documentos, contratos, seguros, hipoteca, patrimonio, inversiones, mercado y decisiones financieras. La IA local explica; los saldos, métricas y escenarios proceden de motores deterministas.

> Estado a 20/09/2026: **runtime v1 ejecutable**. Backend, WebApp y tests viven en este repositorio. `main` es la referencia de implementación; `/docs` describe el comportamiento soportado y sus límites.

## Principios

- datos financieros y documentos privados en el equipo;
- API y Ollama limitados a loopback;
- SQLCipher en runtime estable; SQLite sin cifrar únicamente con `FINANCITO_ALLOW_PLAINTEXT_SQLITE=1` para desarrollo/tests;
- clave de DB y secretos externos en Keychain/credential store;
- ningún LLM calcula saldos, cuotas, riesgo, penalizaciones o ahorro;
- no se interpreta un dato material desconocido como cero;
- ninguna función base exige una API de pago;
- Open Banking es de solo lectura.

## Stack real

### WebApp
- Next.js 16 + React 19 + TypeScript;
- Tailwind CSS 4;
- TanStack Query;
- Recharts;
- export estático servido por FastAPI.

### Backend local
- Python 3.12+ / FastAPI;
- SQLAlchemy;
- SQLCipher + keyring;
- FTS5;
- sqlite-vec con fallback vectorial portable;
- pypdf, python-docx, openpyxl, Pillow/Tesseract y HEIC.

### IA local
- Ollama por loopback;
- selección del modelo de chat y embeddings desde Configuración;
- RAG híbrido BM25 + embeddings + RRF + reranking léxico local;
- el resto de Financito funciona sin Ollama.

## Funcionalidad implementada

- cuentas manuales y Open Banking PSD2;
- importación CSV/XLSX/QIF/OFX/CAMT.053/MT940;
- categorización, reglas, revisión de baja confianza, splits, transferencias y reembolsos;
- dashboard, presupuestos, recurrentes, anomalías, forecast y precisión histórica;
- analytics por categoría/comercio, fijo-variable y esencial-discrecional;
- patrimonio, activos, deuda y centros de coste;
- Vault documental con clasificación, idioma, hechos y evidencia por página;
- búsqueda global y chat local con citas navegables;
- contratos, seguros, duplicidades y requisitos de cobertura;
- hipoteca, amortización extraordinaria y motor de optimización;
- portfolios, trades, FIFO tax lots, valoración, exposición y riesgo;
- Alpha Vantage, CoinGecko, SEC EDGAR, ECB y GDELT como fuentes opcionales;
- Decision Cases y resultado esperado vs observado;
- Action Center, Calendar, Stress Test y Repair Center;
- backup cifrado y restauración verificada;
- export JSON/CSV, borrado local y regeneración de derivados.

## Ejecutable de macOS

Después de clonar el repositorio, el usuario normal no necesita ejecutar comandos para actualizar o arrancar Financito:

- **\`Financito.command\`**: doble clic. Guarda cambios locales en un stash de seguridad, comprueba \`origin/main\`, actualiza por fast-forward, prepara Python/backend/frontend cuando el commit cambia y arranca la aplicación.
- **\`Financito-sin-actualizar.command\`**: doble clic para arrancar con la copia local sin consultar GitHub.

El runner usa \`~/.financito/launcher.log\` para diagnóstico. Si faltan Python/Node/Tesseract y Homebrew está disponible, intenta instalarlos automáticamente. Nunca hace \`reset --hard\` ni elimina cambios locales.

## Arranque local

Desarrollo:

```bash
pip install -e 'apps/api[dev]'
cd apps/web && npm install && npm run build && cd ../..
./scripts/run-local.sh
```

Validación completa:

```bash
./scripts/validate.sh
```

El launcher aplica una restauración pendiente, levanta FastAPI exclusivamente en `127.0.0.1` y abre la WebApp.

## Integraciones opcionales

En **Configuración** pueden guardarse de forma segura:

- Enable Banking: App ID + clave RSA privada;
- Alpha Vantage: API key gratuita;
- CoinGecko Demo: key opcional según modalidad;
- SEC EDGAR: User-Agent identificable;
- Ollama: modelos instalados localmente.

ECB y GDELT no requieren credenciales en la implementación actual.

## Límites explícitos

No se declara como terminado:

- Tax Center normativo por jurisdicción/ejercicio: existen lotes FIFO y estimación parametrizada, pero no reglas fiscales legales versionadas;
- firma/notarización y distribución final macOS: requieren certificados/identidad Apple;
- comparadores comerciales de hipoteca/seguros/energía/telecom: necesitan fuentes/ofertas externas;
- FEIN/FIAE y cláusulas complejas: la extracción actual es conservadora y requiere revisión humana para hechos materiales;
- recomendación de inversión: existen scoring/riesgo/backtest, pero no se presenta como asesoramiento ni predicción.

## Fuente de verdad

- comportamiento HTTP ejecutable: `/api/openapi.json`;
- estado funcional: [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md);
- matriz: [docs/FEATURE_MATRIX.md](docs/FEATURE_MATRIX.md);
- seguridad: [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md);
- pruebas: [docs/TESTING.md](docs/TESTING.md);
- reglas para agentes: [AGENTS.md](AGENTS.md).

No se versionan datos financieros reales, documentos personales, DB de usuario, claves, tokens ni modelos binarios.
