# Rendimiento y eficiencia

## Principio

Optimizar primero arquitectura, acceso a datos y trabajo realizado. No añadir cachés, memoización o concurrencia sin entender el cuello de botella.

## Presupuestos funcionales

Objetivos en un Mac soportado, excluyendo llamadas externas y ejecución LLM:

- navegación entre vistas ya cargadas: inmediata para percepción humana;
- endpoints de lectura simples: objetivo p95 < 100 ms;
- búsquedas locales comunes: objetivo p95 < 200 ms;
- tablas: no cargar más filas de las necesarias;
- UI: sin tareas largas en main thread;
- inicio: mostrar shell/skeleton antes de terminar jobs secundarios.

Son objetivos de ingeniería, no garantías contractuales; deben medirse en CI/perfilado y ajustarse con evidencia.

## Frontend

### Bundle
- dividir por ruta;
- lazy-load de gráficas, preview PDF y editores pesados;
- no importar módulos de toda la app desde barrels globales;
- revisar dependencias duplicadas;
- budget por ruta y alerta ante regresiones.

### Render
- listas grandes virtualizadas;
- componentes pequeños;
- memoización solo si profiling la justifica;
- evitar providers/context globales que rerendericen toda la app;
- selectors finos.

### Datos
- paginación cursor;
- filtros en backend;
- agregaciones en backend/SQL;
- no descargar todos los movimientos para calcular una gráfica;
- TanStack Query con staleTime por recurso;
- invalidación concreta, no global.

## Backend

### SQLite
- índices basados en consultas reales;
- EXPLAIN QUERY PLAN para endpoints calientes;
- WAL si es compatible;
- batch inserts;
- upsert;
- transacciones cortas;
- evitar N+1;
- projections.

### Procesamiento
- I/O async;
- CPU pesado fuera del event loop;
- pipelines reanudables;
- incremental processing;
- deduplicación antes de OCR/embedding;
- batch embeddings.

### Providers
- sesión HTTP reutilizable;
- cache TTL;
- sync incremental;
- rate limiting;
- retry solo en errores recuperables.

## RAG

No ejecutar el pipeline más caro para toda pregunta.

Router:
1. consulta estructurada SQL si resuelve;
2. FTS exacta si procede;
3. hybrid RAG cuando necesita semántica;
4. reranking solo cuando aporta;
5. LLM local al final.

Cachear solo derivados seguros y versionados.

## IA local

ModelRouter:
- pequeño para clasificación;
- embeddings separados;
- medio para RAG;
- grande solo para razonamiento complejo.

No usar LLM para:
- sumar;
- filtrar;
- ordenar;
- convertir moneda;
- calcular hipoteca;
- calcular riesgo;
- buscar coincidencias exactas.

## Jobs

Prioridades:
- interacción usuario;
- sincronización;
- ingestión;
- reindexado;
- backtests masivos.

Evitar que embeddings/backtests degraden la UI.

## Memoria

- streaming para documentos;
- no cargar PDFs completos si basta una página;
- cachés con límites LRU;
- liberar modelos no usados si el runtime lo permite;
- tamaño de batch configurable según RAM.

## Medición

Developer Mode local:
- endpoint latency;
- DB time;
- provider time;
- cache hit;
- rows scanned;
- RAG stages;
- embedding time;
- LLM tokens/latency;
- job queue.

## Regresiones

Toda optimización significativa debe tener medición antes/después. Si una feature aumenta claramente bundle, queries o tiempo de respuesta, documentar la razón.
