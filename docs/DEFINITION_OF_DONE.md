# Definition of Done

Una funcionalidad se considera terminada cuando:

1. compila;
2. tiene tests proporcionales al riesgo;
3. no introduce errores conocidos;
4. maneja loading/empty/error/offline si aplica;
5. no filtra secretos;
6. documenta decisiones nuevas;
7. respeta contratos API;
8. registra fuente/frescura para datos externos;
9. sus cálculos son trazables si afectan a finanzas;
10. la UI cumple accesibilidad básica;
11. no deja TODO/FIXME como sustituto de funcionalidad requerida;
12. migraciones y compatibilidad están verificadas.

## Recomendaciones

Además:
- evidencia;
- cálculos;
- supuestos;
- confianza;
- frescura;
- riesgos;
- sin ejecución automática.

## RAG

Además:
- cita válida;
- no inventa si falta información;
- tests de recuperación;
- documento abrible desde la fuente.

## Providers

Además:
- timeout;
- rate limit;
- retry razonable;
- cache/freshness;
- errores normalizados;
- secrets fuera del código.
