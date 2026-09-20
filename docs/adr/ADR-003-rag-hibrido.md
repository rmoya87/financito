# ADR-003 — RAG híbrido local

Status: Accepted

## Decision

Combinar FTS/BM25 + vector search + filtros + reranking local.

## Rationale

La documentación financiera contiene números, nombres exactos y lenguaje semántico. Ni keyword-only ni vector-only cubren todos los casos.

## Consequences

Se debe medir retrieval y conservar scores/trazabilidad para depuración.
