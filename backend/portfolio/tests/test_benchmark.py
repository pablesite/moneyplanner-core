"""Benchmark estrategico: la cartera contra la politica que estaba escrita cada mes."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from portfolio.benchmark import (
    build_portfolio_benchmark,
    build_portfolio_risk,
    monthly_boundaries,
)
from portfolio.models import (
    AllocationStrategy,
    AllocationTarget,
    Instrument,
    InstrumentPrice,
    PortfolioPosition,
    PositionValuation,
)

from .test_allocation import AllocationFixture

START = date(2025, 1, 31)
END = date(2026, 1, 31)


def month_ends(first: date, count: int) -> list[date]:
    rows = [first]
    while len(rows) < count:
        cursor = rows[-1]
        year = cursor.year + (1 if cursor.month == 12 else 0)
        month = 1 if cursor.month == 12 else cursor.month + 1
        following = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        rows.append(following.replace(day=1) - date.resolution)
    return rows


class BenchmarkFixture(AllocationFixture):
    """Dos clases con crecimiento constante: 1% al mes una, 2% al mes la otra.

    Con rentabilidades fijas, el benchmark compuesto es aritmetica de cabeza y cualquier
    desviacion delata la implementacion en vez de esconderse en los datos. Los valores
    compuestos se guardan con la precision del campo, asi que las ultimas cifras son ruido
    del fixture y no del motor: las comparaciones se hacen con esa holgura, que sigue
    siendo dos ordenes de magnitud menor que la diferencia entre los pesos que se prueban.
    """

    def setUp(self):
        super().setUp()
        self.boundaries = monthly_boundaries(START, END)
        self.equity = self.create_position("Fondo global", Decimal("10000"))
        self.crypto = self.create_position(
            "Bitcoin", Decimal("1000"), asset_class=Instrument.AssetClass.CRYPTO
        )
        self.grow(self.equity, Decimal("10000"), Decimal("1.01"))
        self.grow(self.crypto, Decimal("1000"), Decimal("1.02"))

    def grow(self, position, opening: Decimal, factor: Decimal) -> None:
        value = opening
        for target in self.boundaries:
            PositionValuation.objects.create(
                position=position, valuation_date=target, value=value, currency="EUR"
            )
            value = (value * factor).quantize(Decimal("0.00000001"))

    def strategy_version(self, effective_from: date, targets: dict[str, str]) -> AllocationStrategy:
        strategy = AllocationStrategy.objects.create(
            portfolio=self.portfolio, ownership=self.mine, effective_from=effective_from
        )
        for asset_class, percent in targets.items():
            AllocationTarget.objects.create(
                strategy=strategy, asset_class=asset_class, target_percent=Decimal(percent)
            )
        return strategy

    def benchmark(self, **kwargs):
        return build_portfolio_benchmark(
            portfolio=self.portfolio,
            ownership=self.mine,
            start_date=kwargs.pop("start_date", START),
            end_date=kwargs.pop("end_date", END),
            **kwargs,
        )

    def point(self, result, period: str) -> dict:
        return next(row for row in result["points"] if row["period"] == period)


class BenchmarkCalendarTests(BenchmarkFixture, TestCase):
    def test_only_full_months_take_part(self):
        # Un tramo de nueve dias no es un mes: incluirlo deformaria cualquier cifra que
        # despues se anualice.
        boundaries = monthly_boundaries(date(2025, 1, 20), date(2025, 4, 10))

        self.assertEqual(boundaries, [date(2025, 1, 31), date(2025, 2, 28), date(2025, 3, 31)])

    def test_a_period_without_two_month_ends_has_no_series(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})

        result = self.benchmark(start_date=date(2025, 2, 3), end_date=date(2025, 2, 20))

        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "not_enough_full_months")


class StrategicBenchmarkTests(BenchmarkFixture, TestCase):
    def test_the_benchmark_follows_the_policy_in_force_that_month(self):
        # Es la razon de versionar la estrategia: juzgar marzo con la politica de julio no
        # dice nada, asi que cada mes se compone con lo que estaba escrito entonces.
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})
        self.strategy_version(date(2025, 7, 1), {"equity": "50", "crypto": "50"})

        result = self.benchmark()

        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(float(self.point(result, "2025-06")["benchmark"]), 0.01, places=4)
        self.assertAlmostEqual(float(self.point(result, "2025-08")["benchmark"]), 0.015, places=4)

    def test_a_midmonth_policy_does_not_rewrite_that_month(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})
        self.strategy_version(date(2025, 7, 15), {"equity": "50", "crypto": "50"})

        result = self.benchmark()

        self.assertAlmostEqual(float(self.point(result, "2025-07")["benchmark"]), 0.01, places=4)
        self.assertAlmostEqual(float(self.point(result, "2025-08")["benchmark"]), 0.015, places=4)

    def test_cash_stays_out_of_both_sides_and_it_is_said(self):
        # La serie de la cartera son sus posiciones; el efectivo de contenedor no es de
        # ninguna clase. Incluirlo solo en el benchmark compararia dos cosas distintas.
        self.strategy_version(date(2024, 1, 1), {"equity": "45", "crypto": "45", "cash": "10"})

        result = self.benchmark()

        self.assertTrue(result["cash_excluded"])
        self.assertAlmostEqual(float(self.point(result, "2025-06")["benchmark"]), 0.015, places=4)

    def test_a_planned_class_without_products_is_declared_and_renormalized(self):
        self.strategy_version(
            date(2024, 1, 1), {"equity": "50", "crypto": "25", "real_estate": "25"}
        )

        result = self.benchmark()

        self.assertEqual(result["unreachable_classes"], ["real_estate"])
        # 50/75 al 1% y 25/75 al 2%.
        expected = (Decimal("50") * Decimal("0.01") + Decimal("25") * Decimal("0.02")) / Decimal(
            "75"
        )
        self.assertAlmostEqual(
            float(self.point(result, "2025-06")["benchmark"]), float(expected), places=4
        )

    def test_a_month_without_a_class_return_has_no_benchmark(self):
        # Una posicion seguida por unidades y sin ningun precio no tiene valor resoluble,
        # asi que su clase no tiene rentabilidad que aportar.
        self.strategy_version(
            date(2024, 1, 1), {"equity": "40", "crypto": "40", "commodities": "20"}
        )
        blind = self.create_position(
            "Oro sin precios", Decimal("500"), asset_class=Instrument.AssetClass.COMMODITIES
        )
        blind.tracking_style = PortfolioPosition.TrackingStyle.UNITS_BASED
        blind.save(update_fields=["tracking_style"])
        PositionValuation.objects.filter(position=blind).delete()

        result = self.benchmark()

        # No se reparte el peso de la clase sin dato entre las demas: eso dibujaria
        # continuidad donde no la hay. El mes se declara sin benchmark.
        self.assertIsNone(self.point(result, "2025-07")["benchmark"])
        self.assertEqual(self.point(result, "2025-07")["reason"], "class_return_unavailable")
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "months_without_benchmark")
        self.assertLess(result["months_with_benchmark"], result["months"])

    def test_without_a_policy_there_is_nothing_to_compare_against(self):
        result = self.benchmark()

        self.assertTrue(all(row["benchmark"] is None for row in result["points"]))
        self.assertTrue(all(row["reason"] == "no_strategy" for row in result["points"]))

    def test_excess_return_is_the_distance_between_both_series(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "50", "crypto": "50"})

        result = self.benchmark()

        self.assertIsNotNone(result["portfolio_return"])
        self.assertAlmostEqual(
            float(result["excess_return"]),
            float(result["portfolio_return"]) - float(result["benchmark_return"]),
            places=8,
        )

    def test_benchmark_publishes_annualized_return_for_the_same_months(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})

        result = self.benchmark()

        self.assertEqual(result["benchmark_annualized_return"]["status"], "available")
        self.assertEqual(
            result["benchmark_annualized_return"]["observations"], len(self.boundaries) - 1
        )

    def test_rolling_comparison_only_uses_equivalent_twelve_month_windows(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})

        result = self.benchmark()

        rolling = result["rolling"]
        self.assertEqual(rolling["window_months"], 12)
        self.assertEqual(len(rolling["points"]), 1)
        self.assertEqual(rolling["complete_windows"], 1)
        self.assertEqual(rolling["points"][0]["period"], "2026-01")
        self.assertIsNotNone(rolling["points"][0]["portfolio"])
        self.assertIsNotNone(rolling["points"][0]["benchmark"])


class SecondaryBenchmarkTests(BenchmarkFixture, TestCase):
    def index_instrument(self, currency: str = "EUR") -> Instrument:
        return Instrument.objects.create(
            user=self.user,
            name="MSCI World",
            identity_kind=Instrument.IdentityKind.CUSTOM,
            asset_class=Instrument.AssetClass.EQUITY,
            instrument_type=Instrument.InstrumentType.ETF,
            quote_currency=currency,
        )

    def test_an_index_is_optional_and_says_so_when_missing(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})

        result = self.benchmark()

        self.assertEqual(result["secondary"]["status"], "unavailable")
        self.assertEqual(result["secondary"]["reason"], "not_configured")

    def test_a_configured_index_is_measured_on_the_same_calendar(self):
        strategy = self.strategy_version(date(2024, 1, 1), {"equity": "100"})
        instrument = self.index_instrument()
        strategy.benchmark_instrument = instrument
        strategy.save(update_fields=["benchmark_instrument"])
        close = Decimal("100")
        for target in self.boundaries:
            InstrumentPrice.objects.create(
                instrument=instrument,
                price_date=target,
                close=close,
                currency="EUR",
                fetched_at=timezone.now(),
            )
            close = close * Decimal("1.005")

        result = self.benchmark()

        self.assertEqual(result["secondary"]["status"], "available")
        expected = float(Decimal("1.005") ** (len(self.boundaries) - 1) - 1)
        self.assertAlmostEqual(float(result["secondary"]["cumulative_return"]), expected, places=4)

    def test_an_index_in_another_currency_is_not_pretended_to_be_comparable(self):
        strategy = self.strategy_version(date(2024, 1, 1), {"equity": "100"})
        strategy.benchmark_instrument = self.index_instrument(currency="USD")
        strategy.save(update_fields=["benchmark_instrument"])

        result = self.benchmark()

        self.assertEqual(result["secondary"]["reason"], "currency_mismatch")

    def test_risk_uses_the_configured_index_for_beta_and_correlation(self):
        strategy = self.strategy_version(date(2024, 1, 1), {"equity": "100"})
        instrument = self.index_instrument()
        strategy.benchmark_instrument = instrument
        strategy.save(update_fields=["benchmark_instrument"])
        close = Decimal("100")
        factors = [
            Decimal("1.01"),
            Decimal("0.99"),
            Decimal("1.02"),
            Decimal("0.98"),
            Decimal("1.03"),
            Decimal("1.00"),
            Decimal("0.97"),
            Decimal("1.04"),
            Decimal("1.01"),
            Decimal("0.99"),
            Decimal("1.02"),
            Decimal("1.01"),
        ]
        for index, target in enumerate(self.boundaries):
            InstrumentPrice.objects.create(
                instrument=instrument,
                price_date=target,
                close=close,
                currency="EUR",
                fetched_at=timezone.now(),
            )
            if index < len(factors):
                close *= factors[index]

        result = build_portfolio_risk(
            portfolio=self.portfolio,
            ownership=self.mine,
            start_date=START,
            end_date=END,
        )

        self.assertEqual(result["advanced"]["beta"]["status"], "available")
        self.assertEqual(result["advanced"]["correlation"]["status"], "available")
        self.assertEqual(result["advanced"]["beta"]["against"]["id"], instrument.id)


class PortfolioRiskReadTests(BenchmarkFixture, TestCase):
    def risk(self, **kwargs):
        return build_portfolio_risk(
            portfolio=self.portfolio,
            ownership=self.mine,
            start_date=kwargs.pop("start_date", START),
            end_date=kwargs.pop("end_date", END),
            **kwargs,
        )

    def test_risk_reads_the_same_calendar_and_publishes_its_rate(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})

        result = self.risk()

        self.assertEqual(result["calendar"], {"frequency": "monthly", "boundaries": "month_end"})
        self.assertEqual(result["risk_free_rate"], "0.02")
        self.assertEqual(result["observations"], len(self.boundaries) - 1)

    def test_a_short_window_degrades_every_annualized_metric(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})

        result = self.risk(start_date=date(2025, 1, 31), end_date=date(2025, 5, 31))

        self.assertEqual(result["volatility"]["status"], "insufficient")
        self.assertEqual(result["sharpe"]["status"], "insufficient")
        self.assertEqual(result["max_drawdown"]["status"], "available")

    def test_the_window_actually_measured_travels_with_the_numbers(self):
        # Una volatilidad sin decir sobre cuantos meses se ha calculado no se puede juzgar.
        # Con la serie completa, la ventana medida es el periodo entero y no falta ningun
        # mes; el recorte cuando hay huecos se prueba sobre la serie en `test_risk`.
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})

        coverage = self.risk()["coverage"]

        self.assertEqual(coverage["months_used"], coverage["months_in_period"])
        self.assertEqual(coverage["months_without_data"], [])
        self.assertEqual(coverage["window"]["to"], "2026-01")

    def test_advanced_metrics_travel_declared_but_unavailable(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "100"})

        result = self.risk()

        self.assertEqual(result["advanced"]["beta"]["status"], "unavailable")
        self.assertEqual(result["advanced"]["value_at_risk"]["reason"], "not_enough_observations")

    def test_position_risk_declares_the_value_covered_by_common_series(self):
        self.strategy_version(date(2024, 1, 1), {"equity": "50", "crypto": "50"})

        advanced = self.risk()["advanced"]

        # Las dos posiciones del fixture tienen serie completa. Sus retornos son planos,
        # por lo que no hay volatilidad que repartir, pero la cobertura sigue siendo un
        # hecho del payload y no depende de que el estimador sea calculable.
        contribution = advanced["risk_contribution"]
        self.assertEqual(contribution["reason"], "no_variation")
        self.assertEqual(contribution["included_positions"], 2)
        self.assertEqual(contribution["coverage"], "1")
