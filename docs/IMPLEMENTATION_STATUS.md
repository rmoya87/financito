# Estado de implementación

Fecha de corte: 2026-09-20.

Este documento diferencia explícitamente lo implementado y verificable de lo que sigue requiriendo integración externa o una fase posterior. No sustituye a `FEATURE_MATRIX.md`; describe el código ejecutable presente en el repositorio.

## Implementado en el runtime v1

### Seguridad y operación local
- FastAPI solo admite configuración de bind loopback.
- Validación de Host y Origin para reducir DNS rebinding y llamadas desde sitios externos.
- Cookie de sesión HttpOnly/SameSite=Strict y token CSRF para mutaciones.
- CSP y cabeceras defensivas.
- Vault limitado por path canónico; se rechazan rutas fuera del root y symlinks.
- Launcher local que inicia la API y abre el navegador sin exigir comandos al usuario una vez empaquetado.
- Health Center para DB, Vault, frontend e IA local.
- Auditoría local de eventos materiales.

### Datos y finanzas
- Cuentas manuales y saldo.
- Importación CSV bancaria con fechas/decimales españoles, deduplicación y procedencia.
- Categorización determinista inicial con confianza; corrección manual con auditoría y precedencia.
- Dashboard de ingresos, gastos, ahorro, liquidez, categorías, compromisos y acciones.
- Presupuestos por categoría.
- Compromisos futuros.
- Forecast 7/30/90/180/365 o personalizado mediante API/UI: baseline del mismo periodo del año anterior, tendencia acotada, compromisos conocidos, rango y versión del modelo.
- Motor hipotecario determinista para escenarios de amortización.
- Motor de optimización con beneficio neto y break-even. Una penalización desconocida produce `needs_more_data`; nunca se interpreta como 0.
- Esquema inicial para contratos, hipotecas, portfolio, posiciones, objetivos, decisiones y oportunidades.

### Financial Knowledge Vault
- Indexación por referencia a archivos existentes en el Vault.
- Soporte inicial para PDF, imágenes OCR, DOCX, XLSX, CSV, TXT y JSON.
- SHA-256 y deduplicación.
- Extracción conservadora de hechos contractuales básicos.
- Todo hecho extraído queda `inferred` hasta revisión humana.
- Se genera automáticamente una acción de revisión cuando hay evidencia inferida.

### WebApp
- Shell responsive y navegación local.
- Resumen.
- Cuentas.
- Movimientos/importación y revisión de categorías.
- Previsión y compromisos.
- Documentos/evidencia.
- Action Center.
- Laboratorio de decisiones: hipoteca y cambio de producto.
- Health Center.

## Implementado como contrato/adapters, pendiente de credenciales o software local

- IA local Ollama: Health detecta modelos y el adapter solo acepta loopback. Requiere que el usuario instale/configure un modelo local.
- Open Banking: la especificación y estrategia de fallback están documentadas; no se incluyen credenciales ni contrato de un proveedor.
- Mercado, fundamentales, cripto, noticias y macro: deben activarse mediante adapters gratuitos documentados y credenciales del usuario cuando proceda.

## Pendiente para declarar el alcance 360º completamente terminado

No se consideran terminadas todavía estas áreas de la especificación completa:
- sincronización PSD2 real y renovación de consentimientos;
- parsers específicos de extractos XLSX/OFX/QIF/CAMT/MT940 y perfiles por banco;
- RAG híbrido FTS5 + sqlite-vec con embeddings/reranking local;
- chat financiero con tool registry completo y citas navegables;
- extracción contractual avanzada por página/sección y versionado temporal de cláusulas;
- seguros/coberturas con comparación estructurada completa;
- módulo hipotecario con FEIN/FIAE, vinculaciones, novación/subrogación y curvas variables;
- portfolio completo con trades, tax lots, FX, mercado y riesgo;
- Tax Center por jurisdicción/ejercicio;
- noticias, fundamentales, macro y motores de recomendación;
- stress testing, Financial Graph, cost centers, Decision Outcomes y Repair Center completos;
- backup cifrado/restauración y empaquetado firmado de macOS;
- SQLCipher real en distribución estable.

Estas áreas no se simulan con datos fake ni se presentan como finalizadas. La aplicación base funciona sin ellas y conserva las interfaces/documentación necesarias para implementarlas por fases.

## Cifrado de DB

El repositorio no introduce una falsa sensación de cifrado. El entorno de desarrollo/tests usa SQLite normal únicamente con `FINANCITO_ALLOW_PLAINTEXT_SQLITE=1`. La distribución estable debe integrar SQLCipher (o alternativa auditada) y guardar su clave en Keychain antes de considerar satisfecha la Definition of Done de seguridad.
