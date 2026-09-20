# Motores financieros

## Regla general

Los motores financieros son funciones deterministas, testeables y sin dependencia de LLM. Todas las entradas, fórmulas y salidas relevantes deben ser trazables.

## NetWorthEngine

Calcula:
- activos;
- pasivos;
- patrimonio neto;
- liquidez;
- capital invertible;
- fondo de emergencia.

Evitar doble contabilización entre cuentas y carteras.

## CashFlowEngine

Por periodo:
- ingresos;
- gastos;
- ahorro;
- ratio de ahorro;
- media móvil;
- variación intermensual/interanual.

Transferencias entre cuentas propias no cuentan como ingreso/gasto.

## RecurringEngine

Detecta series mediante:
- comercio normalizado;
- intervalo;
- tolerancia temporal;
- tolerancia de importe;
- historial mínimo.

Salida:
- periodicidad;
- importe esperado;
- próxima fecha;
- confianza;
- anomalías.

## PortfolioEngine

Calcula:
- valor;
- coste;
- P&L realizado/no realizado;
- pesos;
- asignación por activo/sector/país/divisa;
- contribución por posición.

## RiskEngine

Métricas:
- volatilidad;
- beta;
- correlación;
- maximum drawdown;
- Sharpe;
- Sortino;
- VaR;
- CVaR;
- concentración.

Toda métrica debe registrar:
- ventana;
- frecuencia;
- benchmark;
- risk-free rate si aplica;
- metodología.

## RecommendationEngine

No es un LLM.

Combina scores:
- fundamentals;
- valuation;
- growth;
- quality;
- momentum;
- risk;
- news;
- macro;
- portfolio fit.

Los pesos son configurables y versionados.

La salida no debe transformarse directamente en orden de compra.

## ScenarioEngine

Compara decisiones como:
- mantener liquidez;
- amortizar deuda;
- depósito;
- inversión;
- cambio de hipoteca.

Escenarios con supuestos explícitos y sensibilidad.

## BacktestEngine

Debe soportar:
- comisiones;
- dividendos;
- slippage;
- rebalanceo;
- benchmark.

Evitar:
- look-ahead bias;
- survivorship bias;
- data leakage.

Métricas:
- CAGR;
- volatilidad;
- Sharpe;
- Sortino;
- max drawdown;
- Calmar;
- turnover.

Implementar walk-forward para estrategias ajustadas.

## Datos temporales

Todas las comparaciones históricas deben utilizar solo información disponible en la fecha analizada.

## Precisión

Usar Decimal para importes monetarios cuando corresponda. No depender de float binario para cálculos de dinero, cuotas o penalizaciones.


## ForecastEngine

Inputs:
- transactions;
- income series;
- recurring series;
- commitments;
- budgets;
- contract changes;
- extraordinary markers.

Debe utilizar como baseline obligatorio el mismo periodo del año anterior cuando exista histórico suficiente.

No copiarlo literalmente: combinarlo con tendencia reciente, estacionalidad y commitments conocidos.

Outputs:
- predicted income;
- predicted expenses;
- predicted savings;
- predicted liquidity;
- category forecasts;
- confidence intervals;
- drivers;
- accuracy metadata.

## CommitmentsEngine

Resuelve obligaciones futuras y evita tratar saldo bruto como liquidez libre.

## StressTestEngine

Aplica shocks como assumptions sobre snapshots actuales.

## CoverageEngine

Compara coberturas estructuradas y detecta gaps/overlaps.

## CostCenterEngine

Agrega gasto total por activo/área de vida.

## DecisionOutcomeEngine

Compara impacto esperado con observado para calibración posterior.
