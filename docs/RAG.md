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


## Ciclo de vida de la evidencia y uso global

Un documento del Vault tiene dos niveles de uso deliberadamente separados:

1. **Disponible inmediatamente como contexto documental**: al indexarse queda en FTS/RAG y puede recuperarse desde búsqueda y chat local con página de origen.
2. **Dato material estructurado pendiente**: TIN/TAE, costes, preavisos, renovaciones, franquicias, penalizaciones y productos vinculados se guardan inicialmente como `inferred`. No se convierten en cifras contractuales confirmadas por el mero hecho de haber sido extraídos.
3. **Confirmación humana**: desde **Documentos y evidencia** el usuario confirma o marca como dudoso cada hecho material.
4. **Proyección automática**: los hechos `confirmed + user_verified` se sincronizan con las entidades estructuradas que pueden utilizarlos. Actualmente se proyectan a Contratos y, cuando existe una prima confirmada, a Pólizas de seguro. Las entidades conservan enlace al documento fuente.
5. **Consumo posterior**: Contratos/Seguros, Action Center y el contexto estructurado de la IA local utilizan la proyección confirmada. El chat recibe además el estado de los hechos documentales y debe distinguir confirmados de inferidos/dudosos.
6. **Reconciliación al arranque y reprocesado**: Financito vuelve a sincronizar las proyecciones existentes y conserva los hechos ya verificados por el usuario.

No se crean importes cero para datos ausentes. Tampoco se genera automáticamente un compromiso de forecast a partir de una renovación si el documento no aporta evidencia suficiente de que esa fecha sea una fecha real de cobro; así se evita doble contabilización con movimientos/recurrentes bancarios.

La tarea `review_document_evidence` enlaza directamente con el documento. Se completa automáticamente cuando ya no quedan hechos materiales pendientes de revisión y desaparece de **Pendiente de ti**.
