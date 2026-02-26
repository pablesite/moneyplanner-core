# Contribuir a MoneyPlanner Core

Gracias por contribuir a `moneyplanner`.

## Flujo recomendado
1. Crea una rama desde `main`.
2. Haz un cambio pequeno y enfocado.
3. Ejecuta checks dentro de Docker.
4. Abre PR con alcance claro y cambios documentados.

## Setup local
1. Copia env: `cp backend/.env.example backend/.env`
2. Arranca: `docker compose up --build -d`

## Backend
1. Mantener el flujo `views -> serializers -> services`.
2. Reglas de negocio en `services.py`.
3. Actualizar tests cuando cambie comportamiento.
4. Validacion minima:
   - `docker compose exec backend ruff check .`
   - `docker compose exec backend ruff format --check .`
   - `docker compose exec backend mypy .`

## Frontend
1. Organizar por dominios en `frontend/src/domains/*`.
2. Mantener vistas declarativas.
3. Reusar componentes/estilos compartidos.
4. Validacion minima:
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`

## PR checklist
1. Scope pequeno y coherente.
2. Checks ejecutados en Docker.
3. Tests/documentacion actualizados si aplica.
4. Commits con Conventional Commits.
