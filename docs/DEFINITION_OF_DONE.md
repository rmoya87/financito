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


## Categorización

Una feature de movimientos no está terminada si:
- existen movimientos sin estado de clasificación definido;
- no se conserva confidence/method cuando la clasificación es automática;
- una corrección manual puede ser sobrescrita silenciosamente;
- transferencias internas contaminan ingresos/gastos;
- splits no cuadran exactamente;
- no existe trazabilidad de recategorización.

## Decisiones

Toda recomendación material debe incluir:
- alternativas;
- impacto monetario;
- horizonte;
- assumptions;
- fuentes;
- confidence de evidencia;
- riesgos;
- break-even cuando aplique;
- datos faltantes.

No se considera terminada si solo devuelve texto generado por LLM.

## Visualizaciones

Toda gráfica:
- responde a una pregunta;
- usa datos agregados/validados;
- tiene unidades y periodo;
- muestra fuente/frescura;
- tiene alternativa accesible;
- no induce a error visual.

## IA/Agentes de desarrollo

Cualquier cambio generado por IA debe cumplir AI_ENGINEERING_RULES.md y DEVELOPMENT_WORKFLOW.md.

La IA no puede declarar una tarea completa sin:
- build ejecutado cuando exista código;
- tests relevantes ejecutados;
- docs actualizadas;
- limitaciones reales declaradas.
