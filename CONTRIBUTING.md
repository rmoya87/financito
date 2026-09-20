# Contribución

## Antes de desarrollar

Leer:
1. README.md
2. docs/FUNCTIONAL_SPEC.md
3. docs/ARCHITECTURE.md
4. docs/SECURITY.md
5. ADRs relevantes

## Reglas

- Mantener dominio independiente de UI/providers.
- No implementar cálculos críticos en componentes React ni prompts.
- No subir datos reales.
- No hardcodear secretos.
- Añadir migraciones para cambios de DB.
- Añadir tests a motores.
- Actualizar documentación cuando cambie el comportamiento.

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
- riesgos;
- tests;
- screenshots para UI;
- cambios de schema;
- documentación actualizada.

## Datos de prueba

Solo fixtures sintéticos.
