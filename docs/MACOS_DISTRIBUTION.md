# Distribución macOS: firma y notarización

Fecha de revisión: **2026-09-20**.

## Qué queda automatizado

Financito incluye:

- `scripts/build-macos-app.sh`: construye la WebApp, copia backend/frontend al bundle y compila un lanzador nativo Swift;
- `scripts/macos-app-runtime.sh`: arranca el backend desde el bundle y provisiona localmente Python 3.12+ y sus dependencias cuando sea necesario;
- `scripts/sign-notarize-macos.sh`: firma con Developer ID + hardened runtime + timestamp, verifica la firma, envía con `notarytool`, hace `stapler` y valida Gatekeeper;
- `.github/workflows/macos-release.yml`: workflow manual para producir el ZIP firmado/notarizado.

Node se usa para construir la interfaz, no para ejecutar el artefacto final.

## Construcción local

```bash
bash scripts/build-macos-app.sh
```

Salida:

```text
dist/macos/Financito.app
```

## Firma y notarización

Con un certificado Developer ID Application instalado:

```bash
export APPLE_SIGNING_IDENTITY='Developer ID Application: ...'
export APPLE_NOTARY_PROFILE='FinancitoNotary'
bash scripts/sign-notarize-macos.sh
```

También se admite App Store Connect API key:

```bash
export APPLE_API_KEY_PATH=/ruta/AuthKey_XXXXXXXXXX.p8
export APPLE_API_KEY_ID=XXXXXXXXXX
export APPLE_API_ISSUER_ID=00000000-0000-0000-0000-000000000000
bash scripts/sign-notarize-macos.sh
```

## GitHub Actions

El workflow manual requiere estos secrets:

- `MACOS_SIGNING_IDENTITY`;
- `MACOS_CERTIFICATE_P12_BASE64`;
- `MACOS_CERTIFICATE_PASSWORD`;
- `APPLE_NOTARY_KEY_P8_BASE64`;
- `APPLE_NOTARY_KEY_ID`;
- `APPLE_NOTARY_ISSUER_ID`.

El certificado se importa en un keychain temporal y se elimina al finalizar.

## Dependencia externa real

El repositorio puede automatizar el proceso, pero no puede fabricar una identidad Developer ID ni credenciales de notarización. Hasta configurar esos secretos no se puede afirmar que un artefacto concreto haya sido aceptado por el servicio de Apple.

## Referencias oficiales

- [Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
- [Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)
- [Signing Mac Software with Developer ID](https://developer.apple.com/developer-id/)
