# Runtime local y launcher

## Objetivo

Que usar Financito no requiera abrir Terminal ni administrar procesos manualmente.

## Launcher local

Responsabilidades:
1. asegurar instancia única;
2. cargar configuración segura;
3. desbloquear secretos;
4. verificar DB/migraciones;
5. iniciar FastAPI;
6. iniciar workers;
7. comprobar modelo local;
8. recuperar jobs interrumpidos;
9. abrir navegador/WebView en localhost;
10. apagar procesos ordenadamente.

## Supervisor

Monitoriza:
- API;
- workers;
- modelo local;
- scheduler.

Puede reiniciar procesos no críticos de forma controlada.

Nunca expone servicio a LAN.

## Startup

No bloquear la UI esperando:
- sincronizaciones;
- OCR;
- embeddings;
- noticias.

Mostrar shell y Health state; jobs continúan en background local.

## Shutdown

- finalizar requests;
- checkpoint jobs;
- cerrar DB;
- limpiar temporales;
- invalidar sesión.

## Packaging futuro

El launcher puede empaquetarse como app macOS ligera manteniendo la UI web.

No cambia el principio local-only.
