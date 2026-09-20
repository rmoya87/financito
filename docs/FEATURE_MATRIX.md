# Matriz funcional

Leyenda:
- F1–F7: fase objetivo.
- Core: requisito transversal.

| Área | Función | Fase |
|---|---|---|
| Seguridad | DB cifrada | F1 |
| Seguridad | secretos seguros | F1 |
| Seguridad | API loopback | F1 |
| Vault | vigilancia de carpeta | F1 |
| Vault | SHA/deduplicación | F1 |
| Vault | OCR | F1 |
| Vault | clasificación | F1 |
| RAG | chunking semántico | F1 |
| RAG | embeddings locales | F1 |
| RAG | BM25 + vector | F1 |
| RAG | reranking | F1 |
| Chat | respuestas con citas | F1 |
| Demo | dataset ficticio | F1 |
| Movimientos | CSV/OFX/QIF | F2 |
| Movimientos | categorización | F2 |
| Movimientos | reglas | F2 |
| Recurrentes | detección | F2 |
| Recurrentes | subidas/anomalías | F2 |
| Presupuesto | categorías/objetivos | F2 |
| Patrimonio | net worth | F2 |
| Banking | adapter PSD2 | F3 |
| Banking | Bankinter | F3 |
| Banking | Revolut | F3 |
| Banking | consentimientos | F3 |
| Portfolio | posiciones | F4 |
| Markets | cotizaciones/históricos | F4 |
| Crypto | métricas específicas | F4 |
| Risk | exposición/riesgo | F4/F5 |
| Fundamentals | estados/ratios | F5 |
| News | ingestión/dedupe | F5 |
| News | impacto/sentimiento | F5 |
| Recommendation | scoring determinista | F5 |
| Recommendation | portfolio fit | F5 |
| Contracts | extracción | F6 |
| Insurance | comparación | F6 |
| Mortgage | escenarios | F6 |
| Optimization | switching costs | F6 |
| Optimization | break-even | F6 |
| Optimization | puntos/beneficios | F6 |
| Optimization | vinculaciones | F6 |
| Optimization | oportunidades ahorro | F6 |
| Optimization | rendimiento liquidez | F6 |
| Backtest | motor | F7 |
| Planning | amortizar vs invertir | F7 |
| Memory | decisiones históricas | F5+ |
| Observability | Developer Mode | Core |
| Freshness | timestamps/stale | Core |
| Offline | datos locales | Core |
| Accessibility | WCAG AA objetivo | Core |


## Funciones transversales añadidas

| Área | Función | Fase |
|---|---|---|
| Onboarding | wizard local | F1 |
| Data Quality | reconciliación | F2+ |
| Calendar | eventos financieros | F2+ |
| Alerts | alertas locales | F2+ |
| Goals | objetivos financieros | F2+ |
| Scenarios | laboratorio de escenarios | F6/F7 |
| Tax | centro fiscal modular | F7 |
| Currency | multi-divisa | Core |
| Ownership | propiedad personal/compartida | Core |
| Assets | valoración manual | F2 |
| Backup | backup/restore cifrado | F1 |
| Portability | export abierto | F1+ |
| Audit | actividad local | Core |
| Health | salud de sistema/providers | Core |
| AI | gestor de modelos locales | F1 |
| Rules | automatizaciones locales seguras | F2+ |
| Search | búsqueda global | F1+ |
| Privacy | borrado/retención | Core |
| Performance | presupuestos y profiling | Core |


## Categorización, análisis y decisiones

| Área | Función | Fase |
|---|---|---|
| Transactions | taxonomía jerárquica | F2 |
| Transactions | merchant normalization | F2 |
| Transactions | clasificación automática | F2 |
| Transactions | confidence + review queue | F2 |
| Transactions | splits | F2 |
| Transactions | transferencias internas | F2 |
| Transactions | reembolsos | F2 |
| Transactions | anomalías | F2 |
| Analytics | cash-flow temporal | F2 |
| Analytics | gastos por categoría/comercio | F2 |
| Analytics | fijo vs variable | F2 |
| Analytics | esencial vs discrecional | F2 |
| Analytics | forecast | F2 |
| Visualization | gráficas compartidas | F2+ |
| Decision | DecisionCase | F5.5 |
| Decision | alternativas e impacto | F5.5 |
| Decision | sensibilidad | F5.5 |
| Decision | confidence de evidencia | F5.5 |
| Governance | AGENTS.md | Core |
| Governance | workflow estándar | Core |
| Governance | no-alucinación | Core |
| Governance | documentación autoritativa | Core |


## Forecasting, resiliencia y operabilidad

| Área | Función | Fase |
|---|---|---|
| Forecast | mismo periodo año anterior | F2.5 |
| Forecast | tendencia + estacionalidad | F2.5 |
| Forecast | gastos previstos | F2.5 |
| Forecast | ahorro previsto | F2.5 |
| Forecast | liquidez prevista | F2.5 |
| Forecast | intervalos y precisión histórica | F2.5 |
| Forecast | backtesting MAE/WAPE/bias | F2.5 |
| Commitments | obligaciones futuras | F2.5 |
| Resilience | cash runway | F2.5 |
| Resilience | stress testing | F2.5 |
| Cost Centers | coste por área/activo | F2.5 |
| Coverage | duplicidades/huecos | F6 |
| Graph | relaciones financieras | Core |
| Decisions | resultado esperado vs real | F6+ |
| Temporal | as-of reproducible | Core |
| Investments | tax lots | F4 |
| Actions | Action Center | F2+ |
| Integrity | Repair Center | Core |
| AI Quality | model evaluation gates | Core |
| Runtime | launcher/supervisor local | F1 |
