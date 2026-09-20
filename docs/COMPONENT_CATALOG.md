# Catálogo de componentes

## Layout

AppShell, Sidebar, TopBar, Breadcrumbs, ContentContainer, DetailPanel, SplitView y CommandPalette.

## Estados

PageSkeleton, SectionSkeleton, EmptyState, ErrorState, OfflineState, StaleState, PermissionState y JobProgress.

## Datos financieros

Money, MoneyDelta, Percentage, PercentageDelta, CurrencyBadge, SensitiveValue, TrendIndicator, RiskBadge, ConfidenceBadge, FreshnessBadge, SourceBadge y DataQualityBadge.

## Métricas

MetricCard, MetricGroup, KPIHero, ComparisonMetric y BreakdownMetric.

## Evidencia

EvidencePanel, SourceCitation, SourceList, CalculationBreakdown, AssumptionList, DataFreshnessPanel y ConfidenceExplanation.

## Tablas

Base:
- DataTable
- DataTableToolbar
- ColumnSelector
- Pagination
- VirtualRows
- BulkActions

Especializadas como configuración: TransactionsTable, PositionsTable, DocumentsTable, OpportunitiesTable y ContractsTable.

## Filtros

FilterBar, DateRangeFilter, AccountFilter, CategoryFilter, AssetFilter, ProviderFilter, StatusFilter y SearchFilter.

## Gráficas

TimeSeriesChart, AreaTrendChart, AllocationChart, ComparisonBarChart, WaterfallChart, DrawdownChart, CashFlowChart y AmortizationChart.

## Formularios

FormSection, MoneyField, PercentageField, CurrencyField, DateField, ProviderSelect, RiskToleranceField y AllocationField.

## Bancos

AccountCard, InstitutionLogo, BalanceSummary, SyncStatus, ConsentExpiry y ConnectionHealth.

## Movimientos

TransactionRow, MerchantIdentity, CategoryPicker, RuleSuggestion, RecurringIndicator y DuplicateIndicator.

## Documentos

DocumentCard, DocumentStatus, DocumentPreview, ExtractedFacts, FactConfidence, CitationAnchor y ReindexButton.

## Seguros

PolicySummary, CoverageTable, CoverageDifference, DeductibleComparison y RenewalTimeline.

## Hipoteca

MortgageSummary, MortgageTerms, LinkedProductList, ScenarioCard, ScenarioComparison, BreakEvenSummary, AmortizationSchedule y CostStack.

## Inversión

PortfolioSummary, PositionRow, AllocationBreakdown, ExposurePanel, RiskSummary, InvestmentThesis, CatalystList e InvalidationList.

## Optimización

OpportunityCard, NetBenefit, SwitchingCosts, LostBenefits, BreakEvenBadge, EffortBadge, UrgencyBadge, EquivalenceBadge y OpportunityDecision.

## Chat

ChatThread, ChatMessage, ChatComposer, SuggestedPrompt, ToolActivity, AnswerEvidence, CitationChip y CalculationChip.

## Reglas de API de componentes

- no fetch interno en primitives;
- feature components pueden usar hooks de su feature;
- shared components reciben datos normalizados;
- evitar objetos enormes como props;
- evitar explosión de boolean props;
- usar variantes tipadas cuando corresponda.

## Catálogo visual local

Mantener Storybook o equivalente solo local para primitives, shared components, estados, responsive, light/dark y privacy mode. No publicarlo en Internet.


## Evidencia contractual

- ContractEvidencePanel
- ContractFactRow
- ContractConflictAlert
- ClauseSourceLink
- CalculationTrace
- CalculationInputSource
- NeedsMoreDataAlert

Toda cifra material usada en una decisión debe poder navegar desde CalculationTrace hasta el documento/página que la sustenta.
