# Estado del Proyecto — Core

Estado actual de funcionalidades por área. Actualizar cuando cambie el estado de una funcionalidad.

**Última revisión:** 2026-03-18 | **Versión Core:** 0.23.1

---

## En curso y próximas tareas

> Convención de tipo de tarea:
> - **(Manual)** — requiere guía directa del usuario; la dirección se define sobre la marcha. No delegable a un agente sin esa guía.
> - **(Agente)** — delegable; requiere un plan maestro pero no decisiones continuas del usuario.

### En curso

_Sin tareas activas._

### Siguiente tarea disponible

Seleccionar según disponibilidad: ejecutar tareas **(Agente)** cuando haya capacidad para delegar; **(Manual)** cuando haya tiempo para guiar.

| Módulo | Tipo | Descripción | Spec |
|--------|------|-------------|------|
| Presupuesto | Manual | Revisión integral de experiencia de uso del módulo. | Se define durante la revisión. |
| Refactor backend — Phase 4 | Agente | Boundary enforcement: transaction.atomic en flujos cross-domain, documentar contratos. | `core/docs/tasks/backend-refactor/phase-4-boundary-enforcement/backend.md` |
| Refactor backend — Phase 5 | Agente | DX docs: backend patterns guide, PR checklist, backlog de contribución. | `core/docs/tasks/backend-refactor/phase-5-dx-docs/backend.md` |

| Refactor frontend — Fase 0 | Agente | Baseline limpia + cobertura ≥80%: subir thresholds, escribir tests gap, corregir formato app.css. | `core/docs/tasks/frontend-refactor/phase-0-baseline/frontend.md` |
| Refactor frontend — Fase 1 | Agente | Fronteras de arquitectura: eliminar wrappers puente, mover BaseModal/AppHeader a dominios, alinear index.ts. | `core/docs/tasks/frontend-refactor/phase-1-arch-boundaries/frontend.md` |
| Refactor frontend — Fase 2 | Agente | Shell + router: adelgazar App.vue, crear composables de shell, limpiar router, retirar residuales. | `core/docs/tasks/frontend-refactor/phase-2-shell-router/frontend.md` |
| Refactor frontend — Fase 3a | Agente | Descomponer BudgetDashboardView (5,512 líneas) en composables + secciones. | `core/docs/tasks/frontend-refactor/phase-3a-budget-dashboard/frontend.md` |
| Refactor frontend — Fase 3b | Agente | Descomponer NetWorthView (3,608 líneas) en composables + secciones. | `core/docs/tasks/frontend-refactor/phase-3b-net-worth/frontend.md` |
| Refactor frontend — Fase 3c | Agente | Descomponer DataInputView (2,742 líneas) en composables + secciones. | `core/docs/tasks/frontend-refactor/phase-3c-data-input/frontend.md` |
| Refactor frontend — Fase 3d | Agente | Descomponer GuidePhaseDetailView (2,207 líneas), extraer lógica compartida con HomeView. | `core/docs/tasks/frontend-refactor/phase-3d-guide-view/frontend.md` |
| Refactor frontend — Fase 3e | Agente | Descomponer AccountingMovementsView (2,263 líneas) en secciones controladas. | `core/docs/tasks/frontend-refactor/phase-3e-accounting-movements/frontend.md` |
| Refactor frontend — Fase 4 | Agente | CSS contract: consolidar app.css (20K líneas), reducir style scoped, estandarizar estados. | `core/docs/tasks/frontend-refactor/phase-4-css-contract/frontend.md` |
| Refactor frontend — Fase 5 | Agente | Contratos internos de dominio: estandarizar estructura, 0 imports @/lib/api desde vistas. | `core/docs/tasks/frontend-refactor/phase-5-domain-contracts/frontend.md` |
| Refactor frontend — Fase 6 | Agente | Hardening: 0 imports legacy, 0 warnings, shared-package-candidates.md, docs actualizadas. | `core/docs/tasks/frontend-refactor/phase-6-hardening/frontend.md` |

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
| Refactor backend Core | Media | 🔄 | Limpieza de lógica y deuda técnica en progreso. Fases 1, 2 y 3 completadas (baseline de tests + particion de accounting + net_worth domain cleanup). Ver `roadmap/backend-refactor-roadmap.md` |
| Refactor frontend Core | Media | ⏸ | Estructura de componentes, extracción de lógica al backend; ver `roadmap/frontend-refactor-roadmap.md` |
| Auth y seguridad | Alta | ⚪ | Revisar autenticación, permisos, ownership de activos/pasivos; test de flujos reales |
| Importación de datos | Media | ✅ | MoneyWiz v1 corregido: aliases en español para cabeceras (Fecha, Cuentas, Importe, Moneda, etc.) y detección de filas de resumen de cuenta. Validado con CSV real. Excel sigue pendiente. |
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

## En progreso activo

| Área | Estado | Roadmap canónico |
|------|--------|-----------------|
| Accounting-budget separation | ✅ Fases 1-5 completadas | `roadmap/terminados/accounting-category-budget-separation-roadmap.md` |

## Deliberadamente aparcado (funcionalidad primero)

| Área | Estado | Notas |
|------|--------|-------|
| Frontend refactor | 🔄 Planificado | `roadmap/frontend-refactor-roadmap.md`. 11 fases planificadas. Specs en `core/docs/tasks/frontend-refactor/`. BudgetDashboardView 5,512 líneas, NetWorthView 3,608 líneas. Coverage target ≥80%. |
| Backend refactor | 🔄 En progreso | Fases 1, 2 y 3 completadas y validadas en Docker (tests/ruff/mypy). Pendientes fases 4-5. Ver `roadmap/backend-refactor-roadmap.md`. |

---

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado y funcionando |
| 🔄 | En progreso |
| ⚪ | No iniciado (en scope futuro) |
| ⛔ | Fuera de alcance explícito (decisión tomada) |
| ⏸ | Aparcado conscientemente |




