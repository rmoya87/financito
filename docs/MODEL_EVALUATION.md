# Evaluación continua de IA y modelos

## Objetivo

Impedir regresiones al cambiar OCR, embeddings, reranker, LLM, prompts o clasificadores.

## Suites versionadas

- transaction categorization;
- merchant normalization;
- contract extraction;
- OCR;
- RAG retrieval;
- citation correctness;
- abstention;
- prompt injection;
- tool selection;
- structured extraction.

## Golden synthetic dataset

Solo datos sintéticos y públicos permitidos.

## Comparación

Cada cambio de modelo debe comparar versión actual vs candidata.

Métricas según tarea:
- accuracy/F1;
- precision/recall;
- recall@k;
- MRR;
- faithfulness;
- citation accuracy;
- abstention accuracy;
- latency;
- RAM.

## Gate

No promover modelo nuevo si empeora materialmente una métrica crítica sin justificación documentada.

## Reproducibilidad

Guardar:
- model version/hash;
- prompt version;
- embedding version;
- parameters;
- dataset version.
