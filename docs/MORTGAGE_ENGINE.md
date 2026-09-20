# Mortgage Optimization Engine

## Objetivo

Comparar de forma trazable el coste de mantener o modificar una hipoteca.

## Datos actuales

- capital pendiente;
- plazo restante;
- cuota;
- TIN;
- TAE;
- tipo fijo/variable/mixto;
- índice;
- diferencial;
- fecha de revisión;
- comisión de amortización;
- novación;
- subrogación;
- vencimiento.

## Vinculaciones

Modelar individualmente:
- nómina;
- seguro hogar;
- seguro vida;
- tarjetas;
- planes;
- alarma;
- otros.

Cada vinculación:
- coste anual real;
- coste alternativo equivalente;
- descuento sobre tipo;
- beneficio monetario de la bonificación.

## Estrategias

Comparar al menos:
1. mantener;
2. novación;
3. subrogación;
4. cancelación + nueva hipoteca;
5. amortización parcial;
6. amortización total cuando tenga sentido.

## Costes

Según aplicabilidad:
- comisión de apertura;
- amortización;
- novación;
- subrogación;
- tasación;
- gastos administrativos;
- productos vinculados;
- seguros;
- pérdida de bonificaciones;
- impuestos o impacto fiscal aplicable.

Nunca asumir que un coste legal aplica: las reglas deben ser configurables por jurisdicción y fecha.

## Escenarios

Horizontes:
- 1 año;
- 3 años;
- 5 años;
- 10 años;
- vencimiento.

Para variable/mixta:
- escenario base;
- subida de índice;
- bajada de índice;
- sensibilidad configurable.

No presentar escenarios como predicciones.

## Resultados

- cuota;
- intereses;
- costes asociados;
- coste total;
- ahorro bruto;
- coste de cambio;
- ahorro neto;
- break-even;
- cash flow mensual.

## Ejemplo de salida

```text
Mantener:
  coste horizonte 10 años: X

Subrogación:
  coste horizonte 10 años: Y
  costes iniciales: Z

Ahorro bruto: A
Costes cambio: B
Beneficios/vinculaciones: C
Ahorro neto: D
Break-even: N meses
```

## Trazabilidad

Guardar:
- documento actual;
- oferta alternativa;
- fecha;
- parámetros;
- curva/índice usado;
- versión del motor.

## Validación

Tests con:
- fijo;
- variable;
- mixto;
- amortización;
- cambios de plazo;
- comisiones;
- bonificaciones;
- escenarios adversos.
