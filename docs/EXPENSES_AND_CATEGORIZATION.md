# Gastos, categorización y análisis de consumo

## Objetivo

Todo movimiento de cuenta debe terminar en un estado interpretable, trazable y útil para la toma de decisiones.

Financito no se limita a importar movimientos: normaliza comercios, clasifica, detecta recurrencias, identifica anomalías, agrega por categorías y genera insights accionables.

## Taxonomía base

La taxonomía principal implementada usa `system_key` estables para preservar reglas, presupuestos e históricos. Las categorías actuales son:

- Ingresos
- Nómina
- Reembolsos
- Vivienda
- Supermercado
- Restaurantes
- Transporte
- Vehículo
- Suministros
- Telecomunicaciones
- Seguros
- Salud
- Cuidado personal
- Educación
- Familia
- Mascotas
- Deporte
- Ocio
- Tecnología
- Compras
- Suscripciones
- Viajes
- Impuestos
- Comisiones bancarias
- Préstamos y deuda
- Donaciones
- Inversión
- Ahorro
- Transferencias
- Movimiento entre cuentas
- Otros

La taxonomía evita crear categorías demasiado específicas como primer nivel. Cuando se implemente la UX de subcategorías, ejemplos naturales serán:
- Supermercado → supermercado, mercado, panadería.
- Vehículo → combustible, carga eléctrica, parking, peajes, mantenimiento.
- Vivienda → hipoteca, comunidad, reparaciones, muebles.
- Ocio → cine, teatro, entradas, videojuegos.
- Deporte → gimnasio, CrossFit, pádel, fútbol.
- Suscripciones → streaming, software, prensa.

Los `system_key` existentes no se renombran ni reutilizan para otro significado. Las ampliaciones son aditivas para mantener compatibilidad con datos ya categorizados.


## Clasificación multinivel

Pipeline:

1. reglas explícitas del usuario;
2. merchant normalization;
3. coincidencia histórica;
4. reglas deterministas;
5. clasificador local;
6. LLM local solo si sigue existiendo ambigüedad;
7. revisión manual si la confianza es baja.

La clasificación debe devolver:
- category;
- subcategory;
- confidence;
- method;
- evidence;
- model/rule version.

## Prioridad de verdad

Orden de autoridad:

1. corrección manual del usuario;
2. regla explícita creada por el usuario;
3. merchant mapping verificado;
4. clasificador determinista;
5. modelo IA.

La IA nunca debe sobrescribir silenciosamente una categoría confirmada por el usuario.

Cuando evoluciona la taxonomía, la acción **Mejorar categorización con IA local** vuelve a evaluar también clasificaciones automáticas deterministas no verificadas. Esto permite que históricos anteriormente clasificados, por ejemplo, como Transporte u Otros pasen a Vehículo, Deporte u Ocio cuando las nuevas reglas aportan una categoría más precisa. Las correcciones manuales siguen protegidas.

## Merchant normalization

Separar:
- description_raw;
- merchant_raw;
- merchant_normalized;
- merchant_group.

Ejemplos de variantes de un mismo comercio deben poder converger en una identidad común.

Mantener alias y evidencia del mapping.

## Transferencias internas

`Movimiento entre cuentas` es una categoría con semántica contable, no solo una etiqueta:
- ni la salida cuenta como gasto;
- ni la entrada cuenta como ingreso;
- una regla explícita que asigne esta categoría aplica la misma semántica;
- una corrección manual del usuario es autoritativa y no se vuelve a pisar con detección automática.

La detección automática se ejecuta al importar y busca pares entre cuentas propias por importe opuesto, divisa y fechas cercanas. Ya no depende de que el usuario pulse un botón separado.

## Reembolsos

`Reembolsos` también tiene semántica contable propia:
- un importe positivo reduce gasto y nunca infla ingresos;
- cuando existe evidencia suficiente se enlaza con el gasto original;
- si no puede enlazarse con certeza, la categoría manual o una regla sigue corrigiendo el cash-flow global sin inventar una compra de origen.

La detección automática se ejecuta al importar. La interfaz permite crear reglas desde cualquier movimiento para aplicar esa clasificación a casos futuros y a históricos todavía no confirmados.

## Operaciones divididas

Permitir split transaction.

Ejemplo:
Compra de 120 €:
- 80 € supermercado;
- 20 € farmacia;
- 20 € hogar.

La suma de splits debe coincidir exactamente con el movimiento original.

## Gastos recurrentes

Detectar:
- mensual;
- bimestral;
- trimestral;
- semestral;
- anual;
- irregular estable.

Calcular:
- importe típico;
- desviación;
- próxima fecha;
- subida/bajada;
- probabilidad de recurrencia.

## Gastos fijos y variables

Clasificar series como:
- fixed;
- semi_fixed;
- variable;
- discretionary.

Esto permite calcular cuánto gasto es realmente reducible.

## Necesario vs discrecional

El usuario puede configurar una clasificación adicional:
- esencial;
- importante;
- discrecional.

No inferir moralmente qué es esencial para el usuario. Proponer y permitir ajuste.

## Anomalías

Detectar:
- importe muy superior al histórico;
- comercio nuevo de importe elevado;
- duplicados;
- cargo recurrente inesperado;
- cargo después de cancelación;
- subida de suscripción;
- gasto fuera de patrón.

Toda anomalía debe explicar el motivo.

## Métricas de gasto

Por periodo:
- gasto total;
- gasto neto;
- gasto fijo;
- gasto variable;
- gasto discrecional;
- gasto por categoría;
- gasto por comercio;
- ticket medio;
- recurrencias;
- coste anualizado;
- variación vs periodo anterior;
- variación interanual;
- peso sobre ingresos;
- peso sobre ahorro;
- top incrementos;
- top reducciones.

## Insights

Ejemplos válidos:
- “Restaurantes ha aumentado 18 % frente a tu media de 6 meses.”
- “Tres suscripciones suman 41,97 €/mes.”
- “Tu coste anual estimado de telecomunicaciones es 1.032 €.”
- “El gasto en energía cae 12 % respecto al mismo periodo anterior.”

Siempre mostrar:
- periodo;
- base de comparación;
- importe;
- cálculo.

## Presupuestos

Por categoría/subcategoría:
- mensual;
- anual;
- rollover opcional;
- alerta por porcentaje consumido;
- forecast de cierre del mes.

## Forecast

Usar:
- gasto realizado;
- recurrencias pendientes;
- patrón temporal;
- presupuesto.

Distinguir:
- confirmado;
- previsto;
- estimado.

## Calidad y revisión

La pantalla de Movimientos muestra un único histórico buscable y filtrable. La baja confianza no crea una segunda lista que duplique movimientos.

Desde cualquier fila el usuario puede:
- corregir la categoría;
- crear una regla basada en comercio o texto;
- dividir el movimiento.

Las reglas guardadas viven en un modal para no ocupar espacio permanente y nunca sobrescriben movimientos ya confirmados manualmente.

## Datos derivados

Cada clasificación conserva:
- algorithm_version;
- generated_at;
- confidence;
- manually_verified.

## Privacidad

La clasificación se realiza localmente. Ningún descriptor de movimientos se envía a servicios de IA cloud.


## Deduplicación de extractos solapados

La importación está diseñada para que se puedan cargar meses completos aunque parte del periodo ya exista.

Orden de identificación:
1. **Referencia bancaria estable** cuando el formato la aporta (por ejemplo FITID en OFX, referencias de CAMT o columnas de referencia/transaction id).
2. **Huella exacta** por cuenta, fecha, importe, divisa y descripción normalizada.
3. **Coincidencia tolerante conservadora** contra movimientos ya existentes de la misma cuenta, mismo importe/divisa y fecha igual o desplazada como máximo un día. Solo se considera duplicado automático cuando descripción/comercio aportan evidencia suficientemente fuerte.

La coincidencia tolerante:
- elimina ruido habitual de exportación como prefijos de compra/pago, terminales y números largos;
- compara descripción y comercio normalizados;
- es deliberadamente conservadora para no borrar dos compras reales del mismo importe en el mismo comercio;
- cada movimiento existente solo puede emparejarse una vez por importación.

Los duplicados idénticos legítimos se tratan como **multiconjunto**: si un extracto contiene dos movimientos realmente iguales, ambos pueden almacenarse. Al volver a importar el mismo extracto se reconocerán los dos, en vez de colapsarlos en uno.

El resultado de importación separa:
- duplicados por referencia bancaria;
- duplicados exactos;
- duplicados por similitud;
- movimientos insertados;
- omitidos por estado pendiente/revertido/cancelado;
- rechazados por formato/datos inválidos.

No se usa solo “misma fecha + mismo importe” como criterio de borrado automático.


## Signo del movimiento y semántica contable

La categoría es la fuente de verdad contable cuando existe una categoría asignada:

- cualquier movimiento positivo suma a ingresos, incluida `Nómina` e `Ingresos`;
- `Movimiento entre cuentas` es una excepción: tanto la salida como la entrada del traspaso propio se excluyen de ingresos y gastos porque solo cambian el saldo entre cuentas del mismo usuario;
- `Reembolsos` conserva una semántica específica: una entrada positiva reduce gasto y no se presenta como nuevo ingreso;
- una recategorización a cualquier categoría distinta de `Movimiento entre cuentas` elimina automáticamente una marca interna de transferencia que pudiera haber quedado de una versión anterior;
- al arrancar, Financito sincroniza las marcas internas con las categorías guardadas para reparar datos antiguos incoherentes.

El detector automático de transferencias no puede convertir una `Nómina` o un `Reembolso` en transferencia interna solo porque exista otro movimiento del mismo importe y signo contrario en otra cuenta.
