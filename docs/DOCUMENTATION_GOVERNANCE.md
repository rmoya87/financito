# Gobierno de documentación

## Objetivo

Evitar documentación obsoleta, duplicada o contradictoria.

## Fuente por tema

- visión → README
- funcional → FUNCTIONAL_SPEC
- arquitectura → ARCHITECTURE
- seguridad → SECURITY_MODEL
- frontend → FRONTEND_ARCHITECTURE
- backend → BACKEND_ARCHITECTURE
- componentes → COMPONENT_CATALOG
- datos → DATA_MODEL
- API → API/OpenAPI
- RAG → RAG
- IA → AI + AI_ENGINEERING_RULES
- motores → FINANCIAL_ENGINES
- gastos → EXPENSES_AND_CATEGORIZATION
- decisiones → DECISION_ENGINE
- visualizaciones → VISUALIZATION_AND_INSIGHTS
- optimización → OPTIMIZATION_ENGINE
- hipoteca → MORTGAGE_ENGINE
- rendimiento → PERFORMANCE
- proceso → DEVELOPMENT_WORKFLOW
- decisiones estructurales → ADR
- terminología → GLOSSARY
- reglas de agentes → AGENTS.md + AI_ENGINEERING_RULES
- proceso de desarrollo → DEVELOPMENT_WORKFLOW

## Regla de no duplicación

Un concepto tiene un documento autoritativo.

Otros documentos enlazan a él en lugar de copiar reglas extensas.

## Versionado

Cambios incompatibles o relevantes deben registrar:
- fecha;
- ADR cuando aplique;
- migración/API version.

## Cambios funcionales

Ningún cambio funcional se considera completo si la documentación autoritativa sigue describiendo el comportamiento anterior.

## Docs vs código

Si se detecta contradicción:
1. identificar comportamiento real;
2. validar cuál es correcto;
3. corregir código o documentación;
4. añadir test que evite recaída.

## Archivos históricos

No mantener documentos “old”, “final2”, “new”.
Git ya conserva historia.

## Estado

No usar documentos como listas eternas de TODO.
El roadmap contiene fases y estado.

## Diagramas

Preferir Mermaid/texto versionable.
Evitar imágenes binarias para arquitectura salvo necesidad.

## Terminología

Mantener glosario cuando aparezcan conceptos ambiguos.

Nombres de entidades técnicas estables.
