# Especificación funcional

## Objetivo

Financito debe proporcionar una visión financiera personal 360º y convertir datos dispersos en información accionable, sin delegar la verdad financiera en un LLM.

## Perfiles y acceso

La primera versión está orientada a un único usuario local. La arquitectura debe permitir perfiles familiares futuros sin mezclar datos ni permisos.

El acceso local debe poder protegerse mediante sesión, bloqueo automático y, cuando la plataforma lo permita, autenticación biométrica del sistema.

## 1. Resumen

El dashboard muestra:
- patrimonio neto;
- liquidez;
- capital invertible;
- ingresos y gastos del periodo;
- ahorro y ratio de ahorro;
- cartera y riesgo;
- próximos cargos;
- renovaciones;
- alertas;
- oportunidades de ahorro;
- oportunidades de rendimiento;
- noticias relevantes para la cartera.

Todos los widgets deben mostrar fecha de actualización cuando el dato no sea instantáneo.

## 2. Cuentas

Funciones:
- cuentas bancarias manuales e integradas;
- saldo actual y disponible;
- moneda;
- IBAN enmascarado;
- banco;
- estado de sincronización;
- consentimiento Open Banking;
- histórico de saldo cuando esté disponible.

Las conexiones externas son de solo lectura inicialmente.

## 3. Movimientos

Importación por Open Banking, CSV, OFX y QIF.

Campos normalizados:
- fecha;
- fecha valor;
- cuenta;
- descripción original;
- descripción normalizada;
- comercio;
- importe;
- moneda;
- categoría;
- subcategoría;
- recurrente;
- etiquetas;
- fuente.

Funciones:
- edición de categoría;
- reglas de categorización;
- detección de duplicados;
- búsqueda y filtros;
- agrupación por comercio;
- aprendizaje a partir de correcciones.

## 4. Recurrentes y suscripciones

Detectar recurrencia mediante similitud de comercio, periodicidad e importe.

Alertar sobre:
- nueva recurrencia;
- subida de precio;
- cobro duplicado;
- fin de promoción;
- posible servicio no utilizado;
- renovación próxima.

## 5. Presupuesto

Permitir objetivos mensuales/anuales por categoría y comparar:
- presupuesto;
- gasto real;
- desviación;
- tendencia.

No bloquear operaciones: es una herramienta analítica.

## 6. Patrimonio

Incluir:
- efectivo;
- cuentas;
- acciones;
- ETF;
- fondos;
- bonos;
- cripto;
- inmuebles;
- vehículos;
- otros activos;
- hipotecas;
- préstamos;
- otras deudas.

Distinguir:
- Net Worth;
- Liquidity;
- Investable Capital;
- Emergency Fund.

## 7. Documentos

Financial Knowledge Vault configurable.

Formatos iniciales:
PDF, PNG/JPG/HEIC, DOCX, XLSX, CSV, TXT y JSON.

Estados:
Pending, Processing, Indexed, Failed, Excluded.

Acciones:
- abrir original;
- ver texto extraído;
- ver metadatos;
- editar clasificación;
- reindexar;
- excluir de IA;
- eliminar índice sin eliminar original.

Tipos iniciales:
seguros, hipoteca, préstamos, facturas de suministros, telecomunicaciones, nóminas, impuestos, extractos, contratos, suscripciones, vehículo, IBI, comunidad e inversiones.

## 8. Contratos y servicios

Cada producto debe poder almacenar:
- proveedor;
- coste;
- periodicidad;
- inicio;
- renovación;
- permanencia;
- preaviso;
- penalización;
- condiciones;
- beneficios;
- productos vinculados.

## 9. Seguros

Tipos: coche, hogar, vida, salud y genérico.

Comparar por:
- prima;
- coberturas;
- franquicia;
- capitales;
- exclusiones relevantes;
- asistencia;
- condiciones de cancelación;
- bonificaciones;
- calidad/equivalencia de cobertura.

Una póliza más barata no se considera mejor automáticamente.

## 10. Hipoteca

Modelar:
- capital original y pendiente;
- plazo;
- TIN;
- TAE;
- tipo fijo/variable/mixto;
- índice y diferencial;
- cuota;
- revisiones;
- comisiones;
- amortización;
- vinculaciones;
- bonificaciones.

Comparar:
- mantener;
- novación;
- subrogación;
- cancelación + nueva;
- amortización parcial.

Horizontes: 1, 3, 5, 10 años y vencimiento.

## 11. Inversiones

Soportar:
- acciones;
- ETF;
- fondos;
- bonos;
- cripto;
- efectivo.

Entradas:
- API/provider;
- CSV;
- manual;
- documentos.

Mostrar:
- cantidad;
- precio medio;
- precio actual;
- valor;
- P&L;
- moneda;
- peso;
- asignación por activo/sector/país/divisa.

## 12. Mercados y fundamentales

Datos según disponibilidad:
- precio;
- OHLCV;
- dividendos;
- splits;
- market cap;
- sector;
- fundamentales;
- ratios;
- históricos;
- macro.

Toda fuente debe registrar timestamp y proveedor.

## 13. Cripto

Motor separado del de acciones.

Considerar:
- precio;
- volumen;
- capitalización;
- liquidez;
- volatilidad;
- drawdown;
- supply;
- dominancia;
- funding/open interest si existe;
- métricas on-chain cuando sean fiables.

## 14. Noticias

Ingesta, deduplicación y vinculación con activos.

Guardar:
- titular;
- fuente;
- URL;
- fecha de publicación;
- fecha del evento;
- activos afectados;
- sentimiento;
- impacto;
- fiabilidad.

No confundir publicación con fecha del acontecimiento.

## 15. Riesgo

Calcular de forma determinista:
- volatilidad;
- beta;
- correlación;
- drawdown;
- Sharpe;
- Sortino;
- VaR/CVaR;
- concentración;
- exposición sectorial/geográfica/divisa.

## 16. Recomendaciones de inversión

Una recomendación combina motores deterministas y contexto de cartera. El LLM solo explica.

Componentes posibles:
- fundamentales;
- valoración;
- crecimiento;
- calidad;
- momentum;
- riesgo;
- noticias;
- macro;
- encaje en cartera.

Siempre incluir:
- tesis;
- riesgos;
- catalizadores;
- condiciones de invalidación;
- fuentes;
- frescura;
- impacto sobre cartera.

No ejecutar operaciones automáticamente.

## 17. Optimización

Analizar:
- seguros;
- hipoteca;
- préstamos;
- energía;
- telecomunicaciones;
- bancos;
- tarjetas;
- suscripciones;
- efectivo improductivo;
- comisiones;
- productos de inversión.

Cada oportunidad debe exponer:
- coste actual;
- alternativa;
- ahorro bruto;
- costes de cambio;
- penalizaciones;
- beneficios perdidos;
- costes adicionales;
- impacto fiscal cuando proceda;
- ahorro neto;
- break-even;
- riesgo;
- esfuerzo;
- urgencia;
- confianza.

## 18. Puntos y beneficios

Valorar:
- puntos;
- millas;
- cashback;
- seguros incluidos;
- lounges;
- descuentos;
- suscripciones;
- servicios premium.

Distinguir:
- valor teórico;
- valor realizado;
- valor ajustado por el usuario.

## 19. Chat financiero

Preguntas objetivo:
- “¿Cuánto gasté en restaurantes?”
- “¿Qué gastos han subido?”
- “¿Qué seguros renuevan pronto?”
- “¿Me compensa cambiar de hipoteca?”
- “¿Qué penalización tendría?”
- “¿Dónde puedo ahorrar 300 € al mes?”
- “¿Qué capital tengo sin remunerar?”
- “¿Qué ha pasado hoy con mi cartera?”
- “¿Qué cambió respecto al análisis anterior?”

El chat debe usar tools, RAG y motores financieros. Toda respuesta debe poder mostrar evidencia.

## 20. Memoria y decisiones

Guardar por separado:
- hechos;
- preferencias;
- decisiones;
- snapshots de análisis.

Las preferencias no pueden cambiar datos objetivos.

## 21. Fuera de alcance inicial

- ejecución automática de transferencias;
- trading automático;
- asesoramiento a terceros;
- multiusuario cloud;
- almacenamiento remoto de documentos privados.
