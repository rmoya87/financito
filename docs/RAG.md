# RAG local

## Objetivo

Responder sobre documentación y datos privados con recuperación verificable y sin enviar contenido a una IA cloud.

## Pipeline

```text
Pregunta
  -> clasificación de intención
  -> query expansion local
  -> filtros de metadatos
  -> BM25/FTS5
  -> búsqueda vectorial
  -> fusión
  -> reranking
  -> context builder
  -> tools/cálculos si proceden
  -> LLM local
  -> respuesta + citas
```

## Ingestión

Para cada fichero:
1. validar extensión y tamaño;
2. SHA-256;
3. deduplicar;
4. extraer texto;
5. OCR si el texto es insuficiente;
6. detectar idioma;
7. clasificar;
8. extraer metadatos;
9. detectar tablas/cláusulas;
10. chunking semántico;
11. embeddings;
12. FTS;
13. persistir trazabilidad.

## Chunking

No usar únicamente ventanas fijas.

Preservar:
- documento;
- página;
- sección;
- encabezado;
- rango;
- orden.

Orientación inicial:
- 400–800 tokens;
- overlap 50–100;
- tablas y cláusulas indivisibles cuando sea posible.

## Embeddings

Requisitos:
- local;
- multilingüe;
- español/inglés;
- versión registrada;
- posibilidad de reindexar al cambiar de modelo.

La implementación debe comparar modelos E5/BGE multilingües u opciones equivalentes antes de fijar uno.

## Recuperación híbrida

Combinar:
- BM25;
- similitud vectorial;
- metadatos;
- boost por tipo de documento;
- recencia solo cuando tenga sentido.

Usar Reciprocal Rank Fusion o técnica equivalente.

## Reranking

Aplicar reranker local cuando el coste/latencia lo justifique.

Registrar:
- score léxico;
- score vectorial;
- score final;
- chunks seleccionados.

## Citas

Toda respuesta documental debe incluir:
- document_id;
- nombre;
- página;
- chunk;
- fragmento mínimo de soporte.

La UI debe poder abrir el documento en la página citada.

## Consultas híbridas

Una pregunta puede requerir simultáneamente:
- RAG documental;
- SQL estructurado;
- motor financiero;
- dato de mercado.

Ejemplo: “¿Me compensa cambiar la hipoteca?” no se responde solo con embeddings.

## Anti-alucinación

Si la evidencia no contiene un dato:
- no inferirlo como hecho;
- declarar ausencia;
- pedir/configurar la fuente necesaria mediante UI.

Nunca rellenar penalizaciones, tipos o coberturas con supuestos silenciosos.

## Evaluación

Dataset de pruebas:
- answerable;
- unanswerable;
- multi-document;
- OCR;
- tablas;
- español;
- inglés;
- documentos contradictorios.

Métricas:
- recall@k;
- precision@k;
- MRR;
- faithfulness;
- citation accuracy;
- latency.
