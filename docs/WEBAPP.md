# WebApp actual

La interfaz es una WebApp Next.js/React exportada estáticamente y servida por FastAPI desde el mismo origen loopback.

## Navegación implementada

Primer nivel:
- Inicio
- Movimientos
- Patrimonio
- Decisiones

Utilidades globales:
- Buscar
- Preguntar

Configuración:
- General
- Datos y fuentes
- Privacidad y copias
- Avanzado

Las funciones especializadas no desaparecen: Banca se descubre desde Cuentas; Centros de coste desde Análisis; Fiscalidad e Histórico desde Patrimonio; Previsión, Contratos y Seguros desde Decisiones. Las rutas anteriores siguen siendo válidas para deep links.


## Estado y datos
TanStack Query gestiona reads, mutations, cache e invalidación. Los cálculos financieros no se duplican en React: la UI consume resultados del backend.

## Patrones
- loading/empty/error;
- cards responsive;
- tablas con overflow en pantallas estrechas;
- formularios validados por API/Pydantic;
- enlaces de evidencia abren archivo/página;
- secrets se introducen como inputs pero nunca se vuelven a renderizar desde backend.

## Configuración
Permite:
- ver Health;
- seleccionar modelo Ollama y embeddings;
- guardar secrets de Enable Banking/Alpha Vantage/CoinGecko/SEC en credential store.

## Privacidad
Sistema permite:
- backup/restore;
- rebuild de derivados;
- resumen de datos;
- borrado confirmado de DB/índices/secrets.

Los originales del Vault no se eliminan silenciosamente.

## Límites pendientes
- command palette global;
- modo privacidad visual para ocultar importes;
- Developer Mode completo;
- tests de componentes/E2E;
- auditoría WCAG AA formal.
