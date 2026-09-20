# Reglas obligatorias para la IA que construye Financito

## Carácter normativo

Este documento es vinculante para cualquier agente de IA o desarrollador que modifique el repositorio.

Si una petición contradice seguridad, arquitectura local o exactitud financiera, debe señalar el conflicto antes de implementarla.

## 1. Antes de programar

La IA debe:
1. leer README;
2. leer FUNCTIONAL_SPEC;
3. leer ARCHITECTURE;
4. leer SECURITY_MODEL;
5. leer documentación del módulo afectado;
6. inspeccionar código existente;
7. comprobar si ya existe un componente, engine, DTO, provider o utilidad reutilizable;
8. identificar migraciones/tests/docs afectados.

No empezar creando una solución paralela.

## 2. Fuente de verdad

Jerarquía:
1. código + tests que implementan el comportamiento vigente;
2. especificación funcional;
3. ADRs;
4. documentación técnica;
5. comentarios.

Si existe inconsistencia, no elegir silenciosamente: corregirla o documentar el conflicto.

## 3. No alucinar

Prohibido inventar:
- endpoints;
- tablas;
- campos;
- providers;
- APIs;
- capacidades de librerías;
- tipos de interés;
- datos de mercado;
- normativa;
- rutas;
- resultados de tests.

Si algo externo debe verificarse y no está disponible, marcarlo como pendiente externo sin simular éxito.

## 4. No placeholders engañosos

No dejar:
- TODO crítico;
- FIXME crítico;
- funciones que devuelven datos fake en producción;
- catch vacío;
- valores hardcoded para fingir éxito;
- “mock” fuera de demo/tests.

## 5. Reutilización

Antes de crear:
- componente;
- hook;
- helper;
- service;
- engine;
- client;
- schema;

buscar un equivalente.

No duplicar lógica entre frontend y backend.

## 6. Reglas financieras

- usar Decimal;
- cálculos críticos en engines;
- nunca en prompts;
- nunca en componentes React;
- inputs y outputs trazables;
- assumptions explícitos;
- tests con casos límite.

## 7. IA del producto

El LLM:
- no calcula dinero;
- no ejecuta SQL arbitrario;
- no ejecuta shell;
- no navega filesystem sin scope;
- no llama URLs arbitrarias;
- no inventa evidencia.

Debe usar tools registradas.

## 8. Datos

Toda transformación debe preservar:
- origen;
- timestamp;
- versión;
- confianza cuando aplique.

No sobrescribir raw innecesariamente.

## 9. Seguridad

Nunca:
- exponer API a LAN;
- añadir cloud backend;
- introducir analytics;
- enviar contenido privado a IA cloud;
- poner secretos en frontend;
- relajar CSP/CORS sin threat model;
- registrar datos sensibles.

## 10. Rendimiento

Antes de optimizar:
- medir;
- localizar cuello;
- hacer cambio mínimo;
- volver a medir.

Antes de añadir una dependencia pesada, justificarla.

## 11. Frontend

Seguir:
shadcn primitive → shared component → feature component → page.

No crear estilos ad hoc repetidos.

Toda feature debe contemplar:
- loading;
- empty;
- error;
- stale;
- offline;
- accessibility.

## 12. Backend

Routers finos. Reglas en domain/application. Infrastructure detrás de ports.

No introducir Redis/Celery/microservicios sin ADR aprobado.

## 13. Tests

Antes de terminar:
- unit;
- integration afectada;
- migration tests si cambia DB;
- frontend tests si cambia UI;
- security tests si toca frontera;
- build.

No afirmar “tests pasan” sin haberlos ejecutado.

## 14. Documentación obligatoria

Si cambia:
- comportamiento → FUNCTIONAL_SPEC o doc de módulo;
- arquitectura → ARCHITECTURE + ADR;
- DB → DATA_MODEL + migración;
- API → API/OpenAPI;
- seguridad → SECURITY_MODEL;
- componente compartido → COMPONENT_CATALOG;
- proceso → DEVELOPMENT_WORKFLOW;
- engine → doc correspondiente.

## 15. Procedimiento de cierre

Cada tarea debe terminar con:
- archivos modificados;
- comportamiento;
- tests ejecutados;
- resultado;
- migraciones;
- documentación;
- limitaciones reales;
- riesgos.

## 16. Consistencia

No introducir dos términos para el mismo concepto.

Nombres de dominio en inglés dentro de código.
UX puede estar traducida.

Definir enums compartidos y no strings libres cuando el conjunto sea cerrado.

## 17. Cambios de schema

Siempre:
- migración versionada;
- backward compatibility cuando sea viable;
- índice revisado;
- test;
- documentación.

Nunca borrar y recrear DB como estrategia de migración.

## 18. Cambios de API

Mantener contrato versionado.
Evitar romper frontend silenciosamente.
Regenerar cliente TypeScript.

## 19. Commits

Cambios pequeños y coherentes.
No mezclar refactors masivos con funcionalidad sin necesidad.

## 20. Stop conditions

La IA debe detener la implementación de una parte concreta si:
- requiere credenciales que no existen;
- exige acceso externo no autorizado;
- destruiría datos;
- existe ambigüedad material que afecta seguridad o dinero.

En el resto del trabajo debe continuar con lo que sí puede completar.


## 21. IA aplicada a documentos financieros

La IA documental debe trabajar en dos capas.

1. **Interpretación**: puede resumir, explicar, detectar relaciones, riesgos, ventajas, exclusiones, oportunidades y datos faltantes.
2. **Evidencia material**: puede proponer hechos estructurados, pero nunca confirmarlos por sí misma.

Obligatorio:
- LLM local únicamente;
- contexto limitado al documento y hechos estructurados;
- temperatura determinista;
- salida JSON validada/normalizada;
- claves materiales con whitelist;
- página obligatoria para toda propuesta material;
- confianza acotada;
- mantener `user_verified=false` hasta revisión humana;
- conservar análisis como `ai_insight`;
- evitar duplicar hechos confirmados en reanálisis.

Prohibido:
- usar una conclusión narrativa de IA como input monetario;
- convertir una ausencia de cláusula en 0 €;
- inventar coberturas, exclusiones o límites;
- usar una cobertura propuesta para declarar equivalencia hasta su confirmación;
- enviar documentos privados a un LLM cloud.
