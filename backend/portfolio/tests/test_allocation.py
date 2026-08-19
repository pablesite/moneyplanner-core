from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from memberships.models import FamilyMember, Ownership
from net_worth.models import Asset, InvestmentAssetEvent
from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services_ledger import get_account_balance
from portfolio.allocation import (
    build_allocation,
    build_contribution,
    confirm_basket,
    create_basket,
    discard_basket,
    resolve_strategy,
)
from portfolio.models import (
    AllocationStrategy,
    ContainerCashAccount,
    ContributionBasket,
    ContributionBasketLine,
    ContributionCommitment,
    AllocationTarget,
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioPosition,
    PositionAllocationRule,
    PositionClassBreakdown,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
    PositionValuation,
)

TODAY = date(2024, 12, 31)


class AllocationFixture:
    """Cartera de prueba compartida.

    Mixin y no `TestCase`: heredar de una clase de tests hace que cada subclase vuelva a
    ejecutar los tests del padre, que ademas fallan en cuanto la subclase cambia el
    fixture.
    """

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

    def contribute(self, position: PortfolioPosition, amount: Decimal, on_date: date) -> None:
        """Una aportacion real a la posicion, para que el cupo sepa lo que ya llevas."""
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=position.asset,
            event_date=on_date,
            event_type=InvestmentAssetEvent.EventType.CONTRIBUTION,
            amount=amount,
        )

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


class AllocationTests(AllocationFixture, TestCase):
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


class ContributionSolverTests(AllocationFixture, TestCase):
    def contribution(self, amount: str, ownership: Ownership | None = None):
        return build_contribution(
            portfolio=self.portfolio,
            ownership=ownership or self.mine,
            amount=Decimal(amount),
            on_date=TODAY,
        )

    def amounts(self, result) -> dict[int, Decimal]:
        return {row["position_id"]: Decimal(row["amount"]) for row in result["lines"]}

    def test_the_money_goes_where_the_gap_is_not_spread_evenly(self):
        # Esto es lo que sustituye al DCA: mismo importe, dirigido a lo que va corto en
        # vez de repartido a partes iguales.
        equity = self.create_position("Fondo global", Decimal("9000"))
        gold = self.create_position(
            "Oro", Decimal("1000"), asset_class=Instrument.AssetClass.COMMODITIES
        )
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("60", None, None), "commodities": ("40", None, None)},
        )

        result = self.contribution("1000")

        amounts = self.amounts(result)
        self.assertEqual(result["status"], "ok")
        # Con 11.000 tras aportar, el oro deberia valer 4.400 y tiene 1.000: se lleva
        # todo, y la renta variable no recibe nada porque ya va sobrada.
        self.assertEqual(amounts[gold.id], Decimal("1000.00"))
        self.assertNotIn(equity.id, amounts)

    def test_it_never_proposes_selling_what_is_overweight(self):
        equity = self.create_position("Fondo global", Decimal("9000"))
        self.create_position("Oro", Decimal("1000"), asset_class=Instrument.AssetClass.COMMODITIES)
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("10", None, None), "commodities": ("90", None, None)},
        )

        result = self.contribution("500")

        self.assertNotIn(equity.id, self.amounts(result))
        self.assertTrue(all(Decimal(row["amount"]) > 0 for row in result["lines"]))

    def test_the_whole_amount_is_placed_or_explained(self):
        self.create_position("Fondo global", Decimal("5000"))
        self.create_position("Oro", Decimal("5000"), asset_class=Instrument.AssetClass.COMMODITIES)
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("50", None, None), "commodities": ("50", None, None)},
        )

        result = self.contribution("1000")

        placed = sum(self.amounts(result).values(), Decimal("0"))
        total = placed + Decimal(result["reserved_cash"]) + Decimal(result["leftover"])
        self.assertEqual(total, Decimal("1000.00"))

    def test_tactical_cash_is_a_policy_line_that_competes_for_the_money(self):
        # La liquidez tactica no es lo que sobra al final de la operacion, pero tampoco
        # tiene prioridad: compite por el hueco como una clase mas. Reservarla antes que
        # nada hacia que una aportacion entera se fuera a efectivo mientras el resto de
        # la cartera seguia fuera de banda.
        self.create_position("Fondo global", Decimal("9000"))
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("90", None, None), "cash": ("10", None, None)},
        )

        result = self.contribution("1000")

        self.assertEqual(Decimal(result["reserved_cash"]), Decimal("1000.00"))
        self.assertEqual(result["lines"], [])

    def test_a_minimum_that_cannot_be_met_hands_its_money_to_the_others(self):
        big = self.create_position("Fondo global", Decimal("5000"))
        small = self.create_position(
            "Fondo con minimo",
            Decimal("4900"),
            asset_class=Instrument.AssetClass.FIXED_INCOME,
        )
        PositionAllocationRule.objects.create(position=small, min_contribution=Decimal("500"))
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("50", None, None), "fixed_income": ("50", None, None)},
        )

        result = self.contribution("200")

        amounts = self.amounts(result)
        self.assertNotIn(small.id, amounts)
        self.assertEqual(amounts[big.id], Decimal("200.00"))

    def test_an_excluded_position_never_receives_money(self):
        equity = self.create_position("Fondo global", Decimal("5000"))
        closed = self.create_position(
            "Fondo cerrado a nuevas aportaciones",
            Decimal("1000"),
            asset_class=Instrument.AssetClass.FIXED_INCOME,
        )
        PositionAllocationRule.objects.create(position=closed, excluded=True)
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("50", None, None), "fixed_income": ("50", None, None)},
        )

        result = self.contribution("1000")

        amounts = self.amounts(result)
        self.assertNotIn(closed.id, amounts)
        self.assertIn({"position_id": closed.id, "reason": "excluded"}, result["skipped"])
        # Y su dinero no se queda parado: va entero a la que si puede recibirlo.
        self.assertEqual(amounts[equity.id], Decimal("1000.00"))
        self.assertEqual(Decimal(result["leftover"]), Decimal("0.00"))

    def test_rounding_never_proposes_more_money_than_there_is(self):
        position = self.create_position("Fondo por participaciones", Decimal("1000"))
        PositionAllocationRule.objects.create(position=position, rounding_step=Decimal("100"))
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

        result = self.contribution("250")

        self.assertEqual(self.amounts(result)[position.id], Decimal("200.00"))
        self.assertEqual(Decimal(result["leftover"]), Decimal("50.00"))

    def test_an_incomplete_policy_is_refused_instead_of_normalised(self):
        # Normalizar en silencio calcularia el ideal sobre una cartera que no es la tuya
        # y el reparto seria inventado.
        self.create_position("Fondo global", Decimal("1000"))
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("60", None, None)})

        result = self.contribution("500")

        self.assertEqual(result["status"], "incomplete_strategy")
        self.assertEqual(result["lines"], [])

    def test_without_a_policy_there_is_nothing_to_recommend(self):
        self.create_position("Fondo global", Decimal("1000"))

        result = self.contribution("500")

        self.assertEqual(result["status"], "no_strategy")

    def test_a_class_yet_to_be_built_is_built_where_rebalancing_will_be_free(self):
        # Aportar no paga peaje hoy, asi que la eleccion no es fiscal ahora: es de
        # manana. Construir la clase en lo traspasable deja gratis el rebalanceo futuro,
        # y la exposicion es la misma porque son la misma clase.
        self.create_position("Fondo global", Decimal("10000"))
        etf = self.create_position(
            "ETF de bonos", Decimal("0"), asset_class=Instrument.AssetClass.FIXED_INCOME
        )
        fund = self.create_position(
            "Fondo de bonos", Decimal("0"), asset_class=Instrument.AssetClass.FIXED_INCOME
        )
        fund.tax_transferable = True
        fund.save(update_fields=["tax_transferable"])

        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("80", None, None), "fixed_income": ("20", None, None)},
        )

        amounts = self.amounts(self.contribution("2000"))

        self.assertIn(fund.id, amounts)
        self.assertNotIn(etf.id, amounts)

    def test_with_nothing_transferable_an_empty_class_is_split_evenly(self):
        self.create_position("Fondo global", Decimal("10000"))
        first = self.create_position(
            "ETF de bonos A", Decimal("0"), asset_class=Instrument.AssetClass.FIXED_INCOME
        )
        second = self.create_position(
            "ETF de bonos B", Decimal("0"), asset_class=Instrument.AssetClass.FIXED_INCOME
        )
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("80", None, None), "fixed_income": ("20", None, None)},
        )

        amounts = self.amounts(self.contribution("2000"))

        self.assertEqual(amounts[first.id], amounts[second.id])

    def test_each_ownership_solves_against_its_own_policy(self):
        self.create_position("Fondo global", Decimal("1000"))
        self.create_position(
            "Cripto del niño",
            Decimal("1000"),
            asset_class=Instrument.AssetClass.CRYPTO,
            ownership=self.his,
        )
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})
        self.strategy(self.his, date(2024, 1, 1), {"crypto": ("100", None, None)})

        mine = self.contribution("500")
        his = self.contribution("500", ownership=self.his)

        self.assertEqual(len(mine["lines"]), 1)
        self.assertEqual(mine["lines"][0]["asset_class"], "equity")
        self.assertEqual(his["lines"][0]["asset_class"], "crypto")


class ContributionInvariantTests(AllocationFixture, TestCase):
    """Lo que tiene que cumplirse siempre, sea cual sea la cartera y el importe.

    Un solver falla en los bordes, no en el caso de ejemplo: importes diminutos, clases
    ya pasadas de largo, minimos que no se alcanzan y escalones que no dividen.
    """

    HALVES = {"equity": ("50", None, None), "fixed_income": ("50", None, None)}

    def build(self, currents, targets, amount, rules=None):
        positions = [
            self.create_position(f"P{index}", Decimal(value), asset_class=asset_class)
            for index, (asset_class, value) in enumerate(currents)
        ]
        for index, rule in (rules or {}).items():
            PositionAllocationRule.objects.create(position=positions[index], **rule)
        self.strategy(self.mine, date(2024, 1, 1), targets)
        return positions, build_contribution(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal(amount),
            on_date=TODAY,
        )

    def assert_conserves(self, result, amount: str) -> Decimal:
        placed = sum((Decimal(row["amount"]) for row in result["lines"]), Decimal("0"))
        total = placed + Decimal(result["reserved_cash"]) + Decimal(result["leftover"])
        self.assertEqual(total, Decimal(amount))
        self.assertLessEqual(placed, Decimal(amount))
        self.assertTrue(all(Decimal(row["amount"]) > 0 for row in result["lines"]))
        return placed

    def test_a_contribution_of_one_cent_is_conserved(self):
        _, result = self.build([("equity", "1000"), ("fixed_income", "9000")], self.HALVES, "0.01")

        self.assert_conserves(result, "0.01")

    def test_an_awkward_amount_is_conserved(self):
        _, result = self.build([("equity", "1000"), ("fixed_income", "9000")], self.HALVES, "7.77")

        self.assert_conserves(result, "7.77")

    def test_an_empty_portfolio_is_conserved(self):
        _, result = self.build([("equity", "0"), ("fixed_income", "0")], self.HALVES, "1000")

        self.assertEqual(self.assert_conserves(result, "1000"), Decimal("1000.00"))

    def test_a_lopsided_portfolio_is_conserved(self):
        _, result = self.build(
            [("equity", "9999.99"), ("fixed_income", "0.01")], self.HALVES, "333.33"
        )

        self.assert_conserves(result, "333.33")

    def test_a_rounding_step_is_always_respected(self):
        positions, result = self.build(
            [("equity", "1000"), ("fixed_income", "1000")],
            self.HALVES,
            "1000",
            rules={0: {"rounding_step": Decimal("250")}},
        )

        amounts = {row["position_id"]: Decimal(row["amount"]) for row in result["lines"]}
        self.assertEqual(amounts.get(positions[0].id, Decimal("0")) % Decimal("250"), 0)
        self.assert_conserves(result, "1000")

    def test_an_already_overshot_policy_still_invests_the_money(self):
        # Todas las clases pasadas de largo: no hay hueco que cerrar y aun asi el dinero
        # se coloca a peso de politica, en vez de quedarse en efectivo sin decidirlo.
        _, result = self.build([("equity", "8000"), ("fixed_income", "2000")], self.HALVES, "100")

        self.assertEqual(self.assert_conserves(result, "100"), Decimal("100.00"))

    def test_the_solver_is_deterministic(self):
        _, first = self.build(
            [("equity", "1000"), ("fixed_income", "3000"), ("crypto", "500")],
            {
                "equity": ("40", None, None),
                "fixed_income": ("40", None, None),
                "crypto": ("20", None, None),
            },
            "777.77",
        )

        second = build_contribution(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal("777.77"),
            on_date=TODAY,
        )

        self.assertEqual(first["lines"], second["lines"])


class ContributionCommitmentTests(AllocationFixture, TestCase):
    """Lo que hay que llevar a un sitio pase lo que pase con la desviacion.

    Casos reales: el tope deducible de un plan de pensiones, la aportacion periodica que
    conserva una cuenta remunerada, el minimo de entrada de una plataforma y la comision
    de una compra suelta.
    """

    def setUp(self):
        super().setUp()
        self.equity = self.create_position("Fondo global", Decimal("10000"))
        self.pension = self.create_position(
            "Plan de pensiones", Decimal("2000"), asset_class=Instrument.AssetClass.EQUITY
        )
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

    def solve(self, amount: str, on_date: date = TODAY):
        return build_contribution(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal(amount),
            on_date=on_date,
        )

    def amounts(self, result) -> dict[int, Decimal]:
        return {row["position_id"]: Decimal(row["amount"]) for row in result["lines"]}

    def test_an_annual_tax_quota_is_served_before_the_policy(self):
        # 1.500 al ano de tope deducible valen, a tipo marginal alto, varios cientos de
        # euros seguros. La ganancia de rebalancear es una fraccion de punto: cuando
        # compiten, gana la deduccion.
        ContributionCommitment.objects.create(
            position=self.pension,
            period=ContributionCommitment.Period.YEAR,
            amount=Decimal("1500"),
            reason="Tope deducible",
        )

        result = self.solve("2000")

        self.assertEqual(self.amounts(result)[self.pension.id], Decimal("1500.00"))
        self.assertEqual(Decimal(result["commitments"][0]["amount"]), Decimal("1500.00"))

    def test_the_quota_only_claims_what_is_left_of_the_year(self):
        ContributionCommitment.objects.create(
            position=self.pension,
            period=ContributionCommitment.Period.YEAR,
            amount=Decimal("1500"),
        )
        self.contribute(self.pension, Decimal("900"), date(2024, 3, 1))

        result = self.solve("2000")

        # Ya van 900 en el ano: lo pendiente son 600, no 1.500.
        self.assertEqual(Decimal(result["commitments"][0]["amount"]), Decimal("600.00"))

    def test_a_quota_is_a_ceiling_too_not_only_a_floor(self):
        # Meter mas de 1.500 en el plan no desgrava: pasarse no es un extra, es dinero
        # mal colocado. Lo que sobra va a las demas.
        ContributionCommitment.objects.create(
            position=self.pension,
            period=ContributionCommitment.Period.YEAR,
            amount=Decimal("1500"),
        )

        result = self.solve("2000")

        amounts = self.amounts(result)
        self.assertEqual(amounts[self.pension.id], Decimal("1500.00"))
        self.assertEqual(amounts[self.equity.id], Decimal("500.00"))

    def test_a_filled_quota_stops_claiming(self):
        ContributionCommitment.objects.create(
            position=self.pension,
            period=ContributionCommitment.Period.YEAR,
            amount=Decimal("1500"),
        )
        self.contribute(self.pension, Decimal("1500"), date(2024, 3, 1))

        result = self.solve("2000")

        self.assertEqual(result["commitments"], [])
        # Y sigue siendo techo: lleno el cupo, la posicion se aparta del reparto.
        self.assertNotIn(self.pension.id, self.amounts(result))

    def test_a_monthly_floor_keeps_the_perk_alive(self):
        # La cuenta remunerada al 2,5% depende de mantener la aportacion periodica.
        # Perderla por un mes que el reparto decidio no financiar sale caro.
        ContributionCommitment.objects.create(
            position=self.pension,
            period=ContributionCommitment.Period.MONTH,
            amount=Decimal("50"),
            reason="Cuenta remunerada",
        )

        result = self.solve("200")

        self.assertGreaterEqual(self.amounts(result)[self.pension.id], Decimal("50.00"))

    def test_a_commitment_bigger_than_the_contribution_takes_what_there_is(self):
        ContributionCommitment.objects.create(
            position=self.pension,
            period=ContributionCommitment.Period.YEAR,
            amount=Decimal("1500"),
        )

        result = self.solve("300")

        self.assertEqual(self.amounts(result), {self.pension.id: Decimal("300.00")})
        self.assertEqual(Decimal(result["leftover"]), Decimal("0.00"))

    def test_a_line_that_cannot_pay_its_own_fee_is_not_proposed(self):
        # Un euro de comision sobre una linea de doce es un 8%: mas de lo que esa linea
        # puede rendir en un ano. Mejor acumular para la siguiente.
        PositionAllocationRule.objects.create(position=self.pension, operation_cost=Decimal("1"))

        result = self.solve("20")

        self.assertNotIn(self.pension.id, self.amounts(result))
        self.assertTrue(any(row["reason"] == "cost_exceeds_ticket" for row in result["skipped"]))

    def test_the_fee_tolerance_is_a_policy_decision_not_a_constant(self):
        # Quien opera sin comisiones no quiere ninguna tolerancia porque nunca aplica, y
        # quien paga por operacion querra fijar la suya. No puede vivir en el codigo.
        PositionAllocationRule.objects.create(position=self.pension, operation_cost=Decimal("1"))
        strategy = AllocationStrategy.objects.get(ownership=self.mine)
        strategy.max_cost_share = Decimal("0.5")
        strategy.save(update_fields=["max_cost_share"])

        result = self.solve("20")

        # Con la tolerancia por defecto esta linea se descartaba; con esta, no.
        self.assertIn(self.pension.id, self.amounts(result))

    def test_a_recurring_plan_pays_no_fee_so_the_line_stands(self):
        PositionAllocationRule.objects.create(
            position=self.pension, operation_cost=Decimal("1"), fee_free_plan=True
        )

        result = self.solve("20")

        self.assertIn(self.pension.id, self.amounts(result))

    def test_a_commitment_is_honoured_even_if_the_fee_looks_expensive(self):
        # La deduccion vale mucho mas que el euro de comision, asi que aqui no se
        # descarta la linea.
        PositionAllocationRule.objects.create(position=self.pension, operation_cost=Decimal("1"))
        ContributionCommitment.objects.create(
            position=self.pension,
            period=ContributionCommitment.Period.YEAR,
            amount=Decimal("1500"),
        )

        result = self.solve("20")

        self.assertIn(self.pension.id, self.amounts(result))


class ContributionBasketTests(AllocationFixture, TestCase):
    """La propuesta se guarda y se revisa; nada toca la contabilidad hasta confirmar."""

    def setUp(self):
        super().setUp()
        self.equity = self.create_position("Fondo global", Decimal("9900"))
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

    def create(self, amount: str = "1000") -> ContributionBasket:
        return create_basket(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal(amount),
            on_date=TODAY,
        )

    def test_a_basket_is_a_proposal_and_touches_no_accounting(self):
        before = LedgerTransaction.objects.count()

        basket = self.create()

        self.assertEqual(basket.status, ContributionBasket.Status.DRAFT)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), before)
        self.assertTrue(
            all(line.status == ContributionBasketLine.Status.PENDING for line in basket.lines.all())
        )

    def test_the_basket_records_the_version_it_was_solved_against(self):
        # La propuesta se juzga contra la politica que estaba escrita cuando se hizo, no
        # contra la de hoy.
        basket = self.create()

        self.assertEqual(basket.strategy.effective_from, date(2024, 1, 1))

    def test_discarding_keeps_the_proposal_you_did_not_follow(self):
        basket = self.create()

        discard_basket(basket=basket)

        basket.refresh_from_db()
        self.assertEqual(basket.status, ContributionBasket.Status.DISCARDED)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().status, ContributionBasketLine.Status.SKIPPED)

    def test_a_basket_cannot_be_discarded_twice(self):
        basket = self.create()
        discard_basket(basket=basket)

        with self.assertRaises(DjangoValidationError):
            discard_basket(basket=basket)

    def test_without_a_policy_there_is_no_basket_to_save(self):
        other = self.create_position(
            "Cripto del niño",
            Decimal("100"),
            asset_class=Instrument.AssetClass.CRYPTO,
            ownership=self.his,
        )
        del other

        with self.assertRaises(DjangoValidationError):
            create_basket(
                portfolio=self.portfolio,
                ownership=self.his,
                amount=Decimal("500"),
                on_date=TODAY,
            )

    def test_what_cannot_meet_its_minimum_waits_in_the_platform_cash(self):
        # Urbanitae pide 500 de entrada y le tocan cien y pico al mes: repartir su parte
        # entre las demas la condenaria a no financiarse nunca. Se acumula en el efectivo
        # de su propio contenedor, que es dinero real esperando en la plataforma.
        platform = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Urbanitae",
            container_type=InvestmentContainer.ContainerType.PLATFORM,
        )
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Urbanitae efectivo",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        ContainerCashAccount.objects.create(container=platform, ledger_account=cash, currency="EUR")
        crowd = self.create_position(
            "Crowdfunding", Decimal("1000"), asset_class=Instrument.AssetClass.REAL_ESTATE
        )
        crowd.container = platform
        crowd.save(update_fields=["container"])
        PositionAllocationRule.objects.create(position=crowd, min_contribution=Decimal("500"))
        AllocationTarget.objects.filter(strategy__ownership=self.mine).update(
            target_percent=Decimal("70")
        )
        AllocationTarget.objects.create(
            strategy=AllocationStrategy.objects.get(ownership=self.mine),
            asset_class=Instrument.AssetClass.REAL_ESTATE,
            target_percent=Decimal("30"),
        )

        basket = create_basket(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal("200"),
            on_date=TODAY,
        )

        accumulated = basket.lines.filter(cash_account__isnull=False).first()
        self.assertIsNotNone(accumulated)
        self.assertEqual(accumulated.reason, "below_minimum")
        self.assertIsNone(accumulated.position_id)

    def test_a_minimum_line_keeps_the_basket_free_of_pointless_tickets(self):
        # Sin esto el reparto proponia compras de nueve centimos: ningun broker las
        # ejecuta y nadie querria hacerlas.
        # La cartera esta casi en su sitio, asi que los huecos son minusculos y al de la
        # clase pequena le tocarian centimos.
        self.equity.class_breakdown.all().delete()
        crumb = self.create_position(
            "Cripto", Decimal("100"), asset_class=Instrument.AssetClass.CRYPTO
        )
        strategy = AllocationStrategy.objects.get(ownership=self.mine)
        strategy.min_line_amount = Decimal("25")
        strategy.save(update_fields=["min_line_amount"])
        AllocationTarget.objects.filter(strategy=strategy).update(target_percent=Decimal("99"))
        AllocationTarget.objects.create(
            strategy=strategy,
            asset_class=Instrument.AssetClass.CRYPTO,
            target_percent=Decimal("1"),
        )

        basket = self.create("100")

        placed = {line.position_id: line.amount for line in basket.lines.all()}
        self.assertNotIn(crumb.id, placed)
        self.assertTrue(all(amount >= Decimal("25") for amount in placed.values()))

    def test_the_basket_always_adds_up_to_the_contribution(self):
        basket = self.create("1000")

        placed = sum((line.amount for line in basket.lines.all()), Decimal("0"))
        self.assertEqual(placed + basket.reserved_cash + basket.leftover, Decimal("1000"))


class ContributionConfirmTests(AllocationFixture, TestCase):
    """Confirmar es lo unico que toca la contabilidad, y puede ser parcial."""

    def setUp(self):
        super().setUp()
        self.bank = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Apertura",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )
        opening = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 1, 1),
            value_date=date(2024, 1, 1),
            description="Saldo inicial",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=self.bank,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("5000"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("5000"),
            currency="EUR",
        )
        self.equity = self.create_position("Fondo global", Decimal("10000"))
        self.equity.ledger_account = LedgerAccount.objects.create(
            user=self.user,
            name="Fondo global",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.equity.save(update_fields=["ledger_account"])
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

    def basket(self, amount: str = "1000") -> ContributionBasket:
        return create_basket(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal(amount),
            on_date=TODAY,
            source_account_id=self.bank.id,
        )

    def test_confirming_moves_the_money_for_real(self):
        basket = self.basket()

        confirm_basket(basket=basket)

        basket.refresh_from_db()
        self.assertEqual(basket.status, ContributionBasket.Status.CONFIRMED)
        line = basket.lines.get()
        self.assertEqual(line.status, ContributionBasketLine.Status.CONFIRMED)
        self.assertIsNotNone(line.ledger_transaction_id)
        self.assertEqual(get_account_balance(account=self.bank, status="posted"), Decimal("4000"))

    def test_a_basket_can_be_confirmed_line_by_line(self):
        # Una cesta puede tener una linea que hoy no quieres ejecutar y el resto si.
        other = self.create_position(
            "Oro", Decimal("1000"), asset_class=Instrument.AssetClass.COMMODITIES
        )
        other.ledger_account = LedgerAccount.objects.create(
            user=self.user,
            name="Oro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        other.save(update_fields=["ledger_account"])
        # Las dos con hueco, para que la cesta tenga dos lineas que decidir.
        PositionValuation.objects.create(
            position=self.equity,
            valuation_date=date(2024, 12, 31),
            value=Decimal("1000"),
            currency="EUR",
        )
        AllocationTarget.objects.filter(strategy__ownership=self.mine).update(
            target_percent=Decimal("50")
        )
        AllocationTarget.objects.create(
            strategy=AllocationStrategy.objects.get(ownership=self.mine),
            asset_class=Instrument.AssetClass.COMMODITIES,
            target_percent=Decimal("50"),
        )
        basket = self.basket("1000")
        first = basket.lines.first()

        confirm_basket(basket=basket, line_ids=[first.id])

        basket.refresh_from_db()
        # Queda algo por decidir, asi que la cesta sigue abierta.
        self.assertEqual(basket.status, ContributionBasket.Status.DRAFT)
        self.assertEqual(
            basket.lines.filter(status=ContributionBasketLine.Status.CONFIRMED).count(), 1
        )
        self.assertEqual(
            basket.lines.filter(status=ContributionBasketLine.Status.PENDING).count(), 1
        )

    def test_accumulating_into_platform_cash_is_a_transfer_not_a_purchase(self):
        platform = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="Urbanitae",
            container_type=InvestmentContainer.ContainerType.PLATFORM,
        )
        wallet = LedgerAccount.objects.create(
            user=self.user,
            name="Urbanitae efectivo",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        ContainerCashAccount.objects.create(
            container=platform, ledger_account=wallet, currency="EUR"
        )
        crowd = self.create_position(
            "Crowdfunding", Decimal("1000"), asset_class=Instrument.AssetClass.REAL_ESTATE
        )
        crowd.container = platform
        crowd.save(update_fields=["container"])
        PositionAllocationRule.objects.create(position=crowd, min_contribution=Decimal("500"))
        AllocationTarget.objects.filter(strategy__ownership=self.mine).update(
            target_percent=Decimal("70")
        )
        AllocationTarget.objects.create(
            strategy=AllocationStrategy.objects.get(ownership=self.mine),
            asset_class=Instrument.AssetClass.REAL_ESTATE,
            target_percent=Decimal("30"),
        )
        basket = self.basket("200")

        confirm_basket(basket=basket)

        # El dinero espera en el monedero de la plataforma: todavia no se ha invertido.
        self.assertGreater(get_account_balance(account=wallet, status="posted"), Decimal("0"))

    def test_a_basket_without_a_funding_account_cannot_be_confirmed(self):
        basket = create_basket(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal("500"),
            on_date=TODAY,
        )

        with self.assertRaises(DjangoValidationError):
            confirm_basket(basket=basket)

    def test_a_discarded_basket_cannot_be_confirmed(self):
        basket = self.basket()
        discard_basket(basket=basket)

        with self.assertRaises(DjangoValidationError):
            confirm_basket(basket=basket)
