# Estado del Proyecto — Core

Estado actual de funcionalidades por área. Actualizar cuando cambie el estado de una funcionalidad.

**Última revisión:** 2026-03-17 | **Versión Core:** 0.23.0

---

## En curso y próximas tareas

> Convención de tipo de tarea:
> - **(Manual)** — requiere guía directa del usuario; la dirección se define sobre la marcha. No delegable a un agente sin esa guía.
> - **(Agente)** — delegable; requiere un plan maestro pero no decisiones continuas del usuario.

### En curso

| Módulo | Tipo | Descripción |
|--------|------|-------------|
| — | — | Sin tareas manuales en curso. |

### Siguiente tarea disponible

Seleccionar según disponibilidad: ejecutar tareas **(Agente)** cuando haya capacidad para delegar; **(Manual)** cuando haya tiempo para guiar.

| Módulo | Tipo | Descripción | Spec |
|--------|------|-------------|------|
| Presupuesto | Manual | Revisión integral de experiencia de uso del módulo. | Se define durante la revisión. |

### Hoja de ruta pre-producción (resumen por área)

Vista consolidada de todo lo pendiente en Core antes de lanzar a producción. Ver `roadmap/product-roadmap.md` para detalle por módulo.

| Área | Prioridad | Estado | Descripción |
|------|-----------|--------|-------------|
| Contabilidad — UX y bugs | Alta | 🔄 | UX rápida de registro, transferencias entre cuentas con doble impacto automático, bug edición de movimientos |
| Presupuesto — migración y UX | Alta | ⚪ | Migrar ingresos/gastos previstos desde Introducción de Datos; conectar con valores reales del cierre; mejorar visualización |
| Patrimonio — visualizaciones | Media | ⚪ | Gráficas de evolución temporal y distribución (donut), validar consistencia de KPIs, evaluar snapshots legacy |
| Cierre mensual — modo dual | Alta | ⚪ | Integrar modo manual + automático (contabilidad); diseñar UX de elección de modo; simplificar vista de resultados |
| Coach financiero — navegación | Media | ⚪ | Rediseñar integración con módulos; flujo natural coach ↔ producto |
| Eliminar módulo Introducción de Datos | Alta | ⚪ | Migrar TODO a Presupuesto y Patrimonio; eliminar módulo completo |
| Sistema de diseño unificado | Alta (crítico) | ⚪ | Colores, tipografías, componentes; coherencia visual en todas las vistas |
| Refactor backend Core | Media | ⏸ | Limpieza de lógica, eliminación de deuda técnica; ver `roadmap/backend-refactor-roadmap.md` |
| Refactor frontend Core | Media | ⏸ | Estructura de componentes, extracción de lógica al backend; ver `roadmap/frontend-refactor-roadmap.md` |
| Auth y seguridad | Alta | ⚪ | Revisar autenticación, permisos, ownership de activos/pasivos; test de flujos reales |
| Importación de datos | Media | 🔄 | MoneyWiz v1 disponible con preview/commit idempotente, auto-creación de cuentas y espejo UI Core/SaaS. Excel sigue pendiente. |
| Auditoría de seguridad | Alta | ⚪ | Vulnerabilidades backend, CVEs en dependencias, validación auth/permisos/inputs |
| Validación con usuarios reales | Alta | ⚪ | Tests con early adopters; feedback UX, comprensión y valor — crítico antes de MVP |

---

## Funcionalidades implementadas y estables

| Área | Estado | Notas |
|------|--------|-------|
| Net Worth (activos, pasivos, liquidez, snapshots) | ✅ | Completo |
| Budget (ingresos/gastos anuales, check-ins mensuales) | ✅ | Completo |
| Cierre mensual | ✅ | Integrado con budget y accounting |
| Data Input (entradas anuales) | ✅ | Completo |
| Guía financiera / Coach v1 | ✅ | Fases 1-4 con scoring implementado |
| Family & Ownership (FamilyMember, OwnershipLink) | ✅ | Completo |
| Accounting Movements (LedgerAccount/Transaction/Entry) | ✅ | Fases 1-5 completas |
| Market data sync (FX, IPC nacional + CCAA) | ✅ | Fases 1-6 completas, worker `market_data_sync` |
| Portable data (export/import) | ✅ | Con versionado y validación |
| Scoring financiero fases 1-4 | ✅ | Deuda, flujo de caja, fondo emergencia, salud patrimonial |
| Auth Core (JWT, link-token para SaaS) | ✅ | Incluyendo generación de token para linking con SaaS |
| Importador MoneyWiz v1 | ✅ | CSV con `sep=`, preview/commit, huella idempotente, fallback seguro de clasificación y flujo UI en movimientos |

## En progreso activo

| Área | Estado | Roadmap canónico |
|------|--------|-----------------|
| Accounting-budget separation | ✅ Fases 1-5 completadas | `roadmap/terminados/accounting-category-budget-separation-roadmap.md` |

## Deliberadamente aparcado (funcionalidad primero)

| Área | Estado | Notas |
|------|--------|-------|
| Frontend refactor | ⏸ Aparcado | `roadmap/frontend-refactor-roadmap.md`. No se aborda hasta que la funcionalidad esté completa. BudgetDashboardView ~4836 líneas, NetWorthView ~3218 líneas — deuda técnica conocida y aceptada. |
| Backend refactor | ⏸ Aparcado | Mismo criterio. El roadmap está definido pero no es prioritario frente a funcionalidad. |

---

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado y funcionando |
| 🔄 | En progreso |
| ⚪ | No iniciado (en scope futuro) |
| ⛔ | Fuera de alcance explícito (decisión tomada) |
| ⏸ | Aparcado conscientemente |
