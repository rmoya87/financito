# Roadmap

## Fase 0 — Fundación documental

Entregables:
- especificación funcional;
- arquitectura;
- modelo de datos;
- seguridad;
- RAG/IA;
- providers;
- motores;
- UI/UX;
- API;
- ADRs.

Estado: iniciado con esta base.

## Fase 1 — Knowledge Foundation

Objetivo: primer producto útil sin bancos.

- monorepo;
- WebApp;
- FastAPI;
- DB;
- cifrado;
- Vault;
- ingestión PDF/imágenes;
- OCR;
- chunking;
- embeddings;
- FTS/vector;
- chat local;
- citas;
- demo mode.

Criterio:
“Dejo documentos y puedo preguntar sobre ellos con fuentes.”

## Fase 2 — Finanzas personales

- CSV/OFX/QIF;
- cuentas manuales;
- movimientos;
- taxonomía completa;
- categorización automática;
- normalización de comercios;
- reglas;
- splits;
- transferencias internas;
- reembolsos;
- cola de revisión;
- anomalías;
- recurrentes;
- presupuestos;
- forecast;
- analytics;
- gráficas de decisión;
- dashboard;
- net worth básico;
- data quality center.

Criterio:
“Todos mis movimientos están explicados o pendientes de revisión explícita, puedo entender en qué gasto, cómo cambia y qué decisiones tienen impacto.”

## Fase 3 — Open Banking

- adapter;
- proveedor autorizado;
- Bankinter;
- Revolut;
- consentimientos;
- sync incremental;
- reconciliación/deduplicación.

Criterio:
“Mis cuentas y movimientos se actualizan de forma segura.”

## Fase 4 — Inversión

- portfolios;
- import broker;
- market data;
- acciones/ETF/fondos;
- cripto;
- allocation;
- risk engine.

## Fase 5 — Inteligencia de mercado

- fundamentales;
- noticias;
- macro;
- scoring;
- recomendaciones explicables;
- historial de tesis.

## Fase 5.5 — Motor de decisiones

- DecisionCase;
- alternativas;
- impacto mensual/anual/acumulado;
- escenarios;
- sensibilidad;
- evidencia;
- confidence de datos;
- historial de decisiones.

Criterio:
“Cualquier recomendación importante puede compararse, recalcularse y auditarse.”

## Fase 6 — Optimización

- contracts;
- seguros;
- hipoteca;
- switching costs;
- break-even;
- beneficios;
- comparadores;
- oportunidades.

Criterio:
“Financito identifica cambios con beneficio neto real.”

## Fase 7 — Planificación avanzada

- backtesting;
- escenarios;
- amortizar vs invertir;
- fiscalidad modular;
- planificación temporal;
- memoria de decisiones.

## Prioridad permanente

- seguridad;
- exactitud;
- trazabilidad;
- privacidad;
- rendimiento;
- UX.


## Requisitos transversales desde Fase 1

No son una fase posterior:
- arquitectura estrictamente local;
- seguridad;
- backup/restore;
- provenance;
- data quality;
- multi-divisa;
- audit log;
- Health Center;
- performance budgets;
- contratos frontend/backend generados;
- design system reutilizable;
- gestión de modelos locales.

Las features nuevas deben integrarse sin duplicar componentes, engines ni DTO.
