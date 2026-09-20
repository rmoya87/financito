# Estructura del repositorio

Estructura objetivo:

```text
financito/
├─ apps/
│  ├─ web/                    # Next.js + Tailwind + shadcn/ui
│  └─ api/                    # FastAPI
├─ packages/
│  ├─ contracts/              # contratos OpenAPI/tipos compartidos
│  ├─ design-tokens/          # tokens y convenciones visuales
│  └─ fixtures/               # datos ficticios para demo/tests
├─ services/
│  ├─ ingestion/
│  ├─ rag/
│  ├─ ai/
│  └─ financial-engines/
├─ docs/
│  ├─ adr/
│  └─ ...
├─ scripts/
├─ tests/
├─ .env.example
├─ .gitignore
└─ README.md
```

## apps/web

Propuesta:

```text
src/
├─ app/
├─ components/
│  ├─ ui/              # shadcn/ui, no modificar sin motivo
│  ├─ charts/
│  ├─ finance/
│  └─ layout/
├─ features/
│  ├─ dashboard/
│  ├─ accounts/
│  ├─ transactions/
│  ├─ documents/
│  ├─ portfolio/
│  ├─ mortgage/
│  ├─ optimization/
│  └─ chat/
├─ lib/
├─ hooks/
├─ types/
└─ styles/
```

Cada feature agrupa componentes, queries, schemas, mappers y tests propios.

## apps/api

```text
app/
├─ api/
├─ application/
├─ domain/
├─ infrastructure/
├─ providers/
├─ engines/
├─ rag/
├─ ai/
├─ jobs/
├─ security/
├─ db/
└─ main.py
```

## Convenciones

- No importar infrastructure desde domain.
- Los providers implementan protocolos definidos por aplicación/dominio.
- Las reglas financieras tienen tests unitarios sin I/O.
- La UI no reproduce fórmulas financieras.
- Los tipos API se generan desde OpenAPI cuando sea viable.
- Fixtures nunca incluyen información real.


## Producción local

La build de apps/web genera assets estáticos que se empaquetan/empatan con apps/api para que FastAPI sirva UI y API desde un único origen local.

No desplegar apps/web ni apps/api en servicios remotos.

## Paquetes compartidos adicionales

Objetivo:
- packages/contracts: OpenAPI/client generado;
- packages/design-tokens: tokens semánticos;
- packages/fixtures: datos sintéticos;
- packages/config: configuración compartida no secreta cuando sea útil.

No crear packages por abstracciones teóricas sin uso real.

## Documentos técnicos autoritativos

- FRONTEND_ARCHITECTURE.md
- BACKEND_ARCHITECTURE.md
- COMPONENT_CATALOG.md
- SECURITY_MODEL.md
- LOCAL_ONLY.md
- DATA_LIFECYCLE.md
