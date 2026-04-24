# Estado del Proyecto — Core

Estado actual de funcionalidades por área. Actualizar cuando cambie el estado de una funcionalidad.

**Última revisión:** 2026-04-24 | **Versión Core:** 0.23.2

---

## En curso y próximas tareas

> Convención de tipo de tarea:
> - **(Manual)** — requiere guía directa del usuario; la dirección se define sobre la marcha. No delegable a un agente sin esa guía.
> - **(Agente)** — delegable; requiere un plan maestro pero no decisiones continuas del usuario.

### En curso

| Módulo | Tipo | Descripción | Spec |
|--------|------|-------------|------|
| Cierre mensual | Manual | Implementación automática completada; pendiente pulido manual de detalles UX/operativos para cerrar v1. | Se define durante la revisión. |
| Presupuesto | Manual | Revisión integral de experiencia de uso y ajustes funcionales para alinear el comportamiento con la v1 objetivo. | Se define durante la revisión. |

### Siguiente tarea disponible

Seleccionar segun disponibilidad: ejecutar tareas **(Agente)** cuando haya capacidad para delegar; **(Manual)** cuando haya tiempo para guiar.

Nota: `Informe Fiscal Crypto — Phase 0` cerrada el 2026-04-22 (tabla de cobertura API/CSV completada en `core/docs/tasks/fiscal-report/phase-0-api-exploration/notes.md`).
Nota: `Informe Fiscal Crypto — Phase 1` cerrada el 2026-04-23 (app `broker_integrations`, modelos, cliente Pionex API-first + CSV fallback, auto-discovery de bots spot grid y endpoints base). Spec archivada en `core/docs/tasks/fiscal-report/phase-1-pionex/terminados/backend.md`.
Nota: `Informe Fiscal Crypto — Phase 2` cerrada el 2026-04-24 (cliente Binance API-first con firma HMAC, CSV importers de transacciones/convert/recurring, y sync con fallback y captura de gaps). Spec archivada en `core/docs/tasks/fiscal-report/phase-2-binance/terminados/backend.md`.
Nota: `Informe Fiscal Crypto — Phase 3` cerrada el 2026-04-24 (motor FIFO global cross-exchange, conversión EUR para fiscalidad y endpoint `GET /api/v1/broker/fiscal-report/`). Spec archivada en `core/docs/tasks/fiscal-report/phase-3-fiscal-engine/terminados/backend.md`.
Nota: `Informe Fiscal Crypto — Phase 4` cerrada el 2026-04-24 (UI Core para credenciales, sync, import CSV e informe fiscal anual en `/informe-fiscal` y `/informe-fiscal/informe`). Spec archivada en `core/docs/tasks/fiscal-report/phase-4-frontend/terminados/frontend.md`.
Nota: `Informe Fiscal Crypto — Hardening post-Phase 4` aplicado el 2026-04-24 (fallback de `VITE_API_BASE_URL` a `http://localhost:8002`, selector de año también en Integraciones, bloque "Últimos datos importados", conversión EUR robusta con backfill on-demand para fecha de movimiento, y ajuste de bots Pionex para evitar `0` falsos usando `gridProfit` cuando `realizedProfit` llega a `0`).
Nota: Fiscalidad bots actual (2026-04-24): la tabla de bots se mantiene como vista informativa y no se suma al resumen fiscal agregado. El resumen fiscal usa detalle FIFO y posiciones/fuentes con trazabilidad de movimientos.
Nota: espejo SaaS diferido por scope explícito de la fase (MVP Core-only), documentado en `core/docs/frontend/fiscal-report-ux-notes.md`.

| Modulo | Tipo | Descripcion | Spec |
|--------|------|-------------|------|

### Hoja de ruta pre-producción (resumen por área)

Vista consolidada de todo lo pendiente en Core antes de lanzar a producción. Ver `roadmap/product-roadmap.md` para detalle por módulo.

| Área | Prioridad | Estado | Descripción |
|------|-----------|--------|-------------|
| Contabilidad — v1 | Alta | ✅ | Vista de movimientos cerrada v1. Importador MoneyWiz ad-hoc funcional y consolidado; eliminar antes de producción. |
| Presupuesto — v1 | Alta | 🔄 | UX consolidada. Pendiente v1: consistencia de cálculos de barras (tras revisión de movimientos), modales de líneas de presupuesto y ajuste de header al estilo Patrimonio. |
| Patrimonio — modales activos/pasivos | Media | ⚪ | Revisión completa de modales de creación/edición de activos y pasivos. Cierra v1 del módulo. |
| Cierre mensual — modo dual | Alta | 🔄 | Implementación automática completada (backend+frontend); pendiente pulido manual y revisión operativa para cierre v1. |
| Informe Fiscal Crypto | Media | 🔄 | MVP operativo en Core: Pionex + Binance, FIFO global cross-exchange y pantalla de informe. Pendiente para cierre v1 fiscal: trazabilidad completa por operación de bots (sin simplificación agregada) y hardening de cobertura FX/UX final. |
| Coach financiero — navegación | Media | ⚪ | Rediseñar integración con módulos; flujo natural coach ↔ producto |
| Eliminar módulo Introducción de Datos | Alta | ✅ | Ruta `/introduccion-datos` retirada en Core y SaaS. Portable data consolidado en `/account`; activos y pasivos en `/patrimonio`. |
| Sistema de diseño unificado | Alta (crítico) | ⚪ | Colores, tipografías, componentes; coherencia visual en todas las vistas |
| Refactor backend Core | Media | ✅ | Refactor estructural completado (fases 1-5). Queda backlog de contribucion documentado en `roadmap/backend-maintainability-backlog.md`. |
| Refactor frontend Core | Media | ✅ | Roadmap estructural completado; backlog de contribucion documentado en `roadmap/frontend-maintainability-backlog.md`; ver `roadmap/terminados/frontend-refactor-roadmap.md` y `core/docs/architecture/shared-package-candidates.md`. |
| Auth y seguridad | Alta | ⚪ | Revisar autenticación, permisos, ownership de activos/pasivos; test de flujos reales |
| Importación de datos | Media | ✅ | Importador MoneyWiz funcional (ad-hoc). Eliminar antes de producción — no apto para uso general. |
| Auditoría de seguridad | Alta | ⚪ | Vulnerabilidades backend, CVEs en dependencias, validación auth/permisos/inputs |
| Validación con usuarios reales | Alta | ⚪ | Tests con early adopters; feedback UX, comprensión y valor — crítico antes de MVP |

---

## Funcionalidades implementadas y estables

| Área | Estado | Notas |
|------|--------|-------|
| Net Worth (activos, pasivos, liquidez) | 🔄 | Base completa. Snapshots eliminados. Modal de revisión de gastos generados por activos de inversión añadido. Intervalos múltiples de aportación periódica completados (phases 1-2 archivadas). Gráficas (timeline + donut) y KPIs validados. Pendiente v1: revisión completa de modales de creación/edición de activos y pasivos. |
| Budget (ingresos/gastos anuales, check-ins mensuales) | 🔄 | Flujo por categorías completo. Evolución ejecutada (barras), filtro recurrente/puntual, barras YTD y cobertura canónica funcionales. UX general consolidada. Pendiente v1: consistencia de cálculos de barras (tras revisión de movimientos), modales de líneas de presupuesto y ajuste de header al estilo Patrimonio. |
| Cierre mensual | 🔄 | Integrado con budget y accounting; en pulido manual para cierre v1. |
| Data Input (entradas anuales) | ✅ | Módulo/ruta retirados. Responsabilidades reubicadas: ingresos/salidas en Presupuesto, activos/pasivos en Patrimonio y portable data en Cuenta. |
| Guía financiera / Coach v1 | ✅ | Fases 1-4 con scoring implementado |
| Family & Ownership (FamilyMember, OwnershipLink) | ✅ | Completo |
| Accounting Movements (LedgerAccount/Transaction/Entry) | ✅ | Fases 1-5 completas + flujo bidireccional de inversión (`investment` con `inflow`/`outflow`, alias `investment_purchase`, metadatos realizados manuales y agregados de capital aportado). Listado de transacciones migrado a paginación servidor con cursor + filtros server-side + `activity_kind` en API. Importador MoneyWiz adaptado para retiradas de inversión sin ingresos espejo duplicados. Soporte multimoneda en alta/edición rápida de inversión. Vista de movimientos cerrada v1. |
| Market data sync (FX, IPC nacional + CCAA) | ✅ | Fases 1-6 completas, worker `market_data_sync` |
| Portable data (export/import) | ✅ | Con versionado y validación |
| Scoring financiero fases 1-4 | ✅ | Deuda, flujo de caja, fondo emergencia, salud patrimonial |
| Auth Core (JWT, link-token para SaaS) | ✅ | Incluyendo generación de token para linking con SaaS |

## En progreso activo

| Área | Estado | Roadmap canónico |
|------|--------|-----------------|
| Accounting-budget separation | ✅ Fases 1-5 completadas | `roadmap/terminados/accounting-category-budget-separation-roadmap.md` |
| Refactor frontend | ✅ Completado | Fases 0-6 cerradas; specs archivadas en `core/docs/tasks/frontend-refactor/*/terminados/`; `core/docs/architecture/shared-package-candidates.md` creado. |

## Deliberadamente aparcado (funcionalidad primero)

_(ninguna tarea aparcada en este momento)_

---

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado y funcionando |
| 🔄 | En progreso |
| ⚪ | No iniciado (en scope futuro) |
| ⛔ | Fuera de alcance explícito (decisión tomada) |
| ⏸ | Aparcado conscientemente |
