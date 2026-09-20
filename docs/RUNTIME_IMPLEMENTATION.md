# Runtime implementado

## Desarrollo

`./scripts/dev.sh` inicia FastAPI en `127.0.0.1:8765` y Next en `127.0.0.1:3000`. No usar datos reales en desarrollo.

## Producción local

1. construir `apps/web` con `npm run build`;
2. asegurar un backend SQLite cifrado aprobado;
3. ejecutar `./scripts/run-local.sh` o el futuro bundle macOS;
4. FastAPI sirve el export estático y `/api/v1` desde `127.0.0.1:8765`;
5. el launcher abre el navegador cuando el puerto está listo.

El launcher no acepta comandos arbitrarios ni expone shell.

## Sesión y CSRF

La primera llamada a `/api/v1/session` crea una sesión local HttpOnly, SameSite=Strict, y devuelve un token CSRF derivado de la sesión. Todas las mutaciones bajo `/api/` exigen el token.

## Estado de cifrado

SQLite plano se acepta solo para desarrollo/tests con una variable explícita. La distribución estable no debe marcarse como segura hasta integrar SQLCipher/Keychain conforme a `SECURITY_MODEL.md`.
