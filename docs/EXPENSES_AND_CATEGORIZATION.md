# Gastos, categorización y análisis de consumo

## Objetivo

Todo movimiento de cuenta debe terminar en un estado interpretable, trazable y útil para la toma de decisiones.

Financito no se limita a importar movimientos: normaliza comercios, clasifica, detecta recurrencias, identifica anomalías, agrega por categorías y genera insights accionables.

## Taxonomía base

Categorías principales iniciales:

- Vivienda
- Alimentación
- Restaurantes
- Transporte
- Vehículo
- Seguros
- Salud
- Educación
- Hijos y familia
- Mascotas
- Viajes
- Ocio
- Tecnología
- Compras
- Suscripciones
- Telecomunicaciones
- Energía y suministros
- Impuestos y tasas
- Comisiones bancarias
- Préstamos y deuda
- Inversión
- Ahorro
- Transferencias propias
- Ingresos
- Nómina
- Reembolsos
- Donaciones
- Otros

Cada categoría puede tener subcategorías.

Ejemplos:
- Alimentación → supermercado, mercado, delivery, panadería.
- Vehículo → combustible, carga eléctrica, parking, peajes, mantenimiento, seguro.
- Vivienda → hipoteca, comunidad, IBI, reparaciones, muebles.
- Suscripciones → streaming, software, prensa, gimnasio.

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

## Merchant normalization

Separar:
- description_raw;
- merchant_raw;
- merchant_normalized;
- merchant_group.

Ejemplos de variantes de un mismo comercio deben poder converger en una identidad común.

Mantener alias y evidencia del mapping.

## Transferencias internas

Detectar transferencias entre cuentas propias para evitar contar:
- salida como gasto;
- entrada como ingreso.

Matching por:
- importe;
- divisa;
- fechas cercanas;
- cuentas propias;
- referencia.

Si existe duda, marcar como probable y no confirmar automáticamente con baja confianza.

## Reembolsos

Relacionar reembolsos con gastos originales cuando sea posible.

El análisis debe poder mostrar:
- gasto bruto;
- reembolso;
- gasto neto.

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

## Calidad

Movimientos con baja confianza aparecen en una cola de revisión.

Objetivo de UX:
“Revisar 8 movimientos” en vez de esconder errores de clasificación.

## Datos derivados

Cada clasificación conserva:
- algorithm_version;
- generated_at;
- confidence;
- manually_verified.

## Privacidad

La clasificación se realiza localmente. Ningún descriptor de movimientos se envía a servicios de IA cloud.
