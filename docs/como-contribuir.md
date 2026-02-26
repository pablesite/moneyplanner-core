# Cómo contribuir (rápido)

## Antes de abrir cambios
1. Levanta el proyecto con Docker.
2. Reproduce el problema o valida la mejora.
3. Revisa el roadmap comunitario.

## Tipos de ayuda más útiles
1. Bugs reproducibles (pasos + resultado esperado + capturas si aplica).
2. Mejoras de UX (especialmente en introducción de datos y guía).
3. Tests (backend/frontend).
4. Documentación corta y actual.

## Criterios prácticos
1. Cambios pequeños y enfocados.
2. Evitar mezclar refactor + feature + estilo en el mismo PR.
3. Mantener compatibilidad cuando sea razonable.
4. Si cambias comportamiento funcional, actualiza docs.

## Calidad (mínima)
1. Backend: `ruff check .`, `ruff format --check .`, `mypy .`
2. Frontend: `npm run lint`, `npm run format:check`, `npm run typecheck`
3. Ejecutar dentro de Docker.
