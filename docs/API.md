# Contrato API local

## Convenciones

Base:
```text
/api/v1
```

JSON salvo streaming/archivos.

Errores:
```json
{
  "error": {
    "code": "MACHINE_CODE",
    "message": "Mensaje legible",
    "details": {}
  }
}
```

## Health

- GET /health
- GET /status

## Perfil

- GET /profile
- PATCH /profile
- GET /financial-profile
- PATCH /financial-profile

## Cuentas

- GET /accounts
- GET /accounts/{id}
- POST /banking/connections
- POST /banking/connections/{id}/sync
- DELETE /banking/connections/{id}

## Movimientos

- GET /transactions
- GET /transactions/{id}
- PATCH /transactions/{id}
- POST /transactions/import
- POST /transactions/{id}/split
- DELETE /transactions/{id}/split
- POST /transactions/{id}/verify-category
- POST /transactions/reclassify
- GET /transactions/categories
- GET /transactions/review-queue
- GET /transactions/anomalies
- POST /transactions/anomalies/{id}/resolve
- GET /merchants
- PATCH /merchants/{id}
- GET /transaction-rules
- POST /transaction-rules
- PATCH /transaction-rules/{id}
- DELETE /transaction-rules/{id}

Filtros:
- from;
- to;
- account;
- category;
- merchant;
- query;
- recurring;
- page/cursor.

## Documentos

- GET /documents
- GET /documents/{id}
- POST /documents/scan
- POST /documents/{id}/reindex
- PATCH /documents/{id}
- GET /documents/{id}/facts
- GET /documents/{id}/pages/{page}

## Vault

- GET /vault
- PUT /vault/config
- POST /vault/rescan

## Patrimonio

- GET /net-worth
- GET /net-worth/history

## Portfolio

- GET /portfolios
- GET /portfolios/{id}
- GET /portfolios/{id}/risk
- POST /portfolios/import

## Mercado

- GET /market/instruments/{id}
- GET /market/instruments/{id}/history
- GET /market/instruments/{id}/fundamentals
- GET /market/instruments/{id}/news

## Hipoteca

- GET /mortgages
- GET /mortgages/{id}
- POST /mortgages/{id}/scenarios
- POST /mortgages/{id}/compare

## Optimización

- GET /opportunities
- GET /opportunities/{id}
- POST /opportunities/refresh
- POST /opportunities/{id}/decision

## Chat

- POST /chat/sessions
- GET /chat/sessions
- GET /chat/sessions/{id}
- POST /chat/sessions/{id}/messages
- GET /chat/sessions/{id}/stream

Streaming preferente por SSE.

## Jobs

- GET /jobs/{id}
- GET /jobs/{id}/events
- POST /jobs/{id}/cancel cuando sea seguro.

## Respuestas evidenciadas

Para análisis:
```json
{
  "result": {},
  "sources": [],
  "calculations": [],
  "confidence": 0.82,
  "dataFreshness": {}
}
```

## OpenAPI

FastAPI es fuente del schema. El frontend debe generar/validar tipos a partir de OpenAPI para reducir drift.


## Analytics e insights

- GET /analytics/cash-flow
- GET /analytics/spending/by-category
- GET /analytics/spending/by-merchant
- GET /analytics/spending/fixed-vs-variable
- GET /analytics/spending/essential-vs-discretionary
- GET /analytics/spending/trends
- GET /analytics/budget-vs-actual
- GET /analytics/net-worth
- GET /analytics/debt
- GET /insights
- POST /insights/refresh
- POST /insights/{id}/dismiss

Toda agregación para gráficas se calcula en backend/SQL. El frontend no recibe datasets completos si puede recibir series agregadas.

## Presupuestos

- GET /budgets
- POST /budgets
- PATCH /budgets/{id}
- DELETE /budgets/{id}
- GET /budgets/forecast

## Objetivos

- GET /goals
- POST /goals
- PATCH /goals/{id}
- DELETE /goals/{id}
- GET /goals/{id}/projection

## Decisiones y escenarios

- POST /decisions
- GET /decisions
- GET /decisions/{id}
- POST /decisions/{id}/recalculate
- POST /decisions/{id}/alternatives
- POST /decisions/{id}/select
- GET /decisions/{id}/impact

Las respuestas deben incluir alternatives, assumptions, calculations, sources, confidence y dataFreshness.

## Data quality

- GET /data-quality/issues
- POST /data-quality/issues/{id}/resolve
- POST /data-quality/reconcile
- GET /data-quality/summary

## Calendar y alertas

- GET /calendar/events
- GET /alerts
- PATCH /alerts/{id}
- POST /alerts/{id}/dismiss

## Sistema local

- GET /system/health
- GET /system/models
- POST /system/models/verify
- GET /system/audit
- POST /backup
- POST /restore
- POST /export

## Convención monetaria

Importes monetarios críticos viajan como decimal string o formato tipado acordado, nunca como float de precisión no controlada.

## Convención de paginación

Para colecciones grandes usar cursor pagination. Evitar offset profundo salvo datasets pequeños.

## Idempotencia

Imports, sincronizaciones, reindexados y operaciones repetibles deben aceptar o generar idempotency keys cuando exista riesgo de duplicación.


## Evidencia contractual

- GET /contracts/{id}/facts
- GET /contracts/{id}/conflicts
- POST /contracts/{id}/facts/{factId}/verify
- PATCH /contracts/{id}/facts/{factId}
- GET /calculations/{id}/trace

Los facts devuelven documentId, page, section, confidence, status, effective dates y evidencia necesaria para abrir la fuente.

Nunca convertir not_found en 0.


## Forecasting

- GET /forecast
- POST /forecast/recalculate
- GET /forecast/history
- GET /forecast/accuracy
- GET /forecast/categories
- GET /forecast/compare-last-year

Parámetros:
- from;
- to;
- scenario;
- include_extraordinary;
- account;
- category.

Respuesta:
- predictedIncome;
- predictedExpenses;
- predictedSavings;
- predictedLiquidity;
- lowerBound;
- upperBound;
- samePeriodLastYear;
- drivers;
- accuracy;
- knownVsEstimated.

## Commitments

- GET /commitments
- POST /commitments
- PATCH /commitments/{id}
- DELETE /commitments/{id}
- GET /commitments/timeline

## Stress testing

- POST /stress-tests
- GET /stress-tests/{id}

## Cost centers

- GET /cost-centers
- POST /cost-centers
- GET /cost-centers/{id}/analytics
- POST /cost-centers/{id}/links

## Coverage

- GET /coverage
- GET /coverage/overlaps
- GET /coverage/gaps
- POST /coverage/refresh

## Financial Graph

- GET /entities/{type}/{id}/relations
- GET /entities/{type}/{id}/impact

## Decision outcomes

- GET /decisions/{id}/outcomes
- POST /decisions/{id}/outcomes
- GET /decisions/{id}/change-explanation

## Repair Center

- GET /repair/issues
- POST /repair/scan
- POST /repair/issues/{id}/repair
- POST /repair/rebuild-fts
- POST /repair/rebuild-vectors

## Model evaluation

- GET /model-evaluations
- POST /model-evaluations/run
- GET /model-evaluations/{id}
