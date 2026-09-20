# Arquitectura frontend

## Objetivo

Maximizar reutilización, consistencia, rendimiento y mantenibilidad sin duplicar reglas financieras.

## Stack

- Next.js
- React
- TypeScript estricto
- TailwindCSS
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod
- TanStack Table para tablas complejas
- Recharts para visualización cuando aporte valor

Evitar dependencias adicionales salvo necesidad demostrable.

## Producción

La WebApp debe poder exportarse de forma estática. No depender de Server Actions, SSR remoto, middleware cloud, edge runtime ni API routes de Next para lógica de negocio. Toda lógica sensible reside en FastAPI local.

## Capas

app/routes → features → shared business UI → primitives shadcn → cliente API generado.

## Estructura de feature

Cada feature agrupa api, components, hooks, schemas, mappers, types, utils y tests. No crear carpetas globales genéricas cuando el código pertenece claramente a una feature.

## Niveles de componentes

### UI primitives

Proceden de shadcn/ui: Button, Input, Form, Card, Table, Dialog, Sheet, Tabs, Popover, Tooltip, Badge, Skeleton, Alert, Command, Select, DropdownMenu, Calendar, Progress y Separator.

No contienen reglas de negocio.

### Shared application components

Reutilizables:
- PageHeader
- SectionHeader
- MetricCard
- Money
- Percentage
- FreshnessBadge
- SyncStatusBadge
- ConfidenceBadge
- RiskBadge
- SourceBadge
- DataQualityBadge
- EmptyState
- ErrorState
- LoadingState
- DataTable
- FilterBar
- SearchInput
- DateRangePicker
- CurrencySelector
- EvidencePanel
- CalculationBreakdown
- SourceCitation
- SensitiveValue
- PrivacyToggle
- AsyncActionButton
- JobProgress

### Feature components

Solo conceptos del dominio: AccountCard, TransactionRow, InsuranceComparison, MortgageScenario, PortfolioAllocation, OpportunityCard, DocumentFacts y ChatAnswer.

## Regla anti-duplicación

Si dos features necesitan el mismo patrón visual:
1. comprobar shadcn;
2. comprobar shared;
3. extraer solo si realmente es genérico.

No crear abstracciones antes de dos usos claros.

## Estado

TanStack Query es la única fuente para estado procedente de la API local. No copiar respuestas completas a Zustand.

Zustand queda limitado a estado UI efímero como sidebar, privacy mode o panel inspector.

## Contratos

Generar cliente y tipos TypeScript desde OpenAPI. No mantener DTO duplicados manualmente entre Python y TypeScript.

## Formularios

Zod para UX, Pydantic como validación autoritativa y React Hook Form para gestión del formulario.

## Dinero

La UI recibe cantidades como strings decimales o unidades menores definidas por contrato. Nunca realizar cálculos monetarios críticos con number de JavaScript.

## Rendimiento

- code splitting por ruta;
- lazy loading de módulos pesados;
- no cargar gráficas hasta ser necesarias;
- importaciones directas;
- evitar barrel files masivos;
- virtualización para tablas grandes;
- memoización solo con evidencia;
- evitar context global mutable;
- staleTime por recurso;
- deduplicar requests;
- paginación cursor;
- SSE solo mientras exista consumidor;
- presupuesto de bundle por ruta;
- iconos tree-shakeable;
- sin librerías duplicadas.

## DataTable

Crear un único DataTable base con sorting, filtros, columnas, paginación, virtualización opcional, selección, navegación teclado y estados loading/empty/error. Las features solo definen columnas y acciones.

## Gráficas

Wrappers compartidos:
- TimeSeriesChart
- AllocationChart
- ComparisonChart
- WaterfallChart
- DrawdownChart

Todos normalizan tooltip, formato, accesibilidad, responsive, fuente y frescura.

## Seguridad frontend

- ningún secreto en bundle;
- ningún token de provider en navegador;
- ningún dato privado en URL;
- no guardar datos sensibles en localStorage o sessionStorage;
- clipboard solo por acción explícita;
- CSP estricta;
- sanitización de rich text;
- enlaces externos con políticas seguras.

## Accesibilidad

Objetivo WCAG AA, keyboard-first, focus visible, reduced motion, HTML semántico y alternativas textuales para gráficas.

## Design tokens

Centralizar color, spacing, radius, shadow, typography, density y semántica de gráficas mediante variables CSS consumidas por Tailwind.
