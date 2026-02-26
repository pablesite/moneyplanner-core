# Roadmap: refactor profundo del backend (Core)

## Objetivo
Dejar el backend del Core mas facil de mantener, probar y extender, sin romper el comportamiento funcional actual.

## Principios
1. Refactor por fases pequenas.
2. Sin cambios de comportamiento no intencionales.
3. Primero tests y contratos criticos, luego refactor interno.
4. Cada fase debe dejar el repo en estado ejecutable.

## Alcance
1. `accounts`
2. `budget`
3. `core`
4. `memberships`
5. `net_worth`
6. `config` (solo wiring, auth, errores, settings)

## Fuera de alcance (por ahora)
1. Cambios grandes de producto/UX
2. Nuevos modulos funcionales
3. Integraciones externas complejas
4. Reescritura completa de migraciones historicas

## Fase 0 - Baseline y mapa del backend
Objetivo: saber que hay y donde duele.

1. Inventario por app:
   - views
   - serializers
   - services
   - models
   - tests
2. Detectar puntos con logica mezclada en views/serializers.
3. Detectar endpoints sin tests.
4. Definir lista de refactors por riesgo: alto / medio / bajo.

Entregable:
1. Checklist por app con prioridades.

## Fase 1 - Contratos y errores consistentes
Objetivo: estabilizar la superficie publica antes de mover internals.

1. Normalizar respuestas de error (codes, mensajes, shape).
2. Revisar validaciones duplicadas entre serializers/services.
3. Documentar contratos criticos (auth, family/ownership, net_worth, budget).
4. A?adir tests de regresion de endpoints criticos.

Entregable:
1. Contratos criticos cubiertos por tests.

## Fase 2 - Separacion de responsabilidades (views -> serializers -> services)
Objetivo: reducir acoplamiento y logica dispersa.

1. Views:
   - orquestacion minima
   - permisos/throttling
   - status codes
2. Serializers:
   - validacion y shape
   - sin logica de negocio compleja
3. Services:
   - reglas de negocio
   - operaciones atomicas
   - helpers reutilizables

Entregable:
1. Apps prioritarias alineadas al patron.

## Fase 3 - Tests y calidad del dominio
Objetivo: poder refactorizar mas rapido sin miedo.

1. Tests unitarios de services criticos.
2. Tests API de flujos clave por modulo.
3. Helpers/fixtures reutilizables para tests.
4. Reducir tests fragiles acoplados a implementacion interna.

Entregable:
1. Cobertura funcional minima en modulos Core activos.

## Fase 4 - Transacciones, integridad y rendimiento basico
Objetivo: evitar bugs de datos y regresiones de rendimiento.

1. Revisar uso de `transaction.atomic` en escrituras complejas.
2. Revisar `select_related/prefetch_related` en listados principales.
3. Revisar constraints/indexes utiles (sin sobre-optimizar).
4. Revisar operaciones de import/export y sync de ownership.

Entregable:
1. Flujos de escritura criticos seguros y razonablemente eficientes.

## Fase 5 - Limpieza tecnica y DX
Objetivo: facilitar contribucion comunitaria.

1. Nombres y estructura consistentes por app.
2. Reducir deuda obvia (codigo muerto, helpers duplicados).
3. Mejorar docs de backend para contributors.
4. Tareas pequenas etiquetables para comunidad (`good first issue`).

Entregable:
1. Lista de tareas publicables para contribucion.

## Orden recomendado (modulos)
1. `memberships` (reciente, critico para ownership/familia)
2. `net_worth`
3. `budget`
4. `core` (scoring/guia)
5. `accounts`

## Criterio de exito (primer corte)
1. Endpoints Core criticos con tests de regresion.
2. Logica de negocio principal fuera de views.
3. Errores mas consistentes en modulos activos.
4. Documentacion suficiente para que otra persona continue el refactor.

## Como puede ayudar la comunidad
1. Reportar hotspots (archivos dificiles de mantener)
2. Abrir PRs pequenos por modulo
3. Anadir tests antes de refactor
4. Mejorar docs y ejemplos de uso API
