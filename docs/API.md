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
- PATCH /transactions/{id}
- POST /transactions/import
- GET /transactions/categories
- POST /transaction-rules

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
