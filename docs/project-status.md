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

| Refactor frontend — Fase 0 | Agente | Baseline limpia + cobertura ≥80%: subir thresholds, escribir tests gap, corregir formato app.css. | `core/docs/tasks/frontend-refactor/phase-0-baseline/frontend.md` |
| Refactor frontend — Fase 1 | Agente | Fronteras de arquitectura: eliminar wrappers puente, mover BaseModal/AppHeader a dominios, alinear index.ts. | `core/docs/tasks/frontend-refactor/phase-1-arch-boundaries/frontend.md` |
| Refactor frontend — Fase 2 | Agente | Shell + router: adelgazar App.vue, crear composables de shell, limpiar router, retirar residuales. | `core/docs/tasks/frontend-refactor/phase-2-shell-router/frontend.md` |
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
| Refactor backend Core | Media | ✅ | Refactor estructural completado (fases 1-5). Queda backlog de contribucion documentado en `roadmap/backend-refactor-roadmap.md`. |
| Refactor frontend Core | Media | ⏸ | Roadmap aparcado salvo petición explícita. Fases 3a (BudgetDashboardView) y 3b (NetWorthView) cerradas a nivel estructural; ver `roadmap/frontend-refactor-roadmap.md`. |
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
| Frontend refactor | ?? Planificado | `roadmap/frontend-refactor-roadmap.md`. Fase 3b (NetWorthView) completada a nivel estructural; siguientes cortes abiertos en 3a/3c/3d/3e. La baseline global de coverage sigue pendiente en Fase 0. |

---

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado y funcionando |
| 🔄 | En progreso |
| ⚪ | No iniciado (en scope futuro) |
| ⛔ | Fuera de alcance explícito (decisión tomada) |
| ⏸ | Aparcado conscientemente |


