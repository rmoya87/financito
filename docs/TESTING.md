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


## Recurrentes, previsión y cuentas locales

La regresión incluye cobertura para detección determinista de una serie mensual con al menos tres cargos, expansión de recurrentes dentro del horizonte de 90 días, previsión mensual por categorías estables a partir de histórico real, modificación de un saldo manual (incluido un caso de 40.000 €) y bloqueo de la edición manual del saldo de una cuenta conectada, cuyo saldo debe seguir procediendo de PSD2.


## Selector temporal compartido

La regresión comprueba que Movimientos y Análisis exponen el mismo selector temporal que Inicio, que un rango personalizado filtra realmente movimientos fuera de fecha y que recurrentes/anomalías respetan los parámetros `start`/`end` del backend.


## Análisis diario, comercios y eliminación de cuentas

Las regresiones comprueban que la serie diaria incluye todos los días del intervalo, que el total de comercios es coherente con el gasto, que Recurrentes no depende del filtro mensual, que Análisis muestra el horizonte de 30 días y permite alternar gráfica/listado, y que eliminar una cuenta elimina solo sus movimientos sin afectar a otras cuentas.


## Regresiones Casa, seguros, bienes y recurrentes

La cobertura automática comprueba: descarte de patrones recurrentes históricos ya caducados; exclusión de esos patrones del calendario; evolución de un bien a partir de snapshots; borrado de una deuda sin mantenerla en patrimonio actual; exposición de condiciones contractuales, objeto asegurado, condiciones/exclusiones y vigencia de coberturas en el veredicto de seguros; navegación de Patrimonio con Casa; creación/borrado de deuda desde UI; apertura de la ficha completa de una póliza; y porcentajes de comercios que nunca superan el 100 % en gráfica/listado.

## Regresiones de modales documentales y Mercado

Las pruebas cubren la creación de una hipoteca desde Casa, reapertura del modal de datos, apertura del modal contextual de documentación, subida y visualización de un documento hipotecario; en seguros, apertura de ficha, edición efectiva y documentación contextual con subida/visualización. También se comprueba que Casa no vuelve a mostrar el módulo duplicado “Seguros y protección”.

Backend cubre que una limitación 429 del proveedor de noticias se convierte en un aviso legible sin URL/error HTTP y que el análisis de Mercado puede construir contexto con posición, histórico y noticias locales aun sin IA disponible. E2E comprueba además que Mercado muestra la lectura local en la cabecera y no expone mensajes 429 Too Many Requests ni la URL de GDELT.

## Regresión: seguro dentro de documentación hipotecaria

La suite crea una hipoteca y un PDF hipotecario con evidencia confirmada equivalente al caso real de un seguro Vida Anual Renovable: prima anual 378,62 €, renovación 26/05/2027, identificador de contrato/póliza, proveedor Bankinter Seguros de Vida, objeto asegurado y dos coberturas de 118.000 €. Se valida que:

- la hipoteca conserva su prestamista y solo recibe hechos `mortgage_term`;
- la renovación del seguro no se convierte en próxima revisión hipotecaria;
- se crea/actualiza una póliza de vida con prima, proveedor, renovación, número y objeto asegurado;
- las dos coberturas confirmadas se proyectan con su límite;
- la póliza queda vinculada a la hipoteca mediante `LinkedProduct` y aparece en `wealth/home`;
- el veredicto de Seguros consume la misma póliza y coberturas;
- un segundo documento con el mismo identificador asegurador se agrupa con la póliza y no con la hipoteca.

E2E comprueba que Biblioteca no contiene el encabezado “Evidencia extraída”, que muestra “Datos por confirmar” mientras existen hechos pendientes y que un hecho desaparece de esa revisión inmediatamente después de confirmarlo.


## Regresiones: mercados, hipoteca y seguros

- Mercados valida que el fallback nunca muestre más de seis noticias guardadas y que cada activo incluya estado de consideración de inversión y nivel de riesgo.
- Con IA local simulada, se comprueba que solo se acepten IDs reales de noticias seleccionadas y que \`investment_status\`/\`future_risk_level\` lleguen al resultado.
- El comparador hipotecario prueba una referencia que sí recupera una penalización confirmada y otra con TIN inferior que queda descartada por exigir seguro vinculado de coste desconocido.
- También se cubre el caso en que el tipo es menor pero una penalización elevada no se recupera antes de acabar el plazo: \`better_offers\` queda vacío.
- E2E verifica que la modal de cada seguro contiene Obligaciones, Riesgos, Oportunidades de optimizar, Productos vinculados y Puntos para negociar.
- E2E verifica que una acción de seguros en “Para ti” abre \`Detalle de Seguros y coberturas\` en modal sin navegar fuera de Inicio.
- E2E verifica el nuevo bloque “Noticias guardadas · selección útil”.


## Regresiones: Próximamente y revisión hipotecaria

- El dashboard incluye una serie recurrente activa dentro de los próximos 45 días y conserva su importe/origen.
- La proyección hipotecaria desde evidencia confirmada cubre fecha de inicio y vencimiento.
- La preparación de revisión automática exige la regla temporal del índice (\`reference_index_lag_months\`).
- La TAE estimada actual aumenta cuando existen primas futuras de seguros vinculados conocidas.
- Con una fuente BCE simulada se verifica que una revisión vencida usa exactamente el mes contractual, calcula TIN/cuota/TAE estimados y no modifica el TIN guardado.
- E2E verifica que Inicio etiqueta un próximo cargo como “Recurrente” y muestra su base de detección.
