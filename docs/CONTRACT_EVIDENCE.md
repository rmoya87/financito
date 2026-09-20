# Evidencia contractual y documental

## Principio

Los documentos contractuales del usuario son una fuente primaria de verdad para cualquier decisión financiera que dependa de condiciones particulares.

Ejemplos:
- escritura/novación/subrogación de hipoteca;
- FEIN/FIAE;
- póliza y condiciones generales/particulares de seguros;
- contratos bancarios;
- condiciones de tarjetas;
- tarifarios;
- contratos de telecomunicaciones;
- contratos energéticos;
- préstamos;
- anexos;
- cartas de renovación;
- comunicaciones de cambio de precio;
- documentos de cancelación;
- condiciones de bonificaciones.

Financito no debe limitarse a indexar estos documentos para RAG. Debe extraer las cláusulas relevantes a estructuras de dominio y utilizarlas en engines deterministas.

## Jerarquía de evidencia

Para condiciones personales vigentes, prioridad:

1. condiciones particulares firmadas;
2. anexos/modificaciones posteriores;
3. documento precontractual aplicable y vigente;
4. condiciones generales incorporadas al contrato;
5. comunicación formal posterior del proveedor;
6. tarifario oficial vigente;
7. web oficial;
8. comparador/fuente secundaria.

Una fuente genérica nunca debe sobrescribir silenciosamente una condición particular del usuario.

Si dos documentos se contradicen:
- marcar conflicto;
- conservar ambos;
- usar fecha/vigencia/tipo documental para resolver cuando sea inequívoco;
- si no lo es, bloquear la conclusión automática y pedir revisión.

## Extracción contractual

Extraer como facts estructurados, cuando existan:

### Vigencia
- effective_date
- start_date
- renewal_date
- maturity_date
- notice_period_days
- permanence_end_date
- automatic_renewal

### Costes
- premium
- fee
- commission
- periodic_charge
- opening_cost
- maintenance_cost
- cancellation_cost
- switching_cost

### Penalizaciones
- early_exit_penalty
- early_repayment_fee
- subrogation_fee
- novation_fee
- compensation_formula
- minimum_charge
- maximum_charge
- applicable_period

### Bonificaciones y vinculaciones
- linked_product
- discount
- rate_discount
- conditions
- minimum_usage
- payroll_requirement
- card_requirement
- insurance_requirement
- loss_of_discount_condition

### Seguros
- coverage
- coverage_limit
- deductible
- exclusion
- waiting_period
- claim_condition
- insured_value
- cancellation_condition

### Hipoteca/préstamo
- principal
- nominal_rate
- apr
- reference_index
- spread
- revision_frequency
- payment
- term
- repayment_conditions
- interest_rate_bonus

### Servicios
- promotional_price
- standard_price
- promotion_end_date
- permanence
- cancellation_notice
- included_services
- financed_device_balance

Cada fact debe guardar:
- source_document_id;
- page;
- section;
- exact evidence span;
- extraction_method;
- confidence;
- effective_from;
- effective_to;
- user_verified;
- supersedes_fact_id cuando aplique.

## Cláusulas calculables

Cuando una penalización o coste dependa de una fórmula, no guardar solo texto.

Ejemplo:
"0,25 % del capital amortizado durante los primeros X años".

Representar:
- formula_type;
- percentage;
- base;
- start/end applicability;
- cap;
- floor;
- source.

El engine calcula el valor con los datos actuales.

Si una cláusula no puede traducirse con seguridad a una fórmula:
- mantener texto;
- marcar needs_review;
- no inventar fórmula.

## Vigencia y supersesión

Los contratos cambian.

Un fact puede:
- estar vigente;
- haber sido sustituido;
- estar pendiente de vigencia;
- haber expirado.

Nunca usar automáticamente una cláusula antigua si existe una modificación posterior aplicable.

## Uso en motores

Antes de calcular un DecisionCase, el engine debe resolver un ContractSnapshot vigente.

Ejemplo:

MortgageEngine
→ condiciones actuales extraídas
→ penalización real
→ vinculaciones reales
→ costes reales
→ escenario.

InsuranceOptimizationEngine
→ prima real
→ franquicia real
→ coberturas reales
→ preaviso real
→ penalización/cancelación real
→ comparación.

## Cálculos con evidencia

Todo cálculo material conserva un CalculationTrace:

- input_name;
- input_value;
- input_source;
- formula;
- result;
- engine_version.

Ejemplo:

```text
Penalización amortización = 0,25 % × 120.000 €
                           = 300 €

Fuente:
Hipoteca.pdf
página 17
cláusula 8.2
```

La UI debe permitir abrir la fuente.

## Missing data

Nunca asumir 0 € de penalización porque no se encontró una cláusula.

Estados posibles:
- confirmed_zero;
- confirmed_value;
- formula;
- not_found;
- ambiguous;
- conflicting.

"not_found" no equivale a cero.

## OCR y documentos escaneados

Si el documento es escaneado:
- OCR local;
- conservar bounding boxes/página si es posible;
- confidence;
- revisión para facts materiales de baja confianza.

Una cifra OCR con baja confianza no debe alimentar automáticamente una recomendación de alto impacto.

## Tablas

Tarifas, coberturas y comisiones en tablas deben preservarse estructuralmente.

No trocear una fila de tabla de forma que se pierda la relación entre concepto y valor.

## Validación cruzada

Cuando sea posible, contrastar:
- cargo bancario real vs coste contractual;
- prima cobrada vs póliza;
- cuota hipotecaria vs cálculo;
- descuento prometido vs tipo aplicado.

Las diferencias generan Data Quality Issue.

## Decision Engine

Para cada alternativa mostrar:
- condiciones contractuales utilizadas;
- facts confirmados;
- facts inferidos;
- facts faltantes;
- conflicts;
- impacto si cambia una hipótesis.

## Seguridad

Los documentos y facts derivados permanecen locales.

No enviar cláusulas ni contratos a IA cloud.

## Regla de bloqueo

Una decisión de alto impacto no puede marcarse como favorable si depende materialmente de:
- penalización desconocida;
- cobertura no comparada;
- vinculaciones desconocidas;
- plazo/preaviso incierto;
- OCR de baja confianza sin confirmar.

En esos casos el estado es needs_more_data.
