# Mortgage Engine

## Implementado

### Amortización estándar
Input:
- principal;
- TIN anual decimal;
- meses.

Output:
- cuota;
- pagos totales;
- intereses totales.

### Amortización extraordinaria
Input adicional:
- importe extraordinario;
- comisión total conocida.

Compara:
1. **reducir cuota** manteniendo plazo;
2. **reducir plazo** manteniendo aproximadamente la cuota original.

Devuelve para ambos:
- nueva cuota o nuevo plazo;
- intereses restantes;
- ahorro de intereses neto de la comisión indicada.

No se presupone una comisión legal: el valor debe proceder de evidencia/entrada explícita.

### Switching genérico
El motor de optimización calcula:
`ahorro bruto - coste cambio - penalizaciones - beneficios perdidos - coste recurrente adicional - impacto fiscal`

Si la penalización es desconocida, el resultado es `needs_more_data`.

## No implementado como automatismo completo
- FEIN/FIAE estructurada en todos sus campos;
- curvas variables/mixtas y revisiones de índice;
- novación/subrogación;
- costes legales por jurisdicción/fecha;
- ofertas bancarias comerciales automáticas.

Estos elementos deben añadirse como facts versionados y nunca como constantes “universales”.


## Laboratorio conectado a la hipoteca real

El Laboratorio dispone de un perfil hipotecario persistente con:
- entidad;
- capital pendiente actual;
- tipo fijo/variable/mixto;
- TIN actual;
- cuota mensual real;
- meses restantes;
- comisión total conocida de amortización anticipada.

Los cálculos de escenario base, amortización extraordinaria y senda hipotética reciben un `mortgage_id` y leen estos valores de la base local. La interfaz no precarga capitales, tipos o plazos de ejemplo.

Cada alta/actualización de hipoteca genera un snapshot temporal.

### Amortización extraordinaria

El usuario solo introduce el importe hipotético a amortizar. Capital, TIN, plazo y comisión proceden de la hipoteca guardada. Si la comisión es desconocida, el cálculo se bloquea en vez de asumir 0.

### Senda de tipos

El capital, plazo y TIN inicial son los reales guardados. Los cambios futuros de tipo son assumptions explícitos del usuario y nunca se presentan como predicción.
