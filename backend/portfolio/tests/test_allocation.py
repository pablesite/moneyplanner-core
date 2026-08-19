from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from memberships.models import FamilyMember, Ownership
from net_worth.models import Asset
from portfolio.allocation import build_allocation, resolve_strategy
from portfolio.models import (
    AllocationStrategy,
    AllocationTarget,
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioPosition,
    PositionClassBreakdown,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
    PositionValuation,
)

TODAY = date(2024, 12, 31)


class AllocationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="allocation", password="pass")
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        self.container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Broker",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.pablo = FamilyMember.objects.create(
            user=self.user, name="Pablo", role=FamilyMember.Role.ADULT
        )
        self.lucas = FamilyMember.objects.create(
            user=self.user, name="Lucas", role=FamilyMember.Role.CHILD
        )
        self.mine = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.pablo
        )
        self.his = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.lucas
        )

    def create_position(
        self,
        name: str,
        value: Decimal,
        *,
        asset_class: str = Instrument.AssetClass.EQUITY,
        ownership: Ownership | None = None,
        owned_from: date = date(2024, 1, 1),
        status: str = PortfolioPosition.Status.ACTIVE,
    ) -> PortfolioPosition:
        asset = Asset.objects.create(
            user=self.user,
            name=name,
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=value,
            start_date=date(2024, 1, 1),
        )
        instrument = Instrument.objects.create(
            user=self.user,
            name=name,
            identity_kind=Instrument.IdentityKind.CUSTOM,
            asset_class=asset_class,
            instrument_type=Instrument.InstrumentType.FUND,
            quote_currency="EUR",
        )
        position = PortfolioPosition.objects.create(
            portfolio=self.portfolio,
            container=self.container,
            instrument=instrument,
            asset=asset,
            tracking_style=PortfolioPosition.TrackingStyle.VALUE_BASED,
            status=status,
            opened_on=date(2024, 1, 1),
        )
        PositionValuation.objects.create(
            position=position, valuation_date=date(2024, 1, 1), value=value, currency="EUR"
        )
        period = PositionOwnershipPeriod.objects.create(
            position=position,
            ownership=ownership or self.mine,
            start_date=owned_from,
        )
        PositionOwnershipShare.objects.create(
            period=period,
            member=(ownership or self.mine).member,
            percent=Decimal("100"),
        )
        return position

    def strategy(self, ownership: Ownership, effective_from: date, targets: dict):
        strategy = AllocationStrategy.objects.create(
            portfolio=self.portfolio, ownership=ownership, effective_from=effective_from
        )
        for asset_class, (target, floor, ceiling) in targets.items():
            AllocationTarget.objects.create(
                strategy=strategy,
                asset_class=asset_class,
                target_percent=Decimal(target),
                min_percent=None if floor is None else Decimal(floor),
                max_percent=None if ceiling is None else Decimal(ceiling),
            )
        return strategy

    def classes(self, result) -> dict[str, dict]:
        return {row["asset_class"]: row for row in result["by_class"]}

    def test_each_ownership_gets_its_own_portfolio(self):
        # Lo de Pablo y lo de Lucas son mandatos distintos: el niño tiene año y medio y
        # su horizonte no es el del padre. Una politica unica para los dos no diria nada.
        self.create_position("Fondo global", Decimal("9000"))
        self.create_position(
            "Cripto del niño",
            Decimal("1000"),
            asset_class=Instrument.AssetClass.CRYPTO,
            ownership=self.his,
        )

        mine = build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        his = build_allocation(portfolio=self.portfolio, ownership=self.his, on_date=TODAY)

        self.assertEqual(mine["position_count"], 1)
        self.assertEqual(Decimal(mine["total_value"]), Decimal("9000.00"))
        self.assertEqual(his["position_count"], 1)
        self.assertEqual(Decimal(his["total_value"]), Decimal("1000.00"))
        self.assertEqual(self.classes(his)["crypto"]["actual_percent"], "100.00")

    def test_scope_follows_the_ownership_stretch_in_force_on_that_date(self):
        # Si algo dejo de ser compartido en julio, en junio seguia siendolo: la politica
        # de junio le aplicaba. El ambito se lee del tramo vigente, no del ultimo escrito.
        position = self.create_position("Cambia de manos", Decimal("5000"))
        period = position.ownership_periods.get()
        period.end_date = date(2024, 6, 30)
        period.save(update_fields=["end_date"])
        later = PositionOwnershipPeriod.objects.create(
            position=position, ownership=self.his, start_date=date(2024, 7, 1)
        )
        PositionOwnershipShare.objects.create(
            period=later, member=self.lucas, percent=Decimal("100")
        )

        before = build_allocation(
            portfolio=self.portfolio, ownership=self.mine, on_date=date(2024, 6, 1)
        )
        after = build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        his_after = build_allocation(portfolio=self.portfolio, ownership=self.his, on_date=TODAY)

        self.assertEqual(before["position_count"], 1)
        self.assertEqual(after["position_count"], 0)
        self.assertEqual(his_after["position_count"], 1)

    def test_the_version_in_force_is_not_always_the_last_one_written(self):
        self.create_position("Fondo global", Decimal("1000"))
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("50", None, None)})
        self.strategy(self.mine, date(2025, 1, 1), {"equity": ("80", None, None)})

        in_force = resolve_strategy(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)

        self.assertEqual(in_force.effective_from, date(2024, 1, 1))
        result = build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        self.assertEqual(self.classes(result)["equity"]["target_percent"], "50.000")

    def test_the_band_is_what_fires_a_recommendation_not_the_target(self):
        # Sin banda, cualquier desviacion pediria rebalancear y el sistema estaria
        # pidiendolo cada mes por ruido de mercado.
        self.create_position("Fondo global", Decimal("7000"))
        self.create_position("Oro", Decimal("3000"), asset_class=Instrument.AssetClass.COMMODITIES)
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("60", "55", "65"), "commodities": ("40", "35", "45")},
        )

        rows = self.classes(
            build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        )

        # 70/30 con bandas 55-65 y 35-45: las dos fuera, y en direcciones opuestas.
        self.assertEqual(rows["equity"]["band"], "above")
        self.assertEqual(rows["commodities"]["band"], "below")
        self.assertEqual(Decimal(rows["equity"]["drift_value"]), Decimal("-1000.00"))
        self.assertEqual(Decimal(rows["commodities"]["drift_value"]), Decimal("1000.00"))

    def test_a_class_inside_its_band_is_not_flagged_even_if_it_misses_the_target(self):
        self.create_position("Fondo global", Decimal("6200"))
        self.create_position("Oro", Decimal("3800"), asset_class=Instrument.AssetClass.COMMODITIES)
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("60", "55", "65"), "commodities": ("40", "35", "45")},
        )

        rows = self.classes(
            build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        )

        self.assertEqual(rows["equity"]["band"], "within")
        self.assertEqual(rows["commodities"]["band"], "within")

    def test_what_you_hold_without_planning_it_is_shown_not_hidden(self):
        self.create_position("Fondo global", Decimal("9000"))
        self.create_position("Cripto", Decimal("1000"), asset_class=Instrument.AssetClass.CRYPTO)
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", "90", "100")})

        rows = self.classes(
            build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        )

        self.assertEqual(rows["crypto"]["band"], "unplanned")
        self.assertIsNone(rows["crypto"]["target_percent"])

    def test_a_class_you_planned_but_do_not_hold_still_shows_its_gap(self):
        self.create_position("Fondo global", Decimal("10000"))
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("90", None, None), "cash": ("10", "5", "15")},
        )

        rows = self.classes(
            build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        )

        self.assertEqual(Decimal(rows["cash"]["value"]), Decimal("0.00"))
        self.assertEqual(rows["cash"]["band"], "below")
        self.assertEqual(Decimal(rows["cash"]["drift_value"]), Decimal("1000.00"))

    def test_a_mixed_position_lands_in_its_parts_not_in_its_dominant_class(self):
        position = self.create_position("Roboadvisor", Decimal("10000"))
        PositionClassBreakdown.objects.create(
            position=position, asset_class=Instrument.AssetClass.EQUITY, percent=Decimal("60")
        )
        PositionClassBreakdown.objects.create(
            position=position,
            asset_class=Instrument.AssetClass.FIXED_INCOME,
            percent=Decimal("40"),
        )

        rows = self.classes(
            build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        )

        self.assertEqual(Decimal(rows["equity"]["value"]), Decimal("6000.00"))
        self.assertEqual(Decimal(rows["fixed_income"]["value"]), Decimal("4000.00"))

    def test_an_archived_position_no_longer_pulls_the_allocation(self):
        self.create_position("Fondo global", Decimal("9000"))
        self.create_position(
            "Cerrado",
            Decimal("5000"),
            status=PortfolioPosition.Status.ARCHIVED,
        )

        result = build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)

        self.assertEqual(result["position_count"], 1)
        self.assertEqual(Decimal(result["total_value"]), Decimal("9000.00"))
