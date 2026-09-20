# Testing

## CI actual

Cada push a `main` y `implementation/**`, y cada PR, ejecuta cuatro gates:

### Backend
- Python 3.13;
- instalación con dependencias de dev;
- `compileall`;
- pytest.

### Frontend
- Node 24;
- TypeScript typecheck;
- tests;
- Next.js static build.

### E2E
- build frontend + backend local real;
- Chromium Playwright;
- onboarding/demo y navegación;
- creación de cuenta + importación de extracto;
- Vault/indexación/cita;
- banking provider mock;
- Decision Case + alternativa + outcome;
- backup cifrado + restore;
- axe en todas las rutas principales;
- teclado/skip link y reflow 320 px.

### Documentación
- enlaces Markdown internos;
- sintaxis de launchers/scripts shell relevantes.

El CI usa SQLite plaintext solo mediante `FINANCITO_ALLOW_PLAINTEXT_SQLITE=1`. El runtime estable sigue exigiendo almacenamiento cifrado.

## Invariantes adicionales cubiertos

- fiscalidad: tramos progresivos y compensación no se delegan al LLM;
- hipoteca indexada: toda revisión contractual necesita un índice explícito;
- FEIN/FIAE: facts mantienen página/contexto y fórmulas estructuradas;
- comparadores: source/freshness/missing fields controlan comparabilidad;
- desconocido no equivale a cero.

## Accesibilidad

El gate E2E usa axe con WCAG 2.0/2.1/2.2 A y AA. La política completa está en [WCAG_AA_AUDIT.md](WCAG_AA_AUDIT.md).

## Validación local

```bash
./scripts/validate.sh
```

Para E2E:

```bash
cd apps/web
npx playwright install chromium
npm run test:e2e
```

## Criterio de salida

No se cierra un cambio si compile/typecheck/build/tests/E2E fallan, si la documentación promete algo inexistente, o si introduce secretos/datos reales.
