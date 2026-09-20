# Financito

**Financito** es una plataforma financiera personal 360º, local-first y orientada a privacidad. Centraliza cuentas, movimientos, documentos, contratos, seguros, hipoteca, patrimonio, inversiones, bolsa, criptomonedas, noticias financieras y oportunidades de optimización, utilizando IA local como capa de comprensión y motores deterministas como fuente de verdad financiera.

> Estado: **baseline funcional y técnico v1 cerrado para iniciar implementación**. La documentación de `/docs` y `AGENTS.md` es la fuente de verdad. El código ejecutable de las fases todavía debe implementarse siguiendo este contrato.

## Principios

1. **Privacidad por defecto**: los datos financieros y documentos personales permanecen en el equipo del usuario.
2. **IA local**: no se envían datos privados a proveedores cloud de IA.
3. **Fuentes verificables**: saldos, precios, documentos, noticias y cálculos proceden de fuentes identificables.
4. **Determinismo financiero**: el LLM no calcula saldos, rentabilidades, penalizaciones, cuotas ni métricas de riesgo.
5. **Explicabilidad**: recomendaciones y respuestas incluyen fuentes, cálculos, frescura y confianza.
6. **Solo lectura inicialmente**: Open Banking y brokers se integran para consulta, no para ejecutar operaciones.
7. **Optimización neta**: cualquier cambio de seguro, hipoteca, banco o servicio considera costes de salida, permanencias, vinculaciones, puntos, beneficios perdidos, fiscalidad y break-even.
8. **Arquitectura intercambiable**: bancos, mercados, noticias, LLM y embeddings se implementan mediante adapters.
9. **Cero coste recurrente obligatorio**: ninguna funcionalidad base puede depender de una API o agregador de pago; siempre debe existir una ruta gratuita o importación local.

## Stack objetivo

### WebApp
- Next.js + React + TypeScript
- TailwindCSS
- shadcn/ui
- TanStack Query
- React Hook Form + Zod
- Zustand únicamente para estado UI cuando aporte valor
- Recharts o equivalente para visualización

### Backend local
- Python + FastAPI
- Pydantic
- SQLAlchemy/Alembic o equivalente
- SQLite local cifrada mediante SQLCipher o alternativa validada
- FTS5/BM25
- sqlite-vec
- workers locales para ingestión documental y tareas pesadas

### IA local
- adapter para Ollama / llama.cpp / MLX
- embeddings multilingües locales
- RAG híbrido: BM25 + vector + filtros + reranking
- tool calling interno
- ningún dato financiero privado se envía a una API externa de IA

### Datos externos
- Open Banking / PSD2 mediante proveedor regulado cuando sea necesario
- adapters para mercado, cripto, fundamentales, noticias y macro
- caché local con TTL y metadatos de frescura

## Arquitectura

```text
Browser / PWA
    |
    v
Next.js WebApp
    |
    v
Local FastAPI
    |
    +-- Domain / Use Cases
    +-- Financial Engines
    +-- RAG / Local AI
    +-- Provider Adapters
    |
    +-- SQLite / FTS5 / sqlite-vec
    +-- Financial Knowledge Vault
    +-- Local caches
```

La WebApp y la API se ejecutan exclusivamente en el Mac. En producción, Next.js se exporta como frontend estático y FastAPI sirve UI + API desde un único origen en loopback. No hay backend cloud, base de datos cloud, IA cloud, telemetría remota ni almacenamiento remoto propio.

## Módulos funcionales

- Resumen
- Cuentas
- Movimientos
- Presupuestos
- Recurrentes
- Patrimonio
- Inversiones
- Mercados
- Cripto
- Documentos
- Contratos
- Seguros
- Hipoteca
- Servicios
- Oportunidades
- Noticias
- Chat financiero
- Configuración

## Regla de IA

Nunca:

```text
LLM -> respuesta financiera
```

Siempre:

```text
Datos verificables
    -> herramientas
    -> cálculos deterministas
    -> recuperación RAG
    -> LLM local
    -> explicación con evidencia
```

## Financial Knowledge Vault

El usuario selecciona una carpeta local que Financito vigila. Para cada documento nuevo o modificado:

1. SHA-256 y deduplicación;
2. extracción de texto;
3. OCR cuando proceda;
4. detección de idioma y categoría;
5. extracción estructurada;
6. chunking semántico;
7. embeddings locales;
8. indexación FTS/vectorial;
9. asociación de entidades;
10. conservación de página/sección para citas;
11. detección de renovaciones, permanencias, penalizaciones y oportunidades.

## Optimización financiera

El motor analiza seguros, hipoteca, préstamos, energía, telecomunicaciones, bancos, tarjetas, suscripciones, liquidez e inversión.

```text
beneficio_neto =
  ahorro_bruto
  - costes_de_cambio
  - penalizaciones
  - beneficios_perdidos
  - costes_recurrentes_adicionales
  - impacto_fiscal
```

Además calcula break-even y compara calidad/coberturas/prestaciones equivalentes.

## Reglas para agentes

Antes de modificar el repositorio, cualquier agente de IA debe leer [AGENTS.md](AGENTS.md). Las reglas detalladas de implementación, no-alucinación, pruebas y documentación están versionadas dentro del repositorio.

## Documentación

- [Especificación funcional](docs/FUNCTIONAL_SPEC.md)
- [Arquitectura estrictamente local](docs/LOCAL_ONLY.md)
- [Arquitectura frontend](docs/FRONTEND_ARCHITECTURE.md)
- [Arquitectura backend](docs/BACKEND_ARCHITECTURE.md)
- [Catálogo de componentes](docs/COMPONENT_CATALOG.md)
- [Modelo de seguridad estricto](docs/SECURITY_MODEL.md)
- [Ciclo de vida de datos](docs/DATA_LIFECYCLE.md)
- [Rendimiento](docs/PERFORMANCE.md)
- [Gastos y categorización](docs/EXPENSES_AND_CATEGORIZATION.md)
- [Evidencia contractual](docs/CONTRACT_EVIDENCE.md)
- [Forecast, ahorro y compromisos](docs/FORECASTING_AND_COMMITMENTS.md)
- [Stress testing](docs/STRESS_TESTING.md)
- [Financial Graph](docs/FINANCIAL_GRAPH.md)
- [Integridad y recuperación](docs/RECOVERY_AND_INTEGRITY.md)
- [Evaluación de modelos](docs/MODEL_EVALUATION.md)
- [Cost centers y coberturas](docs/COST_CENTERS_AND_COVERAGE.md)
- [Resultados de decisiones](docs/DECISION_OUTCOMES.md)
- [Visualizaciones e insights](docs/VISUALIZATION_AND_INSIGHTS.md)
- [Motor de decisiones](docs/DECISION_ENGINE.md)
- [Reglas de IA para ingeniería](docs/AI_ENGINEERING_RULES.md)
- [Flujo estándar de desarrollo](docs/DEVELOPMENT_WORKFLOW.md)
- [Gobierno documental](docs/DOCUMENTATION_GOVERNANCE.md)
- [Glosario](docs/GLOSSARY.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Estructura del repositorio](docs/REPOSITORY_STRUCTURE.md)
- [Modelo de datos](docs/DATA_MODEL.md)
- [RAG](docs/RAG.md)
- [IA local](docs/AI.md)
- [Seguridad](docs/SECURITY.md)
- [Providers](docs/PROVIDERS.md)
- [Estrategia de conectores gratuitos](docs/FREE_CONNECTORS.md)
- [Motores financieros](docs/FINANCIAL_ENGINES.md)
- [Optimización](docs/OPTIMIZATION_ENGINE.md)
- [Hipoteca](docs/MORTGAGE_ENGINE.md)
- [UI/UX WebApp](docs/UI_UX.md)
- [Contrato API](docs/API.md)
- [Testing](docs/TESTING.md)
- [Roadmap](docs/ROADMAP.md)
- [ADRs](docs/adr/README.md)

## Fases

1. Foundation: seguridad, DB, documentos, OCR, embeddings, RAG y chat local.
2. Movimientos, importación, categorías, recurrentes y dashboard.
3. Open Banking y sincronización.
4. Portfolio, mercados, acciones y cripto.
5. Noticias, fundamentales, riesgo y recomendaciones.
6. Contratos, seguros, hipoteca y optimización.
7. Backtesting y planificación avanzada.

Cada fase debe quedar compilable, testeada y documentada antes de avanzar.

## Prioridades

```text
Seguridad
> corrección de datos
> privacidad
> fiabilidad
> rendimiento
> optimización financiera
> UX
> funcionalidades adicionales
```

## Reglas de repositorio

No versionar:
- datos financieros reales;
- documentos personales;
- bases de datos de usuario;
- tokens o API keys;
- modelos binarios.

El repositorio privado contiene código, schemas, migraciones, configuración segura por defecto y documentación.
