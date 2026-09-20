# Contribución

## Regla principal

Todo humano o agente de IA debe seguir:
- AGENTS.md
- docs/AI_ENGINEERING_RULES.md
- docs/DEVELOPMENT_WORKFLOW.md
- docs/DEFINITION_OF_DONE.md
- docs/DOCUMENTATION_GOVERNANCE.md

## Antes de desarrollar

Leer, como mínimo:
1. README.md
2. AGENTS.md
3. docs/FUNCTIONAL_SPEC.md
4. docs/ARCHITECTURE.md
5. docs/SECURITY_MODEL.md
6. documentación del módulo afectado
7. ADRs relevantes

## Reglas

- Mantener dominio independiente de UI/providers.
- No implementar cálculos críticos en React ni prompts.
- No subir datos reales.
- No hardcodear secretos.
- Añadir migraciones para cambios de DB.
- Añadir tests a motores.
- Generar tipos frontend desde OpenAPI.
- Reutilizar componentes existentes antes de crear otros.
- Actualizar documentación en el mismo cambio.
- No afirmar que algo compila o pasa tests sin ejecutarlo.

## Commits

Preferir Conventional Commits:
- feat:
- fix:
- docs:
- refactor:
- test:
- chore:

## Pull requests

Incluir:
- problema;
- solución;
- comportamiento;
- riesgos;
- seguridad;
- rendimiento;
- tests ejecutados y resultado;
- screenshots para UI;
- cambios de schema/migraciones;
- documentación actualizada;
- limitaciones externas reales.

## Datos de prueba

Solo fixtures sintéticos. Nunca reutilizar datos del usuario.

## Cierre

La tarea debe cumplir docs/DEFINITION_OF_DONE.md antes de declararse terminada.
