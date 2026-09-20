# AGENTS.md — Reglas obligatorias para agentes de IA

Este repositorio contiene software financiero local con datos altamente sensibles. Estas reglas aplican a cualquier agente que cree, modifique, revise o documente código.

## 1. Lectura obligatoria

Antes de cualquier cambio:
1. README.md
2. docs/FUNCTIONAL_SPEC.md
3. docs/ARCHITECTURE.md
4. docs/LOCAL_ONLY.md
5. docs/SECURITY_MODEL.md
6. docs/AI_ENGINEERING_RULES.md
7. docs/DEVELOPMENT_WORKFLOW.md
8. docs/DEFINITION_OF_DONE.md
9. documentación específica del módulo

## 2. Restricciones absolutas

No:
- desplegar nada en cloud;
- añadir backend remoto;
- añadir telemetría;
- añadir analytics;
- enviar datos privados a IA cloud;
- escuchar en 0.0.0.0;
- exponer puertos a LAN;
- hardcodear secretos;
- guardar secretos en frontend;
- usar datos reales en tests;
- ejecutar trading o transferencias automáticas;
- sustituir cálculos por texto de LLM.

## 3. Antes de crear código

Buscar primero si ya existe:
- componente;
- hook;
- schema;
- DTO;
- engine;
- repository;
- provider;
- helper;
- ADR;
- test.

Reutilizar antes de duplicar.

## 4. Arquitectura

Frontend:
shadcn/ui → shared components → feature components → pages.

Backend:
presentation → application → domain.
Infrastructure implementa ports.

No saltarse capas por conveniencia.

## 5. Dinero y cálculos

- Decimal;
- motores deterministas;
- inputs/outputs versionados;
- assumptions explícitos;
- tests;
- trazabilidad.

Nunca calcular importes financieros críticos con float o JavaScript number.

## 6. IA del producto

LLM local únicamente.

El LLM no:
- ejecuta SQL arbitrario;
- ejecuta shell;
- lee filesystem libremente;
- hace fetch de URLs arbitrarias;
- inventa datos;
- inventa fuentes;
- calcula dinero crítico.

Usa tools registradas y validadas.

## 7. Categorización

Respetar prioridad:
manual > rule > verified merchant > deterministic classifier > local AI.

Nunca sobreescribir una corrección manual silenciosamente.

## 8. Decisiones

Toda recomendación material necesita:
- alternativas;
- impacto;
- horizonte;
- assumptions;
- fuentes;
- cálculos;
- riesgos;
- confidence de evidencia;
- datos faltantes.

## 9. Documentación

Actualizar documentación en el mismo cambio.

No crear documentos duplicados.
Consultar docs/DOCUMENTATION_GOVERNANCE.md.

## 10. Tests

Ejecutar tests relevantes antes de cerrar.

No escribir “tests pasan” si no fueron ejecutados.

Si no pueden ejecutarse:
- decirlo;
- explicar por qué;
- no simular resultado.

## 11. Seguridad

Antes de terminar revisar:
- secrets;
- logs;
- CSP;
- localhost;
- Host header;
- path traversal;
- provider allowlist;
- prompt injection;
- archivos;
- migraciones.

## 12. Rendimiento

No usar el LLM cuando SQL/engine/FTS resuelve el problema.

No descargar datasets enteros al frontend para agregarlos.

Medir antes/después de optimizaciones importantes.

## 13. Migraciones

Nunca borrar/recrear la DB para evolucionar schema.

Toda migración:
- versionada;
- testeada;
- documentada;
- con índices revisados.

## 14. Cierre obligatorio

Reportar:
- qué cambió;
- archivos;
- tests;
- build;
- migraciones;
- docs;
- riesgos;
- limitaciones externas.

Una tarea no está terminada hasta cumplir docs/DEFINITION_OF_DONE.md.
