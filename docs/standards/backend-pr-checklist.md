# Backend PR Checklist

Checklist reutilizable para PRs de backend en Core.

## Antes de abrir el PR
- [ ] Los tests pasan: `python manage.py test <app>` o suite equivalente del alcance.
- [ ] `ruff check .` limpio.
- [ ] `ruff format --check .` limpio.
- [ ] `mypy .` limpio cuando aplique.
- [ ] No hay cambios de comportamiento no intencionales.
- [ ] Si cambia el contrato API: documentacion actualizada.
- [ ] Si cambia un modelo: migracion generada y aplicada.
- [ ] Si hay side effects cross-domain: cubiertos con integration tests.

## Reglas de capa
- [ ] Logica de negocio en `services*.py`, no en `views.py`.
- [ ] `views.py` valida input, llama al service y retorna respuesta.
- [ ] `serializers.py` adapta shape y valida tipos; no ejecuta reglas de negocio.
- [ ] Si un service cruza dominios y hay side effects: usar `transaction.atomic`.

## Tests
- [ ] Nuevo comportamiento con test de API (happy path).
- [ ] Cobertura de error path (auth failure, validation error o equivalente).
- [ ] Logica de negocio nueva con unit/service test.
- [ ] Flujos cross-domain relevantes cubiertos en `test_integration.py`.

## Commits
- [ ] Conventional Commits: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- [ ] Commit atomico por bloque funcional validado.
