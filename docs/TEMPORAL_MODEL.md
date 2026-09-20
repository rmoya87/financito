# Modelo temporal y reproducibilidad

## Objetivo

Distinguir:
- cuándo ocurrió algo;
- cuándo empezó a ser válido;
- cuándo Financito lo conoció;
- cuándo fue sustituido.

## Campos temporales

Cuando aplique:
- occurred_at: cuándo ocurrió el evento;
- effective_from/effective_to: vigencia;
- observed_at: cuándo Financito lo conoció;
- fetched_at: cuándo se obtuvo de proveedor;
- created_at/updated_at: persistencia local.

## Regla

Un análisis “a fecha X” solo puede utilizar datos conocidos/vigentes hasta X cuando se pretende reproducir una decisión histórica.

No usar datos futuros para justificar retrospectivamente una recomendación.

## Snapshots

Guardar snapshots para:
- patrimonio;
- cartera;
- condiciones contractuales;
- recomendaciones;
- forecasts;
- decisiones.

## Correcciones

Si se corrige un dato histórico:
- conservar auditoría;
- no reescribir silenciosamente decisiones históricas;
- permitir recalcular una versión corregida diferenciada de la original.

## Backtesting

Toda evaluación histórica usa temporal semantics estrictas para evitar look-ahead.
