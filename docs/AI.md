# IA local

## Principio

El LLM es una capa de interpretación, no la fuente de verdad financiera.

## LocalLLMProvider

Interfaz conceptual:
- generate
- stream
- classify
- summarize
- extract_structured
- reason_with_tools

Adapters objetivo:
- Ollama;
- llama.cpp;
- MLX cuando el entorno lo permita.

## ModelRouter

Selecciona modelo según tarea:
- clasificación: pequeño;
- extracción simple: pequeño;
- resumen: medio;
- RAG: medio;
- razonamiento financiero complejo: modelo local avanzado + tools.

Criterios:
- RAM;
- latencia;
- contexto;
- calidad;
- disponibilidad.

## Tool calling

Herramientas mínimas:
- get_accounts
- get_transactions
- get_cash_flow
- get_expenses
- get_income
- get_recurring
- get_contracts
- get_insurance
- get_mortgage
- search_documents
- get_portfolio
- get_market_price
- get_price_history
- get_fundamentals
- get_crypto_metrics
- get_latest_news
- get_macro_data
- calculate_net_worth
- calculate_portfolio_risk
- calculate_mortgage_scenario
- calculate_switching_costs
- calculate_break_even
- find_savings_opportunities
- run_backtest

El modelo recibe schemas de entrada/salida; la aplicación valida toda llamada.

## Respuesta estructurada

Formato lógico:
```json
{
  "result": "...",
  "sources": [],
  "calculations": [],
  "confidence": 0.0,
  "dataFreshness": {}
}
```

Confidence nunca representa una probabilidad real de rentabilidad salvo que proceda de un modelo estadístico validado.

## Memoria

Separar:
- facts;
- preferences;
- decisions.

No almacenar razonamiento interno del modelo como hecho.

## Privacidad

- prompts locales;
- modelos locales;
- sin telemetría de contenido;
- logs redactados;
- ningún documento enviado a IA cloud.

## Prompting

System prompts versionados en código.
Cada cambio debe tener:
- versión;
- tests;
- motivo.

No incrustar reglas críticas únicamente en prompts; deben existir también en dominio/validación.
