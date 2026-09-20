# Estrategia de testing

## Pirámide

1. unit tests de dominio;
2. tests de integración;
3. tests API;
4. tests UI;
5. E2E de journeys críticos.

## Dominio

Obligatorios:
- dinero/Decimal;
- categorías;
- recurrentes;
- patrimonio;
- riesgo;
- switching costs;
- break-even;
- beneficios;
- hipoteca;
- escenarios.

## Base de datos

- migraciones forward;
- idempotencia;
- constraints;
- deduplicación;
- rollback cuando exista;
- fixtures aislados.

## RAG

Casos:
- respuesta presente;
- no presente;
- multi-documento;
- contradicción;
- OCR;
- tabla;
- ES/EN;
- documento modificado;
- duplicado;
- citas.

## Providers

Contract tests usando fixtures grabadas/sanitizadas cuando la licencia lo permita.

Nunca usar cuentas reales en CI.

## Seguridad

Tests:
- CORS;
- auth local;
- path traversal;
- secretos en logs;
- prompt injection;
- archivos inválidos;
- acceso a documentos fuera de Vault.

## Frontend

- Vitest/Testing Library o equivalente;
- componentes;
- formularios;
- estados loading/empty/error;
- accesibilidad.

E2E con Playwright:
- onboarding;
- Vault;
- importación;
- chat con cita;
- dashboard;
- oportunidad;
- escenario hipotecario.

## Datos ficticios

Crear un hogar ficticio completo con:
- cuentas;
- nóminas;
- hipoteca;
- seguro;
- servicios;
- cartera;
- documentos sintéticos.

No reutilizar datos del usuario.

## CI

Cada PR:
- lint;
- typecheck;
- unit;
- integration seleccionada;
- build web;
- build API;
- test migraciones;
- secret scan.

## Criterio de salida

Una fase no se considera completa si:
- no compila;
- tests críticos fallan;
- migraciones no están verificadas;
- documentación contradice implementación.


## Categorización de gastos

Dataset sintético con:
- comercios conocidos;
- aliases;
- comercios ambiguos;
- transferencias internas;
- reembolsos;
- splits;
- recurrencias;
- duplicados;
- divisas;
- conceptos ruidosos.

Tests:
- regla manual prevalece;
- corrección manual prevalece sobre IA;
- merchant mapping estable;
- baja confianza va a review queue;
- no se cuenta transferencia propia como gasto;
- reembolso netea correctamente;
- split conserva suma exacta;
- recategorización es auditable;
- mismo input + misma versión produce resultado consistente salvo modelos explícitamente no deterministas.

## Analytics y gráficas

Validar datos antes de UI:
- totales de categorías suman total esperado;
- series temporales mantienen periodos;
- presupuesto vs real;
- fixed vs variable;
- ingresos/gastos/ahorro;
- net worth;
- waterfall de oportunidad;
- break-even.

La prueba debe validar números del dataset de la gráfica, no screenshots como única evidencia.

## Decision Engine

Casos:
- alternativa claramente favorable;
- costes de cambio eliminan ahorro bruto;
- break-even fuera del horizonte;
- falta un dato material;
- escenario sensible a tipos;
- inversión esperada vs amortización cierta;
- cobertura de seguro no equivalente.

Verificar:
- assumptions visibles;
- confidence degradada si faltan datos;
- no se inventan probabilidades;
- outputs reproducibles por versión.

## Anti-alucinación

Tests obligatorios para IA:
- pregunta sin dato → reconoce ausencia;
- tool devuelve error → no inventa resultado;
- documento contiene instrucciones maliciosas → se ignoran como instrucciones;
- noticia contradictoria → atribuye y no fusiona como hecho único;
- cifra no presente → no aparece como hecho;
- citation apunta a evidencia real;
- cálculo procede de engine y no de texto del LLM.

## Consistencia documental

Añadir chequeo de enlaces Markdown internos y, cuando sea viable, tests/CI que detecten documentación autoritativa ausente.

## Rendimiento

Benchmarks/regression tests locales para:
- queries de movimientos;
- agregaciones;
- retrieval RAG;
- ingestión;
- endpoints calientes.

No convertir thresholds de desarrollo en tests frágiles dependientes de hardware; medir tendencias/regresiones.


## Evidencia contractual

Tests obligatorios:
- condiciones particulares prevalecen sobre generales;
- anexo posterior sustituye fact anterior;
- penalización ausente no se convierte en cero;
- fórmula porcentual se evalúa correctamente;
- OCR de baja confianza bloquea cálculo material;
- documentos contradictorios generan conflicto;
- cálculo conserva source document/page;
- cambio de vigencia selecciona la cláusula correcta;
- cobertura no equivalente bloquea comparación simplificada;
- calculation trace reproduce el resultado.


## Forecasting

Tests obligatorios:
- mismo periodo del año anterior se alinea por fechas;
- año bisiesto y rangos que cruzan año;
- gasto extraordinario no se repite automáticamente;
- compromiso conocido sustituye estimación residual;
- recurrencias no se duplican con commitments;
- forecast por categoría suma forecast total;
- ahorro se calcula desde ingresos/gastos/componentes definidos;
- rango procede de error histórico;
- accuracy se recalcula con observaciones reales;
- no se usa futuro para estimar pasado en backtesting.

Métricas:
- MAE;
- WAPE;
- bias;
- interval coverage.

## Stress tests

Validar shocks, escenarios combinados, cash runway, liquidez mínima y objetivos afectados.

## Coverage

Validar duplicidades, pérdida de cobertura, franquicias/límites y evidencia documental.

## Financial Graph

Validar relaciones y ausencia de links huérfanos.

## Repair

Simular job interrumpido, reconstrucción FTS/vector, hash inconsistente y derivados huérfanos.

## Model Evaluation

Un modelo candidato no pasa gate si empeora métricas críticas fuera de tolerancia configurada.
