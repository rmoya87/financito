# Lotes de inversión y base fiscal

## Objetivo

Modelar compras/ventas desde el principio para poder calcular correctamente P&L realizado, coste, divisa y fiscalidad modular.

## Tax lot

Campos:
- security_id;
- acquisition_date;
- quantity_original;
- quantity_remaining;
- unit_cost;
- fees;
- currency;
- fx_rate_at_acquisition;
- source;
- account/broker;
- tax_metadata.

## Disposal allocation

Registrar qué lotes se consumen en una venta según la regla fiscal/configuración aplicable.

La regla concreta depende de jurisdicción y ejercicio.

## Corporate actions

Soportar:
- splits;
- reverse splits;
- spin-offs;
- mergers;
- dividends;
- return of capital;
- fees.

No alterar histórico sin trace.

## Divisas

Conservar:
- precio original;
- divisa original;
- FX histórico;
- valor base.

## Tax Center

El motor fiscal:
- es modular por jurisdicción/ejercicio;
- nunca se implementa dentro del LLM;
- muestra supuestos;
- cita fuentes normativas cuando se implemente legislación específica.

## Escenarios de venta

Permitir estimar:
- ganancia/pérdida;
- costes;
- impacto fiscal estimado;
- cambio de allocation;
- liquidez resultante.

No presentar una estimación fiscal como declaración oficial.
