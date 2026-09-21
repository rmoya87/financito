# Financial Optimization Engine

## Objetivo

Encontrar oportunidades reales de:
- ahorro;
- reducción de comisiones;
- mejora de condiciones;
- optimización de deuda;
- mejor uso de liquidez;
- mejora de rendimiento ajustado a riesgo.

## Principio

Nunca:
```text
producto B más barato -> cambiar
```

Siempre:
```text
producto actual
 -> alternativa comparable
 -> diferencias de servicio
 -> costes de salida
 -> costes de entrada
 -> penalizaciones
 -> beneficios perdidos
 -> vinculaciones
 -> impacto fiscal
 -> beneficio neto
 -> break-even
 -> riesgo/esfuerzo
```

## Fórmula base

```text
net_benefit =
 gross_benefit
 - switching_costs
 - penalties
 - lost_benefits
 - additional_recurring_costs
 - tax_impact
```

Cada término debe ser inspeccionable.

## SwitchingCostEngine

Categorías:
- direct_costs;
- indirect_costs;
- one_off_costs;
- recurring_costs;
- penalties;
- lost_benefits;
- tax_impact.

Nunca esconder un coste dentro de una puntuación.

## BreakEvenEngine

```text
break_even_months =
 one_off_net_switching_cost / monthly_net_saving
```

Si el ahorro mensual no es positivo, no existe break-even favorable.

Para flujos variables usar cash-flow descontado o simulación mensual.

## BenefitValuationEngine

Beneficios:
- puntos;
- millas;
- cashback;
- seguros;
- lounges;
- descuentos;
- suscripciones;
- servicios premium.

Valores:
- theoretical_value;
- realized_value;
- user_adjusted_value.

Por defecto, para decisiones se prioriza valor realizado/ajustado frente a valor publicitario.

## LinkedProductEngine

Debe valorar bonificaciones y su coste real.

Ejemplo:
- seguro banco: 520 €/año;
- alternativa equivalente: 180 €/año;
- ahorro hipotecario por vinculación: 240 €/año.

Coste incremental de vinculación: 340 €.
Beneficio: 240 €.
Valor neto: -100 €/año.

## Seguros

Comparar:
- prima;
- franquicia;
- coberturas;
- límites;
- exclusiones;
- asistencia;
- renovación;
- preaviso;
- bonificaciones;
- cancelación.

Una alternativa con peor cobertura debe quedar marcada como no equivalente.

## Energía

Usar consumo real:
- kWh;
- potencia;
- periodos;
- impuestos;
- servicios;
- permanencia;
- descuentos temporales.

Simular factura del usuario, no un consumidor promedio.

## Telecomunicaciones

Considerar:
- fibra;
- velocidad;
- líneas;
- datos;
- roaming;
- TV;
- streaming;
- terminales financiados;
- permanencia;
- promoción;
- precio post-promoción.

Mostrar coste a 12/24/36 meses.

## Bancos y tarjetas

Comparar:
- comisiones;
- remuneración;
- FX;
- transferencias;
- cajeros;
- tarjetas;
- cashback;
- puntos;
- seguros;
- ventajas.

Una cuenta al 0 % puede generar oportunidad de rendimiento, pero debe preservar el colchón de liquidez.

## Opportunity Score

No sustituye a los números.

Puede combinar:
- net financial benefit;
- confidence;
- effort;
- risk;
- urgency;
- service equivalence.

La UI debe mostrar componentes.

## Priorización

Orden recomendado:
1. impacto neto;
2. urgencia;
3. confianza;
4. esfuerzo;
5. riesgo.

## Evidencia

Cada oportunidad conserva:
- fuentes;
- snapshots de oferta;
- fecha;
- supuestos;
- cálculos;
- versión del motor.

Así una recomendación histórica puede reproducirse.


## Evidencia contractual obligatoria

Antes de calcular una oportunidad de cambio, resolver las condiciones vigentes del producto actual desde documentos contractuales.

Entradas materiales:
- penalizaciones;
- preavisos;
- permanencias;
- vinculaciones;
- bonificaciones;
- coberturas;
- costes de salida;
- fórmulas contractuales.

Prioridad: condiciones particulares y modificaciones vigentes sobre tarifas/web genéricas.

Si falta un dato material, el estado pasa a needs_more_data y no se presenta el ahorro neto como conclusión firme.

Ver CONTRACT_EVIDENCE.md.


## Hipótesis combinadas de hipoteca y seguros

El Laboratorio debe contemplar como mínimo:
1. mantener hipoteca y seguros actuales;
2. negociar/novar la hipoteca actual;
3. cambiar solo la hipoteca y conservar seguros si es contractualmente posible;
4. conservar hipoteca y cambiar seguros;
5. cambiar hipoteca y seguros a la nueva entidad;
6. cambiar hipoteca y contratar seguros externos;
7. amortizar parcialmente y mantener;
8. amortizar parcialmente antes de una subrogación.

Cada hipótesis parte de saldo, capital, ingresos, gastos y contratos reales.

## Investigación de mercado bajo demanda

El Laboratorio puede consultar páginas oficiales públicas de bancos y aseguradoras para descubrir alternativas actuales.

Reglas:
- solo fuentes públicas/oficiales configuradas;
- conservar proveedor, URL y fecha de consulta;
- TIN/TAE/promociones públicas son **benchmarks**, no condiciones personales;
- nunca usar una oferta pública como si fuera una FEIN o presupuesto individual;
- para calcular beneficio neto se requiere una oferta personalizada y los costes contractuales actuales confirmados;
- una mejora aparente de TIN debe incorporar seguros, productos vinculados, costes de salida, costes de entrada y cualquier pérdida de bonificación.

## Completitud de la alternativa de mercado

Una mejora nominal no es todavía una mejora neta.

Para hipotecas, el comparador público exige que los costes de entrada de la alternativa estén conocidos o explícitamente declarados inexistentes antes de clasificarla como escenario que compensa. Si una página no permite determinar apertura/gestión u otro coste de entrada material, la comparación queda incompleta aunque el TIN sea inferior.

Los costes de cancelar seguros actuales se muestran dentro del contexto del paquete vinculado, pero no se cargan artificialmente al escenario «cambiar solo la hipoteca» cuando el usuario puede conservar esas pólizas. Se aplican al escenario de paquete completo cuando realmente se cancelen.

Para seguros, las fuentes públicas son exclusivamente discovery. insurance_leads conserva proveedor, fuente y fecha, pero can_decide=false hasta incorporar una oferta personalizada con:
- prima;
- franquicia;
- coberturas y límites equivalentes verificados;
- exclusiones;
- cancelación/preaviso;
- costes de entrada/cambio;
- efecto sobre bonificaciones hipotecarias si aplica.

Esto evita optimizar una prima destruyendo cobertura o encareciendo otra parte del patrimonio financiero.

