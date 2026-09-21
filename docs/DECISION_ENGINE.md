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


## Contexto real y snapshot de decisión

El Laboratorio y los Decision Cases no usan importes de ejemplo como punto de partida.

La fuente de verdad actual es:
- hipotecas guardadas: capital pendiente, TIN actual, cuota real, meses restantes y comisión conocida;
- contratos y evidencia confirmada;
- saldos/liquidez;
- patrimonio y deuda;
- carteras, posiciones, coste de compra y últimos precios de mercado guardados;
- acciones/ETF/fondos/cripto seguidos o poseídos;
- evidencia documental con su estado confirmed/inferred/ambiguous.

Al crear un DecisionCase se conserva un snapshot del contexto real para auditabilidad. Al abrirlo se devuelve además `live_current_state`, calculado con los datos actuales, para detectar cambios desde la creación.

Regla:
- el snapshot histórico no se reescribe;
- la vista actual sí se recalcula desde la base local;
- las variables futuras introducidas por el usuario se identifican como supuestos;
- un precio de mercado conserva proveedor y fecha y puede marcarse como desactualizado;
- un dato ausente permanece desconocido.

## Centro de decisión unificado

GET /api/v1/decision-lab/overview compone una vista determinista orientada a acción sobre el mismo contexto que utiliza el resto de Financito.

La respuesta separa:
- choice_cards: decisiones que ya pueden contrastarse y decisiones bloqueadas por datos;
- prepayment_guardrail: escenario ilustrativo de amortización preservando una referencia de liquidez antes de simular;
- signals: desviaciones de presupuesto y anomalías de movimientos;
- pending_actions: tareas documentales, renovaciones y otras acciones vigentes;
- contexto financiero utilizado.

Estados de preparación no equivalen a una recomendación. Por ejemplo, ready_for_market_check significa que las condiciones actuales necesarias para contrastar ofertas están suficientemente estructuradas; la oferta nueva todavía debe verificarse.

### Cambio de hipoteca

Antes de presentar una referencia pública como económicamente comparable deben estar disponibles:
- capital, plazo y cuota actuales;
- penalización/coste de salida actual;
- vinculaciones y pérdida de bonificaciones;
- costes de entrada conocidos de la nueva alternativa;
- coste de productos vinculados requeridos por la nueva alternativa.

Una referencia con TIN inferior queda bloqueada si falta un coste material. La FEIN u oferta personalizada es necesaria para cerrar el caso.

### Cambio de seguro

La póliza actual debe aportar como mínimo:
- prima;
- franquicia cuando corresponda;
- coberturas verificadas;
- renovación y preaviso;
- coste de salida;
- impacto hipotecario si existe vinculación.

Una referencia pública de una aseguradora solo descubre una opción. No se considera alternativa comparable hasta disponer de prima y franquicia personalizadas, coberturas/límites, exclusiones y condiciones de cancelación equivalentes.

### Alertas y consumo

Presupuestos y anomalías de movimientos forman parte del contexto de decisión. Una alerta puede modificar la lectura de liquidez o capacidad de asumir costes, pero no altera por sí sola una condición contractual.

## Lenguaje de confianza para usuarios no expertos

La interfaz de decisión debe traducir la trazabilidad técnica a tres estados comprensibles:

- **Confirmado**: procede de movimientos, registros o cláusulas validadas por el usuario.
- **Calculado**: resultado determinista reproducible construido exclusivamente con datos confirmados y supuestos visibles.
- **Referencia de mercado**: dato público útil para localizar o solicitar una alternativa, pero que todavía no representa una condición personal.

Nunca se usa una puntuación opaca para ocultar incertidumbre. Si una decisión no puede cerrarse, se muestra qué dato falta, por qué importa y dónde resolverlo.

### Amortización anticipada

Una simulación de amortización guardada debe comprobar antes de calcular:
- que la amortización parcial está permitida según evidencia confirmada;
- si existe importe o porcentaje mínimo/máximo;
- cómo se aplica: reducción de cuota, reducción de plazo, ambas opciones o decisión de la entidad;
- la comisión/fórmula aplicable.

Preaviso, frecuencia, ventanas y otras condiciones operativas se muestran bajo **Antes de hacerlo**. Pueden permitir calcular el impacto económico pero impiden presentar el escenario como listo para ejecutar hasta revisarlas.

Los indicios extraídos por IA o reglas deterministas permanecen pendientes de validación y bloquean una conclusión cuando son materiales.

