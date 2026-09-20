# Auditoría interna WCAG 2.2 AA

Fecha de revisión: **2026-09-20**.  
Objetivo de conformidad: **WCAG 2.2 nivel AA**.

## Alcance

La auditoría cubre todas las rutas principales de la WebApp exportada: resumen, búsqueda, onboarding, cuentas, banca, movimientos, previsión, análisis, patrimonio, histórico, centros de coste, inversiones, mercados, fiscalidad, contratos, seguros, objetivos, documentos, chat, acciones, simuladores, decisiones, integridad, ajustes y desarrollo.

WCAG exige que una declaración de conformidad cubra páginas completas y todos los criterios A y AA aplicables. Por ello Financito no considera suficiente un único resultado de Lighthouse o axe.

## Controles automatizados en CI

Playwright ejecuta Chromium contra el runtime local real y:

- recorre las rutas principales;
- ejecuta axe con tags WCAG 2.0 A/AA, 2.1 A/AA y 2.2 A/AA;
- falla ante cualquier violación reportada;
- comprueba enlace de salto, foco de teclado y `aria-current`;
- comprueba reflow representativo a 320 CSS px sin scroll horizontal global;
- mantiene capturas y trace en caso de error.

## Controles estructurales aplicados

- `lang="es"` en el documento;
- `nav` con nombre accesible y `main` identificable;
- enlace “Saltar al contenido” visible al recibir foco;
- indicador de foco explícito y de alto contraste;
- color de texto secundario ajustado a contraste AA sobre superficies usadas;
- controles nativos y labels visibles en formularios;
- `aria-current="page"` en navegación;
- iconos decorativos de navegación ocultos del árbol accesible;
- reducción de animaciones cuando `prefers-reduced-motion: reduce`;
- sin gestos complejos obligatorios ni contenido multimedia temporizado en el runtime actual.

## Criterios que requieren disciplina continua

Axe no sustituye la revisión humana. Cada cambio de UI debe revisar especialmente:

- 1.1.1 alternativas textuales;
- 1.3.x estructura y relaciones;
- 1.4.3/1.4.11 contraste;
- 1.4.10 reflow;
- 2.1.1 teclado;
- 2.4.1 bypass blocks;
- 2.4.3 orden de foco;
- 2.4.7 foco visible;
- 2.4.11 foco no oculto;
- 2.5.8 tamaño mínimo de objetivo;
- 3.3.x errores, etiquetas e instrucciones;
- 4.1.2 nombre, función y valor.

## Criterio de cierre

Una entrega no puede declararse accesible si falla el job E2E. La auditoría interna se considera vigente mientras:

1. todas las rutas continúen dentro del barrido axe;
2. Playwright permanezca verde;
3. no se introduzcan componentes de interacción que el test de teclado no pueda alcanzar;
4. los cambios de color mantengan contraste AA.

W3C no certifica ni verifica las declaraciones de conformidad de productos. Este documento es la evidencia de auditoría interna del repositorio, no una certificación emitida por un tercero.

## Referencias

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [Conformidad WCAG 2.2](https://www.w3.org/TR/wcag/#conformance-reqs)
- [Understanding Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible)
- [Understanding Focus Not Obscured (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum)
- [Understanding Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum)
