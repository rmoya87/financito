# Providers e integraciones

Ninguna función base exige un proveedor de pago. Los adapters externos son opcionales y los secretos se guardan en el credential store del sistema.

## IA local — Ollama
- endpoint permitido: únicamente loopback;
- modelos de chat y embeddings seleccionables desde Configuración;
- si no está disponible, la app sigue operativa y el chat devuelve cálculos estructurados sin explicación LLM.

## Open Banking — Enable Banking
Credenciales:
- App ID;
- clave RSA privada.

Flujo público:
1. listar ASPSPs por país;
2. iniciar autorización en el banco;
3. completar el callback;
4. persistir conexión/cuentas;
5. sincronizar balances/movimientos;
6. revocar.

Características:
- solo lectura;
- dedupe estable;
- paginación;
- consentimiento con fecha de expiración;
- aviso de renovación;
- no se exponen sesiones ni movimientos provider-crudos mediante la API pública.

Que Bankinter, Revolut u otra entidad aparezca depende del catálogo real del proveedor/país.

## Alpha Vantage
Uso:
- quote;
- histórico diario compacto;
- actualización manual desde cartera;
- persistencia local de observaciones.

Requiere API key gratuita. No se refresca en background para no consumir cuota sin control.

## CoinGecko
Uso:
- simple price;
- market chart;
- volatilidad/drawdown y otras métricas calculadas localmente.

La Demo key se puede guardar en Configuración; el adapter tolera modalidad sin key cuando el endpoint lo permite.

## SEC EDGAR
- `companyfacts`;
- conceptos US-GAAP seleccionados.

Requiere un User-Agent identificable conforme a las prácticas de SEC. No pretende sustituir un feed global de fundamentales.

## ECB
Series SDMX del Banco Central Europeo. No requiere secreto.

## GDELT
Búsqueda/ingestión de noticias y deduplicación por URL canónica. No existe todavía scoring robusto de impacto/sentimiento.

## Seguridad de credenciales
El frontend nunca lee el valor guardado. `GET /provider-config` solo informa de si existe cada secreto. Variables de entorno se mantienen como fallback de desarrollo.

## Política de frescura
Cada dato persistido conserva, cuando aplica:
- provider;
- timestamp/fecha;
- fetched_at;
- delayed.

Un dato externo no se presenta como dato en tiempo real si el proveedor lo marca retrasado.


## Conexión bancaria personal restringida

Para uso personal sin desplegar un agregador propio, Financito soporta Enable Banking en modo Production restringido:
1. crear una aplicación Production en el Control Panel;
2. registrar las redirect URLs autorizadas;
3. generar/guardar la clave RSA privada;
4. activar el modo restringido enlazando las propias cuentas;
5. guardar App ID y clave privada en el Keychain desde Configuración;
6. autorizar cada cuenta desde **Banca conectada**.

La sincronización actualiza saldo disponible/contable expuesto por el ASPSP y movimientos contabilizados. Estos saldos alimentan la liquidez acumulada del Decision Lab. El acceso PSD2 a cuentas de pago no implica que el banco exponga el capital hipotecario pendiente: ese dato sigue procediendo del perfil hipotecario y de documentación contractual.

## Investigación pública de hipotecas y seguros

El provider de investigación de mercado se ejecuta bajo demanda. Consulta una lista acotada de páginas oficiales de entidades y extrae únicamente señales explícitas (TIN/TAE visibles, subrogación, comisiones, vinculaciones, promociones).

El resultado es descubrimiento de candidatos. No sustituye una FEIN, estudio de riesgo, tarificación de seguro ni oferta vinculante.
