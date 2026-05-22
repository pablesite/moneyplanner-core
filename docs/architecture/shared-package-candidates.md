# Shared Package Candidates

_Fecha de cierre documental: 2026-03-19_

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

| Dominio | Estado | Motivo |
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
   dominios con estado.
4. Conservar `auth`, `capabilities` y `lib/api.ts` como fronteras especificas de cada stack.

## Decisión arquitectónica vigente (2026-05-22)

### Situación actual: Opción A — dos frontends espejo

Core y SaaS mantienen frontends separados que se replican manualmente. Es la opción elegida
para salir a producción en el corto plazo. El coste es el mantenimiento dual: cada cambio
en Core debe portarse a SaaS.

Esta decisión es temporal y consciente. No es la arquitectura objetivo.

### Arquitectura objetivo: Opción C — core como librería de componentes Vue

**Visión:** Core exporta sus dominios como un paquete npm (`@moneyplanner/core-ui` o similar).
SaaS importa ese paquete y añade encima únicamente sus capas específicas (auth, billing,
capabilities SaaS). Desaparece la replicación manual.

**Por qué tiene sentido:** el backend ya sigue este modelo — SaaS usa Core como submódulo
Python. El frontend debería espejarlo. Los dominios candidatos ya están preparados (ver
tabla arriba) y elimina la deuda de sincronización que crece con cada feature nueva.

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

**Condiciones para iniciar la extracción:**
1. Core estable en producción y ritmo de cambios estructurales bajo.
2. Necesidad concreta que justifique el coste del setup (vite-lib, publicación
   npm/privada, versionado semver, consumer tests).
3. Dominio piloto elegido de bajo riesgo (candidato: `ui` o `people`).

## Siguientes pasos

1. **Corto plazo**: mantener Opción A. Replicar features Core → SaaS manualmente.
2. **Medio plazo**: cuando Core esté estable en producción, iniciar extracción piloto
   con el dominio `ui` (primitivas sin estado, menor riesgo).
3. **Largo plazo**: migrar dominio a dominio hasta que SaaS no tenga código de UI propio,
   solo extensiones sobre `@moneyplanner/core-ui`.
4. Mantener este documento como referencia canónica de la decisión.

