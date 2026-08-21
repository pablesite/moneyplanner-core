# Cartera - Fase 8: integracion de producto y cierre

## Context
El cierre conecta Cartera con Mi Plan y convierte incidencias deterministas en acciones internas sin crear un sistema global de notificaciones.

## Area
`backend`

## Stack
`core`

## Scope
1. Generar alertas de calidad y estructura: stale, gaps, descuadres, concentracion, drift, exceso de efectivo y cestas pendientes.
2. Mantener umbrales configurables y eventos de dominio preparados para canales futuros; el MVP no envia correo/push.
3. Integrar valor/capital productivo real de Cartera en Mi Plan sin duplicar proyecciones.
4. Reintroducir los inputs backend necesarios para independencia financiera solo cuando la calidad minima este disponible.
5. Auditar rendimiento, permisos, backups y export/import portable de nuevos modelos.
6. Dejar backlog explicito para fiscalidad, conectores de broker y riesgo avanzado.

## Plan
1. Implementar reglas/eventos de alerta e integracion de capital productivo.
2. Auditar doble conteo y calidad entre Portfolio, Net Worth y Plan.
3. Ejecutar hardening, backup/restore y cierre documental.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio plan accounting net_worth accounts
```

## Required Documentation Updates
- [x] Arquitectura Core, roadmap y project status.
- [x] Docs de portable import: no cambia cobertura porque alertas/adaptador no persisten datos.
- [x] `docs/architecture/core-saas-boundaries.md`, capabilities y API registry.

## Risks
Mi Plan ya infiere inversiones desde Patrimonio; introducir Portfolio sin precedencia explicita puede duplicar capital productivo. Añadir tests de reconciliacion end-to-end.

## Completion Criteria
- [x] Alertas deterministas y explicables.
- [x] Mi Plan usa Cartera sin doble conteo.
- [x] Backup/restore y aislamiento verificados: no hay modelos nuevos; el endpoint se resuelve por `request.user`.
- [x] Tests, docs y commit completados.
- [x] Spec movida a `terminados/`.
