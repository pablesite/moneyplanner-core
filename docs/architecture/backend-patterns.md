# Backend Patterns - Core

Guia corta de patrones vigentes para backend Core.

> Nota de mantenimiento: actualizar este documento cuando cambien boundaries o contratos de arquitectura.

## Views (`views.py`)
- Thin adapters: reciben request, llaman services y retornan response.
- Sin reglas de negocio ni orquestacion compleja.
- Reutilizar mixins transversales (`UserScopedQuerySetMixin`) para scope por usuario.
- Errores via excepciones DRF y handler canonico en `config/exceptions.py`.

## Serializers (`serializers.py`)
- Adaptan y validan shape de entrada/salida.
- No ejecutan logica de negocio.
- Pueden componer serializers anidados para respuestas complejas.

## Services (`services*.py`)
- Fuente principal de reglas de negocio y orquestacion.
- Preferir funciones pequenas y explicitas.
- Si hay side effects cross-domain: usar `transaction.atomic`.
- Si crecen demasiado, particionar por subdominio (`services_<subdominio>.py`).

## Tests (`tests/`)
- API tests: `APITestCase`, auth + happy path + error paths relevantes.
- Service tests: validan reglas de negocio sin capa HTTP.
- Integration tests: `test_integration.py` para flujos cross-domain.
- Mantener tests agrupados por dominio para discovery y mantenibilidad.

## Exception handling
- Error contract canonico: `{code, message, details}`.
- Evitar respuestas ad hoc con shape distinto.
- Para features desactivadas: usar helper canonico (`feature_disabled`) cuando aplique.

## `UserScopedQuerySetMixin`
- Usar en ViewSets con datos usuario-especificos.
- Asegura filtrado por `request.user` de forma consistente.

## Modulo `config/`
- Reservado para wiring (urls/settings), auth, excepciones y mixins transversales.
- No anadir logica de dominio en `config/`.
