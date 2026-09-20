# Seguridad y privacidad

Financito adopta un modelo de seguridad estrictamente local y de mínimo privilegio.

La especificación autoritativa está en [SECURITY_MODEL.md](SECURITY_MODEL.md) y [LOCAL_ONLY.md](LOCAL_ONLY.md).

## Reglas no negociables

- Todo dato privado, documento, embedding, base de datos, log, configuración y modelo IA permanece en el Mac.
- No existe infraestructura propia remota.
- La API escucha únicamente en loopback.
- WebApp y API comparten origen en producción.
- No se usan analytics, telemetría, crash reporting ni assets remotos.
- No se guardan secretos en frontend, .env, repositorio ni logs.
- Claves y tokens sensibles se almacenan en Keychain.
- SQLite se cifra con SQLCipher o alternativa auditada.
- LLM, embeddings y reranking son locales.
- Documentos/noticias se consideran input hostil.
- El LLM no tiene acceso arbitrario a SQL, shell, filesystem ni URLs.
- Providers externos se comunican desde adapters con allowlist de hosts.
- Ningún provider puede recibir más datos personales de los estrictamente necesarios.
- Backups son locales y cifrados.
- El usuario puede borrar derivados, índices, conexiones y todos sus datos.

## Threat model mínimo

Proteger frente a:
- robo de secretos;
- fuga de logs;
- acceso no autorizado al Vault;
- XSS;
- CSRF;
- ataques contra localhost y DNS rebinding;
- SSRF;
- path traversal/symlinks;
- parsers maliciosos;
- prompt injection;
- tool abuse;
- supply-chain;
- modelos locales manipulados;
- exposición accidental a LAN.

## Privacy by design

No se persisten datos sensibles en localStorage/sessionStorage. No se incluyen datos privados en URLs. No se cargan Google Fonts, CDNs o iframes remotos.

Todo dato externo guarda procedencia y frescura. Los embeddings se tratan como datos sensibles.

## Security gate

Una fase no se considera terminada si falla cualquiera de los tests de seguridad críticos definidos en SECURITY_MODEL.md y TESTING.md.
