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
