# RAG local — implementación actual

## Objetivo
Recuperar evidencia documental privada sin enviar documentos ni consultas financieras a IA cloud.

## Ingestión
1. validar que el archivo está dentro del Vault;
2. rechazar symlinks, >50 MB y PDF >500 páginas;
3. SHA-256 y deduplicación;
4. extracción/OCR;
5. idioma y clasificación;
6. hechos estructurados conservadores;
7. chunks con página;
8. FTS5;
9. embeddings locales opcionales;
10. sqlite-vec cuando está disponible.

Formatos: PDF, TXT, CSV, JSON, DOCX, XLSX/XLSM, PNG/JPEG/HEIC/TIFF/BMP.

## Chunking real
`chunks_for` agrupa párrafos hasta ~2600 caracteres con overlap de 300. En PDF se procesa por página, por lo que `page_start/page_end` se conserva.

No se describe como “chunking semántico perfecto”: es un algoritmo determinista por párrafos.

## Recuperación híbrida
- FTS5 + BM25;
- embedding de consulta mediante Ollama si está configurado;
- sqlite-vec para ANN; si falla/no está disponible, cosine sobre embeddings persistidos;
- Reciprocal Rank Fusion entre lexical/vector;
- ajuste final por overlap de tokens de consulta.

No hay actualmente un cross-encoder/reranker neuronal separado.

## Evidencia
Cada resultado incluye:
- chunk_id;
- document_id;
- nombre;
- página;
- texto;
- score.

Documentos, Search y Chat abren el archivo original en la página citada.

## Hechos contractuales
La extracción detecta actualmente, cuando el texto lo permite:
- preaviso;
- penalización/comisión;
- coste anual/mensual;
- franquicia;
- TIN/TAE;
- permanencia/renovación.

Se guarda página y contexto. Los hechos materiales permanecen `inferred` hasta confirmación y el reprocesado conserva facts verificados.

## Regla de seguridad
“No encontrado” no equivale a cero. Si falta comisión, penalización, cobertura o preaviso necesario para una conclusión, el motor debe exponer falta de evidencia.

## Reindexado
`privacy/rebuild-derived` puede reconstruir chunks, FTS/vector y derivados manteniendo los datos fuente y hechos confirmados.
