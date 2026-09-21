# Gráficas, visualización e insights

## Principio

Una gráfica solo existe si ayuda a comprender, comparar o decidir.

No añadir visualizaciones decorativas.

Cada gráfica debe responder una pregunta concreta y tener:
- título;
- periodo;
- unidades;
- tooltip;
- fuente;
- frescura;
- alternativa textual accesible.

## Gráficas de gastos

### Cash flow temporal
Línea/área:
- ingresos;
- gastos;
- ahorro.

Granularidad adaptativa: día, semana, mes, año.

### Gastos por categoría
Barra horizontal preferente para comparación exacta.

Mostrar:
- importe;
- porcentaje;
- variación.

Cada categoría debe conservar un color estable y diferenciado en las visualizaciones. El color es apoyo visual, nunca la única forma de identificar la categoría: nombre e importe siguen visibles.

Evitar pie cuando hay muchas categorías.

### Evolución por categoría
Líneas para categorías seleccionadas.

### Gastos fijos vs variables
Barras apiladas por mes.

### Esencial vs discrecional
Composición y evolución.

### Top comercios
Barra horizontal.

### Recurrentes
Serie temporal y coste anualizado.

### Presupuesto vs real
Barra o bullet/progress con forecast.

### Heatmap calendario
Opcional para frecuencia de gasto, no para importes sensibles por defecto.

## Patrimonio

### Net worth
Serie temporal:
- activos;
- pasivos;
- net worth.

### Liquidez
Serie y buffer objetivo.

### Distribución de activos
Barra o donut si las categorías son pocas.

### Deuda
Evolución de principal pendiente.

## Hipoteca

- amortización principal/interés;
- coste acumulado de escenarios;
- diferencia mensual de cuota;
- waterfall de costes de cambio;
- línea de break-even;
- impacto de tipos en escenarios variables.

## Inversión

### Valores seguidos

La vista Mercado puede comparar los activos de la watchlist mediante una línea por activo, normalizada a variación porcentual desde el primer precio disponible del periodo. Esto evita mezclar escalas de precio y divisas distintas.

Cada serie debe mostrar:
- nombre/identificador;
- color diferenciado;
- tooltip porcentual;
- periodo;
- proveedor y fecha de los datos en una alternativa textual.

La gráfica se alimenta del histórico de precios persistido; no inventa puntos cuando un provider no devuelve datos.

### Cartera

- portfolio value;
- performance vs benchmark;
- drawdown;
- allocation por clase;
- sector;
- país;
- divisa;
- contribution to return;
- contribution to risk;
- volatility;
- correlation matrix si aporta valor.

## Cripto

- exposición total;
- drawdown;
- volatilidad;
- peso en cartera;
- concentración.

No sobrecargar con indicadores técnicos si no cambian una decisión.

## Oportunidades

### Waterfall
Desde ahorro bruto hasta ahorro neto:
- gross saving;
- switching costs;
- penalties;
- lost benefits;
- tax;
- net benefit.

### Break-even
Coste acumulado de mantener vs cambiar.

### Comparación
Tabla + barras:
- coste actual;
- alternativa;
- diferencia.

## Decision dashboard

Toda recomendación importante debe tener un panel de impacto:

- impacto mensual;
- impacto anual;
- impacto acumulado;
- liquidez necesaria;
- riesgo;
- esfuerzo;
- break-even;
- sensibilidad.

## Sensitivity charts

Para hipótesis:
- tipos;
- inflación;
- rentabilidad;
- precio;
- consumo.

Nunca mostrar un único escenario como certeza.

## Regla de elección de gráfica

- tendencia temporal → line;
- comparación categórica → bar;
- composición pequeña → pie/donut;
- composición múltiple temporal → stacked bar;
- contribuciones positivas/negativas → waterfall;
- correlación → heatmap/scatter;
- riesgo temporal → drawdown;
- distribución → histogram si procede.

## Movimientos fuera de patrón

La interfaz no presenta la detección como una “anomalía” técnica que el usuario deba interpretar.

Cada aviso debe explicar:
- qué movimiento se compara;
- cuál es el importe habitual comparable;
- cuánto se desvía;
- confianza de la señal;
- que no implica fraude ni error confirmado;
- acciones concretas: marcar como correcto, abrir el movimiento para corregirlo o ignorar el aviso.

## Centros de coste

Un centro de coste responde a preguntas transversales como “¿cuánto me cuesta realmente la vivienda?” o “¿cuánto gasto en el coche?”.

La asociación principal es por categoría: todos los movimientos actuales y futuros de la categoría vinculada alimentan el centro. Contratos, pólizas, activos y deuda pueden añadirse como referencias complementarias. El resumen muestra gasto observado de los últimos 12 meses y media mensual.

## Rendimiento frontend

Gráficas:
- reciben series ya agregadas;
- no procesan datasets completos en React;
- lazy load;
- resize eficiente;
- máximo razonable de puntos según viewport;
- downsampling en backend si es necesario.

## Consistencia

Todos los wrappers compartidos deben usar:
- colores distintos y estables para cada serie cuando una gráfica compara varias magnitudes; ingresos, gastos y ahorro nunca comparten color;
- etiquetas/leyenda además del color para mantener accesibilidad;
- formatos monetarios únicos;
- formatos de porcentaje únicos;
- convenciones temporales;
- tokens de colores semánticos;
- accesibilidad estándar.

## No engañar visualmente

- no truncar ejes sin indicarlo;
- no usar doble eje salvo necesidad justificada;
- no exagerar variaciones;
- no esconder datos negativos;
- no mezclar nominal y real sin etiqueta.


## Selección de noticias de activos seguidos

La superficie de Mercados no debe convertir “Noticias guardadas” en un feed exhaustivo. El backend mantiene el conjunto completo local para análisis y auditoría, pero la UI recibe un \`news_digest\` limitado y priorizado. Cuando la IA local está disponible, selecciona IDs de noticias del catálogo ya existente; cualquier ID no reconocido se descarta.

La lectura de cada activo separa:
- orientación (\`estudiar_entrada\`, \`mantener_observacion\`, \`revisar_exposicion\`, \`datos_insuficientes\`);
- base disponible para considerar inversión (\`investment_status\`);
- riesgo futuro observable (\`future_risk_level\`).

La UI debe presentar estas señales como apoyo a decisión, no como predicciones ni instrucciones automáticas.
