# Integridad, reparación y recuperación local

## Backup
El backup incluye:
- DB;
- contenido del Vault gestionado por Financito;
- manifest con SHA-256 por fichero.

Protección:
- clave derivada con scrypt;
- AES-256-GCM;
- salt y nonce aleatorios;
- magic/version del formato.

## Restore
La restauración:
1. descifra en staging;
2. valida paths para impedir traversal;
3. extrae TAR con filtro seguro;
4. verifica SHA-256 del manifest;
5. crea `.restore-pending`;
6. el launcher aplica DB/Vault antes de arrancar FastAPI.

La UI no sustituye datos activos antes de que el backup haya sido verificado.

## Repair Center
El scanner detecta actualmente:
- documento con texto sin chunks;
- hash del archivo distinto al indexado;
- archivo del Vault desaparecido;
- evidencia inferida sin revisar;
- backup inexistente o >30 días.

Reparaciones automáticas soportadas:
- reindexar documento.

Otros casos producen acción explícita del usuario, en lugar de reparar destructivamente.

## Regeneración de derivados
La función de privacidad puede regenerar:
- FTS/vector/chunks;
- facts inferidos;
- transferencias/reembolsos;
- recurrentes/anomalías;
- Repair Issues.

Se conservan los hechos verificados manualmente.

## Borrado
“Borrar Financito” elimina las tablas locales y, opcionalmente, credenciales de providers. No borra silenciosamente archivos originales externos al control de la app.

## Atomicidad
- DB con WAL, foreign keys y `synchronous=FULL`;
- preferencias se escriben mediante fichero temporal + fsync + replace;
- restore usa staging y marker.
