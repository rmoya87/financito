# Forecasting, ahorro futuro y compromisos

## Objetivo

Responder de forma cuantificada a preguntas como:
- ¿Cuánto gastaré en los próximos 30/90/180/365 días?
- ¿Cuánto ahorraré hasta una fecha?
- ¿Cuál será mi liquidez probable?
- ¿Qué parte del saldo actual está realmente disponible?
- ¿Qué categorías explican la desviación?
- ¿Cómo se compara con el mismo periodo del año pasado?

El forecast es una estimación, nunca un hecho futuro.

## Horizontes

Soportar:
- 7 días
- 30 días
- fin de mes
- 90 días
- 6 meses
- 12 meses
- fecha personalizada

## Componentes del forecast

Forecast de gasto:

1. gasto confirmado ya contabilizado;
2. compromisos futuros conocidos;
3. recurrentes detectados;
4. mismo periodo del año anterior;
5. tendencia reciente;
6. estacionalidad;
7. presupuestos/objetivos;
8. eventos extraordinarios configurados;
9. cambios contractuales conocidos;
10. incertidumbre.

Forecast de ahorro:

```text
forecast_savings =
 forecast_income
 - forecast_expenses
 - planned_debt_payments
 - planned_investments_or_goal_contributions
```

Mostrar también ahorro antes de aportaciones planificadas.

## Same Period Last Year baseline

Para cualquier horizonte [start, end], crear automáticamente el periodo comparable del año anterior.

Ejemplo:
- forecast: 1 octubre 2026 – 31 diciembre 2026
- baseline: 1 octubre 2025 – 31 diciembre 2025

Calcular:
- gasto total LY;
- gasto por categoría LY;
- ingresos LY;
- ahorro LY;
- recurrencias presentes;
- eventos extraordinarios;
- variación actual YTD/recent.

## No copiar el año pasado literalmente

El valor del año anterior es una señal, no la predicción final.

Modelo conceptual por categoría:

```text
baseline = same_period_last_year

adjusted_baseline =
 baseline
 × recent_category_trend
 × seasonality_adjustment
 × known_price_change_adjustment

forecast_category =
 known_commitments
 + expected_recurring
 + residual_behavior_estimate
```

Los factores deben ser acotados y explicables.

No aplicar tendencias extremas de forma ilimitada.

## Categorías con distinto comportamiento

### Recurrente contractual
Usar importe y fecha conocidos.

Ejemplos:
- hipoteca;
- seguro;
- suscripción.

### Estacional
Ponderar fuertemente mismo periodo del año anterior.

Ejemplos:
- vacaciones;
- regalos;
- calefacción;
- material escolar.

### Variable frecuente
Combinar:
- mismo periodo anterior;
- medias recientes;
- tendencia.

Ejemplos:
- supermercado;
- restaurantes;
- combustible.

### Extraordinario
No proyectar automáticamente como recurrente.

Ejemplos:
- compra de vehículo;
- reforma;
- viaje excepcional.

Debe detectarse/marcarse para evitar distorsión.

## Income Forecast

Fuentes:
1. ingresos recurrentes confirmados;
2. nómina histórica;
3. ingresos planificados;
4. mismo periodo anterior;
5. variabilidad histórica.

Ingresos extraordinarios no se repiten automáticamente.

## CommitmentsEngine

Un compromiso es un flujo futuro con evidencia razonable.

Tipos:
- hipoteca/préstamo;
- recibo;
- seguro;
- impuesto;
- suscripción;
- compra financiada;
- pago aplazado;
- reserva;
- objetivo/aportación planificada;
- gasto manual previsto.

Campos:
- amount;
- currency;
- due_date;
- recurrence;
- confidence;
- source;
- mandatory;
- cancellable;
- status.

## Available Cash

Diferenciar:

```text
bank_balance
- near_term_commitments
- protected_emergency_buffer
= operationally_available_cash
```

No etiquetar como “dinero para invertir” automáticamente.

## Escenarios

Como mínimo:
- conservative;
- base;
- favorable.

Los escenarios varían assumptions de categorías inciertas, no facts contractuales conocidos.

## Intervalos

Mostrar:
- point estimate/base;
- expected range;
- confidence/calibration.

El rango debe provenir de error histórico/variabilidad, no de porcentajes inventados.

## Backtesting del forecast

La precisión debe medirse continuamente.

Para cada forecast histórico:
- predicted;
- actual;
- error absolute;
- error percentage cuando sea válido;
- error por categoría;
- horizon;
- model_version.

Métricas:
- MAE;
- WAPE;
- bias;
- coverage del intervalo.

Evitar MAPE cuando denominadores pequeños produzcan resultados engañosos.

## Model selection

No fijar un único algoritmo para todas las categorías.

Comparar localmente modelos simples:
- same-period-last-year;
- rolling mean;
- weighted recent mean;
- seasonal naive;
- trend-adjusted seasonal;
- commitments + residual model.

Elegir por categoría/horizonte según backtesting rolling, con penalización a modelos inestables.

No hace falta ML complejo si un modelo simple funciona mejor.

## Explicación

Ejemplo:

“Entre octubre y diciembre se estiman 8.420 € de gasto. El mismo periodo de 2025 fue 7.980 €. La diferencia se explica principalmente por +260 € de seguros ya confirmados y una tendencia de +4 % en alimentación. Rango histórico esperado: 8.050–8.850 €.”

Cada afirmación debe ser reproducible.

## Gráficas

- actual vs forecast;
- forecast vs same period last year;
- cumulative income/expense/savings;
- stacked forecast by category;
- confidence band;
- commitments timeline.

## Alertas predictivas

- saldo proyectado bajo;
- ahorro objetivo en riesgo;
- gasto proyectado por encima de presupuesto;
- fondo de emergencia proyectado por debajo del objetivo;
- mes con concentración de pagos;
- categoría desviándose del forecast.

## Recalculación

Recalcular cuando:
- entra un nuevo movimiento;
- cambia un compromiso;
- aparece una factura/contrato;
- cambia un ingreso;
- se corrige una categoría;
- cambia el horizonte.

Usar incremental recomputation cuando sea posible.

## Regla anti-alucinación

El LLM explica el forecast. No produce las cifras.

ForecastEngine produce:
- valores;
- escenarios;
- rangos;
- drivers;
- accuracy;
- version.

## UX

Toda previsión debe mostrar:
- horizonte;
- fecha de cálculo;
- baseline del año anterior;
- assumptions;
- rango;
- precisión histórica;
- drivers;
- known vs estimated;
- posibilidad de excluir extraordinarios.


## Previsión automática de cierre de mes

La vista de Análisis calcula automáticamente una previsión al último día del mes usando exclusivamente datos locales.

Para cada cuenta:
1. parte del saldo actual guardado;
2. estima los movimientos restantes con un 70 % del mismo tramo del año anterior y un 30 % del ritmo de los últimos 60 días cuando ambas fuentes existen;
3. si solo existe una fuente histórica, usa únicamente esa;
4. si no existe histórico suficiente, no inventa movimientos;
5. calcula saldo estimado al cierre = saldo actual + ingresos restantes estimados - gastos restantes estimados.

Los compromisos conocidos hasta final de mes actúan como **suelo del gasto restante total**. No se suman ciegamente al histórico para evitar doble conteo. Como el modelo actual de Commitment no identifica una cuenta bancaria de cargo, tampoco se distribuyen artificialmente entre cuentas.

La pantalla muestra grandes indicadores de:
- gasto estimado al cierre;
- ahorro estimado al cierre;
- saldo total estimado;
- precisión histórica del gasto.

### Precisión histórica

Se ejecuta un backtest sobre hasta seis meses cerrados. Para cada mes se simula qué habría pronosticado el modelo en el mismo día relativo del mes y se compara con el resultado real.

Se muestran:
- número de meses evaluados;
- WAPE del gasto;
- precisión derivada `max(0, 1 - WAPE)`;
- MAE del ahorro.

Si no hay histórico suficiente, la precisión se muestra como no disponible en lugar de inventar una confianza.


## Ingresos recurrentes pendientes de cobro

El cálculo operativo de liquidez detecta fuentes de ingreso mensuales a partir de movimientos positivos repetidos, excluyendo transferencias internas y reembolsos. Se proyecta únicamente el siguiente cobro y solo cuando la misma fuente aún no ha entrado en el mes actual.

Ejemplos:
- nómina;
- pensión;
- alquiler recurrente;
- otro ingreso mensual suficientemente estable.

La fecha, el importe y la confianza se muestran al usuario. Un ingreso previsto no se presenta como saldo bancario confirmado.

## Periodos históricos

Cuando el usuario selecciona un periodo ya cerrado, no se reutiliza la liquidez actual para fabricar un «disponible histórico». La interfaz muestra el cierre real del periodo y lo compara con una previsión reconstruida:
- ingresos reales vs previstos;
- gastos reales vs previstos;
- ahorro real vs previsto;
- desviación del ahorro.

La reconstrucción utiliza únicamente señales históricas anteriores al periodo cuando el motor lo permite y se etiqueta como reconstruida; no debe confundirse con una predicción persistida en aquel momento.

## Calibración de infrapredicción

La previsión de cierre de mes mantiene un backtest de meses cerrados. Además de WAPE/MAE, calcula el sesgo y la infrapredicción típica del gasto. Cuando existen al menos tres meses evaluables y el sistema ha tendido a quedarse corto, añade una corrección proporcional a los días restantes.

Los compromisos/recurrentes conocidos y los patrones históricos por categoría actúan como suelos alternativos, no acumulativos, para evitar contar dos veces el mismo gasto.
