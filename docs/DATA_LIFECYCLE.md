# Ciclo de vida y procedencia de datos

## Principio

Todo dato debe poder responder de dónde viene, cuándo se obtuvo, qué transformación sufrió, qué confianza tiene y qué depende de él.

## Etapas

raw → normalized → enriched → derived → presented.

Nunca sobrescribir el raw si es necesario para auditoría.

## Provenance

Campos conceptuales:
- source_type;
- provider;
- source_id;
- source_location;
- fetched_at;
- effective_at;
- normalized_by_version;
- confidence;
- user_verified.

## Centro de reconciliación

Crear Data Reconciliation Center para:
- duplicados;
- import vs Open Banking;
- discrepancias de saldo;
- activos sin ticker;
- documentos contradictorios;
- movimientos sin categoría;
- facts con baja confianza.

## Calidad

Estados:
- verified;
- inferred;
- low_confidence;
- stale;
- conflicting;
- missing.

La UI debe distinguirlos.

## Derivados

Cada cálculo importante conserva engine, engine_version, inputs, timestamp, result y sources.

## Retención

Configurable por tipo. No borrar raw necesario para reproducibilidad sin advertencia.

## Reindexación

Si cambia modelo de embeddings, chunker, extractor u OCR, marcar derivados como versionados y reindexables sin modificar originales.

## Borrado

Cascade controlado sobre original, extracción, chunks, embeddings, facts, relaciones y respuestas cacheadas. El usuario selecciona alcance.

## Export

Exportar en formatos abiertos cuando sea posible: JSON, CSV, documentos originales y manifest. El usuario no debe quedar bloqueado dentro de Financito.
