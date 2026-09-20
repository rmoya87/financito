# Estrategia de conectores gratuitos

## Regla no negociable

Financito debe ser utilizable sin pagar suscripciones a proveedores de datos, agregadores bancarios, APIs de mercado o servicios de IA.

Se permiten servicios externos gratuitos siempre que:
- no requieran coste recurrente;
- sus términos permitan el uso previsto;
- el usuario proporcione sus propias credenciales/API keys cuando proceda;
- exista fallback local si dejan de estar disponibles;
- no sean una fuente única de verdad cuando exista alternativa oficial.

## Banca

### Opción automática preferida: Enable Banking en modo restringido de cuentas propias

La documentación pública actual de Enable Banking permite crear una aplicación de producción restringida y vincular únicamente las propias cuentas antes de firmar un contrato comercial.

Bajo los términos públicos aplicables antes de acuerdo comercial, Control Panel/API se ofrecen sin coste. La aplicación debe verificar estas condiciones en cada implementación/upgrade porque pueden cambiar.

Uso:
- solo Account Information;
- solo cuentas del usuario;
- read-only;
- sin Payment Initiation;
- consentimiento mediante SCA del banco;
- tokens en Keychain;
- datos persistidos localmente.

Bankinter aparece documentado entre los principales ASPSP españoles y Enable Banking describe su flujo de autenticación.

Para Revolut:
- consultar Meta/ASPSP coverage en runtime;
- si está disponible en el modo restringido, integrarlo;
- si no, usar importación local oficial.

Nunca asumir que la disponibilidad de un banco es permanente.

### Fallback obligatorio: importación local

Debe soportar:
- CSV;
- Excel/XLSX;
- OFX;
- QIF;
- CAMT.053 cuando exista;
- MT940 cuando exista;
- PDF como último fallback estructurado/OCR.

Pipeline:
archivo → fingerprint → parser → normalize → deduplicate → reconcile → categorize → analytics.

Revolut Personal permite generar extractos por divisa en PDF o Excel; también existen extractos de inversión y documentos consolidados. Esto permite operar sin API bancaria.

Para cualquier banco no conectado automáticamente, un parser/import profile local debe permitir mapear columnas y guardar el mapping para futuras importaciones.

## Regla de resiliencia bancaria

Financito nunca deja de funcionar porque el conector automático no esté disponible.

Orden:
1. Open Banking gratuito si es válido;
2. formato estructurado oficial;
3. CSV/Excel;
4. PDF/OCR;
5. entrada manual.

## Bolsa

### Datos de mercado gratuitos

Crear MarketDataProvider con varias fuentes gratuitas y capacidad de fallback.

Fuente inicial permitida:
- Alpha Vantage free API key para funciones disponibles en su plan gratuito.

No utilizar endpoints premium como requisito.

Reglas:
- cache local agresiva según TTL;
- no consultar un símbolo repetidamente;
- batch cuando el plan lo permita;
- marcar delayed/realtime según fuente;
- nunca presentar datos retrasados como tiempo real.

Si un dato necesario es premium:
- buscar alternativa gratuita;
- degradar funcionalidad;
- permitir import manual;
- nunca exigir pago.

## Fundamentales

Prioridad:
1. fuente regulatoria/oficial;
2. Investor Relations;
3. API gratuita.

### Estados Unidos

SEC EDGAR/data.sec.gov:
- sin API key;
- filings;
- submissions;
- XBRL companyfacts;
- actualización durante el día.

Guardar accession/filing/source para trazabilidad.

### Europa/España

Preferir:
- CNMV;
- Euronext/bolsa/fuente regulatoria cuando el acceso automatizado y términos lo permitan;
- páginas oficiales de Investor Relations;
- informes XBRL/ESEF públicos.

Evitar scraping frágil si existe feed/API/documento público descargable.

## Cripto

Orden:
1. APIs públicas de exchanges para precio/mercado cuando no requieran cuenta;
2. CoinGecko Demo API gratuita;
3. Alpha Vantage funciones crypto gratuitas disponibles;
4. importación de operaciones/extractos.

Si se conectan cuentas de exchange:
- API key read-only;
- sin trading;
- sin withdrawal;
- scopes mínimos;
- rechazar scopes excesivos cuando puedan inspeccionarse.

## Divisas y macro

Fuente primaria:
- ECB Data Portal / SDMX para EUR, tipos y series macro europeas.

Sin proveedor comercial como requisito.

Otras fuentes públicas gratuitas pueden añadirse detrás de MacroProvider.

## Noticias

Prioridad:
1. regulador;
2. filings;
3. Investor Relations/RSS;
4. fuentes gratuitas tipo GDELT para descubrimiento;
5. medios accesibles legalmente.

La fuente primaria prevalece para hechos corporativos.

No depender de APIs premium de noticias.

Guardar:
- source;
- url;
- published_at;
- event_date;
- retrieved_at;
- entity links;
- reliability.

## Comparadores

Seguros, hipotecas, energía, telecom y bancos no deben depender de comparadores de pago.

Fuentes:
- páginas oficiales;
- PDFs/tarifarios;
- APIs públicas;
- comparadores gratuitos accesibles al usuario;
- ofertas manuales cargadas por documento.

Regla:
una oferta pública es una referencia, no una oferta personalizada.

## IA

Coste obligatorio: 0 €.

- LLM local;
- embeddings locales;
- reranking local;
- OCR local.

Nunca requerir API de pago.

## API keys gratuitas

Todas las keys:
- aportadas/configuradas por usuario;
- Keychain;
- nunca repo;
- nunca frontend;
- nunca logs.

La aplicación debe mostrar:
- proveedor;
- tier conocido;
- última comprobación;
- limitaciones;
- rate-limit status si puede inferirse.

## Rate limits

La arquitectura debe diseñarse para free tiers:
- cache;
- batch;
- sync incremental;
- ETags/Last-Modified;
- scheduler conservador;
- refresh bajo demanda;
- backoff.

## Provider health

Cada provider:
- available;
- degraded;
- rate_limited;
- auth_required;
- unavailable.

La aplicación cambia automáticamente a fallback cuando sea seguro.

## Nunca hacer

- scraping de banca con contraseña;
- automatización de navegador para login bancario;
- guardar credenciales del banco;
- saltarse SCA;
- endpoints privados no documentados;
- reverse-engineering de apps bancarias;
- requerir un servicio comercial para abrir Financito.

## Criterio de aceptación

La versión estable de Financito debe poder:
- importar todas las cuentas manualmente sin coste;
- analizar gastos;
- mantener patrimonio;
- usar RAG/IA local;
- analizar inversiones con datos gratuitos;
- usar macro oficial;
- analizar documentos;
- generar decisiones;

aunque no exista ninguna suscripción externa.
