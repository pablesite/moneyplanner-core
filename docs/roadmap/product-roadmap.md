# Product Roadmap

Planificación de evolución de producto por módulo. Captura pendientes, mejoras y líneas futuras en cada área funcional del Core.

Convenciones:
- `(Roadmap compartido)` — ítem que también aplica o debe coordinarse con el roadmap de SaaS.
- `(Privado - Futuro)` — ítem de baja prioridad o vinculado a lógica de familia/ownership privada.
- ~~tachado~~ — ya resuelto o descartado.

---

## PATRIMONIO

### Para v1

- ✅ **Revisión completa de modales de creación/edición de activos y pasivos.** Coherencia visual, validaciones y flujo revisados; v1 del módulo cerrada a nivel funcional.

### Para v2

- **Onboarding — Asistente para meter activos más fácilmente.** Formulario/flujo ultrasencillo de alta de activos. Activable en cualquier momento desde la vista (no solo al inicio del uso de la aplicación).

---

## PRESUPUESTO

- ✅ Migración fase 1 completada (2026-03-20): formularios de ingresos/gastos previstos integrados en la vista de Presupuesto.
- ✅ Integración fase 2 completada (2026-03-20): introducción de datos y visualización por categorías unificadas en un único flujo contextual dentro de Presupuesto.
- ✅ Conexión gastos presupuesto ↔ cierre y movimientos contables completada.
- ✅ Estilo de evolución ejecutada mensual revisado.
- ✅ Interpretación del estado financiero simplificada.
- ✅ UX general mejorada (barras de progreso, estado del presupuesto).
- ✅ Cierre v1 aplicado y validado manualmente (2026-05-14): summaries mensuales como contrato canónico para barras/cobertura, precedencia ledger sobre check-ins manuales, modales de líneas con errores backend persistentes y header alineado con Patrimonio.

### Para v2

- **Asistente de revisión anual del presupuesto.** Detectar automáticamente desviaciones recurrentes y proponer ajustes por categoría/subcategoría con confirmación manual.

---

## CIERRE DEL MES / AÑO

> Backend modo dual implementado (2026-03-19). Frontend integrado (2026-03-19) — spec: `core/docs/tasks/monthly-close/terminados/dual-mode-frontend.md`. Revisión manual v1 completada (2026-05-14).

### Modos de cierre — decisiones tomadas
- **Sin selección explícita de modo.** El sistema detecta automáticamente cobertura (ledger / checkin / ninguna) y adapta lo que muestra y sugiere.
- Tres perfiles de usuario servidos con un único flujo adaptativo:
  - **Power user:** registra movimientos → cierre = verificación + sign-off
  - **Casual user:** introduce saldos bancarios → sistema sugiere distribución proporcional al presupuesto
  - **Mixto:** registra algunos movimientos → sistema completa los huecos
- `MonthlyClose` es el lifecycle wrapper sobre los checkins existentes. Ciclo de vida: DRAFT → FINALIZED → LOCKED, con reapertura (FINALIZED → DRAFT).
- Status `estimated` añadido a los 3 modelos de checkin para distinguir distribuciones algorítmicas de datos manuales.

### Algoritmo de distribución inteligente
- Usa presupuesto como prior; resta movimientos conocidos (ledger + checkins existentes); distribuye el residual proporcional entre entradas sin cobertura.
- Si hay datos de liquidez: residual = delta_liquidez - (ingresos_conocidos - gastos_conocidos). Si no: usa importe presupuestado directamente.

### Integración con movimientos
- La vista de detalle del cierre autocompletará desde ledger y checkins existentes.
- A partir de ahí, ajustes manuales o aceptar sugerencias (endpoint PATCH accept_suggestions=true).

### API (implementada)
- `GET /api/budget/monthly-close/{year}/{month}/` — estado completo + sugerencias
- `PATCH /api/budget/monthly-close/{year}/{month}/` — actualizar notas / aceptar sugerencias
- `POST /api/budget/monthly-close/{year}/{month}/finalize/` — DRAFT → FINALIZED
- `POST /api/budget/monthly-close/{year}/{month}/reopen/` — FINALIZED → DRAFT
- `POST /api/budget/monthly-close/{year}/{month}/lock/` — FINALIZED → LOCKED

### Frontend integrado ✅
- Fetch unificado (`getMonthlyClose`) en modo cierre; `types.ts` + `api.ts` en dominio budget.
- Distribución inteligente: inputs pre-rellenados con sugerencias del backend para entradas sin cobertura.
- Ciclo de vida UI: badge status (draft/finalized/locked), botones finalizar/reabrir/bloquear en ResultSection.
- Estado locked: inputs deshabilitados con banner informativo cuando cierre FINALIZED/LOCKED.
- Badge "Estimado" para checkins con status `estimated`.
- Mirror Core ↔ SaaS completado.

### Vista de resultados
- Simplificar: actualmente hay dos bloques de conciliación con datos repetidos — reducir duplicación.
- Mostrar solo insights relevantes; añadir gráficas explicables (ingresos/gastos ejecutados con detalle desplegable).

### Cierre del año
- Replicar la lógica del cierre mensual para el cierre anual.

### Transferencias de ownership al cierre
- `(Privado - Futuro)` Añadir lógica para calcular qué transferencia corresponde a cada miembro de la familia al cerrar el mes.

### Vista de resultados
- Simplificar: actualmente hay dos bloques de conciliación con datos repetidos — reducir duplicación.
- Mostrar solo insights relevantes; añadir gráficas explicables (ingresos/gastos ejecutados con detalle desplegable).

### Cierre del año
- Replicar la lógica del cierre mensual para el cierre anual.

### Transferencias de ownership al cierre
- `(Privado - Futuro)` Añadir lógica para calcular qué transferencia corresponde a cada miembro de la familia al cerrar el mes, en base al ownership de activos. Opción habilitada sólo desde settings y sólo si hay varios miembros activos. Objetivo: simplificar el control diario de transferencias entre miembros.

---

## MÓDULO DE CONTABILIDAD

> ✅ **Revisión manual completada (usuario) el 2026-03-17.** Los ajustes finos de contabilidad se validarán durante la implementación y pruebas del importador.

### Para v1

- **Revisión del tracker operativo de cuentas** — 106 cuentas totales, 16 ya revisadas. La coherencia movimientos → cuentas → patrimonio se valida durante esta revisión cuenta a cuenta. Tracker en `core/docs/operations/movements-user1-review-tracker.md`.
- **Re-revisión de categorías/subcategorías en cuentas ya revisadas** — sobre las cuentas ya procesadas en el tracker, revisar que las categorías y subcategorías de sus movimientos sean coherentes con la última actualización de tipología de movimiento vs categoría/subcategoría.
- **Actualizar el header** para que sea exactamente igual al de la vista de Patrimonio.
- **Revisión del estilo visual del cuerpo de la vista** (ya avanzado, pendiente de cierre).

### Para v2

- **UX de entrada rápida**: registro simple de movimientos, formulario ultrasencillo tipo app bancaria. Opcionalmente como asistente rápido o agente conversacional (cuatro datos clave → listo).

### Importación de datos

- ✅ Importador MoneyWiz ad-hoc retirado antes de producción.
- ✅ La trazabilidad de movimientos importados se mantiene en contabilidad mediante `origin`, `import_source` e `import_fingerprint`.
- ✅ La importación portable sigue siendo el flujo soportado para mover/copiar la base de datos entre instancias.

---

## FX-RATES E INFLACIÓN

- `(Roadmap compartido)` Introducir soporte para nuevas monedas a medida que se necesiten.

---

## COACH FINANCIERO

El coach (fases 1–4) está funcional. Pendiente antes de producción:

- ~~Las barras del coach no se renderizan en el frontend del Core.~~ (resuelto)
- **Rediseñar navegación**: integración fluida con los módulos del producto (patrimonio, presupuesto, cierre, contabilidad). El usuario debe poder pasar naturalmente de una recomendación del coach al módulo correspondiente.
- Flujo natural entre coach ↔ producto sin romper el contexto.

---

## MÓDULO INTRODUCCIÓN DE DATOS

- ✅ Retirado el módulo/ruta `/introduccion-datos` (2026-03-20).
- Reubicación aplicada:
  - Formularios de ingresos/gastos previstos → Presupuesto.
  - Entradas relacionadas con activos/pasivos → Patrimonio.
  - Portable data (export/import/replace) → Cuenta (`/account`).

---

## DISEÑO Y EXPERIENCIA DE USUARIO

### Sistema de diseño unificado (crítico para producción)
- 🔄 Fundacion inicial creada en `core/frontend/src/styles/app.css`: tokens semanticos de color, layout, radio, sombras, estados y controles base. Ver `core/docs/frontend/design-system.md`.
- Crear sistema de diseño coherente: colores, tipografías, espaciados, componentes base.
- Unificar todas las vistas bajo el mismo sistema.
- Elevar calidad visual a nivel SaaS profesional.
- ⚠️ Rediseño ≠ refactor técnico — ambos son necesarios y pueden hacerse en paralelo.

### UX transversal
- Simplificar flujos de entrada de datos.
- Mejorar navegación entre módulos.
- Reducir fricción general para el usuario final.

---

## AUTENTICACIÓN Y MODELO DE USUARIO

- Revisar login completo (Core + SaaS).
- Validar sistema de usuarios, familias y ownership de activos/pasivos.
- Verificar permisos y seguridad.
- Test completo de flujos reales (registro, login, ownership compartido, etc.).

---

## IMPORTACIÓN DE DATOS

- Mantener importación/exportación portable como flujo soportado.
- No reintroducir importadores ad-hoc por proveedor salvo decisión explícita de producto.

---

## LEGACY RESIDUAL

Inventario vivo de compatibilidades que siguen presentes tras retirar MoneyWiz activo, `delete-imported`, `accounting/services.py`, `sync_fx_rates` y artefactos `.js` generados. No todo lo legacy es basura: algunas piezas protegen históricos y la portabilidad de datos.

### Pendiente

- ✅ **`net_worth.services.py` — import externo eliminado (2026-05-20).** `get_base_currency_for_user` movida a `accounts/services.py`; `get_financed_asset_queryset_for_user` añadida a `services_assets_core.py`; `_serialize_money` localizada en `services_liquidity.py`. `services.py` re-exporta para consumidores internos y mocks; `portable_data.py` ya no importa del módulo. Ningún consumidor externo activo.

- **`compat.*` en capabilities.**
  - Para qué sirve hoy: puente frontend mientras los checks migran al modelo de capabilities efectivo.
  - Consumidores activos: `capabilities.people` se accede directamente en `people/api.ts` y `net-worth/extensions.ts` (Core y SaaS). `canUsePeople()` y `canUseOwnership()` usan `source.compat.people/ownership`. `isPremium` no tiene consumidores externos.
  - Acción recomendada: migrar accesos directos a `capabilities.people` hacia `canUsePeople()`, luego eliminar el spread `...compat` de `withCompat`.

### Retirado o aclarado

- ✅ **Absorción de Introducción de Datos en Presupuesto — completada.** No quedan rutas, dominios, vistas ni CSS con nombre `data-input`; `core.dataInput` retirado de capabilities.

- ✅ **Campos legacy de aportaciones periódicas en Patrimonio — retirados (2026-05-19).** Migración `net_worth/0039` migró los datos a `contribution_intervals`; migración `net_worth/0042` eliminó los campos escalares (`monthly_contribution_amount`, `expected_end_date`, `investment_contribution_currency`, `investment_contribution_frequency`, `investment_contribution_mode`). Aplicada y verificada.

- **Fallback Budget/check-ins — no es deuda técnica de código.** El mecanismo de checkins es diseño intencional del modo dual: son autoritativos cuando no hay cobertura ledger, y ledger tiene precedencia cuando existe. La deuda es operativa: meses históricos con cobertura solo por checkin que podrían tener respaldo ledger no migrado. No requiere cambio de código.

### Mantener por seguridad de datos

- **Compatibilidad de portable import/export con bundles antiguos.**
  - Para qué sirve hoy: protege bases exportadas con versiones previas, bundles sin metadata y formatos históricos parcialmente migrables.
  - Decisión: mantener. Es parte de la garantía de no perder datos.

- **Trazabilidad de movimientos importados.**
  - Para qué sirve hoy: conserva `origin`, `import_source` e `import_fingerprint` para saber qué movimientos nacieron de una importación histórica.
  - Decisión: mantener. No reintroduce el importador MoneyWiz ni el borrado masivo de importados.

### Referencias históricas

- Los documentos archivados en `core/docs/tasks/**/terminados/` y `core/docs/roadmap/terminados/` pueden seguir mencionando MoneyWiz, `sync_fx_rates`, `accounting/services.py` o flujos antiguos porque describen decisiones pasadas. No implican código activo.

---

## SEGURIDAD

- Auditoría de código: vulnerabilidades backend, validaciones de inputs.
- Auditoría de dependencias: librerías, CVEs conocidos.
- Validación básica: auth, permisos, sanitización de inputs.

---

## REFACTOR Y DEUDA TÉCNICA

> Aparcado deliberadamente hasta completar funcionalidad y rediseño. No es prioritario frente a funcionalidad.

### Core — Backend
- Revisar que funcionen correctamente las funciones de exportar/importar datos.
- Revisión general de backend Core: limpieza de lógica, estructura consistente, eliminación de deuda técnica.

### Core — Frontend
- Extraer lógica de negocio hacia el backend donde corresponda.
- Hacer que los estilos sean coherentes en todas las vistas (después del sistema de diseño).
- Mejorar la navegabilidad.
- Revisar tildes y textos.

### SaaS — Frontend
- Alinear con el frontend del Core; la única diferencia debe ser la vista de administración de perfiles.
- Separar claramente código Core vs SaaS.

### SaaS — Backend
- Revisión general de backend SaaS.

### Documentación y operaciones
- Actualizar la documentación del Core y del SaaS.
- Incluir buenas prácticas de CI/CD.
