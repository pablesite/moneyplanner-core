"""Riesgo de la cartera: volatilidad, caida maxima, mejor/peor periodo y Sharpe.

Tres convenciones fijan todo lo demas, y conviene decirlas antes que ninguna formula
porque son la diferencia entre una cifra comparable y una cifra inventada:

1. **Calendario mensual de fin de mes.** La serie de la cartera ya se construye asi
   (`timeline_dates`), y los tramos parciales de los extremos —del dia elegido al primer
   fin de mes, y del ultimo fin de mes al dia elegido— quedan **fuera** de la estadistica:
   un tramo de nueve dias tratado como un mes deforma la volatilidad hacia arriba.
2. **Anualizacion por raiz del tiempo**: 12 para el retorno, raiz de 12 para la
   desviacion. Es la convencion estandar para series mensuales y la que se asume al
   comparar con cualquier ficha de fondo.
3. **Rentabilidad, no valor.** Todo se calcula sobre la serie de rentabilidades encadenada
   (TWR), nunca sobre el valor: una aportacion sube el valor sin ser una recuperacion, y
   medir la caida maxima sobre el valor convertiria cada aportacion en una mejora.

Y una regla que manda sobre las tres: sin observaciones suficientes no se publica un
numero, se publica `insufficient` con su motivo. Una volatilidad de tres meses no es una
volatilidad pequena, es una que no se sabe.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

ZERO = Decimal("0")
ONE = Decimal("1")
# Un ano de observaciones mensuales. Por debajo, la desviacion depende mas de que meses
# tocaron que de la cartera.
MIN_ANNUALIZED_OBSERVATIONS = 12
# La caida maxima es una lectura del recorrido, no un estimador estadistico, asi que se
# sostiene con muchas menos observaciones.
MIN_DRAWDOWN_OBSERVATIONS = 3
PERIODS_PER_YEAR = 12
FLAT_SERIES_TOLERANCE = Decimal("1e-12")


@dataclass(frozen=True)
class PeriodReturn:
    """La rentabilidad de un tramo mensual completo, o su ausencia declarada."""

    label: str
    value: Decimal | None


def insufficient(reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": "insufficient", "value": None, "reason": reason, **extra}


def available(value: Decimal, **extra: Any) -> dict[str, Any]:
    return {"status": "available", "value": str(value), **extra}


def _sqrt(value: Decimal) -> Decimal:
    if value <= ZERO:
        return ZERO
    return value.sqrt()


def usable_returns(series: list[PeriodReturn]) -> list[Decimal]:
    return [row.value for row in series if row.value is not None]


def longest_complete_run(series: list[PeriodReturn]) -> list[PeriodReturn]:
    """El tramo contiguo mas largo sin huecos, que es sobre el que se puede calcular.

    Un solo mes sin valoracion en dieciocho no puede dejar muda a toda la pantalla, pero
    saltarselo tampoco vale: encadenar enero con marzo trata dos meses como uno y deforma
    cualquier cifra anualizada. La salida honesta es medir sobre el tramo que si es
    continuo y decir cual es y que meses se quedaron fuera.
    """
    best: list[PeriodReturn] = []
    current: list[PeriodReturn] = []
    for row in series:
        if row.value is None:
            current = []
            continue
        current.append(row)
        if len(current) > len(best):
            best = list(current)
    return best


def volatility(series: list[PeriodReturn]) -> dict[str, Any]:
    """Desviacion tipica anualizada de las rentabilidades mensuales.

    Muestral (n-1): la serie es una muestra de lo que la cartera puede hacer, no la
    poblacion entera de sus meses posibles.
    """
    values = usable_returns(series)
    # El hueco se declara antes que el recuento: son dos problemas distintos y se
    # arreglan de forma distinta —uno se espera, el otro se rellena—, y decir "faltan
    # meses" cuando lo que falta es una valoracion manda al usuario al sitio equivocado.
    if len(values) != len(series):
        return insufficient("gaps_in_series", observations=len(values), expected=len(series))
    if len(values) < MIN_ANNUALIZED_OBSERVATIONS:
        return insufficient(
            "not_enough_observations",
            observations=len(values),
            required=MIN_ANNUALIZED_OBSERVATIONS,
        )
    mean = sum(values, ZERO) / Decimal(len(values))
    variance = sum(((row - mean) ** 2 for row in values), ZERO) / Decimal(len(values) - 1)
    return available(
        _sqrt(variance) * _sqrt(Decimal(PERIODS_PER_YEAR)),
        observations=len(values),
        frequency="monthly",
    )


def max_drawdown(series: list[PeriodReturn]) -> dict[str, Any]:
    """La peor caida entre un maximo y el valle posterior, sobre el indice de rentabilidad.

    Se mide sobre el crecimiento acumulado de 1 €, que es lo que aisla la caida de las
    aportaciones. Devuelve tambien cuando empezo y cuando toco fondo, porque una caida sin
    fechas no se puede interpretar.
    """
    values = usable_returns(series)
    if len(values) != len(series):
        return insufficient("gaps_in_series", observations=len(values), expected=len(series))
    if len(values) < MIN_DRAWDOWN_OBSERVATIONS:
        return insufficient(
            "not_enough_observations",
            observations=len(values),
            required=MIN_DRAWDOWN_OBSERVATIONS,
        )
    index = ONE
    peak = ONE
    peak_label = series[0].label
    worst = ZERO
    worst_from: str | None = None
    worst_to: str | None = None
    for row in series:
        assert row.value is not None
        index *= ONE + row.value
        if index > peak:
            peak = index
            peak_label = row.label
            continue
        drop = index / peak - ONE
        if drop < worst:
            worst = drop
            worst_from = peak_label
            worst_to = row.label
    return available(worst, peak_period=worst_from, trough_period=worst_to)


def best_and_worst(series: list[PeriodReturn]) -> dict[str, Any]:
    """El mejor y el peor mes, con su etiqueta: sin ella la cifra no dice nada."""
    rows = [row for row in series if row.value is not None]
    if not rows:
        return {
            "best": insufficient("not_enough_observations", observations=0),
            "worst": insufficient("not_enough_observations", observations=0),
        }
    best = max(rows, key=lambda row: row.value or ZERO)
    worst = min(rows, key=lambda row: row.value or ZERO)
    return {
        "best": available(best.value or ZERO, period=best.label),
        "worst": available(worst.value or ZERO, period=worst.label),
    }


def annualized_return(series: list[PeriodReturn]) -> dict[str, Any]:
    """Rentabilidad media anualizada de los tramos completos, encadenada."""
    values = usable_returns(series)
    if len(values) != len(series):
        return insufficient("gaps_in_series", observations=len(values), expected=len(series))
    if len(values) < MIN_ANNUALIZED_OBSERVATIONS:
        return insufficient(
            "not_enough_observations",
            observations=len(values),
            required=MIN_ANNUALIZED_OBSERVATIONS,
        )
    index = ONE
    for value in values:
        index *= ONE + value
    years = Decimal(len(values)) / Decimal(PERIODS_PER_YEAR)
    if index <= ZERO:
        # Una cartera que se ha ido a cero no tiene tasa anual compuesta que la describa.
        return insufficient("non_positive_growth", observations=len(values))
    growth = float(index) ** (1.0 / float(years))
    return available(Decimal(str(growth)) - ONE, observations=len(values), frequency="monthly")


def sharpe(
    *,
    series: list[PeriodReturn],
    risk_free_rate: Decimal,
) -> dict[str, Any]:
    """Exceso sobre el activo sin riesgo por unidad de volatilidad.

    Se calcula sobre el exceso mensual —cada mes menos su parte de la tasa sin riesgo— y
    no restando dos cifras ya anualizadas: restar despues mezcla dos anualizaciones
    distintas y el resultado deja de ser comparable con el de nadie.
    """
    values = usable_returns(series)
    if len(values) != len(series):
        return insufficient("gaps_in_series", observations=len(values), expected=len(series))
    if len(values) < MIN_ANNUALIZED_OBSERVATIONS:
        return insufficient(
            "not_enough_observations",
            observations=len(values),
            required=MIN_ANNUALIZED_OBSERVATIONS,
        )
    monthly_free = risk_free_rate / Decimal(PERIODS_PER_YEAR)
    excess = [row - monthly_free for row in values]
    mean = sum(excess, ZERO) / Decimal(len(excess))
    variance = sum(((row - mean) ** 2 for row in excess), ZERO) / Decimal(len(excess) - 1)
    deviation = _sqrt(variance)
    # Sin variacion no hay ratio: dividir por casi cero no es un Sharpe enorme, es que la
    # pregunta no aplica. El umbral existe porque la resta de la tasa mensual deja restos
    # de redondeo en Decimal, y una serie plana no debe salir por ellos como si variara.
    if deviation <= FLAT_SERIES_TOLERANCE:
        return insufficient("no_variation", observations=len(values))
    ratio = (mean / deviation) * _sqrt(Decimal(PERIODS_PER_YEAR))
    return available(
        ratio,
        observations=len(values),
        risk_free_rate=str(risk_free_rate),
        frequency="monthly",
    )


def advanced_metric_interfaces() -> dict[str, Any]:
    """Lo que vendra, con su forma ya fijada y su motivo de ausencia.

    Se publican apagadas a proposito: quien consuma la API ve el contrato completo desde
    el principio, y anadirlas mas adelante no rompe a nadie. Todas necesitan una serie de
    mercado por instrumento que hoy no existe para la parte iliquida de la cartera.
    """
    reason = "not_implemented"
    return {
        "beta": {"status": "unavailable", "value": None, "reason": reason, "against": None},
        "correlation": {"status": "unavailable", "matrix": None, "reason": reason},
        "value_at_risk": {
            "status": "unavailable",
            "value": None,
            "reason": reason,
            "confidence": None,
            "horizon_days": None,
        },
        "risk_contribution": {"status": "unavailable", "by_position": None, "reason": reason},
    }
