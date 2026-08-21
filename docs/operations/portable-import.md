# Importacion Portable

## Current status
1. La exportacion portable incluye `exported_app_version`.
2. `Reemplazar datos` is executed in Core as an atomic operation: either it imports everything or it does not modify anything.
3. `append` y `replace` usan un unico endpoint backend.
4. El bloque `data` incluye presupuesto, patrimonio y contabilidad (`accounting.accounts` + `accounting.transactions`).
5. Los movimientos importados remapean referencias internas (activos, pasivos y ownership) al entorno destino.
6. Los apuntes contables ya no pueden traer enlaces legacy a lineas anuales de presupuesto (`annual_income_entry_id` / `annual_expense_entry_id`); si llegan poblados, el backend rechaza el bundle como obsoleto.
7. Las alertas de Cartera y el adaptador de valoración hacia Mi Plan son read-models sin filas propias: no añaden nada que exportar, importar o restaurar. La recuperación de la cartera sigue estando cubierta por la base de datos y por sus `Asset`/ledger existentes.

## Reglas de seguridad
1. `replace` se bloquea si el archivo no incluye `exported_app_version`.
2. `replace` se bloquea si el archivo fue exportado desde una version Core mas nueva que la del destino.
3. Cuando el backend rechaza la importacion, el frontend no borra nada por su cuenta.

## Operativa recomendada
1. Exportar desde el origen y conservar el JSON hasta verificar el destino.
2. Si el destino va mas atrasado, actualizar Core antes de intentar `replace`.
3. If you only need to mix data and the file passes validation, use `Importar datos`.
