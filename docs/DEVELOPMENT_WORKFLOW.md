# Procedimiento estándar de desarrollo

## Objetivo

Que humanos y agentes de IA implementen siempre de la misma forma.

## Paso 1 — Intake

Definir:
- problema;
- comportamiento esperado;
- módulos afectados;
- riesgos;
- datos;
- seguridad;
- rendimiento.

## Paso 2 — Discovery

Buscar:
- funcional existente;
- componentes;
- engines;
- schemas;
- endpoints;
- migraciones;
- tests;
- ADRs.

## Paso 3 — Diseño mínimo

Antes de código, decidir:
- source of truth;
- dominio responsable;
- contrato;
- persistencia;
- UI;
- tests.

Crear ADR solo si la decisión es estructural.

## Paso 4 — Implementación backend

Orden recomendado:
1. domain;
2. application;
3. repository/provider;
4. migration;
5. API;
6. tests.

## Paso 5 — Implementación frontend

Orden:
1. contrato generado;
2. query/mutation;
3. shared component si procede;
4. feature component;
5. page;
6. states;
7. accessibility;
8. tests.

## Paso 6 — Datos y cálculo

Verificar:
- Decimal;
- timestamps;
- provenance;
- freshness;
- confidence;
- deduplicación;
- idempotencia.

## Paso 7 — Seguridad

Checklist:
- loopback;
- auth;
- secrets;
- logs;
- CSP;
- filesystem;
- provider allowlist;
- injection;
- validation.

## Paso 8 — Rendimiento

Comprobar:
- N+1;
- queries;
- índices;
- payload;
- paginación;
- CPU;
- rerenders;
- bundle;
- caches.

## Paso 9 — Validación

Ejecutar:
- lint;
- typecheck;
- unit;
- integration;
- frontend;
- build;
- migraciones;
- security relevante.

## Paso 10 — Documentación

Actualizar en el mismo cambio.

No crear documentación separada de la implementación.

## Paso 11 — Cierre

Resumen estándar:
- Qué se cambió
- Por qué
- Tests
- Migraciones
- Docs
- Riesgos
- Pendientes externos

## Revisión posterior

Si una feature genera deuda o duplicación, abrir acción concreta; no dejar comentarios vagos.

## Definition of Done

La referencia final es DEFINITION_OF_DONE.md.
