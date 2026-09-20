# Integridad, reparación y recuperación local

## Objetivo

Financito debe poder recuperarse de cierres inesperados, índices corruptos o derivados inconsistentes sin destruir datos fuente.

## Principio

Raw/source data es reconstruible solo desde la fuente; índices, embeddings, agregados e insights deben poder regenerarse.

## Startup checks

- DB integrity;
- migration state;
- Vault availability;
- free disk;
- interrupted jobs;
- model availability;
- orphan derivatives;
- pending reconciliation.

## Jobs reanudables

Cada job pesado conserva checkpoint cuando sea razonable.

## Repair Center

Acciones:
- rebuild FTS;
- rebuild vector index;
- re-extract document;
- re-embed;
- reconcile transactions;
- detect orphan rows;
- verify Vault hashes;
- retry failed jobs.

## Atomicidad

Imports y transformaciones críticas deben usar staging + transaction/commit.

No dejar estado parcialmente visible.

## Crash recovery

Tras cierre inesperado:
- detectar jobs running sin lease;
- marcar interrupted;
- reanudar/reintentar según idempotencia.

## Health

Mostrar problemas y acciones posibles sin exigir conocimiento técnico.
