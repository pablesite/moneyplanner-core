# Product Roadmap

Planificación de evolución de producto por módulo. Captura pendientes, mejoras y líneas futuras en cada área funcional del Core.

Convenciones:
- `(Roadmap compartido)` — ítem que también aplica o debe coordinarse con el roadmap de SaaS.
- `(Privado - Futuro)` — ítem de baja prioridad o vinculado a lógica de familia/ownership privada.
- ~~tachado~~ — ya resuelto o descartado.

---

## PATRIMONIO

### Pendientes próximos
- Revisar si añadir más gráficas: evolución temporal o gráfico de quesito.
- **UX — Asistente para meter activos más fácilmente.** Formulario/flujo ultrasencillo de alta de activos.

### Activos — Inmuebles
- Vivienda no habitual:
  - Uso propio: mismo modelo que la vivienda habitual.
  - Alquiler: modelo de generación de rentas → ingresos automáticos vinculados al activo.
- Inversiones:
  - Las inversiones generan ingresos pasivos (reinvertidos) o revalorizaciones automáticas.

### Pasivos
- `(Roadmap compartido)` Motor de hipotecas. Por ahora vale con tipo fijo; añadir soporte completo en el futuro.

---

## PRESUPUESTO

- Conectar los gastos del presupuesto con los valores reales del cierre del mes y los movimientos del día a día.
- Incluir los formularios de alta de ingresos/gastos directamente en la vista de presupuesto y eliminar la vista separada de Introducción de Datos.
- Revisar el estilo de la evolución ejecutada mensual: las barras son visualmente correctas pero no se distinguen bien las categorías de las líneas de gasto/ingreso.

---

## CIERRE DEL MES / AÑO

### Integración con movimientos
- Decidir si la introducción de ingresos/gastos sirve tanto para el día a día como para el presupuesto, o sólo para uno de ellos.
- La vista de detalle del cierre debería autocompletar:
  - El líquido de cada activo de liquidez.
  - Los totales por categoría de ingreso y gasto, a partir de la vista de movimientos.
  - A partir de ahí, se pueden hacer ajustes manuales para movimientos no anotados.

### Vista de resultados
- Simplificar: actualmente hay dos bloques para la conciliación del cierre con datos repetidos.
- Añadir gráficas más explicables: ingresos y gastos ejecutados con detalle desplegable.

### Cierre del año
- Replicar la lógica del cierre mensual para el cierre anual.

### Transferencias de ownership al cierre
- `(Privado - Futuro)` Añadir lógica para calcular qué transferencia corresponde a cada miembro de la familia al cerrar el mes, en base al ownership de activos. Opción habilitada sólo desde settings y sólo si hay varios miembros activos. Objetivo: simplificar el control diario de transferencias entre miembros.

---

## MÓDULO DE CONTABILIDAD

> **Revisión manual pendiente (usuario)** — Revisar la experiencia de uso del módulo para decidir qué mejoras implementar y en qué dirección orientarlo. Esta tarea requiere guía directa del usuario: no es delegable a un agente sin esa revisión previa.

- **UX de entrada rápida**: formulario ultrasencillo para anotar movimientos del día a día. Opcionalmente como asistente rápido o agente conversacional (indicar los cuatro datos clave y listo).
- `(Privado - Futuro)` Importador de movimientos desde MoneyWiz. Tipos de movimiento a mapear:
  - Ingresos a cuentas de liquidez.
  - Ingresos pasivos: dividendos, intereses, otros.
  - Transferencias entre cuentas de liquidez.
  - Gastos corrientes.
  - Gastos a inversiones → Ingreso en inversión.
  - Gastos a inmobiliario → Activo inmobiliario.
  - Gasto en mobiliario → Activo mobiliario.

---

## FX-RATES E INFLACIÓN

- `(Roadmap compartido)` Introducir soporte para nuevas monedas a medida que se necesiten.

---

## CARTERA DE INVERSIÓN

- `(Roadmap compartido)` Vista de cartera de inversión.

---

## COACH FINANCIERO

- ~~Las barras del coach no se renderizan en el frontend del Core.~~ (resuelto)
- `(Roadmap compartido)` Completar Fase 5 del modelo de scoring.
- `(Roadmap compartido)` Incluir objetivos financieros personales. El coach identifica qué KPIs priorizar y qué palancas accionar. Ejemplos de objetivos:
  - Ahorrar X€ para una casa.
  - Eliminar la deuda mala.
  - Alcanzar la independencia financiera en N años.

---

## SIMULADOR FINANCIERO

- `(Roadmap compartido)` Plantear motor de simulaciones: ¿qué pasa si compro una casa de X€? ¿Y si compro un coche?

---

## REFACTOR Y SEGURIDAD

### Core — Backend
- Revisar que funcionen correctamente las funciones de exportar/importar datos.
- Revisión general de backend Core.

### Core — Frontend
- Extraer lógica de negocio hacia el backend donde corresponda.
- Hacer que los estilos sean coherentes en todas las vistas.
- Mejorar la navegabilidad.
- Revisar tildes y textos.

### SaaS — Frontend
- Alinear con el frontend del Core; la única diferencia debe ser la vista de administración de perfiles.

### SaaS — Backend
- Revisión general de backend SaaS.

### Autenticación y seguridad
- Revisar autenticación de ambos sistemas (Core y SaaS).
- Revisar agujeros de seguridad en general.

### Documentación y operaciones
- Actualizar la documentación del Core y del SaaS.
- Incluir buenas prácticas de CI/CD.
- `(Roadmap compartido)` Adaptar el frontend a PWA.
