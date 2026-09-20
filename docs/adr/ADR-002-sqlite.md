# ADR-002 — SQLite

Status: Accepted

## Context

La app es local-first, principalmente de un usuario y necesita datos estructurados, FTS y vectores.

## Decision

Usar SQLite como persistencia principal, cifrado mediante SQLCipher o alternativa validada, FTS5 para texto y sqlite-vec para embeddings.

## Consequences

- operación sin servidor;
- backups sencillos;
- baja complejidad;
- buena integración local.

Si el producto evoluciona a multiusuario cloud, se evaluará Postgres sin cambiar el dominio.
