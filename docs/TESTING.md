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


## Contratos de rutas por secciones

Los flujos críticos que anteriormente podían degradar en HTTP 405 tienen pruebas de contrato explícitas: paginación de movimientos, perfil/estimación fiscal, prueba de IA local, subida documental POST/PUT y resumen patrimonial. Estas pruebas verifican el método HTTP además de la forma mínima de la respuesta para detectar desalineaciones entre WebApp y backend antes de publicar. La WebApp también debe degradar los payloads parciales a errores locales, sin derribar la página completa.


## Semántica de ingresos y transferencias

Las regresiones contables prueban que una `Nómina` positiva cuenta como ingreso incluso si una versión anterior dejó un flag interno de transferencia obsoleto. También se comprueba que el arranque repara ese flag, que el detector de transferencias no roba una nómina por coincidencia de importe y que Dashboard/cierre de mes/Fiscalidad mantienen el mismo criterio.


## Evidencia multipdocumento y reglas por concepto

Las regresiones cubren:

- propagación de una categoría al mismo concepto en el histórico y en una importación futura;
- autoagrupación de un segundo documento con una póliza existente mediante número de póliza;
- validación conjunta: valores coherentes se confirman y valores contradictorios permanecen `conflicting` sin verificación automática;
- exclusión de seguros e hipoteca del endpoint de contratos generales;
- aceptación de intervalos explícitos en el Dashboard.


## Casa e hipoteca

Las regresiones cubren:
- perfil hipotecario ampliado y campos editables;
- valor de vivienda, equity y LTV;
- persistencia de TAE, índice, diferencial, revisión y comisiones;
- comparación de cuota a mismo capital/plazo frente a un TIN público simulado sin depender de red;
- cálculo del punto de equilibrio parcial solo cuando existe un coste de salida conocido.

La comparación de mercado se prueba con fuentes simuladas en tests para que CI no dependa de sitios externos.
