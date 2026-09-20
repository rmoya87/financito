# Arquitectura backend local

## Objetivo

Backend modular, rápido, testeable y completamente local.

## Stack

- Python
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- SQLite + SQLCipher
- FTS5
- sqlite-vec
- asyncio para I/O
- procesos o worker pool para CPU pesado

## Regla de dependencias

presentation → application → domain. Infrastructure implementa contratos de application/domain. Domain no importa FastAPI, SQLAlchemy, providers ni LLM.

## Bounded contexts

Cada módulo separa entities, value objects, policies, services y ports; application separa commands, queries, handlers y DTO; infrastructure contiene repositories y adapters.

## Shared kernel mínimo

- Money
- Currency
- Percentage
- DateRange
- SourceRef
- Freshness
- Result/Error
- IDs

Evitar un utils.py global.

## Money

Usar Decimal, con redondeo y precisión definidos. Nunca float para cuotas, saldos, impuestos, penalizaciones, comisiones o ahorro neto.

## Repositories y Unit of Work

Interfaces en dominio/aplicación e implementaciones SQLite en infraestructura. Usar transacciones explícitas para operaciones multi-tabla.

Evitar repositorios genéricos gigantes.

## Lecturas

Para vistas complejas usar query services y projections específicas. No hidratar grafos completos innecesariamente.

## SQLite

Cada migración debe revisar índices y planes de consulta. Activar WAL si es compatible con la configuración de cifrado seleccionada.

## Jobs

Separar I/O de CPU:
- I/O: providers, filesystem, sync.
- CPU: OCR, embeddings, parsing pesado, backtests.

No bloquear el event loop.

## Scheduler

Un scheduler local central con metadata persistente, locks, idempotency keys, retries y backoff.

No introducir Redis ni Celery en la primera versión.

## Provider clients

Cada provider reutiliza sesión HTTP, define timeouts, retry selectivo, rate limiting, caché y errores tipados. No crear un cliente HTTP nuevo por petición.

## RAG

Separar ingestion, extraction, chunking, embedding, indexing, retrieval, reranking y orchestration. Cada pipeline debe poder reanudarse.

## IA

LLM local mediante adapter. Prohibido ejecutar SQL generado directamente por el LLM, shell arbitrario, acceso libre a filesystem o URL fetch arbitrario.

Tool registry con allowlist y schemas validados.

## API

Endpoints finos: validación, sesión, handler y serialización. No colocar reglas de negocio en routers.

## Errores

Jerarquía estable:
- ValidationError
- NotFound
- Conflict
- ProviderUnavailable
- StaleData
- SecurityError
- CalculationError

Mapeo central a códigos HTTP.

## Observabilidad local

Structured logging con request id, job id, provider, latencia, cache hit y error code. Nunca payloads sensibles.

## Rendimiento

- conexión SQLite adecuada;
- batch insert;
- upsert;
- sincronización incremental;
- índices;
- cursor pagination;
- caché TTL;
- evitar N+1;
- streaming de archivos;
- no cargar documentos completos en RAM si no hace falta.

## Dependencias

Cada dependencia nueva debe justificar función, tamaño, mantenimiento, licencia y seguridad.

## Tests

Dominio sin DB, repositorios con SQLite temporal, migraciones, API, providers con fakes y property-based tests para cálculos críticos cuando aporte valor.
