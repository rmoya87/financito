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


También se cubre la agrupación provisional sin prima confirmada: dos documentos con el mismo número de póliza deben compartir una única ficha de evidencia antes de crear la póliza financiera.


## Casa y optimización hipotecaria

Las regresiones cubren:
- persistencia del perfil hipotecario ampliado: TAE, índice, diferencial, revisiones y comisiones;
- cálculo de LTV a partir del valor completo de la garantía y capital pendiente;
- uso de comisiones introducidas en Casa por los motores de amortización/subrogación;
- comparación de cuota e intereses frente a un TIN público manteniendo capital y plazo, sin depender de red en CI;
- cálculo del punto de equilibrio parcial cuando existe una penalización de salida conocida;
- agrupación de anexos por número de póliza/contrato aunque su clasificación inicial sea distinta;
- reagrupación de documentos procesados antes de que otro archivo identifique/materialice el producto.

Los conflictos entre documentos nunca se confirman automáticamente: permanecen pendientes para decisión explícita del usuario.


## Regresiones de completado documental local

Las pruebas cubren:
- proyección de hechos hipotecarios confirmados al perfil ampliado, incluido `differential_rate`;
- conservación de hechos inferidos por IA como pendientes de revisión, separados de la evidencia confirmada;
- presentación en Seguros de franquicia, renovación, preaviso y penalización localizados por IA como pendientes, sin tratarlos como ausentes ni utilizarlos todavía en cálculos.


## Regresiones de documentación contextual por producto
Las pruebas cubren:
- selección explícita entre varias hipotecas en `/wealth/home?mortgage_id=...`;
- borrado de una hipoteca manteniendo intactos los documentos y eliminando únicamente sus vínculos;
- alta, edición y borrado de pólizas con categoría y datos contractuales;
- filtrado de documentos por entidad para que una hipoteca o seguro no muestre archivos de otro producto.
