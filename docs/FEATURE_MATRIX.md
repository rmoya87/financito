# Matriz funcional

Estado:
- **OK**: implementado y ejecutable.
- **PARCIAL**: implementado con alcance acotado explícito.
- **EXTERNO**: código listo; necesita credenciales, proveedor, certificado u otra fuente externa.
- **PENDIENTE**: no se considera terminado.

| Área | Función | Estado |
|---|---|---|
| Seguridad | SQLCipher + clave segura | OK |
| Seguridad | secretos providers en credential store | OK |
| Seguridad | API loopback + Host/Origin + CSRF | OK |
| Vault | vigilancia, SHA y deduplicación | OK |
| Vault | OCR + HEIC | OK |
| Vault | idioma y clasificación | OK |
| Vault | hechos contractuales con página | PARCIAL |
| Vault | revisión accionable + proyección de facts confirmados | OK |
| RAG | chunking con página | OK |
| RAG | FTS5/BM25 | OK |
| RAG | embeddings locales | OK |
| RAG | sqlite-vec + fallback cosine | OK |
| RAG | RRF + reranking léxico | OK |
| Chat | cálculo estructurado + citas navegables | OK |
| Demo | dataset sintético | OK |
| Movimientos | CSV/XLSX/QIF/OFX/CAMT/MT940 | OK |
| Movimientos | categorización/reglas/review queue | OK |
| Movimientos | splits/transferencias/reembolsos | OK |
| Recurrentes | detección y anomalías | OK |
| Analytics | categoría/comercio/fijo-variable/esencial | OK |
| Forecast | baseline, compromisos y accuracy | OK |
| Presupuesto | categorías y budget-vs-actual | OK |
| Patrimonio | net worth/activos/deuda | OK |
| Banking | adapter PSD2 persistente | OK |
| Banking | Bankinter/Revolut u otro banco disponible | EXTERNO |
| Banking | consentimiento, aviso, sync y revocación | OK |
| Portfolio | posiciones/trades/FIFO tax lots | OK |
| Markets | quotes/histórico/caché | EXTERNO |
| Crypto | precio y riesgo | OK |
| Risk | vol/Sharpe/Sortino/drawdown/VaR/CVaR | OK |
| Risk | exposición y concentración | OK |
| Fundamentals | SEC companyfacts seleccionados | PARCIAL |
| Macro | ECB | OK |
| News | búsqueda e ingestión GDELT | OK |
| News | impacto/sentimiento robusto | PENDIENTE |
| Recommendation | scoring determinista | OK |
| Recommendation | portfolio fit automático | PARCIAL |
| Contracts | extracción + renovación/preaviso | PARCIAL |
| Insurance | pólizas/coberturas/duplicidades | OK |
| Insurance | requisitos y huecos definidos por usuario | OK |
| Mortgage | cuota/intereses | OK |
| Mortgage | amortización parcial cuota/plazo | OK |
| Mortgage | FEIN/FIAE compleja y novación/subrogación | PARCIAL |
| Optimization | switching costs + break-even | OK |
| Optimization | benefits/linked products | OK |
| Optimization | comparadores comerciales | EXTERNO |
| Backtest | media móvil | OK |
| Planning | amortizar vs invertir | OK |
| Decisions | casos/alternativas/outcomes | OK |
| Cost Centers | asignaciones y agregación | OK |
| Stress | shocks y cash runway | OK |
| Calendar | eventos financieros | OK |
| Search | búsqueda global | OK |
| Backup | cifrado + restore verificado | OK |
| Privacy | export, rebuild, borrado | OK |
| Repair | integridad y reparaciones soportadas | OK |
| AI | gestor modelos Ollama | EXTERNO |
| Tax | FIFO y estimación parametrizada | PARCIAL |
| Tax | normativa legal versionada por jurisdicción | PENDIENTE |
| Runtime | launcher local | OK |
| Runtime | app macOS firmada/notarizada | EXTERNO |
| Accessibility | axe WCAG AA en journeys core | PARCIAL |
| E2E | journeys core Playwright | PARCIAL |
| Temporal | provenance/freshness + wealth as-of conservador | PARCIAL |
