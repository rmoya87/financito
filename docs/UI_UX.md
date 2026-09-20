# UI/UX — WebApp

## Tecnología

Frontend objetivo:
- Next.js;
- React;
- TypeScript;
- TailwindCSS;
- shadcn/ui.

El diseño debe sentirse como una herramienta financiera premium, clara y sobria, no como un dashboard saturado.

## Layout

Desktop:
- sidebar persistente;
- header contextual;
- área de contenido;
- panel lateral opcional para detalle/inspector.

Tablet:
- sidebar colapsable;
- detalle como sheet/panel.

Móvil/PWA futuro:
- navegación adaptada;
- sin asumir hover;
- tablas convertidas a cards/rows.

## Navegación

Sidebar:
1. Resumen
2. Cuentas
3. Movimientos
4. Presupuesto
5. Patrimonio
6. Inversiones
7. Mercados
8. Cripto
9. Documentos
10. Contratos
11. Seguros
12. Hipoteca
13. Servicios
14. Oportunidades
15. Chat
16. Configuración

## shadcn/ui

Preferir componentes shadcn para:
- Button;
- Card;
- Table/DataTable;
- Dialog;
- Sheet;
- DropdownMenu;
- Select;
- Tabs;
- Tooltip;
- Popover;
- Command;
- Form;
- Input;
- Badge;
- Alert;
- Skeleton;
- Progress;
- Accordion;
- Drawer cuando aplique.

No crear componentes visuales custom si shadcn cubre correctamente el caso.

## Tailwind

Usar tokens semánticos:
- background;
- foreground;
- card;
- muted;
- primary;
- secondary;
- destructive;
- border;
- ring.

No hardcodear colores repetidos.

## Tema

- light;
- dark;
- system.

Los colores de rentabilidad positiva/negativa no deben ser el único medio de comunicación: incluir iconografía/texto accesible.

## Dashboard

Jerarquía:
1. patrimonio/liquidez;
2. flujo del mes;
3. alertas y oportunidades;
4. cartera;
5. próximos eventos;
6. noticias.

Evitar más de 4–6 KPIs principales en primer viewport.

## Tablas

Movimientos/cartera:
- sticky header;
- ordenación;
- filtros;
- búsqueda;
- paginación/virtualización;
- columnas configurables en fases posteriores.

## Documentos

Vista:
- lista;
- estado de indexación;
- categoría;
- fecha;
- entidades;
- acciones.

Detalle:
- preview;
- texto;
- facts extraídos;
- citas/chunks;
- reindexar;
- excluir de IA.

## Oportunidades

Cada card muestra:
- tipo;
- beneficio neto;
- break-even;
- confianza;
- urgencia;
- principal riesgo.

Detalle con pestañas:
- Resumen;
- Cálculo;
- Diferencias;
- Fuentes;
- Historial.

## Hipoteca

Comparador con:
- escenario actual;
- alternativas;
- cash-flow;
- coste acumulado;
- break-even;
- vinculaciones.

Nunca ocultar assumptions.

## Chat

Patrón:
- conversación central;
- chips de sugerencias;
- streaming;
- panel “Fuentes y cálculos”;
- citas clicables;
- estado de tools opcional en Developer Mode.

## Búsqueda

Cmd/Ctrl+K:
- documentos;
- movimientos;
- activos;
- contratos;
- seguros;
- hipoteca;
- comandos de navegación.

## Estados

Toda vista debe contemplar:
- loading;
- skeleton;
- empty;
- partial data;
- stale;
- error;
- offline.

No usar spinners bloqueantes salvo operaciones breves.

## Accesibilidad

- WCAG AA como objetivo;
- navegación teclado;
- focus visible;
- ARIA correcta;
- contraste;
- no depender solo de color;
- tablas legibles;
- gráficas con resumen textual.

## Gráficas

Usar gráficas solo cuando aporten comprensión.
Siempre:
- tooltip;
- rango temporal;
- unidades;
- fuente/frescura;
- resumen accesible.

## Privacidad visual

Por defecto permitir modo privacidad:
- ocultar saldos;
- ocultar números sensibles;
- revelar bajo acción explícita.

## Design system

Antes de crecer la UI:
- tipografía;
- spacing;
- radius;
- sombras;
- estados;
- tablas;
- densidad;
- motion;
- chart tokens.

Todo debe documentarse en Storybook o catálogo equivalente cuando se implemente.
