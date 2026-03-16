# Roadmap: market data sync y UX de datos auxiliares (Core) - plan ejecutable

## Objetivo
Incorporar en Core una capa estable de ingesta automatica de datos externos para `FX` e `IPC`, con cobertura historica automatica, refresco diario, seleccion de region IPC en patrimonio y una UX orientada a consulta, no a edicion manual.

## Estado de este documento
1. Este documento define el plan operativo completo de la iniciativa.
2. La implementacion debe vivir en `core/`.
3. El trabajo debe ejecutarse en PRs pequenas, reversibles y validadas dentro de Docker.
4. El resultado debe dejar preparada la arquitectura para futuros datasets como cotizaciones de acciones.

## Estado real (2026-03-16)
1. La iniciativa figura implementada en codigo y documentacion operativa.
2. Fase 1 implementada y cerrada:
   - existe el comando canonico `python manage.py sync_market_data --datasets fx inflation --mode reconcile|refresh`
   - existe `MarketDataSyncState` como tabla de cobertura/estado
   - `sync_fx_rates` queda como wrapper de compatibilidad
   - Docker ya usa `market_data_sync` como worker dedicado
3. Fase 2 implementada y cerrada:
   - el worker calcula cobertura requerida y reconcilia huecos historicos
   - la cobertura ya no depende de fetch inline en flujos de usuario
   - `core/backend/core/tests.py` cubre actualizacion de sync state y reconciliacion base
4. Fase 3 implementada y cerrada:
   - `InflationIndex` soporta `ES + CCAA`
   - el status endpoint devuelve `supported_inflation_regions`
   - existen datos y estado por region
5. Fase 4 implementada y cerrada:
   - `accounts.UserSettings` persiste `inflation_region`
   - `SettingsPopover` expone selector de region IPC
   - `net_worth` usa la region efectiva en `summary` y `timeline`
6. Fase 5 implementada y cerrada:
   - `AuxDataView` ya no es CRUD manual
   - `/data` actua como vista observacional de FX/IPC y estado de sync
   - el frontend consume `GET /api/core/market-data/status/`
7. Fase 6 implementada y cerrada:
   - la arquitectura ya refleja `market_data_sync` y `sync_market_data`
   - existen docs operativas en `core/docs/operations/market-data-sync.md`
   - `core/docs/operations/dev-setup.md` ya incorpora el worker en el arranque estandar

## Decisiones ya fijadas
1. La ejecucion vive en un worker dedicado dentro de Core.
2. La persistencia vive en PostgreSQL de Core.
3. El alcance inicial incluye:
   - `FX` diario
   - `IPC` nacional y por comunidad autonoma
4. La region IPC sera una preferencia persistente por usuario.
5. La vista de datos auxiliares deja de ser un CRUD manual.
6. El frontend no debe permitir editar ni eliminar FX/IPC como flujo normal.

## Estado real de partida
1. Ya existe `FxRate` en `core/backend/core/models.py`.
2. Ya existe `InflationIndex` en `core/backend/core/models.py`, hoy limitado a `ES`.
3. Ya existe `fx_sync` en `core/docker-compose.yml`.
4. Ya existe `sync_fx_rates` y logica de provider en `core/backend/core/market_data.py`.
5. `net_worth` ya consume `FxRate` e `InflationIndex`.
6. El modo IPC ya existe en patrimonio, pero hoy fuerza `ES`.
7. Existe una vista `/data` con CRUD manual de FX/IPC en frontend.

## Principios de trabajo
1. Core es duenyo de estos datos auxiliares como comportamiento de producto.
2. El frontend consume datos persistidos; nunca llama a proveedores externos.
3. La logica de sync no debe vivir en views ni en el request path.
4. No duplicar logica entre datasets ni entre Core y SaaS.
5. Cambiar lo minimo necesario por fase.
6. Mantener una arquitectura extensible a nuevos providers y datasets.

## Alcance
1. `core/backend/core`
2. `core/backend/net_worth`
3. `core/frontend`
4. `core/docker-compose.yml`
5. `core/docs/architecture/architecture.md`
6. `core/docs/operations/dev-setup.md`
7. `core/docs/operations/fx-sync.md` o su equivalente ampliado

## Fuera de alcance
1. Integracion SaaS especifica.
2. Billing o packaging.
3. Implementacion efectiva de cotizaciones de acciones en esta iniciativa.
4. Benchmarking financiero o macrodatos fuera de `FX` e `IPC`.
5. Edicion manual para usuario final de tablas sincronizadas por sistema.

## Arquitectura objetivo
### Worker de market data
1. Sustituir el concepto actual de `fx_sync` por un worker de `market data`.
2. El worker ejecuta una pasada al arrancar y luego un bucle periodico.
3. Debe soportar al menos dos modos:
   - `reconcile`: recalcula cobertura requerida y rellena huecos historicos
   - `refresh`: trae solo el tramo incremental
4. Los errores de proveedor no deben bloquear la operativa de usuario.

### Persistencia
1. Mantener `FxRate` como tabla canonica de tipos de cambio.
2. Mantener `InflationIndex` como tabla canonica de IPC mensual.
3. Extender ambas tablas con metadata de procedencia/sync cuando sea necesario:
   - `source`
   - `source_key`
   - `managed_by_system`
   - `last_synced_at`
4. Introducir una tabla de control de cobertura y sync por dataset/scope.
5. Esa tabla debe permitir conocer:
   - dataset
   - scope
   - `required_start_date`
   - `covered_until`
   - `last_attempt_at`
   - `last_success_at`
   - `last_error`

### Providers
1. Definir una interfaz comun para providers de market data.
2. Implementar providers iniciales:
   - `FX fiat`
   - `FX crypto` si sigue aplicando
   - `IPC INE`
3. Dejar preparado el registro de providers para futuros datasets como `security_price`.

### Consumo del dominio
1. `net_worth` y el resto del dominio consumen solo datos persistidos en Core.
2. El backend de patrimonio debe usar la region IPC elegida por el usuario.
3. Si no hay cobertura suficiente para una region, el backend debe responder de forma controlada.
4. No debe haber comportamiento silencioso inconsistente ante datos faltantes.

## Fase 1 - Base tecnica del worker
### Entregables
1. Nuevo comando canonico `sync_market_data`.
2. Abstraccion comun de provider.
3. Tabla de cobertura/sync state.
4. Adaptacion de `fx_sync` a worker de market data.
5. Wrapper de compatibilidad para `sync_fx_rates`.

### Tareas
1. Diseñar `sync_market_data --datasets ... --mode ...`.
2. Crear interfaz base de provider.
3. Crear modelo de cobertura/sync state.
4. Renombrar o evolucionar `fx_sync` a `market_data_sync` en Docker.
5. Mantener compatibilidad temporal con el flujo actual de FX.

### Criterios de salida
1. El worker puede sincronizar FX sin romper el comportamiento actual.
2. La cobertura requerida y real queda trazable en BD.
3. La ejecucion en Docker sigue operativa.

## Fase 2 - Reconciliacion historica automatica
### Entregables
1. Calculo de fecha minima requerida para FX.
2. Calculo de fecha minima requerida para IPC.
3. Relleno automatico de huecos historicos.
4. Desacoplar el fetch externo del create/update de activos y pasivos.

### Tareas
1. Revisar todas las entidades que pueden empujar la fecha minima relevante:
   - `Asset.start_date`
   - `Liability.start_date`
   - valoraciones
   - eventos relevantes si aplican
2. Sustituir la logica actual basada solo en posiciones activas por una basada en fecha minima relevante en BD.
3. Hacer que create/update actualicen necesidad de cobertura, no sync inline.
4. Garantizar idempotencia en la reconciliacion.

### Criterios de salida
1. Un alta retroactiva amplía la cobertura en la siguiente pasada del worker.
2. No se repiten descargas si la cobertura ya existe.
3. Los fallos de proveedor no bloquean la UX de patrimonio.

## Fase 3 - IPC nacional y por CCAA
### Entregables
1. Soporte backend para `ES + CCAA`.
2. Provider INE operativo.
3. Validacion y serializacion de regiones disponibles.
4. Cobertura mensual por region.

### Tareas
1. Extender `InflationIndex.region`.
2. Mapear la nomenclatura de la fuente externa al codigo interno:
   - `ES`
   - `ES-MD`
   - `ES-AN`
   - etc.
3. Implementar carga inicial e incremental por region.
4. Exponer regiones disponibles y cobertura efectiva.

### Criterios de salida
1. Core almacena IPC nacional y autonomico.
2. El backend puede resolver `base_period` por region.
3. Los tests cubren fallback, huecos y meses sin dato nuevo.

## Fase 4 - Integracion con patrimonio y preferencia de region
### Entregables
1. Preferencia persistente de region IPC por usuario.
2. Selector de region en `SettingsPopover`.
3. `summary` y `timeline` usando region efectiva.
4. Payload con `inflation_region` e `inflation_base_period`.

### Tareas
1. Añadir persistencia backend para la preferencia.
2. Leer la preferencia desde `net_worth`.
3. Mantener `real` deshabilitado si no hay cobertura o si la moneda base no es `EUR`.
4. Actualizar ayudas y labels del modo IPC.
5. Definir `ES` como default para usuarios sin preferencia.

### Criterios de salida
1. El usuario puede elegir region desde patrimonio.
2. La eleccion persiste entre sesiones.
3. Summary y timeline son coherentes con la region efectiva.

## Fase 5 - Sustitucion del CRUD manual por vista observacional
### Entregables
1. Eliminacion del flujo de alta/borrado manual de FX/IPC.
2. Nueva vista `/data` orientada a observabilidad.
3. Visualizacion basica de:
   - cobertura temporal
   - ultima actualizacion
   - estado de sync
   - grafica simple de FX
   - grafica simple de IPC por region
4. Endpoints de lectura adaptados a esta UX.

### Tareas
1. Retirar formularios y botones de eliminar de `AuxDataView`.
2. Reconstruir `/data` como vista de estado del sistema.
3. Mostrar errores de sync como estado operativo, no como accion manual.
4. Reconducir o retirar `SettingsFxView` y `SettingsIpcView`.
5. Mantener los endpoints mutables fuera de la UX y restringidos si siguen existiendo.

### Criterios de salida
1. No existe flujo normal de editar/eliminar FX/IPC desde frontend.
2. La nueva pantalla aporta trazabilidad operativa.
3. La UX resulta coherente con datos gestionados por sistema.

## Fase 6 - Documentacion y extensibilidad
### Entregables
1. Documentacion arquitectonica actualizada.
2. Documentacion operativa del nuevo worker.
3. Contrato base para futuros datasets.
4. Checklist para añadir providers.

### Tareas
1. Actualizar `core/docs/architecture/architecture.md`.
2. Sustituir o ampliar `core/docs/operations/fx-sync.md` hacia `market-data-sync`.
3. Actualizar `core/docs/operations/dev-setup.md`.
4. Documentar como anadir un nuevo dataset/provider sin tocar el dominio consumidor.
5. Dejar expresamente trazada la extension futura a `security_price`.

### Criterios de salida
1. Otra persona puede continuar sin contexto tribal.
2. La operacion local queda clara.
3. La extension a nuevos datasets no exige rediseño.

## Cambios de interfaz esperados
### Backend
1. Nuevo comando:
   - `python manage.py sync_market_data --datasets fx inflation --mode reconcile|refresh`
2. `sync_fx_rates` queda como wrapper temporal.
3. Nuevo soporte de preferencia persistente de region IPC por usuario.
4. Nuevo endpoint o ampliacion de payload para:
   - regiones disponibles
   - cobertura efectiva
   - estado de sync

### Frontend
1. `SettingsPopover` gana selector de region IPC.
2. `/data` deja de ser CRUD y pasa a ser dashboard observacional.
3. Las vistas de datos auxiliares dejan de mostrar acciones de alta/edicion/borrado.

### Compatibilidad
1. Las lecturas existentes de FX/IPC pueden mantenerse mientras alimenten la nueva UX.
2. Los endpoints mutables pueden mantenerse solo como compatibilidad tecnica temporal.

## Casos de prueba minimos
### Backend
1. Sync FX incremental.
2. Sync FX historico por gap retroactivo.
3. Sync IPC `ES`.
4. Sync IPC por CCAA.
5. Idempotencia del worker.
6. Error de proveedor no bloquea create/update de patrimonio.
7. Cambio de region de usuario modifica `summary`.
8. `timeline` usa la misma region efectiva.
9. La ausencia de cobertura IPC para una region se maneja segun contrato.

### Frontend
1. `SettingsPopover` muestra selector de region.
2. La region se guarda y se recupera.
3. El modo IPC refleja region y periodo base correctos.
4. `/data` ya no muestra formularios ni botones de borrado.
5. `/data` muestra estados de carga, vacio, error y datos.
6. La vista observacional renderiza tablas/graficas de forma estable.

## Secuencia de ejecucion recomendada
1. Fase 1: worker + comando + coverage state.
2. Fase 2: reconciliacion historica automatica.
3. Fase 3: IPC `ES + CCAA`.
4. Fase 4: preferencia persistente de region + integracion en patrimonio.
5. Fase 5: reemplazo del CRUD manual por vista observacional.
6. Fase 6: documentacion y extensibilidad.

## Validacion obligatoria en Docker
### Diagnostico
1. `cd core`
2. `docker compose ps`
3. `docker compose logs --tail 100 backend`
4. `docker compose logs --tail 100 market_data_sync`

### Calidad backend
1. `docker compose exec backend ruff check .`
2. `docker compose exec backend ruff format --check .`
3. `docker compose exec backend mypy .`

### Calidad frontend
1. `docker compose exec frontend npm run lint`
2. `docker compose exec frontend npm run format:check`
3. `docker compose exec frontend npm run typecheck`

### Tests minimos
1. `docker compose exec backend python manage.py test core`
2. `docker compose exec backend python manage.py test net_worth`
3. `docker compose exec frontend npm run test:unit`

## Checklist de PR
1. [ ] Hay test de regresion para el comportamiento afectado.
2. [ ] No se rompe contrato sin documentarlo.
3. [ ] La logica de negocio queda en backend, no en la UI.
4. [ ] El diff evita refactors fuera de alcance.
5. [ ] Se valida en Docker.
6. [ ] Se actualiza documentacion canonica si cambia arquitectura o flujo.
7. [ ] Se usa Conventional Commit.

## Riesgos a vigilar
1. Acoplar el worker al request path por atajos.
2. Mantener a la vez UX manual y automatica, creando doble fuente de verdad.
3. Hacer la seleccion de region solo en frontend y no persistirla.
4. Seguir basando cobertura en posiciones activas en vez de fecha minima real.
5. Añadir nuevos providers sin interfaz comun.
6. Permitir overrides manuales sin politica clara.

## Criterio de exito
1. Core sincroniza FX e IPC sin intervencion manual del usuario final.
2. La cobertura historica se amplia automaticamente ante datos retroactivos.
3. Patrimonio soporta IPC por region seleccionable y persistente.
4. La pantalla de datos auxiliares pasa a ser observabilidad, no CRUD.
5. La arquitectura queda lista para futuros datasets como cotizaciones de acciones.
