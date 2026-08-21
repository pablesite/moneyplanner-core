# Titularidad por lotes — trabajo pendiente

Leer antes `README.md` de esta carpeta.

---

## Tarea 1 — Aplicar la corrección del bote de bitcoin a producción

### Context

El reparto por lotes ya lee bien el bote, pero en el histórico real hay asientos que dicen
algo que no pasó: la venta del 2023-09-30 está etiquetada como individual cuando lo que
había dentro era mayoritariamente compartido. Sin corregir el libro, lo compartido arrastra
una historia que no vivió.

La corrección está **acordada, verificada y aplicada en local**, pero **no en producción**.

### Area / Stack

`backend` · `core` (datos, no código)

### Qué se acordó exactamente

El 2023-09-30 se vendieron 0,03312867 BTC de un bote de 0,03455447 (el 96%). Dentro había
0,01710241 compartido y 0,01745206 individual.

1. **La venta liquida primero todo lo compartido**: 0,01710241 compartido / 0,01602626
   individual. Quedan 0,00142580, todos individuales.
2. Las tres ventas siguientes (2023-10-25 ×2 y 2023-11-02) **las cubre el bolsillo
   individual sin tocar nada compartido**. No es casualidad: con el bolsillo compartido a
   cero, todo el saldo de la cuenta es individual por definición, y el saldo no puede ser
   negativo.
3. Lo compartido **se reconstruye desde el 2023-11-05** hasta 0,01183599, que es lo que el
   usuario separó en la realidad. La compra que cruza el umbral se parte en dos.
4. El envío del 2026-08-20 a la posición Compartida **se etiqueta como compartido**: sin
   titularidad se reparte a prorrata y se lleva monedas de ambos en lugar de las suyas.

Se descartó el prorrateo de la venta: hacía que lo compartido vendiera 0,0073 BTC por el
camino sin que nadie lo hubiera decidido, ensuciando su rentabilidad.

### Plan

1. Sacar dump de producción (`prod-dev-refresh`) y confirmar que los ids siguen siendo los
   del plan; si han cambiado, **volver a derivarlos**, nunca asumirlos.
2. Ejecutar en seco contra producción y comparar con el plan esperado de abajo.
3. Aplicar con `--apply`.

### Validation

En seco (no escribe nada):

```bash
python manage.py split_commingled_ownership \
  --account-id 26 --shared-ownership-id 4 --own-ownership-id 1 \
  --liquidation-date 2023-09-30 --rebuild-from 2023-11-05 \
  --target-units 0.01183599 --tag-shared 65826 65843
```

Plan esperado:

```
PARTIR                2023-09-30 tx45567  0.03312867 -> compartida 0.01710241 / resto 0.01602626
entera -> compartida  2023-11-05 tx45535  0.01144935
entera -> compartida  2023-12-25 tx45521  0.00034278
PARTIR                2024-01-03 tx45518  0.00034887 -> compartida 0.00004386 / resto 0.00030501
etiquetar compartida  2026-08-20 tx65826  Envío BTC a Compartido (MetaMask)
etiquetar compartida  2026-08-20 tx65843  Comisión de venta · Envío BTC a Co
```

Después de aplicar, tres comprobaciones **obligatorias**:

1. El saldo de la cuenta 26 **no ha cambiado** (debe seguir siendo `0.00000000`). Si cambia,
   el reparto ha creado o destruido unidades: revertir.
2. Los bolsillos quedan así:

   | Fecha | Compartido | Individual |
   | --- | --- | --- |
   | 2023-09-29 | 0,01710241 | 0,01745206 |
   | 2023-10-01 | — | 0,00142580 |
   | 2024-01-04 | 0,01183599 | 0,00173215 |
   | 2026-08-19 | 0,01183599 | 0,03031324 |

3. **La suma de los miembros da el total** en lo aportado. Es la propiedad que fija que el
   reparto no inventa dinero.

### Risks

Edita histórico contable real. El comando abre transacción atómica y no escribe sin
`--apply`, pero **no tiene deshacer**: sacar dump antes. Si los ids de producción no
coinciden con los del plan, parar y volver a derivarlos.

### Completion Criteria

- [ ] Dry-run contra producción coincide con el plan esperado
- [ ] Aplicado con `--apply`
- [ ] Las tres comprobaciones de arriba pasan
- [ ] `project-status.md` actualizado

---

## Tarea 2 — Que los hilos económicos lean los bolsillos, no los tramos

### Context

`build_holding_threads` agrupa por `(instrumento, ownership_id)` leyendo los tramos
declarados de cada posición. Para un bote mezclado eso miente: la posición del bote declara
un solo dueño, así que su parte compartida no aparece como hilo propio.

Efecto hoy: el histórico compartido de bitcoin **se ve correctamente filtrando por el
miembro**, porque el filtro sí lee los bolsillos, pero **no existe como hilo separado**. El
hilo "BTC compartido" arranca el día de la separación en lugar de contar su vida real.

### Area / Stack

`backend` (+ `frontend` si se decide exponerlo) · `core`

### Scope

1. En alcance: que un hilo pueda nacer de un bolsillo y no solo de un tramo, y que el scope
   correspondiente acote los flujos a la parte que le toca.
2. Fuera de alcance: cambiar el modelo de tramos, que sigue siendo correcto para lo que no
   está mezclado.

### Plan

1. Diagnóstico: `build_holding_threads` en `backend/portfolio/performance.py` recorre
   `context.ownership_periods`. Para posiciones presentes en `context.pockets` la fuente de
   verdad es el bolsillo.
2. Decidir el contrato: un hilo por `(instrumento, titularidad)` donde la titularidad puede
   venir de un bolsillo. Ojo con el valor: la parte del bolsillo es una fracción de
   unidades, no una posición aparte, así que el scope no puede ser un simple conjunto de
   ids de posición — hay que decidir si el ámbito admite fracciones o si el hilo se publica
   solo como lectura sin metrica de scope.
3. Tests: un bote mezclado debe producir **dos** hilos, y la suma de sus valores debe dar el
   valor de la posición.

### Risks

`scope_ids` es hoy un conjunto de posiciones enteras y todo el motor asume eso. Admitir
fracciones toca `_metric_block`; conviene medir antes si compensa frente a publicar el hilo
como lectura informativa.

### Required Documentation Updates

- [ ] `docs/architecture/architecture.md` si cambia el contrato de `/api/portfolio/threads/`
- [ ] `project-status.md`

### Completion Criteria

- [ ] Un bote mezclado publica un hilo por titularidad
- [ ] La suma de los hilos de una posición da su valor
- [ ] Tests nuevos en verde y `./scripts/pre-push-check.sh` en verde
