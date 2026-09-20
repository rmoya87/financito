# WebApp

## Objetivo

La interfaz de Financito se implementará como WebApp responsive con Next.js, React, TypeScript, TailwindCSS y shadcn/ui.

## Rutas objetivo

```text
/
  /dashboard
  /accounts
  /transactions
  /budget
  /net-worth
  /investments
  /markets
  /crypto
  /documents
  /contracts
  /insurance
  /mortgage
  /services
  /opportunities
  /news
  /chat
  /settings
```

## App shell

- Sidebar
- Topbar
- Breadcrumb contextual cuando aporte valor
- Main content
- Inspector lateral opcional
- Command palette Cmd/Ctrl+K

## Dashboard

Componentes:
- NetWorthHero
- LiquidityCard
- InvestableCapitalCard
- CashFlowCard
- SavingsRateCard
- PortfolioSummary
- RiskSummary
- UpcomingPayments
- RenewalAlerts
- OptimizationOpportunities
- RelevantNews

## Accounts

- AccountsList
- AccountCard
- BalanceHistory
- SyncStatus
- ConsentStatus

## Transactions

- TransactionDataTable
- TransactionFilters
- CategoryEditor
- MerchantGroup
- RecurringBadge
- RuleBuilder
- ImportDialog

## Documents

- VaultStatus
- DocumentDataTable
- IndexingStatus
- DocumentPreview
- ExtractedFacts
- CitationInspector
- ReindexAction

## Investments

- PortfolioHeader
- AllocationChart
- PositionsTable
- PerformanceChart
- RiskPanel
- ExposureBreakdown

## Opportunities

- OpportunityList
- OpportunityCard
- NetBenefitSummary
- BreakEvenBadge
- ComparisonTable
- CalculationInspector
- SourcesPanel
- DecisionDialog

## Mortgage

- MortgageSummary
- CurrentTerms
- LinkedProducts
- ScenarioBuilder
- ScenarioComparison
- CumulativeCostChart
- BreakEvenChart
- AssumptionsPanel

## Chat

- ChatThread
- PromptComposer
- SuggestedQuestions
- StreamingAnswer
- EvidenceDrawer
- SourceCitation
- CalculationTrace

## Settings

Secciones:
- General
- Vault
- Local AI
- Embeddings
- Banking
- Market Data
- Crypto
- News
- Security
- Privacy
- Financial Profile
- Investment Profile
- Scoring
- Schedulers
- Developer Mode

## Component rules

1. Usar shadcn/ui antes de crear primitives nuevos.
2. Componentes de negocio viven en feature folders.
3. Componentes UI no contienen cálculos financieros.
4. Formularios usan schema compartido/validado.
5. Queries se encapsulan por feature.
6. Ningún secreto se persiste en localStorage.

## Estado

TanStack Query:
- server/local API state;
- caching;
- invalidation;
- mutations.

Zustand solo para:
- preferencia de sidebar;
- filtros UI efímeros;
- inspector;
- modo privacidad;
- estado no persistente cuando sea adecuado.

## Diseño responsive

Desktop es el objetivo principal inicial.

Breakpoints:
- sidebar completa;
- sidebar compacta;
- navegación móvil futura.

Las tablas densas deben ofrecer alternativa móvil.

## Skeletons

Cada módulo con carga remota/local costosa debe tener skeleton específico y evitar layout shift.

## Stale data

Badge estándar:
- actualizado;
- desactualizado;
- offline;
- error de sincronización.

## Privacidad

Modo privacidad global:
- enmascara saldos;
- P&L;
- IBAN;
- capital;
- importes sensibles en gráficas.

## Developer Mode

Panel opcional:
- endpoint;
- provider;
- latencia;
- cache hit;
- freshness;
- tools;
- chunks;
- scores RAG;
- modelo local.
