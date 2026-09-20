# Estado de implementación

Fecha de corte: **2026-09-20**.  
Schema actual: **v5**.

Este documento describe comportamiento ejecutable. Los evolutivos viven en [ROADMAP.md](ROADMAP.md).

## Cierre de los puntos avanzados

### Fiscalidad versionada
- motor independiente del LLM;
- rulesets por jurisdicción/año;
- ES 2025 y ES 2026 con escala del ahorro 19/21/23/27/30;
- integración corriente de rendimientos del capital mobiliario y ganancias/pérdidas patrimoniales con límite cruzado del 25 % y arrastre documentado de 4 años;
- fuentes BOE/AEAT y fecha de verificación;
- Tax Center usa el ruleset automáticamente cuando existe y mantiene la tasa manual solo como simulación explícita;
- no consume pérdidas históricas no registradas ni se presenta como declaración completa.

### FEIN/FIAE e hipotecas
- extracción hipotecaria por página/contexto y revisión humana;
- capital, cuota, TIN/TAE, índice, diferencial, plazo, frecuencia, apertura, reembolso, tramo fijo, suelo/techo, subrogación, novación y vinculaciones;
- fórmula estructurada de comisión de reembolso cuando aparece porcentaje + primeros N años;
- senda libre de tipos y senda contractual indexada;
- variable/mixta con diferencial, revisiones, tramo fijo, suelo y techo;
- si falta el índice de una revisión contractual el cálculo queda en `needs_more_data`, sin interpolación ni predicción.

### Comparación comercial
- `CommercialComparisonProvider` define el contrato para adapters externos;
- matriz de comparación exige procedencia, frescura, campos requeridos y divisa/categoría compatibles;
- una condición desconocida nunca se interpreta como cero;
- adapters en vivo solo se activan al elegir una fuente autorizada concreta.

### Playwright y accesibilidad
- E2E forma parte de CI;
- journeys: onboarding, navegación, importación, Vault/cita, banking mock, decisiones y backup/restore;
- axe cubre WCAG 2.0/2.1/2.2 A+AA en rutas principales;
- test de skip link/foco/aria-current y reflow a 320 px;
- foco visible, contraste secundario AA, navegación accesible y reduced motion;
- auditoría formal interna en [WCAG_AA_AUDIT.md](WCAG_AA_AUDIT.md).

### macOS
- bundle `Financito.app` con launcher Swift y frontend preconstruido;
- backend incluido en Resources; dependencias Python se provisionan localmente en el primer arranque;
- firma Developer ID + hardened runtime + timestamp;
- notarización por `notarytool`, stapling y Gatekeeper;
- workflow manual de GitHub Actions con keychain temporal;
- la ejecución firmada real depende exclusivamente de certificados/credenciales Apple, no de desarrollo pendiente.

## Núcleo v1

Se mantienen además como implementados: runtime local/seguridad/SQLCipher, movimientos/imports/categorización, analytics/forecast, Open Banking, Vault/OCR/RAG/chat, patrimonio/portfolio/FIFO/mercado/riesgo, contratos/seguros, Decision Cases, stress/cost centers, Action/Repair, backup/restore/export y privacidad.

## Dependencias externas de activación

- Enable Banking y disponibilidad bancaria PSD2;
- Alpha Vantage/SEC/ECB/GDELT según credenciales o políticas de cada fuente;
- Ollama/modelos locales;
- Developer ID/notarización Apple;
- fuente comercial concreta para cada adapter en vivo.

Ninguna dependencia externa se sustituye con datos ficticios ni supuestos silenciosos.
