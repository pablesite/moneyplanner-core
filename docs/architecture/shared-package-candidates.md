# Shared Package Candidates

_Fecha de cierre documental: 2026-03-19_

Este documento resume los dominios del frontend Core/SaaS que ya estan preparados para una
futura extraccion como shared package. No implementa nada: solo deja constancia de que
quedo listo, que no y cuales son los siguientes pasos.

## Contexto

El refactor frontend quedo cerrado en Core y replicado en SaaS. La Fase 6 dejo como
salida documental este mapa de candidatos, para evitar que la decision de comparticion se
pierda dentro del roadmap. Ver tambien:
- `core/docs/roadmap/frontend-refactor-roadmap.md`
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

## Siguientes pasos

1. Elegir un dominio con bajo riesgo y alta reutilizacion para la primera extraccion real.
2. Definir la forma del paquete compartido solo cuando exista una necesidad funcional clara.
3. Mantener este documento como referencia canonica hasta que la extraccion empiece.
