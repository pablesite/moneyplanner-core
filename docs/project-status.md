# Project Status — Core

> **English summary** (last updated 2026-05-20 · Core v0.23.5)
>
> All planned v1 modules are implemented and stable: Net Worth, Budget & Monthly Close,
> Accounting Movements, Market Data Sync, DB Backup/Restore, Financial Coach v1, Auth & Security.
> Residual legacy cleanup complete. Active work: Unified Design System (UI consistency pass).
> Paused: Crypto Tax Report (IRPF Spain). Up next: validation with real users.
> Full details in Spanish below.

---

# Estado del Proyecto — Core

Estado actual de funcionalidades por área. Actualizar cuando cambie el estado de una funcionalidad.

**Última revisión:** 2026-05-20 | **Versión Core:** 0.23.5

---

## En curso y próximas tareas

> Convención de tipo de tarea:
> - **(Manual)** — requiere guía directa del usuario; la dirección se define sobre la marcha. No delegable a un agente sin esa guía.
> - **(Agente)** — delegable; requiere un plan maestro pero no decisiones continuas del usuario.

### En curso

| Módulo | Tipo | Descripción | Spec |
|--------|------|-------------|------|
| _(ninguno)_ | — | — | — |

### Siguiente tarea disponible

Seleccionar segun disponibilidad: ejecutar tareas **(Agente)** cuando haya capacidad para delegar; **(Manual)** cuando haya tiempo para guiar.

| Modulo | Tipo | Descripcion | Spec |
|--------|------|-------------|------|
| _(ninguno)_ | — | — | — |

### Hoja de ruta pre-producción (resumen por área)

Vista consolidada de todo lo pendiente en Core antes de lanzar a producción. Ver `roadmap/product-roadmap.md` para detalle por módulo.

| Área | Prioridad | Estado | Descripción |
|------|-----------|--------|-------------|
| Contabilidad — v1 | Alta | ✅ | Vista de movimientos cerrada v1. Trazabilidad de movimientos importados conservada mediante metadatos contables; importador MoneyWiz ad-hoc retirado. |
| Presupuesto — v1 | Alta | ✅ | Cierre funcional aplicado y revisión manual completada: summaries mensuales canónicos para ejecución/cobertura, precedencia ledger sobre check-ins manuales, errores backend dentro de modales de líneas y header alineado con Patrimonio. |
| Patrimonio — modales activos/pasivos | Media | ✅ | Revisión completa de modales de creación/edición de activos y pasivos completada. V1 del módulo cerrada a nivel funcional. |
| Cierre mensual — modo dual | Alta | ✅ | Implementación automática completada (backend+frontend) y revisión manual operativa completada. |
| Informe Fiscal Crypto | Media | ⏸ | Módulo completo IRPF español: Pionex + Binance, FIFO global cross-exchange, casillas 029/332/337. Aparcado — revisar estado antes de retomar. |
| Coach financiero — navegación | Media | ⚪ | Rediseñar integración con módulos; flujo natural coach ↔ producto |
| Eliminar módulo Introducción de Datos | Alta | ✅ | Ruta `/introduccion-datos` retirada en Core y SaaS. Portable data consolidado en `/account`; activos y pasivos en `/patrimonio`. |
| Sistema de diseño unificado | Alta (crítico) | 🔄 | 16 pasos de migración completados (ver `docs/frontend/design-system.md`): HomeView, AccountView, PeopleView, GuidePhaseDetailView, Net Worth, Budget, Accounting, BaseModal, People, Guide/Coach, auth, selects, tablas, compat classes. Pendiente: continuar pulido vista a vista. |
| Limpieza legacy residual | Media | ✅ | Completado 2026-05-20. Retirados: Introducción de Datos, alias `investment_purchase`, campos escalares de aportaciones (migración 0042), import externo de `net_worth.services`, `compat.*` en capabilities. Fallback Budget/check-ins: diseño intencional, no deuda técnica. Ver `roadmap/product-roadmap.md`. |
| Refactor backend Core | Media | ✅ | Refactor estructural completado (fases 1-5). Queda backlog de contribucion documentado en `roadmap/backend-maintainability-backlog.md`. |
| Refactor frontend Core | Media | ✅ | Roadmap estructural completado; backlog de contribucion documentado en `roadmap/frontend-maintainability-backlog.md`; ver `roadmap/terminados/frontend-refactor-roadmap.md` y `core/docs/architecture/shared-package-candidates.md`. |
| Auth y seguridad | Alta | ✅ | Logout con blacklist, aislamiento cross-user (31 tests), registro de usuario desde UI (`/registro`, JWT en signup, rate throttle). Pendiente: auditoría CVEs y flujos reales con usuarios. |
| Backup/restore de base de datos | Media | ✅ | Endpoints admin-only `GET /api/core/db-backup/` y `POST /api/core/db-restore/` basados en pg_dump/pg_restore. AccountView migrada a este flujo; JSON portable retirado. |
| Auditoría de seguridad | Alta | ✅ | CVEs frontend saneados (12→0 via npm audit fix: axios, vite, rollup, postcss, lodash…). Backend: pip CVEs resueltos con upgrade en Dockerfile; app deps limpios. Auth/permisos cubiertos en tarea anterior. |
| Validación con usuarios reales | Alta | ⚪ | Tests con early adopters; feedback UX, comprensión y valor — crítico antes de MVP |

---

## Funcionalidades implementadas y estables

| Área | Estado | Notas |
|------|--------|-------|
| Net Worth (activos, pasivos, liquidez) | ✅ | Base completa. Snapshots eliminados. Modal de revisión de gastos generados por activos de inversión añadido. Intervalos múltiples de aportación periódica completados (phases 1-2 archivadas). Gráficas (timeline + donut) y KPIs validados. Modales de creación/edición de activos y pasivos revisados; v1 del módulo cerrada a nivel funcional. |
| Budget (ingresos/gastos anuales, check-ins mensuales) | ✅ | Flujo por categorías completo. Evolución ejecutada (barras), filtro recurrente/puntual, barras YTD y cobertura canónica funcionales. Los summaries mensuales son contrato canónico para ejecución/cobertura; modales de líneas muestran errores backend sin perder formulario; header alineado con Patrimonio. Revisión manual completada el 2026-05-14. |
| Cierre mensual | ✅ | Integrado con budget y accounting. Modo dual automático, lifecycle DRAFT/FINALIZED/LOCKED y revisión manual completada el 2026-05-14. |
| Data Input (entradas anuales) | ✅ | Módulo/ruta retirados. Responsabilidades reubicadas: ingresos/salidas en Presupuesto, activos/pasivos en Patrimonio y portable data en Cuenta. |
| Guía financiera / Coach v1 | ✅ | Fases 1-4 con scoring implementado |
| Family & Ownership (FamilyMember, OwnershipLink) | ✅ | Completo |
| Accounting Movements (LedgerAccount/Transaction/Entry) | ✅ | Fases 1-5 completas + flujo bidireccional de inversión (`investment` con `inflow`/`outflow`, metadatos realizados manuales y agregados de capital aportado). Listado de transacciones migrado a paginación servidor con cursor + filtros server-side + `activity_kind` en API. Trazabilidad de movimientos importados mantenida con `origin`, `import_source` e `import_fingerprint`; importador MoneyWiz ad-hoc retirado. Soporte multimoneda en alta/edición rápida de inversión. Vista de movimientos cerrada v1. |
| Market data sync (FX, IPC nacional + CCAA) | ✅ | Fases 1-6 completas, worker `market_data_sync`. Tablas con paginación servidor (page_size=50) e infinite scroll en frontend. |
| DB Backup/Restore (pg_dump) | ✅ | Endpoints admin-only de backup y restore basados en pg_dump/pg_restore. JSON portable data retirado de la UI; sustituido por este flujo. |
| Scoring financiero fases 1-4 | ✅ | Deuda, flujo de caja, fondo emergencia, salud patrimonial |
| Auth Core (JWT, link-token para SaaS) | ✅ | Registro de usuario desde UI (`/registro`). Logout con blacklist. Link-token para integración SaaS. |

## En progreso activo

| Área | Estado | Roadmap canónico |
|------|--------|-----------------|
| Accounting-budget separation | ✅ Fases 1-5 completadas | `roadmap/terminados/accounting-category-budget-separation-roadmap.md` |
| Refactor frontend | ✅ Completado | Fases 0-6 cerradas; specs archivadas en `core/docs/tasks/frontend-refactor/*/terminados/`; `core/docs/architecture/shared-package-candidates.md` creado. |

## Deliberadamente aparcado (funcionalidad futura)

| Módulo | Descripción | Specs |
|--------|-------------|-------|
| Informe Fiscal Crypto | Módulo completo IRPF español: integración Pionex + Binance, motor FIFO global cross-exchange, casillas 029/332/337. Aparcado antes de publicación pública del repo; revisar estado de la exploración antes de retomar. | `core/docs/tasks/fiscal-report/` |

---

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado y funcionando |
| 🔄 | En progreso |
| ⚪ | No iniciado (en scope futuro) |
| ⛔ | Fuera de alcance explícito (decisión tomada) |
| ⏸ | Aparcado conscientemente |
