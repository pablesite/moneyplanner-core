# Estado del Proyecto — Core

Estado actual de funcionalidades por área. Actualizar cuando cambie el estado de una funcionalidad.

**Última revisión:** 2026-03-24 | **Versión Core:** 0.23.2

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
| Movimientos | Manual | Remate manual de la vista para dejarla en estado v1 final. Seguimiento operativo por cuentas en `core/docs/operations/movements-user1-review-tracker.md` (usuario 1: 110 cuentas totales, 5 ya revisadas). | Se define durante la revisión. |
| Importación MoneyWiz | Manual | Afinar reglas y casos borde de importación para consolidar la v1 de movimientos. | Se define durante la revisión. |

### Siguiente tarea disponible

Seleccionar segun disponibilidad: ejecutar tareas **(Agente)** cuando haya capacidad para delegar; **(Manual)** cuando haya tiempo para guiar.

| Modulo | Tipo | Descripcion | Spec |
|--------|------|-------------|------|
| _(sin tareas Agente abiertas)_ | - | La fase 3 de Presupuesto (gasto fuera de presupuesto y cobertura real) se completo y quedo archivada en `terminados/`. | `docs/tasks/budget/phase-3-unbudgeted-execution-visibility/terminados/backend.md` + `docs/tasks/budget/phase-3-unbudgeted-execution-visibility/terminados/frontend.md` |

### Hoja de ruta pre-producción (resumen por área)

Vista consolidada de todo lo pendiente en Core antes de lanzar a producción. Ver `roadmap/product-roadmap.md` para detalle por módulo.

| Área | Prioridad | Estado | Descripción |
|------|-----------|--------|-------------|
| Contabilidad — UX y bugs | Alta | 🔄 | UX rápida de registro, transferencias entre cuentas con doble impacto automático, bug edición de movimientos |
| Presupuesto — migración y UX | Alta | 🔄 | Fase 1 y fase 2 completadas (CRUD anual + integración por categorías en un flujo único). Pendiente consolidación UX v1 final. |
| Patrimonio — visualizaciones | Media | ⚪ | Gráficas de evolución temporal y distribución (donut), validar consistencia de KPIs, evaluar snapshots legacy |
| Cierre mensual — modo dual | Alta | 🔄 | Implementación automática completada (backend+frontend); pendiente pulido manual y revisión operativa para cierre v1. |
| Coach financiero — navegación | Media | ⚪ | Rediseñar integración con módulos; flujo natural coach ↔ producto |
| Eliminar módulo Introducción de Datos | Alta | ✅ | Ruta `/introduccion-datos` retirada en Core y SaaS. Portable data consolidado en `/account`; activos y pasivos en `/patrimonio`. |
| Sistema de diseño unificado | Alta (crítico) | ⚪ | Colores, tipografías, componentes; coherencia visual en todas las vistas |
| Refactor backend Core | Media | ✅ | Refactor estructural completado (fases 1-5). Queda backlog de contribucion documentado en `roadmap/backend-maintainability-backlog.md`. |
| Refactor frontend Core | Media | ✅ | Roadmap estructural completado; backlog de contribucion documentado en `roadmap/frontend-maintainability-backlog.md`; ver `roadmap/terminados/frontend-refactor-roadmap.md` y `core/docs/architecture/shared-package-candidates.md`. |
| Auth y seguridad | Alta | ⚪ | Revisar autenticación, permisos, ownership de activos/pasivos; test de flujos reales |
| Importación de datos | Media | 🔄 | MoneyWiz v1 corregido y validado con CSV real; retiradas/desinversiones de cartera se colapsan en `investment outflow` sin duplicar ingresos espejo. Pendiente afinar casos borde restantes y soporte Excel. |
| Auditoría de seguridad | Alta | ⚪ | Vulnerabilidades backend, CVEs en dependencias, validación auth/permisos/inputs |
| Validación con usuarios reales | Alta | ⚪ | Tests con early adopters; feedback UX, comprensión y valor — crítico antes de MVP |

---

## Funcionalidades implementadas y estables

| Área | Estado | Notas |
|------|--------|-------|
| Net Worth (activos, pasivos, liquidez, snapshots) | ✅ | Completo |
| Budget (ingresos/gastos anuales, check-ins mensuales) | 🔄 | Ingresos/gastos anuales ya integrados en el flujo por categorías; en consolidación manual de detalles v1. Evolución ejecutada (barras) funcional en ingresos y gastos, reactiva al filtro recurrente/puntual. Barras YTD de categoría/subcategoría funcionales para ingresos y gastos con selector de mes independiente (defecto: mes actual). Resumen de gasto ampliado con cobertura canónica (`executed_budgeted` vs `executed_unbudgeted`) y visibilidad de subcategorías detectadas sin línea anual. |
| Cierre mensual | 🔄 | Integrado con budget y accounting; en pulido manual para cierre v1. |
| Data Input (entradas anuales) | ✅ | Módulo/ruta retirados. Responsabilidades reubicadas: ingresos/salidas en Presupuesto, activos/pasivos en Patrimonio y portable data en Cuenta. |
| Guía financiera / Coach v1 | ✅ | Fases 1-4 con scoring implementado |
| Family & Ownership (FamilyMember, OwnershipLink) | ✅ | Completo |
| Accounting Movements (LedgerAccount/Transaction/Entry) | 🔄 | Fases 1-5 completas + flujo bidireccional de inversión (`investment` con `inflow`/`outflow`, alias `investment_purchase`, metadatos realizados manuales y agregados de capital aportado). Listado de transacciones migrado a paginación servidor con cursor + filtros server-side + `activity_kind` en API. Importador MoneyWiz adaptado para retiradas de inversión sin ingresos espejo duplicados. Añadida limpieza masiva provisional de movimientos `origin=import` desde la vista de Movimientos (Core-only). Pendiente remate manual de vista para cierre v1. |
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

