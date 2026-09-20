# Estado de implementación

Fecha de corte: **2026-09-21**.  
Schema actual: **v11**.

Este documento describe únicamente comportamiento ejecutable en `main`. Los planes futuros viven en `ROADMAP.md`.

## Implementado y verificable

### Runtime, seguridad y privacidad
- FastAPI solo en loopback, validación Host/Origin, sesión local HttpOnly y CSRF; una sesión válida se reutiliza entre pestañas y el cliente renueva/reintenta una vez si el token queda obsoleto.
- CSP y cabeceras defensivas.
- SQLCipher en runtime estable; la clave se obtiene de entorno explícito o Keychain y se crea en Keychain si no existe.
- Modo SQLite sin cifrar bloqueado salvo `FINANCITO_ALLOW_PLAINTEXT_SQLITE=1`.
- secretos de providers mediante keyring; la API solo devuelve estado configurado/no configurado.
- Vault con path canónico, rechazo de symlinks y límites de tamaño/páginas.
- borrado de datos de Financito sin borrar silenciosamente los originales externos del Vault.
- audit log local.

### Movimientos y analítica
- CSV y formatos bancarios estructurados: XLSX/XLSM, QIF, OFX, CAMT/XML y MT940/STA.
- XLSX multi-sección de Bankinter: detección automática de la tabla contabilizada (`Fecha contable / Fecha valor / Descripción / Importe / Saldo / Divisa`), ignorando el bloque previo de movimientos pendientes para evitar duplicados al contabilizarse.
- deduplicación de extractos solapados por referencia bancaria, huella exacta y similitud conservadora; preserva movimientos idénticos legítimos mediante conteo multiconjunto;
- normalización, categorías, reglas y corrección manual auditable sobre un histórico único buscable; las reglas se gestionan en modal; el listado usa paginación de servidor, búsqueda y filtros por categoría/fechas con 25/50/100 filas por página;
- categorización híbrida local: reglas > memoria de comercios verificados > clasificador determinista > similitud por embeddings > LLM local para casos ambiguos; las propuestas de IA no se marcan como verificadas por el usuario.
- splits exactos; detección automática tras importar; `Movimiento entre cuentas` y `Reembolsos` son categorías con semántica contable propia también cuando proceden de reglas o correcciones manuales.
- reembolsos netean gasto y no inflan ingresos en Dashboard, Analytics, Forecast/Stress y Chat.
- recurrentes y detección de movimientos fuera de patrón con explicación de comparación, diferencia y acciones concretas.
- presupuestos y compromisos.
- análisis por categoría/comercio, fijo-variable, esencial-discrecional y series mensuales.
- forecast con baseline comparable, accuracy histórica y Calendar.
- previsión automática de cierre de mes con gasto, ahorro, saldo total y saldo estimado por cuenta, sin repartir compromisos sin evidencia.
- gráficas multi-serie con colores semánticos distintos y navegación activa verde con texto blanco para contraste.
- Laboratorio de decisiones alimentado por perfiles reales guardados, sin defaults financieros de ejemplo; separa liquidez acumulada de ahorro mensual y valida costes contractuales de salida desde evidencia confirmada.
- investigación de mercado bajo demanda sobre fuentes oficiales para hipoteca/seguros, tratada como benchmark hasta disponer de oferta personalizada.
- stress testing y cash runway.

### Banking
- Enable Banking adapter de solo lectura; modo personal restringido para cuentas propias, con saldos reales que alimentan liquidez acumulada y movimientos que alimentan cash-flow.
- listado de ASPSPs e inicio de autorización.
- intercambio de código por sesión persistida.
- mapeo provider-account -> cuenta local por `identification_hash`.
- balances, transacciones paginadas y deduplicación por referencia estable.
- sync explícita, revocación y estado.
- Action Item cuando el consentimiento está a 14 días o menos de expirar.
- no se exponen endpoints públicos de sesión/balances/transacciones crudos.

### Documentos y RAG
- subida múltiple desde la WebApp mediante selector/drag & drop al Vault privado, accesible directamente desde Inicio y desde las áreas relacionadas, más watcher de Vault en segundo plano.
- PDF, TXT, CSV, JSON, DOCX, XLSX/XLSM, PNG/JPEG/HEIC/TIFF/BMP.
- SHA-256, deduplicación, OCR, detección ES/EN y clasificación conservadora.
- hechos contractuales con página y contexto; confirmación humana persistente; los facts confirmados se proyectan automáticamente a Contratos y, cuando existe prima confirmada, a Pólizas, manteniendo enlace al documento fuente.
- análisis interpretativo con LLM local: resumen, ventajas, penalizaciones, obligaciones, riesgos, exclusiones/límites, vinculaciones, oportunidades, puntos de negociación, requisitos para comparar ofertas, impactos cruzados y datos faltantes; visible en Documentos, Seguros, Hipoteca/Laboratorio, Contratos, Cuentas, Inversiones y Fiscalidad.
- propuestas de hechos materiales y coberturas por IA local con whitelist + página obligatoria; permanecen inferidas hasta confirmación. Las coberturas confirmadas se proyectan a CoverageFact y alimentan huecos/duplicidades. Hechos hipotecarios confirmados pueden alimentar el perfil hipotecario únicamente cuando el usuario ha asociado explícitamente el documento a ese préstamo; las ofertas/referencias quedan aisladas del estado actual.
- FTS5/BM25 + embeddings locales opcionales + sqlite-vec/fallback cosine.
- fusión Reciprocal Rank Fusion y reranking léxico.
- búsqueda global y citas que abren documento/página; el chat local recibe además un contexto estructurado con el estado confirmado/inferido de la evidencia.
- reindexado y reconstrucción de derivados conservando evidencia verificada.

### Patrimonio, inversiones y mercado
- resumen patrimonial 360º con patrimonio neto, liquidez, vivienda/inmuebles, vehículos, otros bienes, inversiones reales, hipoteca, otras deudas y seguros; las primas se muestran como coste/protección y nunca como activo.
- activos y pasivos manuales, net worth y ownership.
- portfolios, securities, trades y FIFO tax lots.
- acciones/ETF/fondos/cripto en modo seguimiento o poseído, con compra real, coste base, último precio persistido, P&L, dividendos y frescura de mercado.
- P&L realizado/no realizado.
- Alpha Vantage: quote e histórico bajo demanda y caché local; si no está configurado, está limitado o no devuelve precio, acciones/ETF intentan Stooq como respaldo gratuito retrasado/EOD para no bloquear seguimiento y simulaciones.
- exposición por activo/clase y concentración HHI.
- risk metrics desde históricos.
- CoinGecko: precio y métricas de riesgo.
- SEC EDGAR, ECB y GDELT adapters.
- backtest MA y escenario amortizar-vs-invertir.

### Contratos, seguros, hipoteca y decisiones
- Inicio/Para ti abre directamente el área que resuelve cada tarea y explica qué acción concreta se espera antes de marcarla como resuelta.
- fuente de verdad documental compartida: los campos que no se reconozcan se completan como hechos confirmados dentro del documento, evitando fichas paralelas.
- veredicto transversal de seguros: cruza pólizas/coberturas documentadas con pagos reales, ingresos/ahorro, huecos, duplicidades y productos vinculados; la IA local solo explica el análisis.
- contratos y Action Center de renovación/preaviso.
- pólizas y hechos de cobertura.
- duplicidades solo entre coberturas verificadas.
- requisitos de cobertura definidos por usuario y detección de huecos contra esos requisitos.
- perfil hipotecario persistente con snapshots; motor hipotecario de cuota/intereses y escenarios basados en el mortgage_id real.
- amortización extraordinaria: reducir cuota vs reducir plazo, con comisión explícita.
- motor de switching con costes, penalizaciones, beneficios perdidos, tax impact y break-even.
- beneficios y productos vinculados.
- Decision Case, alternativas, estados y resultado esperado vs observado.
- centros de coste con asignaciones porcentuales; una categoría vinculada agrega automáticamente su gasto de los últimos 12 meses y puede combinarse con contratos/pólizas/activos/deuda.

### Operación
- Configuración de IA local con prueba de generación real de Ollama, diagnóstico de modelo/tag y compatibilidad con variantes locales de Ollama (`/api/generate`/`/api/chat`, `think=false` y embeddings modernos/legacy).
- las rutas estáticas de la WebApp responden HEAD correctamente para prefetch/health checks, evitando falsos 405; el HTML se sirve sin caché para no mezclar una WebApp antigua con un backend recién actualizado.
- backup cifrado AES-256-GCM, clave derivada con scrypt, manifest SHA-256 y extracción TAR segura.
- restore a staging, verificación y aplicación al siguiente arranque.
- Repair Center.
- Health Center con schema real, DB, Vault, frontend, IA y providers.
- export JSON/CSV.
- demo sintética.
- CI backend + frontend.

## Requiere configuración externa, no desarrollo adicional para activarse
- Enable Banking: registro/credenciales y callback válidos.
- Alpha Vantage: key gratuita.
- SEC EDGAR: User-Agent.
- Ollama y modelos locales.
- disponibilidad real de cada banco dentro del proveedor PSD2.

## Parcial por diseño
- extracción contractual: combina reglas deterministas y propuestas del LLM local. Una FEIN/FIAE, póliza o anexo complejo sigue requiriendo revisión humana de hechos materiales antes de influir en cálculos.
- fundamentals: extracción de conceptos SEC seleccionados, no un terminal financiero completo.
- news: búsqueda/ingestión; no existe todavía un motor robusto de impacto/sentimiento.
- portfolio fit/recommendation: scoring determinista disponible, sin asesoramiento personalizado automático.
- modelo temporal: se conserva fecha/procedencia en fuentes principales, pero no existe aún reconstrucción universal “as-of” de todas las entidades.
- accesibilidad: UI responsive y semántica básica, sin auditoría WCAG AA completa.

## No se declara terminado
- reglas fiscales legales versionadas por país/año y presentación fiscal.
- importadores específicos de brokers con todos sus formatos.
- comparadores comerciales de hipoteca, seguros, energía, telecom y depósitos.
- curvas hipotecarias variables/mixtas completas y novación/subrogación contractual automatizada.
- firma, notarización, auto-update y distribución final macOS.
- E2E Playwright y auditoría accesibilidad automatizada completa.

Un elemento de esta sección no se sustituirá con datos ficticios ni supuestos silenciosos.


## Evidencia agrupada por producto

- Documentos deja de tratar cada archivo como un producto financiero independiente. Varios PDFs, anexos, recibos o condiciones pueden enlazarse mediante `EntityLink(evidence_for)` a una única póliza, hipoteca o contrato.
- Los seguros se autoagrupan cuando existe un identificador fuerte coincidente (por ejemplo, número de póliza); proveedor/tipo por sí solos no se usan para fusionar, para evitar falsos positivos.
- Una ficha de seguro puede existir y reunir varios documentos incluso antes de conocer la prima; cuando aparece evidencia suficiente, se proyecta una única póliza y no una por archivo.
- La interfaz de Documentos permite corregir manualmente la vinculación a una ficha existente y muestra cuántos archivos forman el producto.
- La validación en bloque confirma datos coherentes entre los documentos del grupo. Si dos archivos contradicen un mismo campo, el dato queda como `conflicting` y requiere una decisión explícita; no se confirma silenciosamente.
- Seguros consolida todas las fuentes documentales por póliza. Contratos excluye `insurance` y `mortgage`, que permanecen en sus dominios específicos.
- Las tareas de `Para ti` relacionadas con documentos llevan al archivo y a la acción concreta; una conclusión de IA puede marcarse como revisada u ocultarse desde la propia pantalla.
- Inicio admite periodos Este mes, últimos 30/90 días, este año y últimos 12 meses, y el backend calcula ingresos, gasto y ahorro para el intervalo seleccionado.

## Categorización por concepto

- Cambiar la categoría desde Todos los movimientos crea/actualiza una regla persistente `description_exact`.
- La corrección se aplica al histórico completo con el mismo concepto normalizado y a los futuros movimientos iguales.
- Las semánticas especiales (movimiento entre cuentas, reembolsos, ingresos) siguen aplicándose después de la propagación.


### Casa y optimización hipotecaria
- Patrimonio incorpora **Casa** entre el resumen y el resto del detalle patrimonial. Consolida valor de vivienda, capital pendiente, cuota, plazo, TIN, TAE, tipo fijo/variable/mixto, fechas, índice+diferencial, revisiones y comisiones relevantes.
- Los campos ausentes se muestran explícitamente con el motivo por el que hacen falta y pueden completarse desde la propia ficha; la evidencia documental confirmada rellena huecos sin pisar una corrección manual.
- Se calculan equity estimado y LTV usando el valor atribuible de la vivienda y el capital pendiente.
- Los seguros de hogar/vida relacionados se muestran junto a la hipoteca para evaluar el coste efectivo de vinculaciones.
- La comparación de mercado consulta referencias públicas bajo demanda, mantiene capital y plazo pendientes para hacer comparable la cuota y muestra diferencia mensual e intereses restantes. Si existe un coste de salida confirmado, calcula un punto de equilibrio parcial.
- Banco de España aparece como fuente oficial de referencia; las páginas comerciales se tratan como señales públicas, nunca como oferta personalizada. El ahorro neto definitivo requiere incorporar FEIN/oferta, seguros vinculados y todos los costes de cambio.


### Casa: vivienda e hipoteca
- Patrimonio incorpora una sección **Casa** entre el resumen y el resto del patrimonio, con valor actual de vivienda, capital hipotecario pendiente, equity y LTV.
- La ficha hipotecaria permite completar y corregir capital/cuota/plazo/TIN y datos ampliados: capital y plazo iniciales, fechas, TAE, índice de referencia, diferencial, periodicidad/próxima revisión y comisiones de apertura, amortización, subrogación o salida.
- Cuando un dato ampliado falta pero existe evidencia documental confirmada, Casa puede utilizarlo informativamente sin sobrescribir silenciosamente el perfil manual.
- Hogar/vida vinculados se muestran junto a la hipoteca para analizar su coste conjunto y posibles bonificaciones.
- La comparación de mercado se ejecuta bajo demanda: mantiene capital y plazo para hacer comparables las cuotas, muestra diferencia estimada de intereses y, cuando existe una penalización de salida confirmada, un punto de equilibrio parcial.
- Las referencias comerciales se presentan como señales para solicitar novación/subrogación; no se consideran una oferta personalizada. El ahorro neto definitivo requiere incorporar FEIN/oferta, seguros/vinculaciones y todos los costes de cambio.
