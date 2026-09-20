# Seguridad y privacidad

## Modelo de amenaza

Proteger frente a:
- robo de secretos;
- fuga en logs;
- acceso no autorizado al Vault;
- exposición accidental de API local;
- documentos maliciosos;
- prompt injection desde documentos/noticias;
- proveedores externos comprometidos;
- dependencias vulnerables.

## Datos en reposo

- SQLite cifrada;
- claves fuera de la DB;
- secretos en Keychain/almacén seguro del sistema;
- documentos opcionalmente cifrados si Financito gestiona copias;
- backups cifrados.

## API local

Por defecto:
- bind a 127.0.0.1 / ::1;
- CORS restringido;
- token/sesión local;
- protección CSRF donde aplique;
- sin exposición LAN automática.

## Secretos

Nunca:
- hardcode;
- localStorage para tokens sensibles;
- commits;
- logs.

Usar almacén seguro del SO.

## Logs

Redactar:
- IBAN;
- números de cuenta;
- tokens;
- API keys;
- identificadores bancarios;
- documentos;
- payloads sensibles.

## Open Banking

- consentimiento explícito;
- read-only inicial;
- no guardar usuario/contraseña bancaria;
- tokens cifrados;
- mostrar expiración del consentimiento;
- desconexión/revocación.

## Navegador

La WebApp no debe exponer secretos a JavaScript si no es necesario.
La comunicación con providers externos debe pasar por la API local cuando requiera credenciales.

## Upload/ingestión

Validar:
- MIME real;
- tamaño;
- extensión;
- paths;
- traversal;
- descompresión;
- parser sandboxing cuando sea viable.

## Prompt injection

Todo contenido externo es datos no confiables.
Un documento/noticia no puede:
- modificar system prompt;
- autorizar tools;
- revelar secretos;
- cambiar políticas.

Las tools se permiten según intención y política de aplicación.

## Dependencias

- lockfiles;
- análisis de vulnerabilidades;
- actualizaciones controladas;
- evitar paquetes abandonados.

## Backups

Definir:
- export cifrado;
- restauración;
- integridad;
- versión de schema.

## Privacidad

No recopilar telemetría de datos financieros por defecto.
Cualquier telemetría futura debe ser opt-in y no contener contenido.
