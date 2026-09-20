# Mortgage Engine

## Motores disponibles

### Amortización estándar
Entrada: principal, TIN anual decimal y meses.  
Salida: cuota, pagos totales e intereses.

### Amortización extraordinaria
Compara mantener plazo/reducir cuota frente a mantener aproximadamente la cuota/reducir plazo. La comisión debe ser explícita.

### Senda libre de tipos
`MortgageRatePathEngine` recalcula la cuota en cada cambio de tipo indicado. Sirve para escenarios deterministas, no para predicción.

### Variable/mixta indexada
`MortgageIndexedRateEngine` modela:

- tipo variable;
- tipo mixto con tramo fijo inicial;
- índice + diferencial;
- frecuencia contractual de revisión;
- suelo y techo opcionales;
- recalculo de cuota en cada revisión.

La curva de índice se proporciona como `mes -> valor`. El motor calcula qué meses de revisión son obligatorios y, si falta cualquiera, devuelve `needs_more_data`. No interpola ni extrapola.

Endpoint:

```text
POST /api/v1/mortgage/indexed-path
```

La WebApp lo expone en **Simuladores → Hipoteca variable o mixta por índice**.

## Evidencia FEIN/FIAE

La extracción documental reconoce, cuando el texto lo contiene:

- FEIN/FIAE;
- capital y cuota;
- tipo fijo/variable/mixto;
- TIN/TAE;
- índice y diferencial;
- plazo y revisión;
- tramo fijo;
- suelo/techo;
- apertura y reembolso anticipado;
- subrogación y novación;
- nómina, seguros, tarjeta y plan de pensiones vinculados;
- fórmula temporal de reembolso anticipado.

Los facts son inferidos, conservan página/contexto y requieren confirmación humana antes de tratarlos como evidencia contractual.

## Límites deliberados

- no se predice Euríbor;
- no se inventa comisión legal;
- no se supone que una condición ausente valga cero;
- una novación/subrogación concreta debe evaluarse con sus hechos contractuales y fiscales vigentes.
