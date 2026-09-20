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

La navegación principal se organiza por intención de usuario, no por módulos técnicos.

Sidebar principal:
1. Inicio
2. Movimientos
3. Patrimonio
4. Decisiones

Utilidades globales:
- Buscar
- Preguntar

Configuración aparece separada al pie del sidebar.

### Navegación contextual

Movimientos:
- Movimientos
- Análisis
- Cuentas
- Banca conectada se abre desde Cuentas.
- Centros de coste se abre desde Análisis.

Patrimonio:
- Resumen
- Inversiones
- Mercado
- Histórico
- Fiscalidad se abre de forma contextual desde Patrimonio/Inversiones.

Decisiones:
- Para ti
- Objetivos
- Simular
- Mis decisiones
- Previsión, Contratos y Seguros se presentan como herramientas relacionadas dentro de Para ti.

Configuración:
- General
- Datos y fuentes
- Privacidad y copias
- Avanzado

Las rutas internas especializadas se conservan para deep links, búsqueda y flujos contextuales, pero no deben añadirse de nuevo al primer nivel salvo una revisión explícita de arquitectura de información.

Regla de densidad:
- máximo 4 áreas financieras en navegación principal;
- búsqueda e IA son utilidades globales;
- configuración y diagnóstico no compiten con el flujo financiero diario;
- las capacidades avanzadas se descubren de forma progresiva desde su contexto.

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


## Arquitectura de componentes

La definición autoritativa de composición y reutilización está en:
- FRONTEND_ARCHITECTURE.md
- COMPONENT_CATALOG.md

Regla:
shadcn/ui → shared components → feature components.

No duplicar componentes por feature si el patrón ya existe.

## Rendimiento UI

- static build en producción;
- code splitting por ruta;
- tablas grandes virtualizadas;
- paginación cursor;
- skeleton específico;
- cada widget falla de forma aislada;
- gráficas lazy;
- TanStack Query para toda comunicación con API;
- Zustand solo para estado visual efímero;
- sin cálculos financieros en React.

## Seguridad UI

La WebApp no contiene secretos ni llama directamente a providers que requieran credenciales. No almacena datos financieros persistentes en browser storage. Assets y fuentes son locales.


## Documentos como entrada de datos

La carpeta física del Vault no debe ser requisito de uso.

Reglas de UX:
- Inicio debe ofrecer acceso visible a **Añadir documentos**;
- Seguros, Hipoteca/Laboratorio, Contratos, Cuentas, Inversiones y Fiscalidad deben enlazar a Documentos cuando la evidencia pueda mejorar la sección;
- la pantalla Documentos debe admitir selector nativo y drag & drop;
- después de subir, mostrar procesamiento, hechos pendientes y análisis local;
- toda conclusión material debe permitir volver a la evidencia/página;
- la aplicación explica claramente qué parte es dato confirmado y qué parte es interpretación de IA.
