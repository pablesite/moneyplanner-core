# Shared Package Candidates

_Documentary closing date: 2026-03-19_

Este documento resume los dominios del frontend Core/SaaS que ya estan preparados para una
futura extraccion como shared package. No implementa nada: solo deja constancia de que
quedo listo, que no y cuales son los siguientes pasos.

## Contexto

El refactor frontend quedo cerrado en Core y replicado en SaaS. La Fase 6 dejo como
salida documental este mapa de candidatos, para evitar que la decision de comparticion se
pierda dentro del roadmap. Ver tambien:
- `core/docs/roadmap/terminados/frontend-refactor-roadmap.md`
- `docs/roadmap/frontend-refactor-roadmap.md`

## Candidatos preparados

| Domain | Status | Reason |
|---------|--------|--------|
| `net-worth` | Listo | Dominio compartido en Core y SaaS, con estructura ya separada por dominio y dependencias acotadas. |
| `people` | Listo | UI y logica de dominio equivalentes en ambos frontends. |
| `guide` | Listo | Flujos y calculos reutilizables entre Core y SaaS. |
| `aux-data` | Listo | Pantallas y helpers equivalentes, sin diferencias de negocio relevantes. |
| `data-input` | Listo | Estructura ya alineada para extraer vistas/composables compartibles. |
| `ui` | Listo | Componentes visuales transversales con uso repetido en ambos frontends. |

## No compartibles

| Elemento | Motivo |
|----------|--------|
| `auth` | Las URLs, guards y flujos de acceso difieren entre Core y SaaS. |
| `capabilities` | Los planes y helpers de capacidad no son identicos entre ambos productos. |
| `lib/api.ts` | El cliente HTTP tiene bases URL y contexto distintos; debe seguir siendo especifico de cada frontend. |

## Reglas de extraccion

1. Mantener la separacion de dominios antes de extraer.
2. No mover logica de negocio que dependa de contratos SaaS o Core especificos.
3. Extraer primero primitivas UI y helpers puros, despues composables y finalmente
stateful domains.
4. Conservar `auth`, `capabilities` y `lib/api.ts` como fronteras especificas de cada stack.

## Current architectural decision (2026-05-22)

### Current situation: Option A — two mirror frontends

Core and SaaS maintain separate frontends that are manually replicated. It is the chosen option
to go into production in the short term. The cost is dual maintenance: each change
en Core debe portarse a SaaS.

This decision is temporary and conscious. It is not the target architecture.

### Target architecture: Option C — core as Vue component library

**Vision:** Core exports its domains as an npm package (`@moneyplanner/core-ui` or similar).
SaaS imports that package and adds only its specific layers on top (auth, billing,
SaaS capabilities). Manual replication disappears.

**Why it makes sense:** the backend already follows this model — SaaS uses Core as a submodule
Python. The frontend should mirror it. The candidate domains are already prepared (see
table above) and eliminates the synchronization debt that grows with each new feature.

**Forma aproximada del paquete:**
```
@moneyplanner/core-ui
  /net-worth      → componentes + composables
  /people         → componentes + composables
  /guide          → componentes + composables
  /aux-data       → componentes + composables
  /data-input     → componentes + composables
  /ui             → primitivas visuales compartidas
  /budget         → cuando esté listo para extracción
```

**Lo que NO entra en el paquete:**
- `auth` — diferente en Core (sin auth) y SaaS (JWT + memberships)
- `capabilities` — los planes SaaS no existen en Core standalone
- `lib/api.ts` — base URL y contexto distintos por stack

**Conditions to start the extraction:**
1. Stable core in production and low rate of structural changes.
2. Specific need that justifies the cost of the setup (vite-lib, publication
   npm/privada, versionado semver, consumer tests).
3. Dominio piloto elegido de bajo riesgo (candidato: `ui` o `people`).

## Siguientes pasos

1. **Short term**: maintain Option A. Replicate Core → SaaS features manually.
2. **Medium term**: when Core is stable in production, start pilot mining
with the domain `ui` (stateless primitives, lower risk).
3. **Long term**: migrate domain to domain until SaaS has no UI code of its own,
   solo extensiones sobre `@moneyplanner/core-ui`.
4. Keep this document as a canonical reference of the decision.

