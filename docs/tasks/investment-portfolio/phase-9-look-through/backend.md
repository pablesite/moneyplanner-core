# Cartera - Fase 9: exposicion real por look-through

## Context
Una posicion agregada —una cartera de roboadvisor, un fondo mixto, una plataforma con
varios proyectos— se cuenta hoy entera en su clase dominante. Para una politica por
clases eso basta y esta comprobado sobre datos reales: los tres agregados de la cartera de
referencia (roboadvisor, Urbanitae, bots) son de una sola clase cada uno, asi que el
look-through no mueve sus pesos por clase. Lo que no permite es la pregunta siguiente:
dentro de renta variable, como estoy diversificado; que solapamiento hay entre el
indexado global del plan de pensiones y el fondo US del roboadvisor; cuanto pesa Espana
en mi inmobiliario.

`PositionClassBreakdown` cubre hoy el caso minimo —repartir una posicion entre clases— y
se mantiene, pero es manual y se queda corto: los pesos reales se mueven solos con el
mercado y el detalle interesante esta dentro de la clase, no entre clases.

## Area
`backend`

## Stack
`core`

## Scope

### Entrega 1 — exposicion declarada (hecha)
1. Exposicion por posicion y dimension —geografia, sector, vehiculo— con el peso de cada
   bucket dentro de la posicion y la fecha de la ficha de la que sale el dato.
2. Agregado de cartera calculado **sobre lo declarado**, con la cobertura al lado y la
   ficha mas antigua que lo sostiene.
3. Concentracion: peso de las cinco mayores y numero equivalente de posiciones iguales
   (`1/HHI`), mas el indice 0-1 normalizado contra el reparto perfecto de esas mismas
   posiciones.
4. Solapamiento de exposicion entre pares, con cuanto dinero esta expuesto dos veces a lo
   mismo. Suelo del 25% para no convertir una senal en una lista.
5. Declarar `insufficient` cuando nadie ha declarado una dimension, en vez de dibujar un
   grafico incompleto como si fuera completo.

### Entrega 2 — tenencias (pendiente)
6. Tenencias por posicion: instrumento subyacente, peso y fecha de referencia.
7. Derivar el reparto por clase y las dimensiones desde las tenencias cuando existan,
   dejando la declaracion manual como entrada para quien no las tenga.
8. Solapamiento exacto por subyacente compartido, que la exposicion declarada no puede
   dar: dos fondos con el mismo reparto geografico pueden tener acciones distintas.
9. Importador de holdings por emisor (iShares, Amundi, Vanguard) si la entrega 2 se
   ejecuta: es lo unico automatizable sin licencia de datos.

## Fuera de alcance
1. Conectores de broker que descarguen las tenencias solos.
2. Correlacion entre posiciones. Necesita series de rentabilidad, y la mitad de la cartera
   —crowdfunding, crowdlending— no cotiza ni las tendra: no es una limitacion del software
   sino del activo. Un activo iliquido parece menos volatil solo porque nadie le pone
   precio a diario, y construir correlaciones sobre eso subestima el riesgo.

## Plan
1. Modelar tenencias con vigencia y su cobertura por posicion.
2. Derivar clase y dimensiones de exposicion, con el fallback manual intacto.
3. Anadir concentracion y solapamiento sobre el read model de composicion.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio
```

## Required Documentation Updates
- [ ] `core/docs/architecture/architecture.md` si cambia el read model de composicion.
- [ ] `docs/architecture/api-registry.md`.
- [ ] `docs/frontend/domain-map.md`.
- [ ] Project status de Core y SaaS.

## Risks
El mantenimiento manual de pesos envejece rapido y una exposicion desactualizada engana
mas que no tenerla. La cobertura y su fecha tienen que viajar con el dato.

## Completion Criteria

### Entrega 1
- [x] La exposicion declara su cobertura y emite `insufficient` cuando no llega.
- [x] El reparto se calcula sobre lo declarado, no sobre el total.
- [x] El solapamiento de exposicion entre posiciones es visible, con el dinero expuesto
      dos veces a lo mismo.
- [x] Concentracion legible: numero equivalente de posiciones iguales.
- [x] Tests, docs y commit completados. 176 tests de portfolio en verde.

### Entrega 2
- [x] Una posicion con tenencias reparte su valor por ellas; sin tenencias se comporta como hoy.
- [x] El solapamiento por subyacente compartido es visible.
- [x] Tests y docs completados; el commit se crea al cerrar el bloque integrado Core/SaaS.

## Nota de alcance (2026-08-20)

La entrega 1 se adelanto por delante de la fase 7 a peticion del usuario: lo que bloquea
decidir hoy es no saber como esta repartida la cartera por dentro, no medir el sistema
contra un benchmark.

Los pesos se declaran a mano y eso no es un escalon provisional. El ISIN sirve para poner
precio, no para saber que hay dentro de un fondo: son datasets distintos y el segundo no
lo regala ningun proveedor a partir del identificador. Lo automatizable sin licencia es el
CSV de holdings que publican los emisores de ETF, que es trabajo por emisor y solo cubre
una parte de esta cartera —el roboadvisor y el plan seguirian siendo manuales—.
