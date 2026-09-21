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


## Resolución de costes de salida para decisiones

El Decision Lab resuelve los costes de salida desde hechos **confirmados por el usuario** antes de comparar una alternativa.

Para hipoteca:
- `early_repayment_fee_percent` se aplica al importe concreto de amortización extraordinaria;
- `subrogation_fee_percent` se aplica al capital pendiente actual;
- `cancellation_fee_percent` puede utilizarse cuando la documentación confirme que es la cláusula aplicable;
- `linked_home_insurance_rate_penalty_pp`, `linked_life_insurance_rate_penalty_pp` y `linked_salary_rate_penalty_pp` recogen cuánto sube el tipo al perder cada bonificación; Financito calcula el incremento de cuota/intereses antes de considerar rentable sacar un producto fuera del banco;
- un importe fijo confirmado puede utilizarse como fallback;
- si no existe evidencia suficiente, el resultado es `needs_more_data`; nunca se presupone 0 €.

Para seguros:
- prima anual;
- fecha de renovación;
- preaviso;
- coste/penalización de salida cuando exista;
- franquicia y coberturas verificadas;
- documento fuente.

El endpoint de preparación de cambio devuelve los datos faltantes antes de permitir considerar cerrada una comparación.


## Ingesta desde la aplicación y análisis local

La UI de **Documentos y evidencia** permite seleccionar o arrastrar documentos directamente desde el Mac. El backend:
- sanea el nombre;
- valida tipo y tamaño;
- copia el archivo a `<vault>/uploads`;
- indexa texto/OCR y RAG;
- clasifica el documento;
- extrae hechos deterministas;
- programa el análisis interpretativo con el LLM local cuando está disponible.

El usuario no necesita navegar a la carpeta oculta del Vault para usar el sistema.

## Doble capa: hechos vs interpretación

Financito separa estrictamente:

**Hechos materiales**
- importes;
- porcentajes;
- fechas;
- preavisos;
- comisiones;
- penalizaciones;
- primas;
- tipos;
- vinculaciones calculables;
- coberturas estructuradas.

Estos hechos solo alimentan cálculos cuando están confirmados por el usuario.

**Análisis IA local**
- resumen;
- ventajas;
- obligaciones;
- riesgos;
- exclusiones/límites;
- productos vinculados;
- oportunidades de optimización;
- impactos cruzados entre áreas;
- información ausente.

El análisis de IA se conserva como interpretación y nunca sustituye silenciosamente un hecho confirmado.

## Propuestas de evidencia por IA

El modelo local puede proponer un hecho material que la extracción determinista no haya detectado si:
- usa una clave permitida;
- existe una página concreta de evidencia;
- el valor aparece explícitamente en el documento;
- queda marcado como `inferred`;
- requiere confirmación humana.

Las propuestas confirmadas pasan por el mismo pipeline que los hechos deterministas.

En seguros, la IA puede proponer coberturas estructuradas. Tras la confirmación:
- se crean `CoverageFact` vinculados a la póliza y documento;
- entran en análisis de huecos;
- entran en detección de duplicidades;
- conservan página y confianza.

Un reanálisis preserva hechos ya confirmados y regenera solo propuestas pendientes.

## Reutilización entre dominios

Los análisis documentales forman parte del contexto local de:
- Seguros;
- Laboratorio de decisiones / Hipoteca;
- Contratos;
- Chat/RAG;
- Action Center.

Ejemplo: una póliza puede indicar que cancelarla hace perder una bonificación hipotecaria. Esa relación aparece tanto en Seguros como en el contexto de la decisión hipotecaria, mientras que el coste cuantitativo solo se calcula con hechos contractuales confirmados.


## Propagación cruzada entre dominios

Cuando un hecho material se confirma, Financito lo proyecta únicamente a entidades compatibles y con trazabilidad:

- documento de seguro -> Contrato + Póliza + Coberturas;
- documento hipotecario -> Contrato + Hipoteca únicamente cuando el usuario lo vincula explícitamente;
- documento contractual -> Contrato;
- renovación/preaviso confirmado -> Action Center;
- coberturas confirmadas -> detección de duplicidades y huecos;
- cláusulas de vinculación -> Laboratorio de decisiones;
- conclusiones interpretativas -> secciones de Seguros, Hipoteca, Contratos, Cuentas, Inversiones y Fiscalidad según tipo documental.

### Regla de enlace hipotecario

Un documento hipotecario solo puede actualizar un perfil de hipoteca si existe un enlace explícito documento -> hipoteca elegido por el usuario.

Una FEIN, simulación u oferta de otra entidad puede permanecer como **oferta o referencia**: se indexa, se analiza con IA local y puede usarse para comparar, pero no modifica capital, TIN, cuota, plazo ni penalizaciones de la hipoteca actual.

No se enlazan documentos hipotecarios automáticamente por el mero hecho de existir una única hipoteca.

Los hechos confirmados que pueden alimentar el perfil incluyen:
- remaining_principal;
- nominal_rate;
- monthly_payment;
- remaining_months;
- interest_type;
- provider_name.

Los porcentajes documentales se convierten a la escala interna decimal antes de entrar en cálculos.

### Separación de capas

- extracción determinista: primera fuente para importes, porcentajes, fechas y cláusulas reconocibles;
- IA local: interpretación, descubrimiento de relaciones, propuestas de hechos no detectados, negociación y requisitos de comparación;
- confirmación humana: necesaria antes de que una propuesta de IA material cambie cálculos;
- engines: solo consumen datos estructurados confirmados o inputs explícitos.

La IA nunca sobrescribe silenciosamente datos financieros confirmados.

## Edición manual sin segunda fuente

Cuando la extracción no reconoce un dato material, el usuario puede añadirlo desde el detalle del documento.

El fact resultante:
- pertenece al mismo `document_id`;
- queda `status=confirmed`;
- queda `user_verified=true`;
- registra `source_section=Introducido por el usuario`;
- conserva página si el usuario la conoce;
- pasa por el mismo pipeline de proyección que los facts extraídos.

Esto aplica a términos contractuales, hipoteca, coberturas, productos vinculados y términos de inversión. Una edición manual no debe crear una ficha de contrato/póliza/hipoteca separada.

## Veredicto de seguros

El análisis de seguros debe cruzar:
- prima anual y franquicia confirmadas;
- coberturas y límites;
- renovación/preaviso/penalización;
- pagos reales categorizados como seguro;
- ingresos y ahorro observados;
- requisitos de cobertura definidos por el usuario;
- duplicidades potenciales;
- productos vinculados a hipoteca u otros contratos;
- campos documentales pendientes.

La IA local puede resumir prioridades y formular preguntas, pero no decide suficiencia de cobertura ni recomienda cancelar/cambiar una póliza sin equivalencia demostrada.


## Completado asistido por IA local

El análisis documental no se limita a producir un resumen. Para cada tipo de documento mantiene una lista de hechos materiales esperables y busca de forma explícita los que todavía no están representados.

Ejemplos:
- hipoteca: TIN/TAE, índice, diferencial, revisiones, capital/cuota/plazo, comisiones y vinculaciones;
- seguros: entidad, número de póliza, tipo, prima, franquicia, renovación, preaviso, coste de salida, objeto asegurado y coberturas;
- préstamos: tipos, saldo, cuota, plazo y costes de amortización/salida;
- energía/telecomunicaciones: coste, renovación, preaviso, permanencia, promoción/precio estándar y costes de cancelación;
- inversiones documentales: identificación del producto y costes explícitos de gestión, custodia, suscripción o reembolso.

La IA local:
1. reutiliza los hechos ya extraídos y no vuelve a declarar como ausente una clave que ya exista;
2. busca en el texto local únicamente los datos esperados que todavía no estén representados;
3. solo crea propuestas materiales cuando el valor aparece explícitamente y puede citar una página;
4. marca esas propuestas como `inferred` y `user_verified=false`;
5. nunca convierte automáticamente una propuesta en dato confirmado.

La UX distingue tres estados:
- **confirmado**: puede alimentar proyecciones y engines;
- **encontrado, pendiente de validar**: la IA/extractor ya localizó el dato y se muestra con documento/página para revisión;
- **no encontrado**: no existe todavía evidencia suficiente y se solicita documentación o revisión adicional.

En hipotecas, los hechos confirmados de TAE, índice, diferencial, periodicidad/próxima revisión y porcentajes de comisión completan los huecos de `MortgageProfileExtra` sin sobrescribir silenciosamente valores manuales existentes. En seguros, prima, franquicia, renovación, preaviso y coste de salida siguen el mismo principio. Los contratos e inversiones conservan sus propuestas estructuradas para reutilización en sus áreas correspondientes.

Los análisis de IA incluyen una versión de esquema. Al arrancar la aplicación, si el modelo local está disponible, los documentos con análisis ausente o de una versión anterior se reanalizan en segundo plano; esta actualización puede generar nuevas propuestas, pero nunca las confirma automáticamente.


## Documentación contextual por producto

La navegación documental parte del producto financiero y no de una biblioteca global:
- una hipoteca abre una vista documental filtrada por su `mortgage_id`;
- una póliza abre una vista documental filtrada por su `insurance_policy_id`;
- los archivos subidos desde esa vista quedan vinculados al producto antes de lanzar el análisis de IA;
- también se puede asociar un archivo ya existente o desvincularlo sin borrar el original del Vault.

La biblioteca global se conserva como inventario técnico y para documentos todavía sin asociar, pero deja de ser el lugar donde se crean y mantienen las fichas de hipoteca o seguro.

La eliminación de una hipoteca o póliza elimina su ficha y sus vínculos de evidencia, pero no borra los documentos físicos del Vault. Esos archivos quedan disponibles para asociarlos de nuevo.

### Datos que faltan

Cada producto distingue:
1. dato confirmado;
2. dato localizado por extractor/IA y pendiente de validar;
3. dato realmente no encontrado.

Desde la sección del producto se puede relanzar el análisis de IA local solo sobre sus documentos asociados. Si el dato sigue sin aparecer, la UI ofrece un campo manual para los campos estructurados editables. Los valores introducidos manualmente se guardan en el perfil del producto y pueden modificarse posteriormente desde sus opciones de edición.

## Documentos mixtos y proyección por dominio

Un archivo puede contener evidencia de más de un producto. El caso típico es documentación hipotecaria que incluye un seguro de vida u hogar vinculado. Financito no debe tratar todos los hechos confirmados del archivo como si pertenecieran al producto principal.

Antes de proyectar hechos confirmados, la sincronización separa el dominio hipotecario del asegurador usando `fact_type`, claves explícitas y el contexto/página donde aparecen marcadores de seguro o coberturas. Un `provider_name`, `annual_cost`, `renewal_date`, `contract_number` o `next_review_date` situado en una sección de seguro no puede modificar el prestamista ni el calendario de revisión de la hipoteca.

Cuando un documento hipotecario contiene evidencia aseguradora confirmada suficiente, Financito crea o actualiza la póliza y su contrato, proyecta prima, proveedor, renovación, número de póliza/contrato, objeto asegurado, franquicia y coberturas verificadas, conserva el mismo documento como evidencia de la póliza y registra la relación `mortgage -> insurance_policy` mediante `LinkedProduct`. No se crea una póliza nueva si falta una prima real confirmada: nunca se inventa un coste 0.

Los identificadores usados para agrupar documentos también respetan el dominio. Un `contract_number` situado en una sección de seguro no puede hacer que un recibo posterior de esa póliza se vincule por error a la hipoteca que contiene el anexo.


## Regla especial: notas simples y responsabilidad hipotecaria

Una nota simple puede expresar cantidades máximas garantizadas por capital, intereses ordinarios, intereses de demora, costas/gastos y valor de subasta. Esas cantidades describen responsabilidad hipotecaria registral y no deben proyectarse automáticamente como:
- penalización de cancelación;
- comisión de amortización anticipada;
- gasto inicial ya pagado;
- cuota;
- capital pendiente;
- TAE.

Si el mismo texto contiene un TIN nominal, un porcentaje máximo de demora, un vencimiento o un plazo explícitos, esos elementos sí pueden convertirse en propuestas de hechos independientes, siempre con página y manteniendo estado inferido hasta su confirmación.

La ausencia explícita de TAE, diferencial, índice, comisión de subrogación o amortización sigue siendo “información que falta”; el análisis narrativo no puede inventarla.
