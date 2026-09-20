# ADR-005 — Finanzas deterministas

Status: Accepted

## Decision

Todos los cálculos financieros críticos viven en motores deterministas. El LLM únicamente interpreta, coordina tools y explica.

## Consequences

- resultados reproducibles;
- tests fiables;
- trazabilidad;
- menor riesgo de alucinación.
