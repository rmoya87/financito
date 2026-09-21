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
- activos y pasivos manuales, net worth y ownership; vivienda, vehículos y otros bienes pueden editarse o eliminarse conservando snapshot de auditoría.
- portfolios, securities, trades y FIFO tax lots.
- acciones/ETF/fondos/cripto en modo seguimiento o poseído, con cantidad/unidades, precio y fecha de compra, coste base, último precio persistido, P&L, dividendos y frescura de mercado.
- histórico persistido de los valores seguidos y gráfica comparativa normalizada por rendimiento porcentual, con series diferenciadas y fuente/frescura visibles.
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
- perfil hipotecario persistente con snapshots; desde Documentos una escritura/FEIN puede crear y vincular explícitamente el perfil inicial, y los hechos confirmados pasan a ser reutilizables por Patrimonio y simulaciones.
- motor hipotecario de cuota/intereses y escenarios basados en el mortgage_id real seleccionado; escenario base, amortización, senda de tipos y escaneo de mercado comparten esa selección.
- amortización extraordinaria: reducir cuota vs reducir plazo, con comisión explícita.
- motor de switching con costes, penalizaciones, beneficios perdidos, tax impact y break-even; la vista de mercado formula una conclusión accionable y solo señala una referencia concreta cuando el ahorro neto conocido es positivo y no faltan costes contractuales materiales.
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
- modelo temporal: se conserva fecha/procedencia en fuentes principales y la UI denomina la reconstrucción disponible “Patrimonio en una fecha”; sigue sin existir reconstrucción universal de todas las entidades.
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
- La interfaz de Documentos permite corregir manualmente la vinculación a una ficha existente y muestra cuántos archivos forman el producto.
- La validación en bloque confirma datos coherentes entre los documentos del grupo. Si dos archivos contradicen un mismo campo, el dato queda como `conflicting` y requiere una decisión explícita; no se confirma silenciosamente.
- Seguros consolida todas las fuentes documentales por póliza. Contratos excluye `insurance` y `mortgage`, que permanecen en sus dominios específicos.
- Las tareas de `Para ti` relacionadas con documentos llevan al archivo y a la acción concreta; una conclusión de IA puede marcarse como revisada u ocultarse desde la propia pantalla.
- Inicio admite periodos Este mes, últimos 30/90 días, este año y últimos 12 meses, y el backend calcula ingresos, gasto y ahorro para el intervalo seleccionado.

## Categorización por concepto

- Cambiar la categoría desde Todos los movimientos crea/actualiza una regla persistente `description_exact`.
- La corrección se aplica al histórico completo con el mismo concepto normalizado y a los futuros movimientos iguales.
- Las semánticas especiales (movimiento entre cuentas, reembolsos, ingresos) siguen aplicándose después de la propagación.


### Agrupación provisional y avisos

Cuando un seguro/servicio todavía no tiene datos suficientes para materializar su ficha financiera, un número de póliza/contrato fiable puede crear una agrupación provisional sin inventar prima, fechas ni condiciones. Si no existe identificador fiable, el usuario puede crear explícitamente la ficha de agrupación desde Documentos y enlazar a ella los demás archivos.

Las conclusiones de IA de varios documentos vinculados al mismo producto comparten un único aviso pendiente en `Para ti`. El Dashboard muestra una instrucción breve; el análisis completo permanece en Documentos y el aviso se puede marcar como revisado o descartar allí.


### Casa: vivienda e hipoteca
- Patrimonio incorpora una sección **Casa** inmediatamente después del resumen patrimonial, con valor actual de la vivienda, capital hipotecario pendiente, equity y LTV.
- La hipoteca se puede completar y corregir con capital/cuota/plazo/TIN, TAE, índice y diferencial, periodicidad/próxima revisión y comisiones de apertura, amortización, subrogación o salida.
- Los datos confirmados de la documentación pueden cubrir huecos informativos sin sobrescribir silenciosamente los valores introducidos manualmente.
- Los seguros de hogar/vida/hipoteca relacionados se muestran junto a la vivienda porque pueden modificar el coste efectivo de la financiación.
- Las comisiones completadas en Casa alimentan de verdad los motores de amortización y cambio de hipoteca, incluido el cálculo de costes de salida y punto de equilibrio.
- La comparación de mercado se ejecuta bajo demanda y mantiene capital pendiente y plazo para hacer comparables las cuotas. Las referencias públicas se tratan como benchmark; el ahorro neto definitivo exige incorporar la oferta personalizada/FEIN, seguros vinculados y demás costes.
- La agrupación documental por número de póliza/contrato puede corregir una clasificación inicial distinta y reagrupar anexos procesados antes o después del documento principal.


### Completado documental asistido por IA local
- La IA local recibe una lista de hechos esperables según el dominio y busca de forma sistemática los que todavía no están representados.
- Una clave ya extraída (por ejemplo `differential_rate`) deja de aparecer como simplemente ausente: si aún no está confirmada se presenta como **encontrada, pendiente de validar** con trazabilidad al documento/página.
- Los hechos hipotecarios confirmados completan también el perfil ampliado (`MortgageProfileExtra`): TAE, índice, diferencial, plazo original derivable, revisiones y comisiones. Los valores manuales existentes no se sobrescriben silenciosamente.
- Seguros separa datos encontrados pendientes de revisión de datos realmente no encontrados para prima, franquicia, renovación, preaviso y coste de salida.
- El mismo patrón de búsqueda se aplica a préstamos, energía, telecomunicaciones, contratos generales e informes de inversión, manteniendo confirmación humana para cualquier hecho material antes de usarlo en cálculos.
- No se ha añadido IA cloud ni confirmación automática de condiciones financieras.

- Los análisis documentales están versionados; con Ollama disponible, el arranque reanaliza en segundo plano documentos con análisis antiguo o ausente para aplicar la estrategia de extracción vigente sin volver a subir archivos.


### Gestión contextual de hipotecas, seguros y documentos
- Patrimonio permite mantener varias hipotecas, seleccionar cuál se está revisando, crear nuevas, editar y eliminar la ficha sin borrar los archivos documentales.
- El botón **Documentación** de una hipoteca abre únicamente sus archivos asociados; las subidas desde esa vista quedan vinculadas directamente a esa hipoteca.
- Seguros permite crear una póliza, categorizarla (hogar, coche, vida, salud, mascota, viaje u otro), editarla, eliminarla y abrir exclusivamente su documentación.
- Las pólizas manuales mantienen aseguradora, prima, franquicia, número de póliza, renovación, preaviso y penalización de salida en una única ficha.
- La vista contextual permite asociar un documento existente o desvincularlo del producto sin borrar el archivo del Vault.
- En **Información que falta**, hipotecas y seguros pueden relanzar la IA local solo sobre sus documentos. Si el dato continúa sin encontrarse, los campos compatibles pueden completarse manualmente desde la propia sección y editarse después desde la ficha.
- La biblioteca documental global queda como inventario/entrada para archivos sin asociar, no como gestor principal de hipotecas o pólizas.


## Movimientos previsibles y saldos reales locales (2026-09)

- **Recurrentes**: la detección combina periodicidad e importes por comercio/concepto, normalización de referencias variables y una segunda pasada opcional con la IA local. Las propuestas de la IA solo se convierten en una serie recurrente después de validar matemáticamente al menos tres movimientos y una cadencia compatible.
- Los patrones recurrentes se recalculan de forma ligera tras cada sincronización bancaria y con IA local tras una importación manual o al pulsar **Recalcular patrones**.
- **Próximos 90 días** ya no es solo un calendario de compromisos: incluye todas las ocurrencias futuras de las series recurrentes y previsiones mensuales de categorías con histórico suficientemente estable (p. ej. supermercado, educación, suministros, transporte, seguros, mascotas o suscripciones), mostrando confianza y base histórica.
- **Calidad de los datos** sustituye al nombre ambiguo “Calidad y reconciliación”. Explica problemas accionables de categorización, sincronización bancaria y evidencia documental sin mezclarlos con recomendaciones financieras.
- **Cuentas** distingue dos fuentes de verdad: cuentas conectadas PSD2 con saldo de solo lectura procedente del banco, y cuentas manuales con saldo editable/auditado para ahorro, efectivo o entidades no conectadas.
- Las conexiones PSD2 se refrescan desde el proceso local cada 15 minutos mientras Financito está abierto y también pueden sincronizarse manualmente. No se presenta como streaming en tiempo real porque la frecuencia efectiva depende de la API bancaria.
- Los importes monetarios usan agrupación de miles explícita (por ejemplo, 4.988,93 €) mediante el componente común Money.
