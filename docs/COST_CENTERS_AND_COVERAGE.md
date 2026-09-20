# Cost Centers y Coverage

## Cost Centers
Se pueden crear áreas de coste arbitrarias y vincular:
- contratos;
- pólizas;
- activos;
- pasivos;
- commitments;
- transactions mediante API.

Cada vínculo tiene `allocation_percentage`.

El resumen calcula:
- gasto observado enlazado;
- compromisos/costes anuales;
- valor de activos de referencia;
- deuda de referencia;
- vínculos sin dato valorable.

No se mezclan valor patrimonial y gasto como si fueran la misma métrica.

## Coverage
Los `CoverageFact` contienen:
- tipo;
- límite;
- franquicia;
- vigencia;
- evidencia/documento;
- confidence;
- flag verificado.

### Duplicidades
Solo se generan overlaps cuando:
- cobertura está verificada;
- tipo coincide;
- procede de pólizas/contratos diferentes;
- vigencias no son incompatibles.

No se estima coste redundante si no puede atribuirse.

### Huecos
Un hueco solo existe frente a un `CoverageRequirement` definido por el usuario:
- tipo de póliza opcional;
- coverage_type;
- límite mínimo opcional.

Resultados:
- `missing_verified_coverage`;
- `limit_unknown`;
- `limit_below_requirement`;
- covered.

Financito no inventa qué cobertura “debería” contratar el usuario.
