# Financial Graph lógico

## Objetivo

Relacionar entidades sin introducir una base de grafos separada en v1.

## Relaciones principales

- account -> transaction
- transaction -> merchant
- transaction -> recurring_series
- transaction -> contract
- contract -> provider
- contract -> document
- document -> contract_fact
- contract -> asset/liability
- asset -> expense
- portfolio -> position -> security
- opportunity -> contract/asset/account
- decision_case -> opportunity/alternative
- calculation_trace -> facts/sources

## Casos de uso

- coste total del coche;
- productos vinculados a hipoteca;
- todos los pagos relacionados con un proveedor;
- documentos que sustentan una decisión;
- gasto asociado a vivienda;
- duplicidad de coberturas;
- decisiones afectadas por una cláusula modificada.

## Implementación

Relaciones SQL explícitas + entity_link para relaciones dinámicas.

No introducir Neo4j ni servicio adicional salvo ADR futuro justificado.
