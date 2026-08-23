"""Riesgo contra calculos independientes.

Los valores esperados no se recalculan con las mismas funciones que se prueban: salen de
`statistics` y `math` de la libreria estandar sobre la misma serie, que es lo unico que
convierte estos tests en una comprobacion y no en un espejo.
"""

import math
import statistics
from decimal import Decimal

from django.test import TestCase, override_settings

from portfolio.benchmark import DEFAULT_RISK_FREE_RATE, resolve_risk_free_rate
from portfolio.risk import (
    MIN_ANNUALIZED_OBSERVATIONS,
    MIN_HISTORICAL_VAR_OBSERVATIONS,
    PeriodReturn,
    advanced_metric_interfaces,
    annualized_return,
    beta,
    best_and_worst,
    correlation,
    historical_value_at_risk,
    longest_complete_run,
    max_drawdown,
    paired_complete_run,
    sharpe,
    volatility,
)

MONTHLY = [
    "0.02",
    "-0.01",
    "0.03",
    "0.00",
    "-0.04",
    "0.05",
    "0.01",
    "-0.02",
    "0.02",
    "0.03",
    "-0.01",
    "0.04",
]


def series(values=None, *, gaps: set[int] | None = None) -> list[PeriodReturn]:
    rows = values if values is not None else MONTHLY
    gaps = gaps or set()
    return [
        PeriodReturn(f"2026-{index + 1:02d}", None if index in gaps else Decimal(value))
        for index, value in enumerate(rows)
    ]


def as_floats(values=None) -> list[float]:
    return [float(row) for row in (values if values is not None else MONTHLY)]


class RiskMetricsTests(TestCase):
    """Convenciones: mensual, anualizacion por raiz del tiempo, muestral."""

    def test_volatility_matches_an_independent_calculation(self):
        expected = statistics.stdev(as_floats()) * math.sqrt(12)

        result = volatility(series())

        self.assertEqual(result["status"], "available")
        self.assertAlmostEqual(float(result["value"]), expected, places=10)
        self.assertEqual(result["frequency"], "monthly")

    def test_annualized_return_matches_an_independent_calculation(self):
        index = 1.0
        for row in as_floats():
            index *= 1 + row
        expected = index ** (12 / len(MONTHLY)) - 1

        result = annualized_return(series())

        self.assertEqual(result["status"], "available")
        self.assertAlmostEqual(float(result["value"]), expected, places=8)

    def test_sharpe_matches_an_independent_calculation(self):
        monthly_free = 0.02 / 12
        excess = [row - monthly_free for row in as_floats()]
        expected = (statistics.mean(excess) / statistics.stdev(excess)) * math.sqrt(12)

        result = sharpe(series=series(), risk_free_rate=Decimal("0.02"))

        self.assertEqual(result["status"], "available")
        self.assertAlmostEqual(float(result["value"]), expected, places=8)
        self.assertEqual(result["risk_free_rate"], "0.02")

    def test_drawdown_reads_the_growth_index_not_the_value(self):
        # -4% en un solo mes es la peor caida de la serie, y se identifica por sus fechas.
        result = max_drawdown(series())

        self.assertEqual(result["status"], "available")
        self.assertAlmostEqual(float(result["value"]), -0.04, places=10)
        self.assertEqual(result["trough_period"], "2026-05")

    def test_drawdown_chains_consecutive_falls(self):
        result = max_drawdown(series(["0.10", "-0.05", "-0.05", "0.01"]))

        expected = (1.10 * 0.95 * 0.95) / 1.10 - 1
        self.assertAlmostEqual(float(result["value"]), expected, places=10)
        self.assertEqual(result["peak_period"], "2026-01")
        self.assertEqual(result["trough_period"], "2026-03")

    def test_best_and_worst_carry_their_month(self):
        result = best_and_worst(series())

        self.assertEqual(result["best"]["period"], "2026-06")
        self.assertEqual(result["worst"]["period"], "2026-05")
        self.assertAlmostEqual(float(result["best"]["value"]), 0.05, places=10)

    def test_a_short_history_is_insufficient_not_optimistic(self):
        short = series(MONTHLY[:6])

        self.assertEqual(volatility(short)["status"], "insufficient")
        self.assertEqual(volatility(short)["reason"], "not_enough_observations")
        self.assertEqual(volatility(short)["required"], MIN_ANNUALIZED_OBSERVATIONS)
        self.assertEqual(annualized_return(short)["status"], "insufficient")
        self.assertEqual(annualized_return(short)["required"], MIN_ANNUALIZED_OBSERVATIONS)
        self.assertEqual(
            sharpe(series=short, risk_free_rate=Decimal("0.02"))["status"], "insufficient"
        )
        # La caida maxima describe el recorrido y se sostiene con menos historia.
        self.assertEqual(max_drawdown(short)["status"], "available")

    def test_a_gap_invalidates_the_series_instead_of_being_skipped(self):
        # Saltarse un mes sin dato fabricaria continuidad: la serie dejaria de describir
        # el periodo que dice describir.
        with_gap = series(gaps={4})

        self.assertEqual(volatility(with_gap)["reason"], "gaps_in_series")
        self.assertEqual(max_drawdown(with_gap)["reason"], "gaps_in_series")
        self.assertEqual(annualized_return(with_gap)["reason"], "gaps_in_series")

    def test_a_flat_series_has_no_sharpe_rather_than_an_infinite_one(self):
        flat = series(["0.01"] * 12)

        result = sharpe(series=flat, risk_free_rate=Decimal("0.02"))

        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "no_variation")

    def test_the_longest_uninterrupted_stretch_is_what_gets_measured(self):
        # Un mes sin valoracion en dieciocho no puede dejar muda la pantalla entera, y
        # saltarselo tampoco vale: se mide el tramo que si es continuo.
        rows = series(gaps={1, 9})

        run = longest_complete_run(rows)

        self.assertEqual(
            [row.label for row in run], [f"2026-{index:02d}" for index in range(3, 10)]
        )

    def test_a_series_without_holes_is_measured_whole(self):
        self.assertEqual(len(longest_complete_run(series())), len(MONTHLY))

    def test_advanced_metrics_publish_their_shape_while_the_index_is_unavailable(self):
        interfaces = advanced_metric_interfaces()

        self.assertEqual(
            sorted(interfaces), ["beta", "correlation", "risk_contribution", "value_at_risk"]
        )
        for row in interfaces.values():
            self.assertEqual(row["status"], "unavailable")
        self.assertEqual(interfaces["beta"]["reason"], "benchmark_unavailable")
        self.assertEqual(
            interfaces["risk_contribution"]["reason"], "position_return_series_unavailable"
        )

    def test_beta_and_correlation_use_only_a_contiguous_common_run(self):
        portfolio = series()
        market = [
            PeriodReturn(row.label, (row.value or Decimal("0")) * Decimal("0.5"))
            for row in portfolio
        ]
        pairs = paired_complete_run(portfolio, market)

        beta_result = beta(pairs, against={"id": 7, "name": "Indice prueba"})
        correlation_result = correlation(pairs, against={"id": 7, "name": "Indice prueba"})

        self.assertEqual(beta_result["status"], "available")
        self.assertAlmostEqual(float(beta_result["value"]), 2.0, places=10)
        self.assertEqual(correlation_result["status"], "available")
        self.assertAlmostEqual(float(correlation_result["value"]), 1.0, places=10)
        self.assertEqual(correlation_result["against"]["name"], "Indice prueba")

    def test_historical_var_requires_two_full_years_and_is_a_loss_percentage(self):
        values = [Decimal("0.01")] * (MIN_HISTORICAL_VAR_OBSERVATIONS - 1)
        short = [PeriodReturn(f"2024-{index:02d}", value) for index, value in enumerate(values, 1)]
        self.assertEqual(historical_value_at_risk(short)["reason"], "not_enough_observations")

        full = [
            PeriodReturn(f"2025-{index:02d}", Decimal("-0.04") if index <= 3 else Decimal("0.01"))
            for index in range(1, MIN_HISTORICAL_VAR_OBSERVATIONS + 1)
        ]
        result = historical_value_at_risk(full)

        self.assertEqual(result["status"], "available")
        self.assertEqual(result["confidence"], "0.95")
        self.assertEqual(result["horizon_days"], 21)
        self.assertGreater(float(result["value"]), 0)


class RiskFreeRateTests(TestCase):
    def test_the_rate_is_configurable(self):
        with override_settings(PORTFOLIO_RISK_FREE_RATE="0.035"):
            self.assertEqual(resolve_risk_free_rate(), Decimal("0.035"))

    def test_an_unreadable_rate_falls_back_to_the_documented_default(self):
        with override_settings(PORTFOLIO_RISK_FREE_RATE="dos por ciento"):
            self.assertEqual(resolve_risk_free_rate(), DEFAULT_RISK_FREE_RATE)
