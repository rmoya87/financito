# Providers e integraciones

**Política obligatoria:** ninguna funcionalidad base puede exigir un proveedor de pago. Ver [FREE_CONNECTORS.md](FREE_CONNECTORS.md).

## Patrón

Toda dependencia externa implementa una interfaz estable. El dominio no conoce SDKs concretos.

## BankingProvider

Métodos conceptuales:
- connect
- refresh_consent
- list_accounts
- get_balances
- get_transactions
- disconnect

Requisitos:
- PSD2/Open Banking;
- solo lectura inicial;
- normalización de estados;
- idempotencia;
- rate limiting;
- expiración de consentimiento.

Bankinter y Revolut se integrarán mediante el mecanismo permitido por el proveedor regulado seleccionado o API oficial cuando aplique.

## MarketDataProvider

- quote
- candles
- dividends
- splits
- instrument metadata

## FundamentalDataProvider

- financial statements
- ratios
- estimates si la licencia lo permite

## CryptoProvider

- quotes
- OHLCV
- market metrics
- derivatives cuando proceda
- on-chain cuando sea fiable

## NewsProvider

- búsqueda por entidad;
- feeds;
- canonical URL;
- timestamps;
- fuente.

Priorizar fuentes primarias para resultados, filings y comunicaciones corporativas.

## MacroProvider

- tipos;
- inflación;
- índices;
- divisas;
- indicadores oficiales.

## ComparisonProvider

Familias:
- InsuranceComparisonProvider
- MortgageComparisonProvider
- EnergyComparisonProvider
- TelecomComparisonProvider
- BankProductComparisonProvider

Una oferta debe distinguir:
- dato público;
- estimación;
- oferta personalizada;
- fecha;
- condiciones.

## Caché

Cada provider define TTL por recurso.

Ejemplos:
- precio: corto durante mercado abierto;
- fundamentales: días;
- contratos/documentos: hasta cambio;
- comparadores: según fecha de consulta.

## Fallos

Aplicar:
- timeout;
- retry con backoff;
- circuit breaker cuando aporte valor;
- fallback a caché;
- marca stale.

## Licencias

Antes de producción, documentar términos de uso y permisos de redistribución de cada fuente. No asumir que una API gratuita permite almacenar o mostrar cualquier dato.


## Política de coste

Todo adapter debe declarar:
- free_available;
- requires_paid_plan;
- requires_key;
- official_source;
- fallback_provider;
- manual_fallback.

Un provider de pago puede estudiarse en el futuro, pero nunca convertirse en requisito para funcionalidad base sin cambiar explícitamente la política del producto.
