# API local

La fuente ejecutable del contrato es **`/api/openapi.json`** y la UI de FastAPI está en **`/api/docs`**.

Base funcional: `/api/v1`.

## Seguridad
1. `GET /api/v1/session` crea una sesión local HttpOnly y devuelve el token CSRF.
2. Toda ruta `/api/v1/*` salvo `session` requiere cookie de sesión.
3. POST/PATCH/PUT/DELETE requieren `X-CSRF-Token`.
4. Host y Origin deben ser loopback.

## Sistema
- `GET /session`
- `GET /health`
- `GET /audit`
- `GET /provider-config`
- `PATCH /provider-config`
- `GET /ai/config`
- `PATCH /ai/config`

## Cuentas y dashboard
- `GET /accounts`
- `POST /accounts`
- `GET /dashboard`
- `GET /categories`
- `GET /budgets`
- `POST /budgets`
- `GET /commitments`
- `POST /commitments`
- `POST /forecast`
- `GET /forecast/accuracy`

## Movimientos
- `GET /transactions`
- `PATCH /transactions/{id}/category`
- `POST /imports/csv`
- `POST /imports/statement?account_id=...`
- `GET /transaction-rules`
- `POST /transaction-rules`
- `DELETE /transaction-rules/{id}`
- `POST /transactions/detect-transfers`
- `POST /transactions/detect-refunds`
- `GET /transactions/review-queue`
- `GET /transactions/{id}/splits`
- `PUT /transactions/{id}/splits`

`/imports/statement` soporta los formatos implementados por `import_formats`: CSV/XLSX/XLSM/QIF/OFX/CAMT/XML/MT940/STA.

## Analytics
- `POST /analytics/refresh`
- `GET /analytics/overview`
- `GET /recurring`
- `GET /anomalies`
- `GET /reconciliation`
- `GET /calendar`
- `POST /stress`
- `POST /backtest/ma`
- `POST /planning/amortize-vs-invest`
- `POST /recommendation/score`
- `GET /graph`

## Search, export y demo
- `GET /search?q=...`
- `GET /export/json`
- `GET /export/transactions.csv`
- `POST /demo/seed`

## Vault, documentos y RAG
- `POST /documents/index`
- `GET /documents`
- `GET /documents/{id}/facts`
- `POST /documents/{id}/reprocess`
- `GET /documents/{id}/file`
- `PATCH /facts/{id}`
- `POST /rag/search`
- `POST /rag/rebuild/{document_id}`
- `POST /chat`

El endpoint `file` valida de nuevo que la ruta pertenezca al Vault y puede abrirse con `#page=N`.

## Open Banking
Superficie pública intencionada:
- `GET /banking/aspsps?country=ES`
- `POST /banking/auth`
- `POST /banking/complete?code=...`
- `GET /banking/connections`
- `POST /banking/connections/{id}/sync`
- `DELETE /banking/connections/{id}`

No existen rutas públicas para leer directamente la sesión PSD2, balances provider-crudos ni transacciones provider-crudas. La lectura pasa por sincronización persistida/deduplicada.

## Patrimonio
- `GET /wealth`
- `GET /assets`
- `POST /assets`
- `GET /liabilities`
- `POST /liabilities`
- `GET /cost-centers`
- `POST /cost-centers`
- `GET /cost-centers/{id}/summary`
- `POST /cost-center-links`

## Inversión y mercado
- `GET /portfolios`
- `POST /portfolios`
- `GET /portfolios/{id}/exposure`
- `GET /securities`
- `POST /securities`
- `POST /trades`
- `GET /market/quote/{symbol}`
- `GET /market/security/{id}/history`
- `POST /market/security/{id}/refresh`
- `GET /market/security/{id}/risk`
- `POST /risk/calculate`
- `GET /crypto/price`
- `GET /crypto/metrics/{coin_id}`
- `GET /fundamentals/sec/{cik}`
- `GET /macro/ecb/{flow}/{key}`
- `GET /news/search`
- `POST /news/ingest`

## Contratos y seguros
- `GET /contracts`
- `POST /contracts`
- `GET /insurance`
- `POST /insurance`
- `GET /coverage`
- `POST /coverage`
- `POST /coverage/compare`
- `GET /coverage/overlaps`
- `POST /coverage/overlaps/scan`
- `GET /coverage-requirements`
- `POST /coverage-requirements`
- `DELETE /coverage-requirements/{id}`
- `GET /coverage/gaps`
- `GET /benefits`
- `POST /benefits`
- `POST /linked-products`

## Hipoteca y optimización
- `POST /mortgage/scenario`
- `POST /mortgage/prepayment`
- `POST /optimization/calculate`

La penalización desconocida en optimización se representa como `null` y produce `needs_more_data`.

## Objetivos y decisiones
- `GET /goals`
- `POST /goals`
- `PATCH /goals/{id}`
- `GET /decisions`
- `POST /decisions`
- `GET /decisions/{id}`
- `PATCH /decisions/{id}`
- `POST /decisions/{id}/alternatives`
- `POST /decisions/{id}/outcomes`
- `GET /model-evaluations`
- `POST /model-evaluations`

## Acción, integridad, backup y privacidad
- `GET /actions`
- `PATCH /actions/{id}`
- `GET /repair`
- `POST /repair/{id}`
- `POST /backups`
- `POST /backups/restore`
- `GET /privacy/summary`
- `POST /privacy/rebuild-derived`
- `DELETE /privacy/data`

## Fiscalidad
- `POST /tax/estimate`

Es una estimación parametrizada, no un motor normativo legal por jurisdicción/año.

## Compatibilidad
Los nombres y payloads de OpenAPI son la referencia última. Si este documento y `/api/openapi.json` difieren, debe corregirse la documentación en el mismo cambio.
