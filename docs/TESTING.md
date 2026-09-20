# Testing

## CI actual
Cada push a `main` y `implementation/**`, y cada PR, ejecuta:

Backend:
- Python 3.13;
- instalación editable con dependencias de dev;
- `compileall`;
- pytest.

Frontend:
- Node 24;
- instalación;
- TypeScript typecheck;
- Next.js build.

El CI usa SQLite plaintext exclusivamente mediante `FINANCITO_ALLOW_PLAINTEXT_SQLITE=1`; esto no cambia el requisito SQLCipher del runtime estable.

## Cobertura backend presente
Suites para:
- seguridad local;
- migraciones;
- API/session/health;
- imports y deduplicación;
- forecast;
- backup/restore;
- motores financieros;
- FIFO/tax lots;
- transferencias y splits;
- reglas de categoría;
- aprendizaje de categoría por comercio confirmado y categorización IA local con fallback seguro;
- RAG;
- stress/backtest/planning;
- Open Banking authorize/sync/pagination/dedupe/revoke;
- reembolsos refund-aware;
- clasificación documental y evidencia por página;
- hipoteca extraordinaria;
- centros de coste;
- requisitos/huecos de cobertura;
- Decision Cases/outcomes;
- superficie bancaria sin endpoints raw.

## Invariantes obligatorios
- transferencias propias no son gasto;
- reembolso reduce gasto y no crea ingreso;
- split conserva suma exacta;
- corrección manual prevalece;
- la IA nunca sobrescribe movimientos verificados por el usuario y solo acepta categorías existentes;
- dato contractual ausente no se convierte en cero;
- quotes/históricos externos conservan provider/frescura;
- backup inválido no se restaura;
- archivos fuera del Vault no se indexan;
- rutas mutantes requieren CSRF;
- el API público no expone sesión PSD2 ni datos bancarios provider-crudos.

## Frontend
El typecheck/build cubre integridad estática. Aún queda como trabajo futuro:
- tests de componentes;
- accesibilidad automatizada;
- E2E Playwright de journeys críticos.

## Validación local
```bash
./scripts/validate.sh
```

## Criterio de salida
No se considera cerrado un cambio si:
- compile/typecheck/build fallan;
- tests críticos fallan;
- documentación afirma una funcionalidad que el runtime no ofrece;
- introduce secretos/datos reales en el repositorio.
