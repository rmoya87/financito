# Operación local

## Procesos

Financito puede ejecutar:
- web;
- API;
- workers;
- modelo local externo;
- scheduler.

## Scheduler

Frecuencias configurables.

Orientación:
- banca: 1–4 veces/día según provider/consentimiento;
- mercado: bajo demanda + TTL;
- cripto: bajo demanda + TTL;
- noticias: intervalo configurable;
- documentos: evento/rescan;
- fundamentales: días;
- comparadores: bajo demanda o cerca de renovación.

No hacer polling agresivo.

## Jobs

Estados:
- queued;
- running;
- completed;
- failed;
- cancelled.

Cada job:
- id;
- type;
- progress;
- started_at;
- finished_at;
- error_code seguro.

## Backups

Debe existir export cifrado que incluya:
- DB;
- configuración no secreta;
- metadatos del Vault;
- versionado.

Los documentos originales pueden excluirse si ya viven fuera de Financito.

## Recovery

Al restaurar:
1. validar versión;
2. verificar integridad;
3. migrar schema;
4. reconstruir índices si es necesario;
5. nunca regenerar datos financieros silenciosamente.

## Modelos

No versionar binarios.
Ajustes deben mostrar:
- modelo;
- tamaño;
- RAM estimada;
- estado;
- checksum.

## Actualizaciones

Toda actualización:
- backup recomendado;
- migraciones transaccionales cuando sea posible;
- rollback documentado;
- no destruir DB.

## Observabilidad

Logs locales estructurados sin PII.
Rotación y límite de tamaño.

Developer Mode puede exponer métricas técnicas, nunca secretos.
