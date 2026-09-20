# Roadmap

La mayor parte del runtime v1 está implementada. Este roadmap enumera trabajo restante; no repite módulos ya finalizados.

## Cerrado en v1
- runtime local y seguridad;
- SQLCipher/Keychain;
- WebApp y API;
- Vault, OCR, clasificación, RAG híbrido y chat local;
- movimientos/imports/categorización/analytics/forecast;
- Open Banking persistente;
- patrimonio, portfolio, FIFO, mercado y riesgo;
- contratos, seguros, hipoteca y optimización;
- Decision Cases/Outcomes;
- stress, cost centers, Action/Calendar/Repair;
- backup/restore, export y privacidad.

## Próxima prioridad: calidad y distribución

### Testing de experiencia
- Playwright: onboarding, importación, Vault/cita, banking mock, decisión y restore;
- tests de componentes UI;
- axe/accessibility en CI;
- datasets RAG de answerable/unanswerable/contradicción.

### Distribución macOS
- bundle de frontend/backend/runtime;
- detección/instalación guiada de Tesseract/Ollama cuando proceda;
- firma Developer ID;
- notarización;
- updater seguro;
- smoke tests sobre artefacto firmado.

Estas tareas requieren identidad/certificados Apple y no se pueden completar solo con código genérico.

## Fiscalidad
- motor normativo versionado por jurisdicción y ejercicio;
- reglas de adquisición/transmisión y compensación verificadas;
- trazabilidad de fuente legal/fecha;
- nunca mezclar una estimación parametrizada con una declaración fiscal oficial.

## Contratos/hipoteca avanzados
- parser específico FEIN/FIAE;
- formulas de comisión estructuradas;
- tipos variables/mixtos con revisiones;
- novación/subrogación;
- vinculaciones derivadas automáticamente de evidencia confirmada.

## Mercado
- más cobertura internacional de fundamentales;
- corporate actions/dividendos;
- benchmark/performance TWR/MWR;
- importer de brokers;
- news entity-linking e impacto con evaluación.

## Producto
- auditoría WCAG AA;
- Developer Mode/freshness inspector más detallado;
- as-of universal/reconstrucción temporal;
- perfiles/reglas multiusuario si se decide ampliar el modelo local single-user.

## Regla permanente
Cualquier nueva función debe:
1. mantener privacidad local;
2. usar motor determinista para cifras;
3. conservar provenance/frescura;
4. no introducir proveedor de pago obligatorio;
5. añadir test y actualizar documentación en el mismo cambio.
