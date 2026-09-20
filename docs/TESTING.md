# Estrategia de testing

## Pirámide

1. unit tests de dominio;
2. tests de integración;
3. tests API;
4. tests UI;
5. E2E de journeys críticos.

## Dominio

Obligatorios:
- dinero/Decimal;
- categorías;
- recurrentes;
- patrimonio;
- riesgo;
- switching costs;
- break-even;
- beneficios;
- hipoteca;
- escenarios.

## Base de datos

- migraciones forward;
- idempotencia;
- constraints;
- deduplicación;
- rollback cuando exista;
- fixtures aislados.

## RAG

Casos:
- respuesta presente;
- no presente;
- multi-documento;
- contradicción;
- OCR;
- tabla;
- ES/EN;
- documento modificado;
- duplicado;
- citas.

## Providers

Contract tests usando fixtures grabadas/sanitizadas cuando la licencia lo permita.

Nunca usar cuentas reales en CI.

## Seguridad

Tests:
- CORS;
- auth local;
- path traversal;
- secretos en logs;
- prompt injection;
- archivos inválidos;
- acceso a documentos fuera de Vault.

## Frontend

- Vitest/Testing Library o equivalente;
- componentes;
- formularios;
- estados loading/empty/error;
- accesibilidad.

E2E con Playwright:
- onboarding;
- Vault;
- importación;
- chat con cita;
- dashboard;
- oportunidad;
- escenario hipotecario.

## Datos ficticios

Crear un hogar ficticio completo con:
- cuentas;
- nóminas;
- hipoteca;
- seguro;
- servicios;
- cartera;
- documentos sintéticos.

No reutilizar datos del usuario.

## CI

Cada PR:
- lint;
- typecheck;
- unit;
- integration seleccionada;
- build web;
- build API;
- test migraciones;
- secret scan.

## Criterio de salida

Una fase no se considera completa si:
- no compila;
- tests críticos fallan;
- migraciones no están verificadas;
- documentación contradice implementación.
