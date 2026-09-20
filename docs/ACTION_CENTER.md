# Action Center

## Objetivo

Convertir alertas, oportunidades y decisiones en acciones gestionables.

## Action item

Campos:
- title;
- type;
- related_entity;
- due_date;
- priority;
- status;
- expected_impact;
- source;
- decision_case_id;
- notes.

Estados:
- pending;
- in_progress;
- done;
- dismissed;
- snoozed.

## Fuentes automáticas

Crear acciones desde:
- renovación próxima;
- fin de preaviso;
- consentimiento bancario;
- oportunidad de ahorro;
- conflicto documental;
- dato faltante para una decisión;
- anomalía;
- backup pendiente;
- objetivo en riesgo.

## Regla

Financito ayuda a gestionar la acción, pero no ejecuta transferencias, contrataciones, cancelaciones o trading automáticamente en v1.

## UX

Vista:
- Hoy
- Próximamente
- Alto impacto
- Requiere datos
- Completadas

Cada acción muestra impacto esperado y la evidencia relacionada.


## Revisión de evidencia documental

Cuando el Vault extrae hechos materiales de un documento crea una acción `review_document_evidence`.

Comportamiento:
- **Revisar documento** abre directamente ese documento en **Documentos y evidencia**;
- no se ofrece **Hecho** mientras existan facts `inferred` pendientes;
- cada fact se confirma o se marca como dudoso en su evidencia/página;
- al quedarse sin facts pendientes, la acción se marca automáticamente como `done`;
- las acciones `done` y `dismissed` no aparecen en **Pendiente de ti**;
- **Descartar** es una decisión explícita del usuario y no se recrea en cada arranque;
- un reprocesado que descubre nueva evidencia puede reabrir una tarea previamente completada.

Los datos confirmados se proyectan a las entidades estructuradas soportadas y mantienen trazabilidad al documento fuente.
