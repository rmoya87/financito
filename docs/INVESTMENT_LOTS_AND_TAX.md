# Lotes de inversión y fiscalidad

## Lotes y disposals

Compras y ventas conservan cantidad, coste, comisiones, divisa, FX y trazabilidad. Las ventas asignan lotes FIFO y generan P&L realizado.

## Motor fiscal versionado

La normativa vive en módulos deterministas por `jurisdiction + tax_year`, fuera del LLM.

Rulesets iniciales:

- `ES-IRPF-ahorro-2025-v1`;
- `ES-IRPF-ahorro-2026-v1`.

Cada ruleset conserva:
- escala;
- límites de compensación;
- años de arrastre;
- referencias legales;
- URLs oficiales;
- fecha de verificación.

## España: base del ahorro

El módulo actual implementa la integración corriente de los dos saldos de la base del ahorro y la escala conjunta 19/21/23/27/30. El cruce entre saldo negativo de un bloque y saldo positivo del otro está limitado al 25 %, con remanente documentado para arrastre de cuatro años.

No se consumen automáticamente saldos negativos de ejercicios anteriores porque necesitan su propia evidencia histórica.

## Tax Center

Si existe ruleset para el ejercicio:
- aplica la normativa versionada;
- muestra versión, fuentes y fecha;
- indica inputs fiscales ausentes;
- etiqueta el resultado como cálculo parcial cuando solo dispone del P&L de inversiones.

Si no existe ruleset:
- no inventa tipos;
- permite una tasa explícita únicamente como simulación.

Endpoint detallado:

```text
POST /api/v1/tax/savings/calculate
```

## Alcance

Financito no presenta este cálculo como Modelo 100 ni declaración oficial. Mínimo personal/familiar, arrastres previos, otras rentas y ajustes que no estén registrados siguen fuera del resultado.
