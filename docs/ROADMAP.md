# Roadmap

Fecha de corte: **2026-09-20**.

La lista que antes quedaba como “evolutivos/dependencias externas” se ha cerrado como gap de producto. A partir de ahora el roadmap solo debe contener extensiones de cobertura o activaciones que dependen de terceros.

## Cerrado en el runtime

- normativa fiscal versionada por jurisdicción/ejercicio, con primer ruleset verificable **ES 2025 y ES 2026**, fuente legal y fecha de verificación;
- integración/compensación corriente de la base del ahorro y escala progresiva; los datos fiscales que Financito no conoce siguen marcados como ausentes;
- extracción FEIN/FIAE ampliada con tipo de documento, capital, cuota, fijo/variable/mixto, índice, diferencial, frecuencia de revisión, tramo fijo, suelo/techo, comisiones de apertura/reembolso/subrogación/novación, vinculaciones y fórmula temporal de reembolso cuando aparece en el texto;
- motor hipotecario variable/mixto basado en curva explícita de índice, con revisiones contractuales, diferencial, tramo fijo, suelo/techo y bloqueo si falta una revisión;
- contrato de provider comercial externo y matriz normalizada de evidencia/frescura/comparabilidad sin tratar condiciones desconocidas como cero;
- Playwright E2E en CI para onboarding, navegación, importación, Vault/citas, banking mock, decisiones y backup/restore;
- axe WCAG 2.0/2.1/2.2 A+AA sobre rutas principales, teclado, skip link y reflow a 320 px;
- auditoría interna WCAG 2.2 AA documentada;
- creación de `Financito.app`, firma Developer ID, hardened runtime, notarización con `notarytool`, stapling y verificación Gatekeeper automatizados.

## Dependencias externas de activación

### Apple
El código de distribución está terminado, pero un artefacto real solo puede firmarse/notarizarse al configurar un certificado Developer ID y credenciales de Apple. Véase [MACOS_DISTRIBUTION.md](MACOS_DISTRIBUTION.md).

### Fuentes comerciales
Financito ya puede normalizar y validar ofertas externas. Cada adapter en vivo requiere una fuente concreta con acceso permitido, condiciones de uso compatibles y una ruta gratuita/propia. No se añadirá scraping frágil ni un proveedor de pago obligatorio solo para “marcar” el punto como terminado.

### Fiscalidad adicional
Añadir otro país o ejercicio consiste en incorporar un ruleset versionado, fuentes oficiales y tests. No requiere cambiar la arquitectura del motor.

## Evolutivos reales posteriores

- más jurisdicciones/ejercicios fiscales;
- adapters comerciales concretos a medida que exista una fuente pública/autorizada estable;
- importadores específicos de más brokers;
- más corporate actions y fundamentales internacionales;
- updater firmado de macOS;
- pruebas con matriz física de VoiceOver/navegadores como validación complementaria;
- reconstrucción “as-of” universal de todas las entidades.

## Regla permanente

Cualquier nueva función debe mantener privacidad local, cálculos deterministas, provenance/frescura, ausencia de dependencia de pago obligatoria, tests y documentación en el mismo cambio.
