# Arquitectura

## Enfoque

Financito es una WebApp local-first. La UI se ejecuta en el navegador; el backend y los datos privados permanecen en el equipo del usuario.

## Componentes

```text
┌─────────────────────────────────────────────┐
│ Next.js WebApp · Tailwind · shadcn/ui       │
└───────────────────┬─────────────────────────┘
                    │ HTTPS/localhost
┌───────────────────▼─────────────────────────┐
│ FastAPI Local API                           │
├─────────────────────────────────────────────┤
│ Application / Use Cases                     │
│ Domain                                      │
│ Financial Engines                           │
│ RAG / AI Orchestrator                       │
│ Provider Adapters                           │
└──────────────┬───────────────┬──────────────┘
               │               │
      ┌────────▼───────┐ ┌─────▼────────────┐
      │ SQLite/FTS/vec │ │ External sources │
      └────────┬───────┘ └──────────────────┘
               │
      ┌────────▼──────────────┐
      │ Financial Vault      │
      └───────────────────────┘
```

## Frontend

Responsabilidades:
- presentación;
- navegación;
- formularios;
- filtros;
- visualización;
- estado de carga/error;
- caché cliente;
- accesibilidad.

No contiene reglas financieras críticas.

Tecnologías:
- Next.js;
- React;
- TypeScript;
- TailwindCSS;
- shadcn/ui;
- TanStack Query;
- React Hook Form;
- Zod;
- gráficos accesibles.

## API local

FastAPI actúa como frontera entre navegador y datos privados.

Responsabilidades:
- autenticar sesión local;
- validar inputs;
- coordinar use cases;
- streaming del chat;
- exponer estado de jobs;
- no filtrar secretos.

La API debe escuchar solo en loopback por defecto.

## Capas

### Domain
Entidades, value objects, políticas y reglas financieras puras.

### Application
Use cases y orquestación.

### Infrastructure
SQLite, filesystem, OCR, modelos locales, providers externos.

### Presentation
API HTTP y WebApp.

## Módulos de dominio

- Banking
- Transactions
- Budgeting
- Recurring
- Documents
- Contracts
- Insurance
- Mortgage
- NetWorth
- Portfolio
- MarketData
- Crypto
- News
- Risk
- Recommendations
- Optimization
- Savings
- Planning

## Motores deterministas

Los motores financieros no dependen de LLM:
- NetWorthEngine
- CashFlowEngine
- RecurringEngine
- RiskEngine
- PortfolioEngine
- MortgageEngine
- SwitchingCostEngine
- BreakEvenEngine
- BenefitValuationEngine
- LinkedProductEngine
- FinancialOptimizationEngine
- BacktestEngine
- ScenarioEngine

## IA

AI Orchestrator:
1. interpreta intención;
2. selecciona tools;
3. recupera evidencia;
4. solicita cálculos a motores;
5. compone contexto;
6. invoca LLM local;
7. valida formato y citas.

El LLM no recibe acceso SQL directo.

## Persistencia

SQLite como fuente estructurada.

Extensiones/capacidades:
- SQLCipher o cifrado equivalente;
- FTS5 para búsqueda textual;
- sqlite-vec para vectores.

Los archivos originales permanecen en el Vault; la DB almacena referencias, hashes, metadatos y texto indexado.

## Jobs

Procesos pesados:
- OCR;
- extracción;
- embeddings;
- sincronizaciones;
- importaciones;
- ingestión de noticias;
- backtests.

Deben ejecutarse fuera del request síncrono y reportar progreso.

## Providers

Interfaces:
- BankingProvider
- MarketDataProvider
- FundamentalDataProvider
- CryptoProvider
- NewsProvider
- MacroProvider
- MortgageComparisonProvider
- InsuranceComparisonProvider
- EnergyComparisonProvider
- TelecomComparisonProvider
- BankProductComparisonProvider

## Frescura

Cada registro externo debe incluir:
- source;
- source_id cuando exista;
- fetched_at;
- source_updated_at;
- freshness_policy;
- stale flag derivable.

## Offline

Sin Internet siguen disponibles:
- documentos indexados;
- RAG local;
- movimientos ya almacenados;
- patrimonio;
- cartera histórica;
- analítica;
- comparaciones guardadas.

La UI muestra claramente datos obsoletos.

## Escalabilidad

El diseño debe admitir en el futuro:
- PWA instalable;
- empaquetado desktop;
- múltiples perfiles;
- workers separados;
- Postgres opcional.

La versión inicial no introduce infraestructura distribuida innecesaria.
