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
# Beta, correlacion y una cola historica no son lecturas de tres o cuatro meses. El mismo
# minimo anual evita que una coincidencia puntual se presente como una propiedad estable.
MIN_ADVANCED_OBSERVATIONS = 12
MIN_HISTORICAL_VAR_OBSERVATIONS = 24
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


def paired_complete_run(
    left: list[PeriodReturn], right: list[PeriodReturn]
) -> list[tuple[PeriodReturn, PeriodReturn]]:
    """Tramo comun mas largo de dos series mensuales, sin saltar meses ausentes."""
    by_label = {row.label: row for row in right}
    best: list[tuple[PeriodReturn, PeriodReturn]] = []
    current: list[tuple[PeriodReturn, PeriodReturn]] = []
    for row in left:
        other = by_label.get(row.label)
        if row.value is None or other is None or other.value is None:
            current = []
            continue
        current.append((row, other))
        if len(current) > len(best):
            best = list(current)
    return best


def _paired_values(
    pairs: list[tuple[PeriodReturn, PeriodReturn]],
) -> tuple[list[Decimal], list[Decimal]]:
    return (
        [left.value for left, _ in pairs if left.value is not None],
        [right.value for _, right in pairs if right.value is not None],
    )


def beta(
    pairs: list[tuple[PeriodReturn, PeriodReturn]], *, against: dict[str, Any]
) -> dict[str, Any]:
    """Beta mensual contra un indice con el mismo calendario y moneda."""
    if len(pairs) < MIN_ADVANCED_OBSERVATIONS:
        return insufficient(
            "not_enough_observations",
            observations=len(pairs),
            required=MIN_ADVANCED_OBSERVATIONS,
            against=against,
        )
    portfolio, market = _paired_values(pairs)
    market_mean = sum(market, ZERO) / Decimal(len(market))
    market_variance = sum(((value - market_mean) ** 2 for value in market), ZERO) / Decimal(
        len(market) - 1
    )
    if market_variance <= FLAT_SERIES_TOLERANCE:
        return insufficient("no_variation", observations=len(pairs), against=against)
    portfolio_mean = sum(portfolio, ZERO) / Decimal(len(portfolio))
    covariance = sum(
        (
            (portfolio[index] - portfolio_mean) * (market[index] - market_mean)
            for index in range(len(portfolio))
        ),
        ZERO,
    ) / Decimal(len(portfolio) - 1)
    return available(covariance / market_variance, observations=len(pairs), against=against)


def correlation(
    pairs: list[tuple[PeriodReturn, PeriodReturn]], *, against: dict[str, Any]
) -> dict[str, Any]:
    """Correlacion de Pearson entre cartera e indice, sobre meses comparables."""
    if len(pairs) < MIN_ADVANCED_OBSERVATIONS:
        return insufficient(
            "not_enough_observations",
            observations=len(pairs),
            required=MIN_ADVANCED_OBSERVATIONS,
            against=against,
        )
    portfolio, market = _paired_values(pairs)
    portfolio_mean = sum(portfolio, ZERO) / Decimal(len(portfolio))
    market_mean = sum(market, ZERO) / Decimal(len(market))
    portfolio_variance = sum(
        ((value - portfolio_mean) ** 2 for value in portfolio), ZERO
    ) / Decimal(len(portfolio) - 1)
    market_variance = sum(((value - market_mean) ** 2 for value in market), ZERO) / Decimal(
        len(market) - 1
    )
    denominator = _sqrt(portfolio_variance) * _sqrt(market_variance)
    if denominator <= FLAT_SERIES_TOLERANCE:
        return insufficient("no_variation", observations=len(pairs), against=against)
    covariance = sum(
        (
            (portfolio[index] - portfolio_mean) * (market[index] - market_mean)
            for index in range(len(portfolio))
        ),
        ZERO,
    ) / Decimal(len(portfolio) - 1)
    return available(covariance / denominator, observations=len(pairs), against=against)


def historical_value_at_risk(
    series: list[PeriodReturn], *, confidence: Decimal = Decimal("0.95")
) -> dict[str, Any]:
    """Perdida historica mensual a un nivel de confianza, expresada como porcentaje.

    Es una VaR de cola empirica, no una promesa de perdida maxima. Requiere dos anos de
    meses completos: con doce puntos el percentil 95 seria practicamente solo el peor mes.
    """
    values = usable_returns(series)
    if len(values) != len(series):
        return insufficient("gaps_in_series", observations=len(values), expected=len(series))
    if len(values) < MIN_HISTORICAL_VAR_OBSERVATIONS:
        return insufficient(
            "not_enough_observations",
            observations=len(values),
            required=MIN_HISTORICAL_VAR_OBSERVATIONS,
        )
    ordered = sorted(values)
    rank = (Decimal(len(ordered) - 1)) * (ONE - confidence)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    quantile = ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - Decimal(lower))
    return available(
        max(ZERO, -quantile),
        observations=len(values),
        confidence=str(confidence),
        horizon_days=21,
        frequency="monthly",
    )


def _sample_covariance(left: list[Decimal], right: list[Decimal]) -> Decimal:
    left_mean = sum(left, ZERO) / Decimal(len(left))
    right_mean = sum(right, ZERO) / Decimal(len(right))
    return sum(
        ((left[index] - left_mean) * (right[index] - right_mean) for index in range(len(left))),
        ZERO,
    ) / Decimal(len(left) - 1)


def position_risk_analysis(
    *, positions: list[dict[str, Any]], total_value: Decimal
) -> dict[str, dict[str, Any]]:
    """Correlacion y contribucion a volatilidad sobre el universo realmente medible.

    `positions` ya llega filtrado a una ventana comun completa. La contribucion no intenta
    repartir el P&L historico: es un modelo de volatilidad futura condicionada a los pesos
    de cierre actuales y a la covarianza observada en esa misma ventana.
    """
    empty_correlation = {
        "status": "insufficient",
        "matrix": [],
        "pairs": [],
        "reason": "not_enough_positions",
    }
    empty_contribution = {
        "status": "insufficient",
        "by_position": [],
        "reason": "not_enough_positions",
    }
    if not positions:
        return {"position_correlation": empty_correlation, "risk_contribution": empty_contribution}

    observations = len(positions[0]["series"])
    included_value = sum((row["value"] for row in positions), ZERO)
    coverage = ZERO if total_value <= ZERO else included_value / total_value
    metadata = {
        "observations": observations,
        "required": MIN_ADVANCED_OBSERVATIONS,
        "included_positions": len(positions),
        "included_value": str(included_value),
        "total_value": str(total_value),
        "coverage": str(coverage),
    }
    if observations < MIN_ADVANCED_OBSERVATIONS:
        reason = "not_enough_observations"
        return {
            "position_correlation": {**empty_correlation, **metadata, "reason": reason},
            "risk_contribution": {**empty_contribution, **metadata, "reason": reason},
        }

    values = {row["position_id"]: [point.value for point in row["series"]] for row in positions}
    # La entrada se construye solo con series completas; este assert protege que un cambio
    # futuro no convierta un hueco en un cero dentro de una matriz estadistica.
    assert all(all(value is not None for value in series) for series in values.values())
    decimal_values: dict[int, list[Decimal]] = {
        key: [value for value in series if value is not None] for key, series in values.items()
    }
    covariance = {
        (left["position_id"], right["position_id"]): _sample_covariance(
            decimal_values[left["position_id"]], decimal_values[right["position_id"]]
        )
        for left in positions
        for right in positions
    }

    matrix = []
    pairs = []
    for left in positions:
        left_id = left["position_id"]
        left_variance = covariance[(left_id, left_id)]
        correlations = []
        for right in positions:
            right_id = right["position_id"]
            right_variance = covariance[(right_id, right_id)]
            denominator = _sqrt(left_variance) * _sqrt(right_variance)
            value = (
                None
                if denominator <= FLAT_SERIES_TOLERANCE
                else covariance[(left_id, right_id)] / denominator
            )
            correlations.append(
                {"position_id": right_id, "value": None if value is None else str(value)}
            )
            if right_id > left_id and value is not None:
                pairs.append(
                    {
                        "left_id": left_id,
                        "left_name": left["name"],
                        "right_id": right_id,
                        "right_name": right["name"],
                        "value": str(value),
                    }
                )
        matrix.append({"position_id": left_id, "name": left["name"], "correlations": correlations})
    pairs.sort(key=lambda row: abs(Decimal(row["value"])), reverse=True)

    correlation_result: dict[str, Any] = {
        "status": "available" if len(positions) >= 2 else "insufficient",
        "matrix": matrix,
        "pairs": pairs,
        **metadata,
    }
    if len(positions) < 2:
        correlation_result["reason"] = "not_enough_positions"

    if included_value <= ZERO:
        return {
            "position_correlation": correlation_result,
            "risk_contribution": {**empty_contribution, **metadata, "reason": "no_value"},
        }
    weights = {row["position_id"]: row["value"] / included_value for row in positions}
    covariance_weight = {
        row["position_id"]: sum(
            (
                covariance[(row["position_id"], other["position_id"])]
                * weights[other["position_id"]]
                for other in positions
            ),
            ZERO,
        )
        for row in positions
    }
    portfolio_variance = sum(
        (weights[row["position_id"]] * covariance_weight[row["position_id"]] for row in positions),
        ZERO,
    )
    if portfolio_variance <= FLAT_SERIES_TOLERANCE:
        return {
            "position_correlation": correlation_result,
            "risk_contribution": {**empty_contribution, **metadata, "reason": "no_variation"},
        }
    portfolio_deviation = _sqrt(portfolio_variance)
    contributions = [
        {
            "position_id": row["position_id"],
            "name": row["name"],
            "weight": str(weights[row["position_id"]]),
            "contribution": str(
                weights[row["position_id"]]
                * covariance_weight[row["position_id"]]
                / portfolio_variance
            ),
            "annualized_volatility_contribution": str(
                weights[row["position_id"]]
                * covariance_weight[row["position_id"]]
                / portfolio_deviation
                * _sqrt(Decimal(PERIODS_PER_YEAR))
            ),
        }
        for row in positions
    ]
    contributions.sort(key=lambda row: Decimal(row["contribution"]), reverse=True)
    return {
        "position_correlation": correlation_result,
        "risk_contribution": {
            "status": "available",
            "by_position": contributions,
            "model_volatility": str(portfolio_deviation * _sqrt(Decimal(PERIODS_PER_YEAR))),
            **metadata,
        },
    }


def advanced_metric_interfaces() -> dict[str, Any]:
    """Forma estable para metricas que requieren un indice o series por posicion."""
    reason = "benchmark_unavailable"
    return {
        "beta": {"status": "unavailable", "value": None, "reason": reason, "against": None},
        "correlation": {
            "status": "unavailable",
            "value": None,
            "against": None,
            "reason": reason,
        },
        "value_at_risk": {
            "status": "unavailable",
            "value": None,
            "reason": reason,
            "confidence": None,
            "horizon_days": None,
        },
        "risk_contribution": {
            "status": "unavailable",
            "by_position": None,
            "reason": "position_return_series_unavailable",
        },
        "position_correlation": {
            "status": "unavailable",
            "matrix": [],
            "pairs": [],
            "reason": "position_return_series_unavailable",
        },
    }
