# Modelo de seguridad estricto

## Objetivo

Financito maneja datos de máxima sensibilidad. La seguridad forma parte de la arquitectura.

## Activos protegidos

Credenciales, tokens, movimientos, saldos, IBAN, documentos, pólizas, hipoteca, patrimonio, inversiones, historial de decisiones, prompts, respuestas, embeddings y backups.

Los embeddings se consideran datos sensibles.

## Frontera de confianza

Confiable: procesos de Financito instalados localmente, DB cifrada y almacén seguro del sistema.

No confiable: navegador fuera de sesión, documentos, noticias, webs externas, providers, contenido HTML, modelos descargados sin verificar y cualquier input.

## Red

### Entrada

Solo loopback: 127.0.0.1 y ::1.

Prohibido: 0.0.0.0, bind LAN, túneles, reverse proxy remoto y acceso remoto.

Validar Host explícitamente.

### Mismo origen

En producción la WebApp y la API comparten origen. Esto elimina CORS normal entre ambas y reduce superficie de ataque.

### Sesión local

Generar secreto criptográficamente seguro. Sesión HttpOnly, SameSite=Strict, con rotación, expiración y bloqueo por inactividad.

Para acciones sensibles exigir sesión desbloqueada recientemente.

### CSRF

Verificar Origin/Referer y token anti-CSRF en mutations cuando corresponda. Rechazar content-types inesperados.

### Ataques contra localhost

Mitigar DNS rebinding y sitios maliciosos mediante:
- Host allowlist;
- bind loopback;
- sin CORS wildcard;
- sesión obligatoria;
- ningún endpoint GET con efectos laterales.

## Autenticación local

Preferencia: desbloqueo mediante biometría/almacén seguro del sistema cuando el empaquetado lo permita.

Fallback opcional con passphrase local. Derivación Argon2id con salt aleatorio y parámetros versionados. Nunca almacenar passphrase.

## Cifrado

### DB

SQLCipher o alternativa auditada. Clave aleatoria en Keychain, nunca en .env ni repositorio.

### Vault

Dos modos:
1. referenciado: Financito no copia originales y depende de FileVault/permisos del usuario;
2. gestionado: copia cifrada administrada por Financito.

La UI debe indicar claramente el modo.

### Backups

Cifrado autenticado, clave separada, checksum, versión y prueba de restauración.

## Keychain

Guardar clave DB, secretos de providers, refresh tokens, claves de backup y secretos persistentes imprescindibles.

## Providers

Nunca exponer secretos al frontend. El backend añade credenciales, minimiza payloads, valida TLS, establece timeout y aplica allowlist de hosts.

## Política de salida

Default deny lógico. Cada adapter declara hosts permitidos. Un host nuevo exige configuración/cambio explícito.

Esto impide que un documento o LLM provoque exfiltración a dominios arbitrarios.

## CSP

Política objetivo:
- default-src self;
- script-src self;
- style-src self;
- img-src self más blob/data solo cuando sea necesario;
- connect-src self;
- frame-src none;
- object-src none;
- base-uri none;
- form-action self.

## Sin assets remotos

Prohibidos Google Fonts, analytics, CDN JS, widgets remotos e iframes financieros de terceros.

## XSS

React escaping por defecto. No usar dangerouslySetInnerHTML salvo sanitización estricta. Markdown con allowlist. No renderizar HTML recibido de noticias o documentos.

## Prompt injection

Documentos y noticias son datos hostiles. Nunca pueden modificar system prompt, tool policy, secretos ni reglas.

Tools:
- registry fijo;
- parámetros validados;
- scopes;
- sin shell;
- sin URL arbitraria.

## SSRF

Las descargas externas se limitan a providers registrados. Bloquear hosts privados/localhost cuando una URL procede de datos externos y validar redirects.

## Filesystem

- paths canónicos;
- roots permitidos;
- rechazar traversal;
- controlar symlinks;
- permisos mínimos;
- no leer fuera del Vault/configuración autorizada.

## Parsers

Límites de tamaño, páginas, descompresión y tiempo. No ejecutar macros. Aislar parsers de mayor riesgo cuando sea viable.

## Modelos locales

Verificar checksum, origen, licencia y tamaño. No ejecutar código descargado junto a un modelo. Preferir formatos de pesos sin ejecución arbitraria.

## Supply chain

Lockfiles, secret scanning, SBOM local/release y revisión de dependencias.

## Logs

Nunca registrar documentos, prompts completos, respuestas completas por defecto, IBAN, saldos, movimientos, tokens, auth headers ni API keys.

## Audit log

Log local para cambios de configuración, imports, sync, reindexación, decisiones, restauraciones y cambios de modelo. Sin secretos.

## Temporales

No usar directorios temporales inseguros para contenido descifrado. Borrar temporales y aplicar permisos restrictivos.

## Browser storage

No persistir datos sensibles en localStorage, sessionStorage o IndexedDB salvo futura decisión explícita con nuevo threat model.

## Bloqueo

Al bloquear: invalidar sesión UI, ocultar datos y exigir reautenticación para volver a mostrarlos.

## Eliminación

Permitir eliminar índice, derivados, embeddings, cachés, conexiones y todos los datos. Diferenciar borrar índice de borrar original.

## Testing de seguridad

Obligatorio: DNS rebinding, CSRF, Host header, XSS, SSRF, traversal, symlink escape, zip bombs, parser timeouts, prompt injection, tool abuse, secret leakage, backup/restore, DB locked y sesiones revocadas.
