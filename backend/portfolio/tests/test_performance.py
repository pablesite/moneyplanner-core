from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from core.models import FxRate, InflationIndex
from memberships.models import FamilyMember, Ownership, OwnershipLink, OwnershipSplit
from net_worth.models import Asset, InvestmentAssetEvent
from portfolio.models import (
    ContainerCashAccount,
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioPosition,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
    PositionValuation,
)
from portfolio.performance import build_portfolio_timeline
from portfolio.performance_math import (
    DatedAmount,
    DatedValue,
    annualized,
    chained_twr,
    linked_dietz,
    modified_dietz,
    monetary_result,
    real_return,
    xirr,
)


class PerformanceGoldenMathTests(TestCase):
    def test_no_flows_has_ten_percent_return(self):
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        result = monetary_result(
            opening_value=Decimal("100"), closing_value=Decimal("110"), external_flows=[]
        )
        dietz = modified_dietz(
            opening_value=Decimal("100"),
            closing_value=Decimal("110"),
            external_flows=[],
            start_date=start,
            end_date=end,
        )
        twr = chained_twr(
            valuations=[DatedValue(start, Decimal("100")), DatedValue(end, Decimal("110"))],
            external_flows=[],
        )

        self.assertEqual(result, Decimal("10"))
        self.assertEqual(dietz, Decimal("0.1"))
        self.assertEqual(twr, Decimal("0.1"))

    def test_multiple_contributions_chain_exact_subperiod_returns(self):
        start = date(2024, 1, 1)
        flow_date = date(2024, 7, 1)
        end = date(2024, 12, 31)

        result = chained_twr(
            valuations=[
                DatedValue(start, Decimal("100")),
                DatedValue(flow_date, Decimal("155")),
                DatedValue(end, Decimal("170")),
            ],
            external_flows=[DatedAmount(flow_date, Decimal("50"))],
        )

        expected = (Decimal("105") / Decimal("100")) * (Decimal("170") / Decimal("155")) - Decimal(
            "1"
        )
        self.assertEqual(result, expected)

    def test_midperiod_contribution_and_withdrawal_have_declared_dietz_weights(self):
        start = date(2024, 1, 1)
        midpoint = date(2024, 7, 1)
        end = date(2024, 12, 31)

        contribution = modified_dietz(
            opening_value=Decimal("100"),
            closing_value=Decimal("170"),
            external_flows=[DatedAmount(midpoint, Decimal("50"))],
            start_date=start,
            end_date=end,
        )
        withdrawal = modified_dietz(
            opening_value=Decimal("100"),
            closing_value=Decimal("100"),
            external_flows=[DatedAmount(midpoint, Decimal("-20"))],
            start_date=start,
            end_date=end,
        )

        contribution_weight = Decimal((end - midpoint).days) / Decimal((end - start).days)
        self.assertEqual(
            contribution,
            Decimal("20") / (Decimal("100") + Decimal("50") * contribution_weight),
        )
        self.assertEqual(
            withdrawal,
            Decimal("20") / (Decimal("100") - Decimal("20") * contribution_weight),
        )

    def test_linked_dietz_neutralizes_flow_timing_unlike_whole_period_dietz(self):
        start, mid, end = date(2024, 1, 1), date(2024, 7, 1), date(2024, 12, 31)
        # Asset doubles in the first half and stays flat in the second, while the money
        # only arrives for the flat half: the time-weighted and money-weighted answers
        # must diverge, and the whole-period Dietz must not be read as time-weighted.
        # A valuation dated D reflects the balance after that day's movements, which is
        # the convention the derived valuations follow, so the 1000 is already inside it.
        valuations = [
            DatedValue(start, Decimal("100")),
            DatedValue(mid, Decimal("1200")),
            DatedValue(end, Decimal("1200")),
        ]
        flows = [DatedAmount(mid, Decimal("1000"))]

        linked = linked_dietz(valuations=valuations, external_flows=flows)
        whole_period = modified_dietz(
            opening_value=Decimal("100"),
            closing_value=Decimal("1200"),
            external_flows=flows,
            start_date=start,
            end_date=end,
        )

        # Chained: the asset doubled in the first half, then stayed flat.
        self.assertEqual(linked, Decimal("1"))
        self.assertNotEqual(whole_period, linked)
        self.assertLess(whole_period, linked)

    def test_linked_dietz_takes_the_funding_flow_as_base_when_opening_is_zero(self):
        start, mid, end = date(2024, 1, 1), date(2024, 7, 1), date(2024, 12, 31)
        valuations = [
            DatedValue(start, Decimal("0")),
            DatedValue(mid, Decimal("100")),
            DatedValue(end, Decimal("150")),
        ]

        linked = linked_dietz(
            valuations=valuations, external_flows=[DatedAmount(mid, Decimal("100"))]
        )

        # First subperiod has no return (funded exactly at its close), then 150/100.
        self.assertEqual(linked, Decimal("0.5"))

    def test_annualized_converts_a_cumulative_return_to_an_annual_rate(self):
        # Doubling over two years is sqrt(2) - 1 per year.
        two_years = annualized(total_return=Decimal("1"), days=730)

        self.assertIsNotNone(two_years)
        self.assertAlmostEqual(float(two_years), 2**0.5 - 1, places=6)
        self.assertEqual(annualized(total_return=Decimal("0.1"), days=365), Decimal("0.1"))
        # A total loss has no real annual rate, and neither has an empty period.
        self.assertIsNone(annualized(total_return=Decimal("-1"), days=365))
        self.assertIsNone(annualized(total_return=Decimal("0.1"), days=0))
        self.assertIsNone(annualized(total_return=None, days=365))

    def test_xirr_and_real_return_match_independent_closed_forms(self):
        result = xirr(
            [
                DatedAmount(date(2023, 1, 1), Decimal("-100")),
                DatedAmount(date(2024, 1, 1), Decimal("110")),
            ]
        )
        inflation_adjusted = real_return(
            nominal_return=Decimal("0.10"),
            opening_index=Decimal("100"),
            closing_index=Decimal("105"),
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(float(result), 0.10, places=7)
        self.assertEqual(inflation_adjusted, Decimal("1.10") / Decimal("1.05") - Decimal("1"))


class PortfolioPerformanceApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="performance", password="pass")
        self.client.force_authenticate(self.user)
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        self.container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Broker",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.member = FamilyMember.objects.create(
            user=self.user,
            name="Titular",
            role=FamilyMember.Role.ADULT,
        )
        self.ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=self.member,
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2024, 1, 1),
            index=Decimal("100"),
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2024, 12, 1),
            index=Decimal("105"),
        )
        self.position = self.create_position("Fondo", Decimal("100"), Decimal("170"))
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=self.position.asset,
            event_date=date(2024, 7, 1),
            event_type=InvestmentAssetEvent.EventType.CONTRIBUTION,
            amount=Decimal("50"),
        )

    def create_position(
        self,
        name: str,
        opening: Decimal,
        closing: Decimal,
        *,
        currency: str = "EUR",
    ) -> PortfolioPosition:
        asset = Asset.objects.create(
            user=self.user,
            name=name,
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency=currency,
            amount=closing,
            start_date=date(2024, 1, 1),
        )
        instrument = Instrument.objects.create(
            user=self.user,
            name=name,
            identity_kind=Instrument.IdentityKind.CUSTOM,
            asset_class=Instrument.AssetClass.PRIVATE_EQUITY,
            instrument_type=Instrument.InstrumentType.FUND,
            quote_currency=currency,
        )
        position = PortfolioPosition.objects.create(
            portfolio=self.portfolio,
            container=self.container,
            instrument=instrument,
            asset=asset,
            tracking_style=PortfolioPosition.TrackingStyle.VALUE_BASED,
            status=PortfolioPosition.Status.ACTIVE,
            opened_on=date(2024, 1, 1),
        )
        PositionValuation.objects.create(
            position=position,
            valuation_date=date(2024, 1, 1),
            value=opening,
            currency=currency,
        )
        PositionValuation.objects.create(
            position=position,
            valuation_date=date(2024, 12, 31),
            value=closing,
            currency=currency,
        )
        period = PositionOwnershipPeriod.objects.create(
            position=position,
            ownership=self.ownership,
            start_date=date(2024, 1, 1),
        )
        PositionOwnershipShare.objects.create(
            period=period,
            member=self.member,
            percent=Decimal("100"),
        )
        return position

    def ownership_period_payload(self, position, start_date):
        return {
            "position_id": position.id,
            "ownership_id": self.ownership.id,
            "start_date": start_date,
            "shares": [{"member_id": self.member.id, "percent": "100"}],
        }

    def test_registering_a_change_of_ownership_closes_the_previous_stretch(self):
        # El caso real: un activo que se llevó compartido y en algún momento dejó de
        # serlo. Los tramos son inmutables, así que sin cerrar el anterior no había forma
        # de contarlo: el solapamiento lo rechazaba.
        response = self.client.post(
            "/api/portfolio/ownership-periods/",
            self.ownership_period_payload(self.position, "2024-07-01"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        periods = list(
            PositionOwnershipPeriod.objects.filter(position=self.position).order_by("start_date")
        )
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0].end_date, date(2024, 6, 30))
        self.assertIsNone(periods[1].end_date)

    def test_undoing_a_stretch_hands_the_position_back_to_the_previous_one(self):
        created = self.client.post(
            "/api/portfolio/ownership-periods/",
            self.ownership_period_payload(self.position, "2024-07-01"),
            format="json",
        )

        deleted = self.client.delete(f"/api/portfolio/ownership-periods/{created.data['id']}/")

        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        periods = list(PositionOwnershipPeriod.objects.filter(position=self.position))
        self.assertEqual(len(periods), 1)
        # Sin reabrirlo la posición se quedaría sin titularidad desde esa fecha.
        self.assertIsNone(periods[0].end_date)

    def test_rewriting_a_closed_stretch_is_still_refused(self):
        # Lo que se abre es cerrar el tramo, no reescribirlo: de la titularidad pasada
        # dependen las cifras ya calculadas.
        period = PositionOwnershipPeriod.objects.filter(position=self.position).first()

        period.start_date = date(2023, 1, 1)

        with self.assertRaises(DjangoValidationError):
            period.save(update_fields=["start_date"])

    def test_only_the_last_stretch_can_be_undone(self):
        self.client.post(
            "/api/portfolio/ownership-periods/",
            self.ownership_period_payload(self.position, "2024-07-01"),
            format="json",
        )
        first = (
            PositionOwnershipPeriod.objects.filter(position=self.position)
            .order_by("start_date")
            .first()
        )

        with self.assertRaises(DjangoValidationError):
            first.delete()

    def test_periods_are_listed_per_position(self):
        other = self.create_position("Otro", Decimal("10"), Decimal("20"))

        response = self.client.get(f"/api/portfolio/ownership-periods/?position_id={other.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual([row["position_id"] for row in response.data], [other.id])

    def test_inventory_filter_scopes_the_whole_workspace_not_just_the_table(self):
        # Un filtro de inventario reduce de qué habla la pantalla entera. Antes el hero
        # seguía describiendo la cartera completa mientras la tabla mostraba una clase, y
        # las dos cifras no se parecían en nada.
        equity = self.create_position("Acciones", Decimal("200"), Decimal("300"))
        equity.instrument.asset_class = Instrument.AssetClass.EQUITY
        equity.instrument.save(update_fields=["asset_class"])
        query = "?date_from=2024-01-01&date_to=2024-12-31"

        whole = self.client.get(f"/api/portfolio/workspace/{query}")
        scoped = self.client.get(f"/api/portfolio/workspace/{query}&asset_class=equity")

        self.assertEqual(whole.status_code, status.HTTP_200_OK, whole.data)
        self.assertEqual(scoped.status_code, status.HTTP_200_OK, scoped.data)
        self.assertIsNone(whole.data["scope"])
        self.assertEqual(scoped.data["scope"], [equity.id])
        # 170 del fondo + 300 de las acciones frente a las 300 de la clase filtrada.
        self.assertEqual(Decimal(whole.data["overview"]["value"]), Decimal("470"))
        self.assertEqual(Decimal(scoped.data["overview"]["value"]), Decimal("300"))
        self.assertEqual(Decimal(scoped.data["timeline"]["results"][-1]["value"]), Decimal("300"))
        self.assertEqual(scoped.data["quality"]["positions"]["total"], 1)

    def test_currency_filter_scopes_by_denomination(self):
        self.create_position("US Fund", Decimal("100"), Decimal("110"), currency="USD")
        FxRate.objects.create(
            rate_date=date(2024, 12, 31),
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("1.00"),
        )
        query = "?date_from=2024-01-01&date_to=2024-12-31&currency=USD"

        response = self.client.get(f"/api/portfolio/workspace/{query}")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data["scope"]), 1)
        self.assertEqual(Decimal(response.data["overview"]["value"]), Decimal("110"))

    def test_read_endpoints_expose_reconciled_metrics_and_declared_fallback(self):
        query = "?date_from=2024-01-01&date_to=2024-12-31"

        overview = self.client.get(f"/api/portfolio/overview/{query}")
        performance = self.client.get(f"/api/portfolio/performance/{query}")
        positions = self.client.get(f"/api/portfolio/positions/performance/{query}")
        timeline = self.client.get(f"/api/portfolio/timeline/{query}")
        quality = self.client.get(f"/api/portfolio/quality/{query}")

        self.assertEqual(overview.status_code, status.HTTP_200_OK, overview.data)
        self.assertEqual(performance.status_code, status.HTTP_200_OK, performance.data)
        self.assertEqual(positions.status_code, status.HTTP_200_OK, positions.data)
        self.assertEqual(timeline.status_code, status.HTTP_200_OK, timeline.data)
        self.assertEqual(quality.status_code, status.HTTP_200_OK, quality.data)
        self.assertEqual(performance.data["opening_value"], "100.00000000")
        self.assertEqual(performance.data["closing_value"], "170.00000000")
        self.assertEqual(performance.data["net_contributed"], "50.00000000")
        self.assertEqual(performance.data["monetary_result"], "20.00000000")
        # Without a valuation on the flow date the exact chain is impossible, but the
        # subperiods the valuations do delimit are still chained; the estimate stays
        # declared instead of collapsing into a whole-period money-weighted number.
        self.assertEqual(performance.data["return"]["method"], "linked_dietz")
        self.assertTrue(performance.data["return"]["estimated"])
        self.assertEqual(timeline.data["results"][-1]["monetary_result"], "20.00000000")
        self.assertEqual(len(positions.data["results"]), 1)

    def test_exact_twr_is_used_when_flow_date_has_a_real_valuation(self):
        PositionValuation.objects.create(
            position=self.position,
            valuation_date=date(2024, 7, 1),
            value=Decimal("155"),
            currency="EUR",
        )

        response = self.client.get(
            "/api/portfolio/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )

        expected = (Decimal("105") / Decimal("100")) * (Decimal("170") / Decimal("155")) - Decimal(
            "1"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["return"]["method"], "twr")
        self.assertFalse(response.data["return"]["estimated"])
        self.assertEqual(
            Decimal(response.data["return"]["twr"]),
            expected.quantize(Decimal("0.00000001")),
        )

    def test_ledger_flow_wins_over_same_day_legacy_event(self):
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Fondo",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=self.position.asset,
        )
        cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.position.ledger_account = investment_account
        self.position.save(update_fields=["ledger_account", "updated_at"])
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 7, 1),
            value_date=date(2024, 7, 1),
            description="Aporte",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=investment_account,
            asset=self.position.asset,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("50"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("50"),
            currency="EUR",
        )

        response = self.client.get(
            "/api/portfolio/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )

        contributions = [row for row in response.data["flows"] if row["kind"] == "contribution"]
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["net_contributed"], "50.00000000")
        self.assertEqual(len(contributions), 1)
        self.assertEqual(contributions[0]["source"], "ledger")

    def test_funded_purchase_from_container_cash_is_internal_to_portfolio(self):
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Fondo",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=self.position.asset,
        )
        cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo cartera",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        ContainerCashAccount.objects.create(
            container=self.container,
            ledger_account=cash_account,
            currency="EUR",
        )
        self.position.ledger_account = investment_account
        self.position.save(update_fields=["ledger_account", "updated_at"])
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 7, 1),
            value_date=date(2024, 7, 1),
            description="Compra financiada",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=investment_account,
            asset=self.position.asset,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("50"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("50"),
            currency="EUR",
        )

        aggregate = self.client.get(
            "/api/portfolio/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )
        positions = self.client.get(
            "/api/portfolio/positions/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )
        position_row = positions.data["results"][0]["performance"]

        self.assertEqual(aggregate.status_code, status.HTTP_200_OK, aggregate.data)
        self.assertEqual(aggregate.data["closing_value"], "120.00000000")
        self.assertEqual(aggregate.data["net_contributed"], "0E-8")
        self.assertEqual(aggregate.data["monetary_result"], "20.00000000")
        funded = next(row for row in aggregate.data["flows"] if row["kind"] == "funded_purchase")
        self.assertFalse(funded["external"])
        self.assertEqual(position_row["net_contributed"], "50.00000000")

        # Para una clase aislada, el efectivo del contenedor queda fuera del alcance. La
        # evolución debe tratar esta compra como aporte igual que el resumen, no dejar la
        # línea de capital en cero por seguir usando la semántica de cartera completa.
        scoped = self.client.get(
            "/api/portfolio/workspace/"
            "?date_from=2024-01-01&date_to=2024-12-31&asset_class=private_equity"
        )

        self.assertEqual(scoped.status_code, status.HTTP_200_OK, scoped.data)
        self.assertEqual(scoped.data["performance"]["net_contributed"], "50.00000000")
        self.assertEqual(
            scoped.data["timeline"]["results"][-1]["contributed_to_date"], "50.00000000"
        )

    def test_legacy_directionless_cashback_is_income_not_withdrawal(self):
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Fondo cashback",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=self.position.asset,
        )
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cashback",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        self.position.ledger_account = investment_account
        self.position.save(update_fields=["ledger_account", "updated_at"])
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 8, 1),
            value_date=date(2024, 8, 1),
            description="Cashback reinvertido",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=investment_account,
            asset=self.position.asset,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("5"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("5"),
            currency="EUR",
        )

        response = self.client.get(
            "/api/portfolio/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )
        cashback = next(row for row in response.data["flows"] if row["kind"] == "income_reinvested")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["net_contributed"], "50.00000000")
        self.assertEqual(response.data["income"], "5.00000000")
        self.assertFalse(cashback["external"])

    def test_income_cost_and_closed_position_remain_in_analytical_history(self):
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=self.position.asset,
            event_date=date(2024, 8, 1),
            event_type=InvestmentAssetEvent.EventType.FEE,
            amount=Decimal("2"),
        )
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=self.position.asset,
            event_date=date(2024, 9, 1),
            event_type=InvestmentAssetEvent.EventType.PASSIVE_INCOME,
            amount=Decimal("3"),
            is_reinvested=True,
        )
        self.position.status = PortfolioPosition.Status.ARCHIVED
        self.position.closed_on = date(2024, 12, 31)
        self.position.save(update_fields=["status", "closed_on", "updated_at"])

        response = self.client.get(
            "/api/portfolio/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["monetary_result"], "20.00000000")
        self.assertEqual(response.data["costs"], "2.00000000")
        self.assertEqual(response.data["gross_result"], "22.00000000")
        self.assertEqual(response.data["income"], "3.00000000")

    def test_multicurrency_position_reconciles_asset_and_fx_attribution(self):
        usd_position = self.create_position(
            "US Fund", Decimal("100"), Decimal("110"), currency="USD"
        )
        FxRate.objects.create(
            rate_date=date(2024, 1, 1),
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.90"),
        )
        FxRate.objects.create(
            rate_date=date(2024, 12, 31),
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("1.00"),
        )

        response = self.client.get(
            "/api/portfolio/positions/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )
        usd_row = next(
            row for row in response.data["results"] if row["position_id"] == usd_position.id
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(usd_row["performance"]["monetary_result"], "20.00000000")
        self.assertEqual(usd_row["attribution"]["asset"], "10.00000000")
        self.assertEqual(usd_row["attribution"]["fx"], "10.00000000")
        self.assertEqual(
            Decimal(usd_row["attribution"]["asset"]) + Decimal(usd_row["attribution"]["fx"]),
            Decimal(usd_row["attribution"]["total"]),
        )

    def test_holding_currency_is_the_denomination_not_the_valuation_currency(self):
        # Bitcoin se tiene en BTC y se valora en euros: filtrar por divisa necesita saber
        # en qué está denominada la posición, no en qué se expresa su valor. Con
        # `native_currency` el selector de la cartera nunca llegaba a ofrecer BTC.
        crypto = self.create_position("Bitcoin", Decimal("1000"), Decimal("1200"))
        crypto.ledger_account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
        )
        crypto.save(update_fields=["ledger_account"])

        response = self.client.get(
            "/api/portfolio/positions/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )
        row = next(row for row in response.data["results"] if row["position_id"] == crypto.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(row["holding_currency"], "BTC")
        self.assertEqual(row["native_currency"], "EUR")

    def test_the_workspace_publishes_container_cash_so_composition_matches_the_hero(self):
        # La composicion se dibuja desde las posiciones, y el efectivo enlazado no es
        # ninguna: el grafico sumaba menos que el valor de la cartera y la liquidez no
        # salia por ningun lado. Con un filtro de inventario queda fuera, porque no
        # pertenece a ninguna clase concreta.
        cash_asset = Asset.objects.create(
            user=self.user,
            name="Efectivo broker",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("300"),
            start_date=date(2024, 1, 1),
        )
        cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=cash_asset,
        )
        ContainerCashAccount.objects.create(
            container=self.container, ledger_account=cash_account, currency="EUR"
        )
        opening = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 1, 1),
            description="Saldo inicial",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("300"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=LedgerAccount.objects.create(
                user=self.user,
                name="Aportacion",
                account_type=LedgerAccount.AccountType.EQUITY,
                currency="EUR",
            ),
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("300"),
            currency="EUR",
        )
        query = "?date_from=2024-01-01&date_to=2024-12-31"

        whole = self.client.get(f"/api/portfolio/workspace/{query}")
        scoped = self.client.get(f"/api/portfolio/workspace/{query}&asset_class=equity")

        self.assertEqual(whole.status_code, status.HTTP_200_OK, whole.data)
        # 170 de la posicion mas 300 de efectivo: lo mismo que declara el hero.
        self.assertEqual(Decimal(whole.data["cash"]["value"]), Decimal("300.00"))
        self.assertEqual(Decimal(whole.data["overview"]["value"]), Decimal("470"))
        self.assertEqual(Decimal(scoped.data["cash"]["value"]), Decimal("0.00"))

    def test_a_personal_expense_from_container_cash_is_a_withdrawal_not_a_cost(self):
        # La compra del supermercado pagada desde la cuenta enlazada no es un coste de
        # invertir: es dinero que sale de la cartera. Contarla como coste hundia la
        # rentabilidad con gasto corriente. La categoria contable ya lo distingue.
        cash_asset = Asset.objects.create(
            user=self.user,
            name="Efectivo broker",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1000"),
            start_date=date(2024, 1, 1),
        )
        cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=cash_asset,
        )
        ContainerCashAccount.objects.create(
            container=self.container, ledger_account=cash_account, currency="EUR"
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Compra",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        for category, amount in (("consumption_expenses", "200"), ("financial_investments", "50")):
            transaction = LedgerTransaction.objects.create(
                user=self.user,
                booking_date=date(2024, 6, 1),
                value_date=date(2024, 6, 1),
                description="Gasto",
                quick_entry_kind=LedgerTransaction.QuickEntryKind.EXPENSE,
                status=LedgerTransaction.Status.POSTED,
            )
            LedgerEntry.objects.create(
                transaction=transaction,
                account=cash_account,
                side=LedgerEntry.Side.CREDIT,
                amount=Decimal(amount),
                currency="EUR",
            )
            LedgerEntry.objects.create(
                transaction=transaction,
                account=expense_account,
                side=LedgerEntry.Side.DEBIT,
                amount=Decimal(amount),
                currency="EUR",
                flow_family=LedgerEntry.FlowFamily.EXPENSE,
                category_key=category,
            )

        response = self.client.get(
            "/api/portfolio/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        # Solo los 50 con categoria de inversion son coste; los 200 de consumo salen de
        # la cartera y se restan de la aportacion de 50 que ya traia el escenario.
        self.assertEqual(Decimal(response.data["costs"]), Decimal("50"))
        self.assertEqual(Decimal(response.data["net_contributed"]), Decimal("-150"))

    def test_quality_keeps_stale_values_and_partial_unit_detail_explicit(self):
        missing = self.create_position("Crypto sin precio", Decimal("1"), Decimal("1"))
        missing.tracking_style = PortfolioPosition.TrackingStyle.UNITS_BASED
        missing.save(update_fields=["tracking_style", "updated_at"])
        missing.manual_valuations.all().delete()

        response = self.client.get(
            "/api/portfolio/quality/?date_from=2024-01-01&date_to=2025-02-01"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "needs_review")
        self.assertEqual(response.data["positions"]["stale"], 1)
        self.assertEqual(response.data["positions"]["missing"], 1)
        self.assertEqual(response.data["metric_coverage"]["value"], "partial")

    def test_timeline_query_count_does_not_grow_per_position(self):
        with CaptureQueriesContext(connection) as initial_queries:
            build_portfolio_timeline(
                portfolio=self.portfolio,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )
        for index in range(4):
            self.create_position(f"Fondo {index}", Decimal("100"), Decimal(str(110 + index)))
        with CaptureQueriesContext(connection) as expanded_queries:
            rows = build_portfolio_timeline(
                portfolio=self.portfolio,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )

        self.assertEqual(len(rows), 13)
        self.assertLessEqual(len(expanded_queries), len(initial_queries) + 1)

    def test_member_filter_is_historically_applied_and_cross_user_is_rejected(self):
        query = f"?date_from=2024-01-01&date_to=2024-12-31&member_id={self.member.id}"
        response = self.client.get(f"/api/portfolio/performance/{query}")
        other_user = get_user_model().objects.create_user(username="other-performance")
        other_member = FamilyMember.objects.create(
            user=other_user,
            name="Ajeno",
            role=FamilyMember.Role.ADULT,
        )
        rejected = self.client.get(
            "/api/portfolio/performance/"
            f"?date_from=2024-01-01&date_to=2024-12-31&member_id={other_member.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["closing_value"], "170.00000000")
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST, rejected.data)

    def test_ownership_change_is_neutralized_as_a_member_external_flow(self):
        other_member = FamilyMember.objects.create(
            user=self.user,
            name="Cotitular",
            role=FamilyMember.Role.ADULT,
        )
        other_ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=other_member,
        )
        first_period = self.position.ownership_periods.get()
        PositionOwnershipPeriod.objects.filter(id=first_period.id).update(
            end_date=date(2024, 9, 30)
        )
        second_period = PositionOwnershipPeriod.objects.create(
            position=self.position,
            ownership=other_ownership,
            start_date=date(2024, 10, 1),
        )
        PositionOwnershipShare.objects.create(
            period=second_period,
            member=other_member,
            percent=Decimal("100"),
        )
        PositionValuation.objects.create(
            position=self.position,
            valuation_date=date(2024, 10, 1),
            value=Decimal("160"),
            currency="EUR",
        )

        response = self.client.get(
            "/api/portfolio/performance/"
            f"?date_from=2024-01-01&date_to=2024-12-31&member_id={self.member.id}"
        )
        ownership_flow = next(
            row for row in response.data["flows"] if row["kind"] == "ownership_transfer"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["opening_value"], "100.00000000")
        self.assertEqual(response.data["closing_value"], "0E-8")
        self.assertEqual(response.data["net_contributed"], "-110.00000000")
        self.assertEqual(response.data["monetary_result"], "10.00000000")
        self.assertEqual(ownership_flow["amount_base"], "-160.00000000")


class ContainerCashOwnershipTests(APITestCase):
    """El efectivo del contenedor tiene dueno: el del activo que lo respalda."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cashowner", password="pass")
        self.client.force_authenticate(self.user)
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        self.container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Broker",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.member = FamilyMember.objects.create(
            user=self.user, name="Titular", role=FamilyMember.Role.ADULT
        )
        self.other = FamilyMember.objects.create(
            user=self.user, name="Otra", role=FamilyMember.Role.ADULT
        )
        self.ownership = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.member
        )
        self.cash_ledger = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.cash_asset = Asset.objects.create(
            user=self.user,
            name="Efectivo broker",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("0"),
            start_date=date(2024, 1, 1),
            accounting_account_id=self.cash_ledger.id,
        )
        ContainerCashAccount.objects.create(
            container=self.container, ledger_account=self.cash_ledger, currency="EUR"
        )
        self.fund_account = LedgerAccount.objects.create(
            user=self.user,
            name="Origen",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 3, 1),
            value_date=date(2024, 3, 1),
            description="Entra efectivo",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=self.cash_ledger,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=self.fund_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100"),
            currency="EUR",
        )

    def link_cash_to(self, ownership):
        OwnershipLink.objects.update_or_create(
            user=self.user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=self.cash_asset.id,
            defaults={"ownership": ownership},
        )

    def quality_for(self, member):
        response = self.client.get(
            f"/api/portfolio/quality/?date_from=2024-01-01&date_to=2024-12-31&member_id={member.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def test_cash_with_ownership_is_not_reported_as_missing(self):
        # Antes bastaba con tener efectivo para que el aviso saltara en todas las
        # titularidades, aunque la cuenta tuviera dueno declarado en Patrimonio.
        self.link_cash_to(self.ownership)

        self.assertFalse(self.quality_for(self.member)["cash_ownership_missing"])
        self.assertFalse(self.quality_for(self.other)["cash_ownership_missing"])

    def test_cash_without_ownership_is_still_reported(self):
        # Sin enlace no se puede atribuir, y eso si es trabajo del usuario.
        self.assertTrue(self.quality_for(self.member)["cash_ownership_missing"])

    def test_cash_value_follows_the_owner_of_its_account(self):
        self.link_cash_to(self.ownership)

        mine = self.client.get(
            "/api/portfolio/performance/"
            f"?date_from=2024-01-01&date_to=2024-12-31&member_id={self.member.id}"
        )
        theirs = self.client.get(
            "/api/portfolio/performance/"
            f"?date_from=2024-01-01&date_to=2024-12-31&member_id={self.other.id}"
        )

        self.assertEqual(mine.data["closing_value"], "100.00000000")
        self.assertEqual(theirs.data["closing_value"], "0E-8")

    def test_shared_cash_splits_by_declared_percentages(self):
        shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        OwnershipSplit.objects.create(ownership=shared, member=self.member, percent=Decimal("50"))
        OwnershipSplit.objects.create(ownership=shared, member=self.other, percent=Decimal("50"))
        self.link_cash_to(shared)

        mine = self.client.get(
            "/api/portfolio/performance/"
            f"?date_from=2024-01-01&date_to=2024-12-31&member_id={self.member.id}"
        )

        self.assertEqual(mine.data["closing_value"], "50.00000000")
        self.assertFalse(self.quality_for(self.member)["cash_ownership_missing"])


class HoldingThreadTests(APITestCase):
    """El mismo activo bajo la misma titularidad, aunque cambie de custodio."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="threads", password="pass")
        self.client.force_authenticate(self.user)
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        self.old_custodian = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Exchange viejo",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.new_custodian = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Exchange nuevo",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.member = FamilyMember.objects.create(
            user=self.user, name="Titular", role=FamilyMember.Role.ADULT
        )
        self.ownership = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.member
        )
        # Un unico instrumento que vive primero en un custodio y luego en otro.
        self.instrument = Instrument.objects.create(
            user=self.user,
            name="Bitcoin",
            identity_kind=Instrument.IdentityKind.CUSTOM,
            asset_class=Instrument.AssetClass.CRYPTO,
            instrument_type=Instrument.InstrumentType.CRYPTO,
            quote_currency="EUR",
        )
        self.old_position = self.create_position(
            "BTC viejo", self.old_custodian, opening=Decimal("100"), closing=Decimal("0")
        )
        self.new_position = self.create_position(
            "BTC nuevo", self.new_custodian, opening=Decimal("0"), closing=Decimal("150")
        )
        self.move_between_custodians(Decimal("120"))

    def create_position(self, name, container, *, opening, closing):
        asset = Asset.objects.create(
            user=self.user,
            name=name,
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=closing,
            start_date=date(2024, 1, 1),
        )
        account = LedgerAccount.objects.create(
            user=self.user,
            name=name,
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        position = PortfolioPosition.objects.create(
            portfolio=self.portfolio,
            container=container,
            instrument=self.instrument,
            asset=asset,
            ledger_account=account,
            tracking_style=PortfolioPosition.TrackingStyle.VALUE_BASED,
            status=PortfolioPosition.Status.ACTIVE,
            opened_on=date(2024, 1, 1),
        )
        PositionValuation.objects.create(
            position=position, valuation_date=date(2024, 1, 1), value=opening, currency="EUR"
        )
        PositionValuation.objects.create(
            position=position, valuation_date=date(2024, 12, 31), value=closing, currency="EUR"
        )
        period = PositionOwnershipPeriod.objects.create(
            position=position, ownership=self.ownership, start_date=date(2024, 1, 1)
        )
        PositionOwnershipShare.objects.create(
            period=period, member=self.member, percent=Decimal("100")
        )
        return position

    def move_between_custodians(self, amount):
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 7, 1),
            value_date=date(2024, 7, 1),
            description="Mudanza de exchange",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=self.new_position.ledger_account,
            asset=self.new_position.asset,
            side=LedgerEntry.Side.DEBIT,
            amount=amount,
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=self.old_position.ledger_account,
            asset=self.old_position.asset,
            side=LedgerEntry.Side.CREDIT,
            amount=amount,
            currency="EUR",
        )

    def performance(self, query=""):
        # El scope de inventario lo resuelve el workspace, que es el que sirve `/cartera`.
        response = self.client.get(
            f"/api/portfolio/workspace/?date_from=2024-01-01&date_to=2024-12-31{query}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data["performance"]

    def test_the_move_is_a_contribution_for_the_arriving_position_alone(self):
        # Leida sola, la posicion nueva empieza el dia de la mudanza y lo que llega es
        # dinero nuevo: es justo la lectura que hace ilegible la historia del activo.
        alone = self.performance(f"&container_id={self.new_custodian.id}")

        self.assertEqual(alone["net_contributed"], "120.00000000")

    def test_the_thread_nets_out_the_move_between_custodians(self):
        thread = self.performance(
            f"&instrument_id={self.instrument.id}&ownership_id={self.ownership.id}"
        )

        # Dentro del hilo la mudanza es interna: no entra ni sale dinero, y el resultado
        # es el del activo entero (100 -> 150) en lugar del de media historia.
        self.assertEqual(thread["net_contributed"], "0E-8")
        self.assertEqual(thread["opening_value"], "100.00000000")
        self.assertEqual(thread["closing_value"], "150.00000000")
        self.assertEqual(thread["monetary_result"], "50.00000000")

    def test_threads_endpoint_flags_the_one_that_changed_custodian(self):
        response = self.client.get(
            "/api/portfolio/threads/?date_from=2024-01-01&date_to=2024-12-31"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 1)
        thread = response.data[0]
        self.assertEqual(thread["instrument_name"], "Bitcoin")
        self.assertEqual(thread["ownership_id"], self.ownership.id)
        self.assertTrue(thread["spans_custodians"])
        self.assertEqual(
            sorted(thread["position_ids"]),
            sorted([self.old_position.id, self.new_position.id]),
        )
        self.assertEqual(thread["containers"], ["Exchange viejo", "Exchange nuevo"])


class OwnershipSplitConsistencyTests(APITestCase):
    """Filtrar por titular reparte la cartera; no puede crear ni destruir dinero."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="split", password="pass")
        self.client.force_authenticate(self.user)
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        self.container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Broker",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.one = FamilyMember.objects.create(
            user=self.user, name="Uno", role=FamilyMember.Role.ADULT
        )
        self.two = FamilyMember.objects.create(
            user=self.user, name="Dos", role=FamilyMember.Role.ADULT
        )
        self.owned_by_one = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.one
        )
        self.owned_by_two = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.two
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES, period=date(2024, 1, 1), index=Decimal("100")
        )
        # Dos posiciones nacidas *dentro* de la ventana: es el caso que inventaba una
        # aportacion por el valor entero al filtrar por titular.
        self.first = self.build_position("Fondo uno", self.owned_by_one, Decimal("300"))
        self.second = self.build_position("Fondo dos", self.owned_by_two, Decimal("100"))

    def build_position(self, name, ownership, closing):
        asset = Asset.objects.create(
            user=self.user,
            name=name,
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=closing,
            start_date=date(2024, 6, 1),
        )
        account = LedgerAccount.objects.create(
            user=self.user,
            name=name,
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        position = PortfolioPosition.objects.create(
            portfolio=self.portfolio,
            container=self.container,
            instrument=Instrument.objects.create(
                user=self.user,
                name=name,
                identity_kind=Instrument.IdentityKind.CUSTOM,
                asset_class=Instrument.AssetClass.PRIVATE_EQUITY,
                instrument_type=Instrument.InstrumentType.FUND,
                quote_currency="EUR",
            ),
            asset=asset,
            ledger_account=account,
            tracking_style=PortfolioPosition.TrackingStyle.VALUE_BASED,
            status=PortfolioPosition.Status.ACTIVE,
            opened_on=date(2024, 6, 1),
        )
        PositionValuation.objects.create(
            position=position, valuation_date=date(2024, 12, 31), value=closing, currency="EUR"
        )
        period = PositionOwnershipPeriod.objects.create(
            position=position, ownership=ownership, start_date=date(2024, 6, 1)
        )
        PositionOwnershipShare.objects.create(
            period=period,
            member=ownership.member,
            percent=Decimal("100"),
        )
        self.contribute(position, account, asset, closing)
        return position

    def contribute(self, position, account, asset, amount):
        outside = LedgerAccount.objects.create(
            user=self.user,
            name=f"Banco {position.id}",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 6, 1),
            value_date=date(2024, 6, 1),
            description="Compra",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=account,
            asset=asset,
            side=LedgerEntry.Side.DEBIT,
            amount=amount,
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=outside,
            side=LedgerEntry.Side.CREDIT,
            amount=amount,
            currency="EUR",
        )

    def performance(self, member=None):
        suffix = f"&member_id={member.id}" if member else ""
        response = self.client.get(
            f"/api/portfolio/performance/?date_from=2024-01-01&date_to=2024-12-31{suffix}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def test_a_new_position_is_not_a_contribution_to_its_owner(self):
        # El primer tramo de titularidad no cambia nada: la posicion nace y su compra ya
        # esta contada. Emitiendo tambien ahi, lo aportado por un miembro superaba lo
        # aportado a la cartera entera.
        mine = self.performance(self.one)

        self.assertEqual(mine["net_contributed"], "300.00000000")
        self.assertFalse(
            [row for row in mine["flows"] if row["kind"] == "ownership_transfer"],
        )

    def test_the_members_add_up_to_the_whole_portfolio(self):
        whole = self.performance()
        first = self.performance(self.one)
        second = self.performance(self.two)

        self.assertEqual(whole["net_contributed"], "400.00000000")
        self.assertEqual(
            Decimal(first["net_contributed"]) + Decimal(second["net_contributed"]),
            Decimal(whole["net_contributed"]),
        )
        self.assertEqual(
            Decimal(first["closing_value"]) + Decimal(second["closing_value"]),
            Decimal(whole["closing_value"]),
        )

    def test_a_real_change_of_ownership_still_moves_value_between_members(self):
        # Ceder la mitad no mueve dinero, pero si cambia la posicion economica de cada uno,
        # y eso tiene que seguir contando.
        shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        OwnershipSplit.objects.create(ownership=shared, member=self.one, percent=Decimal("50"))
        OwnershipSplit.objects.create(ownership=shared, member=self.two, percent=Decimal("50"))
        previous = self.first.ownership_periods.get()
        previous.end_date = date(2024, 8, 31)
        previous.save(update_fields=["end_date"])
        period = PositionOwnershipPeriod.objects.create(
            position=self.first, ownership=shared, start_date=date(2024, 9, 1)
        )
        PositionOwnershipShare.objects.create(period=period, member=self.one, percent=Decimal("50"))
        PositionOwnershipShare.objects.create(period=period, member=self.two, percent=Decimal("50"))

        giver = self.performance(self.one)

        transfers = [row for row in giver["flows"] if row["kind"] == "ownership_transfer"]
        self.assertEqual(len(transfers), 1)
        self.assertTrue(Decimal(transfers[0]["amount_base"]) < 0)


class CommingledPositionTests(APITestCase):
    """Un bote con monedas de dos titularidades se reparte por unidades, no por porcentaje."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="pot", password="pass")
        self.client.force_authenticate(self.user)
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        self.container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Exchange",
            container_type=InvestmentContainer.ContainerType.BROKER,
        )
        self.her = FamilyMember.objects.create(
            user=self.user, name="Ella", role=FamilyMember.Role.ADULT
        )
        self.him = FamilyMember.objects.create(
            user=self.user, name="El", role=FamilyMember.Role.ADULT
        )
        self.his_own = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.him
        )
        self.shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        OwnershipSplit.objects.create(ownership=self.shared, member=self.her, percent=Decimal("50"))
        OwnershipSplit.objects.create(ownership=self.shared, member=self.him, percent=Decimal("50"))
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES, period=date(2024, 1, 1), index=Decimal("100")
        )
        self.asset = Asset.objects.create(
            user=self.user,
            name="Cripto",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("800"),
            start_date=date(2024, 1, 1),
        )
        self.account = LedgerAccount.objects.create(
            user=self.user,
            name="Cripto",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=self.asset,
        )
        self.position = PortfolioPosition.objects.create(
            portfolio=self.portfolio,
            container=self.container,
            instrument=Instrument.objects.create(
                user=self.user,
                name="Cripto",
                identity_kind=Instrument.IdentityKind.CUSTOM,
                asset_class=Instrument.AssetClass.CRYPTO,
                instrument_type=Instrument.InstrumentType.CRYPTO,
                quote_currency="EUR",
            ),
            asset=self.asset,
            ledger_account=self.account,
            tracking_style=PortfolioPosition.TrackingStyle.VALUE_BASED,
            status=PortfolioPosition.Status.ACTIVE,
            opened_on=date(2024, 1, 1),
        )
        PositionValuation.objects.create(
            position=self.position,
            valuation_date=date(2024, 12, 31),
            value=Decimal("800"),
            currency="EUR",
        )
        # El tramo declara la posicion entera del que la lleva hoy: es justo la simplificacion
        # que el bote tiene que corregir.
        period = PositionOwnershipPeriod.objects.create(
            position=self.position, ownership=self.his_own, start_date=date(2024, 1, 1)
        )
        PositionOwnershipShare.objects.create(
            period=period, member=self.him, percent=Decimal("100")
        )
        self.buy(date(2024, 2, 1), Decimal("200"), self.shared)
        self.buy(date(2024, 3, 1), Decimal("200"), self.his_own)

    def buy(self, day, amount, ownership):
        outside = LedgerAccount.objects.create(
            user=self.user,
            name=f"Banco {day}",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=day,
            value_date=day,
            description="Compra",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
            ownership=ownership,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=self.account,
            asset=self.asset,
            side=LedgerEntry.Side.DEBIT,
            amount=amount,
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=outside,
            side=LedgerEntry.Side.CREDIT,
            amount=amount,
            currency="EUR",
        )

    def sell(self, day, amount, ownership):
        outside = LedgerAccount.objects.create(
            user=self.user,
            name=f"Banco venta {day}",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=day,
            value_date=day,
            description="Venta",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.OUTFLOW,
            ownership=ownership,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=self.account,
            asset=self.asset,
            side=LedgerEntry.Side.CREDIT,
            amount=amount,
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=outside,
            side=LedgerEntry.Side.DEBIT,
            amount=amount,
            currency="EUR",
        )

    def value_for(self, member):
        response = self.client.get(
            "/api/portfolio/performance/"
            f"?date_from=2024-01-01&date_to=2024-12-31&member_id={member.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return Decimal(response.data["closing_value"])

    def test_the_pot_is_split_by_what_each_ownership_put_in(self):
        # Mitad comprada en comun y mitad propia: de los 800, 200 son de ella (la mitad de
        # la mitad comun) y 600 de el. El tramo, que lo daba todo a el, no sabia esto.
        self.assertEqual(self.value_for(self.her), Decimal("200.00000000"))
        self.assertEqual(self.value_for(self.him), Decimal("600.00000000"))

    def test_the_two_members_still_add_up_to_the_whole_position(self):
        whole = self.client.get(
            "/api/portfolio/performance/?date_from=2024-01-01&date_to=2024-12-31"
        )

        self.assertEqual(
            self.value_for(self.her) + self.value_for(self.him),
            Decimal(whole.data["closing_value"]),
        )

    def test_a_sale_uses_its_ledger_ownership_not_the_end_of_day_pocket(self):
        # Tras vender lo compartido el bolsillo compartido queda vacio. Si el flujo mira
        # ese saldo final, atribuye la venta entera a el y deja las aportaciones de ella
        # sin su retirada correspondiente.
        self.sell(date(2024, 4, 1), Decimal("200"), self.shared)

        response = self.client.get(
            "/api/portfolio/performance/"
            f"?date_from=2024-01-01&date_to=2024-12-31&member_id={self.her.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["net_contributed"], "0E-8")
