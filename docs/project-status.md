# Estado del Proyecto — Core

Estado actual de funcionalidades por área. Actualizar cuando cambie el estado de una funcionalidad.

**Última revisión:** 2026-03-27 | **Versión Core:** 0.23.2

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
| Movimientos | Manual | Remate manual de la vista para dejarla en estado v1 final. Seguimiento operativo por cuentas en `core/docs/operations/movements-user1-review-tracker.md` (usuario 1: 106 cuentas totales, 42 ya revisadas). Cierre de categorizacion final completado para las cuentas revisadas; bloque de préstamos personales cerrado (incluida consolidación de `iPhone 15 Ana` en `Préstamo - Iphone 15 Pro` y eliminación de la cuenta obsoleta) y cierre completo de `Hipoteca Palmito` (concepto, clasificación principal/interés y ownership 50/50). Revisados también `MyInvestor Depósito 1 mes`, `MyInvestor 3 meses`, `Spot Binance` (incluye visibilidad de saldo tras movimiento en el timeline de cuentas y limpieza de cuenta obsoleta `Earn Binance`), `Kutxa (Hucha)`, `Monedero Ana` y `Monedero compartido` (revisión a fondo). | Se define durante la revisión. |
| Importación MoneyWiz | Manual | Afinar reglas y casos borde de importación para consolidar la v1 de movimientos. | Se define durante la revisión. |

### Siguiente tarea disponible

Seleccionar segun disponibilidad: ejecutar tareas **(Agente)** cuando haya capacidad para delegar; **(Manual)** cuando haya tiempo para guiar.

| Modulo | Tipo | Descripcion | Spec |
|--------|------|-------------|------|
| _(sin tareas Agente abiertas)_ | - | Net Worth Phase 1 (backend) + Phase 2 (frontend) completadas y archivadas en `terminados/`. | `core/docs/tasks/net-worth/phase-1-contribution-intervals-backend/terminados/backend.md` + `core/docs/tasks/net-worth/phase-2-contribution-intervals-frontend/terminados/frontend.md` |

### Hoja de ruta pre-producción (resumen por área)

Vista consolidada de todo lo pendiente en Core antes de lanzar a producción. Ver `roadmap/product-roadmap.md` para detalle por módulo.

| Área | Prioridad | Estado | Descripción |
|------|-----------|--------|-------------|
| Contabilidad — v1 | Alta | 🔄 | Pendiente v1: revisión del tracker de cuentas (coherencia movimientos→patrimonio), header al estilo Patrimonio y revisión de estilo visual del cuerpo. Importador MoneyWiz ad-hoc funcional; eliminar antes de producción. |
| Presupuesto — v1 | Alta | 🔄 | UX consolidada. Pendiente v1: consistencia de cálculos de barras (tras revisión de movimientos), modales de líneas de presupuesto y ajuste de header al estilo Patrimonio. |
| Patrimonio — modales activos/pasivos | Media | ⚪ | Revisión completa de modales de creación/edición de activos y pasivos. Cierra v1 del módulo. |
| Cierre mensual — modo dual | Alta | 🔄 | Implementación automática completada (backend+frontend); pendiente pulido manual y revisión operativa para cierre v1. |
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
| Accounting Movements (LedgerAccount/Transaction/Entry) | 🔄 | Fases 1-5 completas + flujo bidireccional de inversión (`investment` con `inflow`/`outflow`, alias `investment_purchase`, metadatos realizados manuales y agregados de capital aportado). Listado de transacciones migrado a paginación servidor con cursor + filtros server-side + `activity_kind` en API. Importador MoneyWiz adaptado para retiradas de inversión sin ingresos espejo duplicados. Añadida limpieza masiva provisional de movimientos `origin=import` desde la vista de Movimientos (Core-only). Soporte multimoneda reforzado en alta/edición rápida de inversión y migración manual BTC/Spot Binance en ejecución. Pendiente remate manual de vista para cierre v1. |
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
