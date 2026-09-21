# Lotes de inversión y base fiscal

## Objetivo

Modelar compras/ventas desde el principio para poder calcular correctamente P&L realizado, coste, divisa y fiscalidad modular.

## Tax lot

Campos:
- security_id;
- acquisition_date;
- quantity_original;
- quantity_remaining;
- unit_cost;
- fees;
- currency;
- fx_rate_at_acquisition;
- source;
- account/broker;
- tax_metadata.

## Disposal allocation

Registrar qué lotes se consumen en una venta según la regla fiscal/configuración aplicable.

La regla concreta depende de jurisdicción y ejercicio.

## Corporate actions

Soportar:
- splits;
- reverse splits;
- spin-offs;
- mergers;
- dividends;
- return of capital;
- fees.

No alterar histórico sin trace.

## Divisas

Conservar:
- precio original;
- divisa original;
- FX histórico;
- valor base.

## Tax Center

El motor fiscal:
- es modular por jurisdicción/ejercicio;
- nunca se implementa dentro del LLM;
- muestra supuestos;
- cita fuentes normativas cuando se implemente legislación específica.

## Escenarios de venta

Permitir estimar:
- ganancia/pérdida;
- costes;
- impacto fiscal estimado;
- cambio de allocation;
- liquidez resultante.

No presentar una estimación fiscal como declaración oficial.


## Acciones, ETF, fondos y cripto: seguimiento real

Un activo puede estar:
- **watching**: el usuario quiere seguirlo pero declara no poseerlo;
- **owned**: existe una posición real construida desde operaciones de compra/venta.

Al registrar una posición inicial se guardan cantidad, precio de compra, fecha, comisiones, divisa y FX de compra. No se crea una posición ficticia cuando el usuario selecciona “no lo tengo”.

Para cada activo poseído Financito expone:
- cantidad;
- precio medio de compra;
- coste base;
- último precio real guardado;
- valor actual;
- P&L no realizado y porcentaje;
- P&L realizado por lotes FIFO;
- dividendos registrados;
- resultado total registrado;
- proveedor, timestamp y frescura del precio.

Precios:
- acciones/ETF/fondos con ticker: Alpha Vantage cuando está configurado;
- cripto: CoinGecko mediante el ID del activo;
- los precios se persisten localmente con proveedor/fecha;
- la UI permite actualizar un activo o todos los precios obsoletos;
- si no existe precio real, se muestra n/d y no se sustituye por el coste de compra como “precio actual”.


## Histórico de mercado y seguimiento

Actualizar un activo seguido puede persistir tanto la última cotización como el histórico diario disponible. La vista Mercado permite actualizar todos los activos con histórico y conserva proveedor, fecha y carácter retrasado del dato.

La gráfica conjunta de activos seguidos muestra rendimiento porcentual normalizado desde el primer precio disponible del periodo, no precios absolutos mezclados. Cada serie tiene identidad y color estable dentro de la vista, además de leyenda textual y tabla de procedencia.

Para una posición `owned`, “cantidad” significa unidades reales (acciones, participaciones, BTC, etc.) y “precio de compra” es el coste por unidad en la operación inicial. Compras o ventas posteriores se registran como operaciones para preservar lotes, coste base y P&L; no se corrige la posición sobrescribiendo una cantidad agregada.

Un ticker inexistente no genera una cotización sintética. Los providers gratuitos pueden devolver “no encontrado”; la UI debe presentar un error legible y mantener el último dato válido si existe.
