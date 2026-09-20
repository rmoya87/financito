# Seguimiento de decisiones y resultados

## Objetivo

Cerrar el ciclo:
recomendación -> decisión -> resultado observado -> calibración.

## Decision Outcome

Guardar:
- decision_case_id;
- selected_alternative;
- expected_impact;
- observed_impact;
- observation_period;
- variance;
- explanation;
- data_completeness.

## Ejemplos

- ahorro estimado vs real tras cambiar seguro;
- cuota hipotecaria estimada vs real;
- reducción de gasto objetivo vs real;
- rendimiento de estrategia vs benchmark, sin convertirlo en promesa futura.

## Change explanation

Una recomendación debe poder explicar por qué cambió desde la versión anterior:
- nuevos datos;
- nueva cláusula;
- precio;
- tipo;
- saldo;
- coste;
- cobertura;
- provider freshness.

## Calibration

Los errores observados pueden ajustar modelos de forecast/estimación, nunca alterar facts históricos.
