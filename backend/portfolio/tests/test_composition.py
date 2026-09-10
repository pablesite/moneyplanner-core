from datetime import date
from decimal import Decimal

from django.test import TestCase

from portfolio.allocation import build_allocation
from portfolio.exposure import build_exposure
from portfolio.models import Instrument, PositionClassBreakdown, PositionHolding, PositionValuation
from portfolio.performance import build_portfolio_positions

from .test_allocation import TODAY, AllocationFixture


class ClassCompositionTests(AllocationFixture, TestCase):
    def hold(self, position, asset_class, percent, *, observed_on=TODAY, name=None):
        return PositionHolding.objects.create(
            position=position,
            underlying_name=name or asset_class,
            asset_class=asset_class,
            percent=Decimal(percent),
            observed_on=observed_on,
        )

    def read_classes(self, *, on_date=TODAY):
        allocation = build_allocation(
            portfolio=self.portfolio, ownership=self.mine, on_date=on_date
        )
        exposure = build_exposure(portfolio=self.portfolio, on_date=on_date)
        return allocation, exposure["classes"]

    def assert_values(self, allocation, exposure, expected):
        self.assertEqual(
            {row["asset_class"]: Decimal(row["value"]) for row in allocation["by_class"]},
            expected,
        )
        self.assertEqual(
            {row["asset_class"]: Decimal(row["value"]) for row in exposure["rows"]}, expected
        )
        self.assertEqual(sum(expected.values()), Decimal(allocation["total_value"]))

    def test_holdings_override_manual_split_in_all_three_composition_reads(self):
        position = self.create_position("Mixto", Decimal("10000"))
        PositionClassBreakdown.objects.create(
            position=position, asset_class="equity", percent=Decimal("100")
        )
        self.hold(position, "equity", "60")
        self.hold(position, "fixed_income", "40")

        allocation, exposure = self.read_classes()
        self.assert_values(
            allocation, exposure, {"equity": Decimal("6000"), "fixed_income": Decimal("4000")}
        )
        row = allocation["by_position"][0]
        self.assertEqual(row["composition_source"], "holdings")
        self.assertEqual(row["composition_observed_on"], TODAY.isoformat())
        self.assertEqual(Decimal(row["class_covered_percent"]), Decimal("100"))
        self.assertEqual(
            {r["asset_class"]: Decimal(r["value"]) for r in row["class_breakdown"]},
            {"equity": Decimal("6000"), "fixed_income": Decimal("4000")},
        )
        positions = build_portfolio_positions(
            portfolio=self.portfolio, start_date=date(2024, 1, 1), end_date=TODAY
        )
        self.assertEqual(
            {r["asset_class"]: Decimal(r["percent"]) for r in positions[0]["class_breakdown"]},
            {"equity": Decimal("60"), "fixed_income": Decimal("40")},
        )

    def test_partial_factsheet_keeps_unknown_value_without_filling_from_manual_split(self):
        position = self.create_position("Parcial", Decimal("10000"))
        PositionClassBreakdown.objects.create(
            position=position, asset_class="fixed_income", percent=Decimal("100")
        )
        self.hold(position, "equity", "70")

        allocation, exposure = self.read_classes()
        self.assert_values(
            allocation, exposure, {"equity": Decimal("7000"), "unclassified": Decimal("3000")}
        )
        self.assertEqual(exposure["percent_basis"], "positions_total")
        self.assertEqual(Decimal(exposure["covered_percent"]), Decimal("70"))
        self.assertEqual(exposure["status"], "partial")
        self.assertEqual(
            {r["asset_class"]: Decimal(r["percent"]) for r in exposure["rows"]},
            {"equity": Decimal("70"), "unclassified": Decimal("30")},
        )
        self.assertEqual(self.classes(allocation)["unclassified"]["band"], "unplanned")

    def test_new_snapshot_never_rewrites_a_previous_date(self):
        position = self.create_position("Fechado", Decimal("10000"))
        self.hold(position, "equity", "100", observed_on=date(2024, 6, 1))
        self.hold(position, "fixed_income", "70", observed_on=date(2024, 12, 1))
        PositionValuation.objects.create(
            position=position,
            valuation_date=date(2024, 11, 30),
            value=Decimal("10000"),
            currency="EUR",
            source=PositionValuation.Source.MANUAL,
        )

        before, exposure_before = self.read_classes(on_date=date(2024, 11, 30))
        after, exposure_after = self.read_classes()
        self.assert_values(before, exposure_before, {"equity": Decimal("10000")})
        self.assert_values(
            after,
            exposure_after,
            {"fixed_income": Decimal("7000"), "unclassified": Decimal("3000")},
        )
        self.assertEqual(before["by_position"][0]["composition_observed_on"], "2024-06-01")

    def test_future_holdings_leave_manual_and_effective_class_fallbacks_intact(self):
        manual = self.create_position("Manual", Decimal("6000"))
        self.create_position("Clase", Decimal("4000"), asset_class="other")
        PositionClassBreakdown.objects.create(
            position=manual, asset_class="fixed_income", percent=Decimal("100")
        )
        self.hold(manual, "equity", "100", observed_on=date(2025, 1, 1))

        allocation, exposure = self.read_classes()
        self.assert_values(
            allocation, exposure, {"fixed_income": Decimal("6000"), "other": Decimal("4000")}
        )
        self.assertEqual(exposure["source"], "manual")
        self.assertEqual(Decimal(exposure["covered_percent"]), Decimal("100"))

    def test_unknown_class_is_not_reported_as_covered(self):
        self.create_position(
            "Pendiente", Decimal("10000"), asset_class=Instrument.AssetClass.UNCLASSIFIED
        )

        allocation, exposure = self.read_classes()
        self.assert_values(allocation, exposure, {"unclassified": Decimal("10000")})
        self.assertEqual(exposure["status"], "insufficient")
        self.assertEqual(Decimal(exposure["covered_percent"]), Decimal("0"))

    def test_two_holdings_of_same_class_are_added_once_and_other_ownership_stays_out(self):
        mine = self.create_position("Mía", Decimal("10000"))
        his = self.create_position("Suya", Decimal("2000"), ownership=self.his)
        self.hold(mine, "equity", "30", name="Uno")
        self.hold(mine, "equity", "70", name="Dos")
        self.hold(his, "fixed_income", "100")

        allocation = build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        self.assertEqual(list(self.classes(allocation)), ["equity"])
        self.assertEqual(Decimal(allocation["total_value"]), Decimal("10000"))
        self.assertEqual(len(allocation["by_position"][0]["class_breakdown"]), 1)

    def test_invalid_overallocated_snapshot_cannot_create_extra_money(self):
        position = self.create_position("Ficha inválida", Decimal("10000"))
        self.hold(position, "equity", "80")
        self.hold(position, "fixed_income", "80")

        allocation, exposure = self.read_classes()
        self.assert_values(allocation, exposure, {"unclassified": Decimal("10000")})
        self.assertEqual(exposure["status"], "insufficient")
