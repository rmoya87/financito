# Motor de decisiones e impacto

## Objetivo

Convertir datos en alternativas comparables sin sustituir la decisión humana.

Financito debe responder:
- qué opciones existen;
- cuánto cuesta cada una;
- cuánto podría ahorrar/ganar;
- qué riesgos introduce;
- cuándo se recupera el coste;
- qué supuestos utiliza;
- qué información falta.

## Decision Case

Toda decisión relevante se modela como un DecisionCase.

Campos:
- id;
- type;
- question;
- current_state;
- alternatives[];
- assumptions[];
- constraints[];
- sources[];
- created_at;
- calculation_version.

## Alternative

Cada alternativa debe devolver:
- name;
- one_off_cost;
- monthly_cost;
- annual_cost;
- expected_benefit;
- net_benefit;
- liquidity_impact;
- risk_level;
- effort;
- reversibility;
- break_even;
- horizon_results;
- pros[];
- cons[];
- uncertainties[];
- sources[].

## Horizontes

Como mínimo:
- inmediato;
- 12 meses;
- 36 meses;
- 60 meses;
- largo plazo cuando aplique.

## Impacto

Separar:
- cash flow;
- patrimonio;
- liquidez;
- riesgo;
- fiscalidad;
- cobertura/prestaciones;
- concentración;
- flexibilidad.

## Escenarios

Cuando una variable futura es incierta, generar:
- conservative;
- base;
- optimistic;

o escenarios específicos del dominio.

No asignar probabilidades inventadas.

## Hipoteca

Comparar:
- mantener;
- novar;
- subrogar;
- cancelar/nueva;
- amortizar.

Impacto:
- cuota;
- intereses;
- costes de entrada;
- vinculaciones;
- liquidez;
- break-even;
- coste total.

## Seguro

Comparar:
- mantener;
- alternativa equivalente;
- alternativa de menor cobertura si el usuario lo solicita.

Impacto:
- prima;
- franquicia;
- coberturas;
- exclusiones;
- riesgo asumido;
- coste neto.

## Suscripciones/servicios

Comparar:
- mantener;
- cancelar;
- downgrade;
- cambiar proveedor.

Impacto:
- ahorro;
- pérdida de funcionalidad;
- permanencia;
- coste cambio.

## Inversión

No producir una orden automática.

Debe mostrar:
- capital disponible real;
- cambio de allocation;
- concentración resultante;
- riesgo;
- liquidez;
- horizonte;
- escenarios;
- tesis;
- invalidación.

## Amortizar vs invertir

Separar:
- ahorro financiero cierto de amortización;
- rentabilidad esperada no garantizada;
- fiscalidad;
- liquidez perdida;
- riesgo;
- horizonte.

No comparar una rentabilidad esperada como si fuera garantizada.

## Recommendation status

Estados:
- informational;
- candidate;
- needs_more_data;
- favorable_under_assumptions;
- unfavorable_under_assumptions.

Evitar labels absolutos tipo “mejor” sin condiciones.

## Confidence

Confidence describe calidad/completitud de evidencia, no probabilidad de éxito financiero.

Componentes:
- source_quality;
- data_completeness;
- calculation_stability;
- recency;
- equivalence_quality.

## Missing data

Si falta un dato material:
- identificarlo;
- cuantificar su posible impacto si es posible;
- no inventarlo;
- degradar confidence;
- marcar needs_more_data.

## Auditabilidad

Cada caso conserva:
- inputs;
- outputs;
- fuentes;
- versiones de motor;
- assumptions;
- decisión del usuario;
- resultado observado posteriormente si se registra.

## UX

Siempre permitir:
- Ver cálculo
- Ver fuentes
- Cambiar supuesto
- Comparar alternativas
- Guardar decisión
- Recalcular con datos actuales


## ContractSnapshot

Antes de comparar alternativas que dependan de un contrato vigente, crear un snapshot de condiciones aplicables basado en evidencia documental.

El DecisionCase debe exponer:
- facts confirmados;
- facts inferidos;
- facts no encontrados;
- conflicts;
- documentos/páginas;
- impacto de los datos faltantes.

Un dato contractual crítico desconocido bloquea estados concluyentes.

Ver CONTRACT_EVIDENCE.md.
