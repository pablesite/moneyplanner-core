# Product Roadmap

Planificación de evolución de producto por módulo. Captura pendientes, mejoras y líneas futuras en cada área funcional del Core.

Convenciones:
- `(Roadmap compartido)` — ítem que también aplica o debe coordinarse con el roadmap de SaaS.
- `(Privado - Futuro)` — ítem de baja prioridad o vinculado a lógica de familia/ownership privada.
- ~~tachado~~ — ya resuelto o descartado.

---

## PATRIMONIO

### Pendientes próximos
- Revisar si añadir más gráficas: evolución temporal o gráfico de quesito (donut de distribución).
- **UX — Asistente para meter activos más fácilmente.** Formulario/flujo ultrasencillo de alta de activos.
- Validar consistencia global de datos y KPIs (activos, pasivos, liquidez neta).
- Evaluar eliminación del sistema de snapshots si resulta legacy/redundante.

---

## PRESUPUESTO

- Migrar los formularios de ingresos/gastos previstos desde el módulo de Introducción de Datos directamente a la vista de presupuesto.
- Conectar gastos definidos en el presupuesto con los valores reales del cierre y los movimientos contables del día a día (ahora son placeholders).
- Revisar el estilo de la evolución ejecutada mensual: las barras son visualmente correctas pero no se distinguen bien las categorías.
- Simplificar la interpretación del estado financiero: menos ruido visual, más claridad para el usuario final.
- Mejorar UX general: barras de progreso más legibles, estado del presupuesto más explícito.

---

## CIERRE DEL MES / AÑO

> Considerar renombrar este módulo para que refleje mejor su función (ej. "Revisión mensual" o "Seguimiento mensual").

### Modos de cierre
- Integrar dos modos de trabajo:
  - **Manual:** input directo de saldos por el usuario.
  - **Automático:** cierre basado en datos de contabilidad (movimientos del período).
- Diseñar UX para elegir el modo activo y, si aplica, combinar ambos (manual como ajuste sobre el automático).

### Integración con movimientos
- Decidir si la introducción de ingresos/gastos sirve tanto para el día a día como para el presupuesto, o sólo para uno de ellos.
- La vista de detalle del cierre debería autocompletar:
  - El líquido de cada activo de liquidez.
  - Los totales por categoría de ingreso y gasto a partir de los movimientos contables.
  - A partir de ahí, ajustes manuales para movimientos no anotados.

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

### Pendientes próximos
- **UX de entrada rápida**: registro simple de movimientos, formulario ultrasencillo tipo app bancaria. Opcionalmente como asistente rápido o agente conversacional (cuatro datos clave → listo).
- **Transferencias entre cuentas**: implementar doble impacto automático (salida de una cuenta + entrada en otra).
- **Bug edición de movimientos**: corregir modal roto al editar un movimiento existente.
- Validar consistencia end-to-end: movimientos → cuentas → patrimonio.

### Importación de datos
- ✅ Importador MoneyWiz v1 completado:
  - Preview + commit desde CSV exportado por MoneyWiz.
  - Idempotencia por huella de fila.
  - Auto-creación de cuentas operativas cuando faltan.
  - Fallback seguro de clasificación para categorías sin mapeo exacto.
  - Flujo UI integrado en `AccountingMovementsView` y espejado en SaaS.
- Pendiente después de v1:
  - Afinar heurísticas de mapeo para categorías MoneyWiz menos frecuentes.
  - Contraste e importador dedicado desde Excel.

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

- **Eliminar el módulo completo** una vez migrado todo:
  - Formularios de ingresos/gastos previstos → Presupuesto.
  - Entradas relacionadas con activos/pasivos → Patrimonio.
- Hacer esta migración antes del rediseño para no arrastrar deuda de UX.

---

## DISEÑO Y EXPERIENCIA DE USUARIO

### Sistema de diseño unificado (crítico para producción)
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

- Implementar importador masivo para uso propio (objetivo: test real con datos personales):
  - Desde MoneyWiz.
  - Desde Excel.
- Mapear: movimientos, cuentas, categorías.

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
