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
1. Tenencias por posicion: instrumento subyacente, peso y fecha de referencia.
2. Derivar el reparto por clase desde las tenencias cuando existan, dejando
   `PositionClassBreakdown` como entrada manual para quien no las tenga.
3. Dimensiones de exposicion sobre las tenencias: geografia, sector y tipo de vehiculo.
4. Metricas de concentracion: peso de las N mayores y un indice de diversificacion
   comparable al que ya calcula `plan/services_foundations.py`.
5. Detectar solapamiento entre posiciones que comparten instrumento subyacente.
6. Declarar `insufficient` cuando la cobertura de tenencias no llegue, en vez de publicar
   una exposicion incompleta como si fuera completa.

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
- [ ] Una posicion con tenencias reparte su valor por ellas; sin tenencias se comporta como hoy.
- [ ] La exposicion declara su cobertura y emite `insufficient` cuando no llega.
- [ ] El solapamiento entre posiciones que comparten subyacente es visible.
- [ ] Tests, docs y commit completados.
