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

El dashboard debe incluir únicamente visualizaciones que ayuden a decidir. Como mínimo:
- evolución de ingresos, gastos y ahorro;
- gasto por categoría;
- fijos vs variables;
- presupuesto vs real y forecast;
- evolución de patrimonio;
- deuda;
- cartera/riesgo cuando exista;
- oportunidades priorizadas;
- próximas obligaciones.

Las reglas completas de visualización están en VISUALIZATION_AND_INSIGHTS.md.

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
- categorización automática de todos los movimientos;
- subcategorización;
- normalización y agrupación de comercios;
- edición manual;
- reglas de categorización;
- clasificación esencial/importante/discrecional configurable;
- clasificación fijo/semi-fijo/variable;
- splits;
- detección de transferencias internas;
- relación de reembolsos;
- detección de duplicados;
- detección de anomalías;
- búsqueda y filtros;
- agrupación por comercio;
- aprendizaje a partir de correcciones;
- cola de revisión para baja confianza;
- trazabilidad de método, confianza y versión.

La taxonomía, prioridad de clasificación y reglas completas se definen en EXPENSES_AND_CATEGORIZATION.md.

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

Los documentos contractuales descargados por el usuario son fuente primaria para condiciones particulares, penalizaciones, preavisos, vinculaciones y coberturas. Financito debe extraer estas cláusulas a datos estructurados y utilizarlas directamente en los motores de cálculo.

No basta con que el PDF sea consultable por RAG.

La jerarquía de evidencia, vigencia, conflictos y reglas de bloqueo se definen en CONTRACT_EVIDENCE.md.



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

## 20. Motor de decisiones

Toda decisión material debe poder modelarse como un caso con estado actual, alternativas, assumptions, restricciones, fuentes e impacto.

El usuario debe poder comparar:
- impacto mensual;
- impacto anual;
- impacto acumulado por horizonte;
- liquidez;
- patrimonio;
- riesgo;
- esfuerzo;
- reversibilidad;
- fiscalidad cuando aplique;
- break-even.

No presentar escenarios futuros como certezas.

El comportamiento autoritativo se define en DECISION_ENGINE.md.

## 21. Memoria y decisiones

Guardar por separado:
- hechos;
- preferencias;
- decisiones;
- snapshots de análisis.

Las preferencias no pueden cambiar datos objetivos.

## 22. Onboarding y configuración inicial

El primer arranque debe guiar al usuario sin exigir integraciones externas.

Wizard:
1. crear perfil local;
2. moneda base y región;
3. configurar bloqueo/seguridad;
4. seleccionar o crear Financial Knowledge Vault;
5. elegir modelo IA local;
6. comprobar embeddings;
7. configurar imports iniciales;
8. conectar providers opcionalmente;
9. definir perfil financiero;
10. definir perfil de inversión;
11. ejecutar diagnóstico local.

El usuario puede saltar integraciones y usar Demo Mode.

## 23. Centro de calidad y reconciliación

Crear una vista específica para detectar y resolver:
- movimientos duplicados;
- discrepancias de saldo;
- importaciones solapadas;
- documentos contradictorios;
- facts de baja confianza;
- activos sin identificar;
- monedas desconocidas;
- proveedores desactualizados;
- transacciones sin categorizar.

Las correcciones manuales deben conservar auditoría y prevalecer sobre inferencias automáticas hasta que el usuario las cambie.

## 24. Calendario financiero y alertas

Crear Financial Calendar con:
- recibos previstos;
- nóminas;
- renovaciones;
- vencimientos;
- revisiones hipotecarias;
- fin de permanencias;
- impuestos configurados;
- dividendos;
- cupones;
- eventos relevantes de cartera cuando exista fuente fiable.

Alertas locales:
- renovación próxima;
- subida de precio;
- consentimiento bancario próximo a expirar;
- dato obsoleto;
- gasto anómalo;
- oportunidad con fecha límite;
- fondo de emergencia por debajo del objetivo.

Las notificaciones son locales. No usar servicios push cloud propios.

## 25. Objetivos financieros

Permitir crear objetivos:
- fondo de emergencia;
- ahorro;
- compra;
- viaje;
- amortización;
- inversión;
- reducción de deuda.

Campos:
- objetivo;
- importe;
- fecha;
- prioridad;
- aportación actual;
- aportación mensual prevista.

El sistema puede simular progreso, pero no mover dinero automáticamente.

## 26. Laboratorio de escenarios

Crear Scenario Lab para comparar decisiones:
- ahorrar vs invertir;
- amortizar vs invertir;
- cambiar hipoteca;
- cancelar suscripción;
- cambiar seguro;
- modificar aportación mensual;
- aumentar fondo de emergencia;
- cambio de asignación de cartera.

Todo escenario debe conservar assumptions y diferenciar datos conocidos de hipótesis.

## 27. Fiscalidad

Crear Tax Center modular.

Objetivo inicial:
- recopilar datos potencialmente relevantes;
- registrar plusvalías/minusvalías;
- dividendos/intereses;
- retenciones;
- fechas de compra/venta;
- costes;
- documentos fiscales;
- estimaciones claramente marcadas.

La normativa específica por país debe implementarse como módulo versionado por jurisdicción y ejercicio.

Nunca presentar una estimación fiscal como declaración oficial.

## 28. Multi-divisa

Soportar múltiples monedas desde el inicio.

Toda cantidad externa debe conservar:
- importe original;
- moneda original;
- importe en moneda base;
- tipo de cambio;
- fecha/fuente del FX.

No reescribir históricos al cambiar el FX actual.

## 29. Propiedad y ámbito familiar

Aunque la primera versión tenga un único usuario local, cuentas, activos, pasivos y gastos deben poder indicar ownership:
- personal;
- compartido;
- porcentaje de propiedad;
- miembro/etiqueta lógica.

Esto evita rehacer el modelo si se incorpora visión familiar.

No implica multiusuario remoto.

## 30. Valoración de activos manuales

Permitir activos no conectables:
- vivienda;
- vehículos;
- efectivo;
- objetos;
- otros.

Cada valoración:
- fecha;
- fuente;
- valor;
- moneda;
- método;
- confianza.

No actualizar una valoración estimada sin conservar histórico.

## 31. Backup, restore y exportabilidad

Funciones:
- backup cifrado local;
- verificación;
- restauración;
- export completo;
- export parcial;
- portabilidad en formatos abiertos.

El usuario debe poder recuperar sus datos sin depender de Financito.

## 32. Auditoría y actividad

Crear Activity/Audit Center local:
- imports;
- sincronizaciones;
- correcciones;
- cambios de configuración;
- reindexación;
- modelos cambiados;
- recomendaciones;
- decisiones;
- backups/restores.

No registrar secretos ni contenido sensible innecesario.

## 33. Salud del sistema e integraciones

Crear Health Center:
- estado DB;
- espacio disponible;
- estado Vault;
- jobs pendientes;
- modelo local;
- embeddings;
- providers;
- última sync;
- consentimientos;
- errores recientes;
- calidad de datos.

Debe diferenciar claramente un fallo técnico de un dato desactualizado.

## 34. Gestión de modelos IA locales

Desde Configuración:
- listar modelos instalados;
- verificar checksum;
- mostrar tamaño;
- RAM estimada;
- contexto;
- rol recomendado;
- activar/desactivar;
- borrar;
- cambiar modelo por tarea.

La descarga nunca debe ejecutar código arbitrario del repositorio del modelo.

## 35. Reglas y automatizaciones locales

Permitir reglas deterministas:
- categorizar comercio;
- etiquetar movimiento;
- ignorar transferencia interna;
- alertar por importe;
- detectar vencimiento;
- ejecutar reindexación;
- actualizar una comparación cuando se acerque renovación.

No permitir reglas que ejecuten transferencias o trading en la primera versión.

## 36. Búsqueda global

Cmd/Ctrl+K debe localizar:
- cuentas;
- movimientos;
- documentos;
- contratos;
- seguros;
- hipotecas;
- activos;
- noticias;
- oportunidades;
- acciones de navegación.

La búsqueda semántica se usa donde aporta valor; no sustituye filtros exactos.

## 37. Privacidad, retención y borrado

El usuario debe poder:
- bloquear Financito;
- ocultar valores;
- desconectar providers;
- borrar cachés;
- borrar embeddings;
- eliminar índices;
- eliminar datos importados;
- exportar antes de borrar;
- realizar borrado total de Financito.

Diferenciar siempre dato original, copia gestionada y derivado.

## 38. Fuera de alcance inicial

- ejecución automática de transferencias;
- trading automático;
- asesoramiento a terceros;
- multiusuario cloud;
- almacenamiento remoto de documentos privados.


## 39. Forecast de gastos, ahorro y liquidez

Financito debe generar previsiones a horizonte configurable basadas en:
- mismo periodo del año anterior;
- recurrencias confirmadas;
- compromisos futuros;
- tendencia reciente;
- estacionalidad;
- cambios contractuales conocidos;
- ingresos esperados;
- eventos extraordinarios excluibles.

El mismo periodo del año anterior es baseline obligatorio cuando exista suficiente histórico.

La previsión debe mostrar:
- gasto previsto;
- ahorro previsto;
- liquidez prevista;
- rango esperado;
- precisión histórica;
- categorías que explican la desviación;
- comparación contra mismo periodo del año anterior.

El detalle se define en FORECASTING_AND_COMMITMENTS.md.

## 40. Compromisos futuros

Crear CommitmentsEngine para identificar dinero ya comprometido aunque siga en cuenta.

Ejemplos:
- hipoteca;
- seguros;
- impuestos;
- suscripciones;
- compras financiadas;
- pagos aplazados;
- reservas;
- aportaciones planificadas.

Distinguir saldo bancario de liquidez operativamente disponible.

## 41. Stress testing personal

Permitir simular shocks de ingresos, gastos, tipos y mercado para medir resiliencia.

No son predicciones.

Outputs:
- cash runway;
- fondo de emergencia;
- mínimo de liquidez;
- objetivos afectados;
- compromisos en riesgo;
- impacto patrimonial.

## 42. Cost centers personales

Permitir agrupar costes por vivienda, vehículo, familia, mascota, viaje, tecnología, salud u objeto configurable.

## 43. Coverage Engine

Detectar coberturas duplicadas, perdidas, solapadas o deterioradas al cambiar producto.

## 44. Financial Graph lógico

Mantener relaciones explícitas entre cuentas, movimientos, contratos, documentos, assets, proveedores, oportunidades, decisiones y cálculos.

## 45. Seguimiento de decisiones

Guardar expectativa y resultado observado y explicar por qué cambia una recomendación respecto a versiones anteriores.

## 46. Integridad y Repair Center

Detectar jobs interrumpidos, verificar DB/Vault y reconstruir índices/derivados sin destruir fuentes.

## 47. Evaluación continua de modelos

OCR, embeddings, reranking, LLM, prompts y clasificadores deben evaluarse contra suites versionadas antes de promoción.
