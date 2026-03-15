# Importacion Portable

## Estado actual
1. La exportacion portable incluye `exported_app_version`.
2. `Reemplazar datos` se ejecuta en Core como operacion atomica: o importa todo o no modifica nada.
3. `append` y `replace` usan un unico endpoint backend.

## Reglas de seguridad
1. `replace` se bloquea si el archivo no incluye `exported_app_version`.
2. `replace` se bloquea si el archivo fue exportado desde una version Core mas nueva que la del destino.
3. Cuando el backend rechaza la importacion, el frontend no borra nada por su cuenta.

## Operativa recomendada
1. Exportar desde el origen y conservar el JSON hasta verificar el destino.
2. Si el destino va mas atrasado, actualizar Core antes de intentar `replace`.
3. Si solo necesitas mezclar datos y el archivo pasa validacion, usar `Importar datos`.
