from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from budget.models import AnnualExpenseEntry
from memberships.models import FamilyMember, Ownership, OwnershipLink
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
        # Positivo es ir sobrado; negativo, quedarse corto.
        self.assertEqual(Decimal(rows["equity"]["drift_value"]), Decimal("1000.00"))
        self.assertEqual(Decimal(rows["commodities"]["drift_value"]), Decimal("-1000.00"))

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
        self.assertEqual(Decimal(rows["cash"]["drift_value"]), Decimal("-1000.00"))

    def test_linked_cash_shows_up_as_liquidity_and_only_for_its_owner(self):
        # El efectivo enlazado cuenta en el valor de la cartera, así que tiene que contar
        # también en la composición: sin esto la clase Liquidez marcaba cero teniendo
        # dinero, y el total de la tabla no cuadraba con el hero.
        self.create_position("Fondo global", Decimal("9000"))
        wallet_asset = Asset.objects.create(
            user=self.user,
            name="Efectivo bróker",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1000"),
            start_date=date(2024, 1, 1),
        )
        OwnershipLink.objects.create(
            user=self.user,
            ownership=self.mine,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=wallet_asset.id,
        )
        wallet = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo bróker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=wallet_asset,
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
            description="Saldo",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=wallet,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000"),
            currency="EUR",
        )
        ContainerCashAccount.objects.create(
            container=self.container, ledger_account=wallet, currency="EUR"
        )

        mine = self.classes(
            build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        )
        his = self.classes(
            build_allocation(portfolio=self.portfolio, ownership=self.his, on_date=TODAY)
        )

        self.assertEqual(Decimal(mine["cash"]["value"]), Decimal("1000.00"))
        # El efectivo no lleva titularidad propia pero su activo sí: sumarlo a todos los
        # ámbitos lo contaría varias veces.
        self.assertNotIn("cash", his)

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


class SecondLevelAllocationTests(AllocationFixture, TestCase):
    """El reparto dentro de una clase: cual de tus fondos, no cuanta renta variable."""

    def setUp(self):
        super().setUp()
        self.indexed = self.create_position("Indexado global", Decimal("6000"))
        self.small_caps = self.create_position("Small caps", Decimal("2000"))
        self.gold = self.create_position(
            "Oro", Decimal("2000"), asset_class=Instrument.AssetClass.COMMODITIES
        )

    def with_position_target(self, position, percent: str):
        strategy = self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("80", None, None), "commodities": ("20", None, None)},
        )
        AllocationTarget.objects.create(
            strategy=strategy, position=position, target_percent=Decimal(percent)
        )
        return strategy

    def positions(self, result) -> dict[int, dict]:
        return {row["position_id"]: row for row in result["by_position"]}

    def test_a_position_target_is_a_share_of_its_class_not_of_the_portfolio(self):
        # "De mi renta variable, un 75% al indexado". Sobre la cartera eso es un 60%,
        # porque la renta variable pesa un 80%. Declararlo sobre la cartera obligaria a
        # rehacer todas las lineas cada vez que cambia el objetivo de la clase.
        self.with_position_target(self.indexed, "75")

        rows = self.positions(
            build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        )

        self.assertEqual(Decimal(rows[self.indexed.id]["target_percent"]), Decimal("60.00"))
        self.assertEqual(rows[self.indexed.id]["class_share"], "75.000")
        # Lo que queda de la clase se lo reparte el resto: aqui solo hay una posicion mas.
        self.assertEqual(Decimal(rows[self.small_caps.id]["target_percent"]), Decimal("20.00"))

    def test_a_position_without_a_line_of_its_own_still_has_a_target(self):
        # Heredar el trozo de su clase no es no tener objetivo: sin esto el segundo nivel
        # solo sabia hablar de las posiciones que alguien habia escrito a mano.
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("80", None, None), "commodities": ("20", None, None)},
        )

        rows = self.positions(
            build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)
        )

        # 6000 y 2000 dentro de una clase que quiere el 80%: 60 y 20.
        self.assertEqual(Decimal(rows[self.indexed.id]["target_percent"]), Decimal("60.00"))
        self.assertEqual(Decimal(rows[self.small_caps.id]["target_percent"]), Decimal("20.00"))
        self.assertEqual(rows[self.indexed.id]["band"], "derived")
        self.assertIsNone(rows[self.indexed.id]["class_share"])

    def test_the_contribution_follows_the_second_level(self):
        # Con el indexado ya en su sitio y las small caps cortas, la aportacion va a las
        # small caps aunque la clase entera este en su objetivo.
        self.with_position_target(self.indexed, "75")

        result = build_contribution(
            portfolio=self.portfolio, ownership=self.mine, amount=Decimal("1000"), on_date=TODAY
        )

        amounts = {row["position_id"]: Decimal(row["amount"]) for row in result["lines"]}

        self.assertEqual(result["status"], "ok")
        # 80% de renta variable repartido 75/25: el indexado quiere 6.600 y tiene 6.000;
        # las small caps quieren 2.200 y tienen 2.000. Cada una recibe su hueco.
        self.assertEqual(amounts[self.indexed.id], Decimal("600.00"))
        self.assertEqual(amounts[self.small_caps.id], Decimal("200.00"))


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

    def test_a_planned_class_with_nothing_to_buy_is_reported_not_ignored(self):
        # Objetivo escrito para una clase de la que no tienes ningun producto: el dinero
        # no tiene donde ir. Antes desaparecia en silencio y su parte se la repartian las
        # demas clases, asi que la propuesta parecia ignorar la politica.
        self.create_position("Fondo global", Decimal("9000"))
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("80", None, None), "private_equity": ("20", None, None)},
        )

        result = build_contribution(
            portfolio=self.portfolio, ownership=self.mine, amount=Decimal("1000"), on_date=TODAY
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual([row["asset_class"] for row in result["unreachable"]], ["private_equity"])
        self.assertEqual(result["unreachable"][0]["reason"], "no_position")
        # El dinero sigue colocandose: no se queda en el limbo por no poder cumplir esa linea.
        self.assertEqual(sum(Decimal(row["amount"]) for row in result["lines"]), Decimal("1000"))


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


class CommitmentPriorityTests(AllocationFixture, TestCase):
    """Cuando la aportacion no llega para todos los compromisos, quien cobra primero."""

    def setUp(self):
        super().setUp()
        self.robo = self.create_position("Roboadvisor", Decimal("5000"))
        self.pension = self.create_position("Plan de pensiones", Decimal("5000"))
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

    def commit(self, position, amount: str, breach: str, period="month"):
        return ContributionCommitment.objects.create(
            position=position,
            period=period,
            amount=Decimal(amount),
            breach_cost=Decimal(breach),
            reason="prueba",
        )

    def test_the_costliest_commitment_to_break_is_served_first(self):
        # Dejar la aportacion periodica del roboadvisor tira la remuneracion de toda la
        # cuenta del banco: son 250 EUR al ano frente a los 30 de la otra. Antes decidia
        # el orden en que estuvieran guardados, que no significa nada.
        self.commit(self.pension, "300", "30")
        self.commit(self.robo, "300", "250")

        result = build_contribution(
            portfolio=self.portfolio, ownership=self.mine, amount=Decimal("300"), on_date=TODAY
        )

        served = [row["position_id"] for row in result["commitments"]]
        self.assertEqual(served, [self.robo.id])
        self.assertEqual(
            [row["position_id"] for row in result["unmet_commitments"]], [self.pension.id]
        )

    def test_commitments_that_cost_the_same_to_break_share_what_there_is(self):
        # Con 1.500 y 2.100 al ano pendientes, una aportacion de 300 se reparte 125 y 175:
        # cada uno recibe su parte de lo que reclama. Antes se servia en orden hasta
        # agotar, asi que el mayor se llevaba los 300 enteros y el otro se quedaba a cero
        # sin que nadie hubiera decidido eso.
        self.commit(self.pension, "1500", "0", period="year")
        self.commit(self.robo, "2100", "0", period="year")

        result = build_contribution(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal("300"),
            on_date=date(2024, 1, 31),
        )

        served = {row["position_id"]: Decimal(row["amount"]) for row in result["commitments"]}
        self.assertEqual(served[self.pension.id], Decimal("125.00"))
        self.assertEqual(served[self.robo.id], Decimal("175.00"))

    def test_a_costlier_breach_still_goes_first(self):
        # Repartir a prorrata es solo entre iguales: si romper uno cuesta mas, ese cobra
        # entero antes de que el otro vea un euro.
        self.commit(self.pension, "300", "0")
        self.commit(self.robo, "300", "250")

        result = build_contribution(
            portfolio=self.portfolio, ownership=self.mine, amount=Decimal("300"), on_date=TODAY
        )

        served = {row["position_id"]: Decimal(row["amount"]) for row in result["commitments"]}
        self.assertEqual(served, {self.robo.id: Decimal("300.00")})

    def test_what_the_contribution_cannot_cover_is_reported_with_its_cost(self):
        self.commit(self.robo, "500", "250")

        result = build_contribution(
            portfolio=self.portfolio, ownership=self.mine, amount=Decimal("200"), on_date=TODAY
        )

        unmet = result["unmet_commitments"]
        self.assertEqual(len(unmet), 1)
        # Se aportan 200 de los 500: faltan 300, y romperlo cuesta 250 al ano.
        self.assertEqual(Decimal(unmet[0]["amount"]), Decimal("300"))
        self.assertEqual(Decimal(unmet[0]["breach_cost"]), Decimal("250"))

    def test_a_covered_commitment_reports_nothing_pending(self):
        self.commit(self.robo, "100", "250")

        result = build_contribution(
            portfolio=self.portfolio, ownership=self.mine, amount=Decimal("500"), on_date=TODAY
        )

        self.assertEqual(result["unmet_commitments"], [])


class MinimumWithoutCashTests(AllocationFixture, TestCase):
    """Un minimo de entrada sin sitio donde esperar tiene que decirse."""

    def setUp(self):
        super().setUp()
        self.big = self.create_position("Fondo global", Decimal("9000"))
        self.urbanitae = self.create_position(
            "Crowdfunding", Decimal("1000"), asset_class=Instrument.AssetClass.REAL_ESTATE
        )
        PositionAllocationRule.objects.create(
            position=self.urbanitae, min_contribution=Decimal("500")
        )
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("50", None, None), "real_estate": ("50", None, None)},
        )

    def test_a_position_below_its_minimum_without_container_cash_says_so(self):
        # 25 EUR no llegan al minimo de 500, y el contenedor no tiene efectivo enlazado
        # donde esperar. Antes su parte volvia al reparto en silencio y la posicion
        # desaparecia de la propuesta sin explicacion.
        result = build_contribution(
            portfolio=self.portfolio, ownership=self.mine, amount=Decimal("25"), on_date=TODAY
        )

        reasons = {row["position_id"]: row for row in result["skipped"]}
        self.assertEqual(reasons[self.urbanitae.id]["reason"], "below_minimum_no_cash")
        self.assertEqual(Decimal(reasons[self.urbanitae.id]["minimum"]), Decimal("500"))
        # El dinero no se pierde: se coloca en lo que si puede recibirlo.
        self.assertEqual(sum(Decimal(row["amount"]) for row in result["lines"]), Decimal("25"))

    def test_with_container_cash_it_waits_there_instead(self):
        cash_asset = Asset.objects.create(
            user=self.user,
            name="Monedero Urbanitae",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("0"),
        )
        ContainerCashAccount.objects.create(
            container=self.container,
            ledger_account=LedgerAccount.objects.create(
                user=self.user,
                name="Monedero Urbanitae",
                account_type=LedgerAccount.AccountType.ASSET,
                currency="EUR",
                asset=cash_asset,
            ),
            currency="EUR",
        )

        result = build_contribution(
            portfolio=self.portfolio, ownership=self.mine, amount=Decimal("25"), on_date=TODAY
        )

        self.assertTrue(result["accumulate"])
        self.assertEqual(result["accumulate"][0]["reason"], "below_minimum")


class ContainerFloorTests(AllocationFixture, TestCase):
    """El minimo de una plataforma es de la plataforma, no de un producto suyo."""

    def setUp(self):
        super().setUp()
        self.robo = self.create_position("Roboadvisor", Decimal("5000"))
        self.pension = self.create_position("Plan de pensiones", Decimal("5000"))
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})
        ContributionCommitment.objects.create(
            container=self.container,
            period=ContributionCommitment.Period.MONTH,
            amount=Decimal("300"),
            breach_cost=Decimal("300"),
            reason="Minimo de MyInvestor",
        )
        ContributionCommitment.objects.create(
            position=self.pension,
            period=ContributionCommitment.Period.YEAR,
            amount=Decimal("1500"),
            reason="Tope deducible",
        )
        ContributionCommitment.objects.create(
            position=self.robo,
            period=ContributionCommitment.Period.YEAR,
            amount=Decimal("2100"),
            reason="Resto del minimo anual",
        )

    def january(self, amount: str):
        return build_contribution(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal(amount),
            on_date=date(2024, 1, 31),
        )

    def test_the_year_quota_is_paced_instead_of_emptied_in_january(self):
        # Meter los 1.500 del plan en enero deja los once meses siguientes sin nada que
        # aportar ahi, y con un minimo mensual de plataforma por medio eso es perderlo.
        result = self.january("300")

        served = {row["position_id"]: Decimal(row["amount"]) for row in result["commitments"]}
        self.assertEqual(served[self.pension.id], Decimal("125.00"))
        self.assertEqual(served[self.robo.id], Decimal("175.00"))

    def test_the_floor_is_covered_between_the_products_of_its_container(self):
        # 300 al mes en la plataforma, repartidos a proporcion de lo que le queda a cada
        # cupo: 1.500 y 2.100 son 5 y 7 de cada 12.
        result = self.january("300")

        total = sum(Decimal(row["amount"]) for row in result["lines"])
        self.assertEqual(total, Decimal("300"))
        self.assertEqual(result["unmet_commitments"], [])

    def test_one_line_per_position_even_when_two_reasons_feed_it(self):
        # El cupo del plan y el suelo de MyInvestor son dos motivos del mismo dinero. En
        # dos lineas se leian como dos destinos distintos —"114 al plan" y "36 de
        # compromiso"— cuando son 150 al plan.
        ContributionCommitment.objects.filter(position=self.robo).delete()

        result = self.january("300")

        served = {row["position_id"]: Decimal(row["amount"]) for row in result["commitments"]}
        pension = next(
            row for row in result["commitments"] if row["position_id"] == self.pension.id
        )

        # Una fila por posicion, aunque la alimenten dos motivos.
        self.assertEqual(len(result["commitments"]), len(served))
        self.assertEqual(pension["reason"], "Tope deducible · Minimo de MyInvestor")
        self.assertEqual(sum(served.values()), Decimal("300"))

    def test_a_contribution_below_the_floor_says_what_is_missing(self):
        result = self.january("200")

        unmet = result["unmet_commitments"]
        self.assertTrue(any(row.get("container_id") == self.container.id for row in unmet))

    def test_in_december_the_quota_claims_what_is_left(self):
        # Con un solo mes por delante, repartir por los meses que quedan es reclamarlo
        # todo: el cupo se pierde si no se llena antes de que acabe el ano.
        result = build_contribution(
            portfolio=self.portfolio,
            ownership=self.mine,
            amount=Decimal("5000"),
            on_date=date(2024, 12, 31),
        )

        served = {row["position_id"]: Decimal(row["amount"]) for row in result["commitments"]}
        self.assertEqual(served[self.pension.id], Decimal("1500.00"))


class SuggestedContributionTests(AllocationFixture, TestCase):
    """Lo que queda por aportar este mes, no el mes entero cada vez que se mira."""

    def setUp(self):
        super().setUp()
        self.position = self.create_position("Fondo global", Decimal("10000"))
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Aportacion mensual",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            subcategory="index_funds",
            time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
            amount_annual=Decimal("1200.00"),
            fiscal_year=TODAY.year,
            currency="EUR",
        )

    def withdraw(self, amount: Decimal, on_date: date) -> None:
        InvestmentAssetEvent.objects.create(
            user=self.user,
            asset=self.position.asset,
            event_date=on_date,
            event_type=InvestmentAssetEvent.EventType.WITHDRAWAL,
            amount=amount,
        )

    def solved(self) -> dict:
        return build_allocation(portfolio=self.portfolio, ownership=self.mine, on_date=TODAY)

    def test_what_is_already_in_this_month_is_discounted(self):
        self.contribute(self.position, Decimal("40"), TODAY)

        result = self.solved()

        self.assertEqual(result["planned_contribution"], "100.00")
        self.assertEqual(result["contributed_this_month"], "40.00")
        self.assertEqual(result["suggested_contribution"], "60.00")

    def test_selling_to_buy_elsewhere_is_not_contributing(self):
        # Vender un fondo para comprar otro no es dinero nuevo: contando solo las entradas,
        # una recolocacion se comia el presupuesto del mes sin salir un euro del bolsillo.
        self.contribute(self.position, Decimal("700"), TODAY)
        self.withdraw(Decimal("700"), TODAY)

        result = self.solved()

        self.assertEqual(result["contributed_this_month"], "0.00")
        self.assertEqual(result["suggested_contribution"], "100.00")

    def test_a_month_already_covered_suggests_nothing(self):
        self.contribute(self.position, Decimal("250"), TODAY)

        result = self.solved()

        self.assertEqual(result["contributed_this_month"], "250.00")
        self.assertEqual(result["suggested_contribution"], "0.00")

    def test_last_month_does_not_count_against_this_one(self):
        self.contribute(self.position, Decimal("90"), date(TODAY.year, TODAY.month - 1, 15))

        result = self.solved()

        self.assertEqual(result["contributed_this_month"], "0.00")
        self.assertEqual(result["suggested_contribution"], "100.00")


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

    def test_confirming_books_the_commission_the_rule_declares(self):
        # Lo que cuesta ejecutar la linea ya esta escrito en la regla de la posicion, que
        # es el numero con el que el reparto decide si la operacion se sostiene.
        PositionAllocationRule.objects.create(position=self.equity, operation_cost=Decimal("1.50"))
        basket = self.basket()

        confirm_basket(basket=basket)

        line = basket.lines.get()
        transaction = LedgerTransaction.objects.get(id=line.ledger_transaction_id)
        fee = transaction.fee_movements.get()
        self.assertEqual(fee.entries.get(side=LedgerEntry.Side.DEBIT).amount, Decimal("1.50"))
        # La comision sale de la misma cuenta que financia la compra, ademas del importe.
        self.assertEqual(
            get_account_balance(account=self.bank, status="posted"), Decimal("3998.50")
        )

    def test_a_fee_free_plan_is_confirmed_without_commission(self):
        PositionAllocationRule.objects.create(
            position=self.equity, operation_cost=Decimal("1.50"), fee_free_plan=True
        )
        basket = self.basket()

        confirm_basket(basket=basket)

        transaction = LedgerTransaction.objects.get(id=basket.lines.get().ledger_transaction_id)
        self.assertFalse(transaction.fee_movements.exists())
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


class AllocationApiTests(AllocationFixture, APITestCase):
    """El contrato que va a consumir la interfaz."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)
        self.equity = self.create_position("Fondo global", Decimal("10000"))

    def test_a_policy_is_written_with_its_targets_in_one_call(self):
        response = self.client.post(
            "/api/portfolio/strategies/",
            {
                "ownership_id": self.mine.id,
                "effective_from": "2024-01-01",
                "targets": [
                    {"asset_class": "equity", "target_percent": "60", "min_percent": "55"},
                    {"asset_class": "cash", "target_percent": "40"},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["target_total"], "100.000")
        self.assertEqual(len(response.data["targets"]), 2)

    def test_a_target_belongs_to_a_class_or_to_a_position_but_not_both(self):
        response = self.client.post(
            "/api/portfolio/strategies/",
            {
                "ownership_id": self.mine.id,
                "effective_from": "2024-01-01",
                "targets": [
                    {
                        "asset_class": "equity",
                        "position_id": self.equity.id,
                        "target_percent": "100",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_you_cannot_set_a_target_for_what_is_not_classified_yet(self):
        response = self.client.post(
            "/api/portfolio/strategies/",
            {
                "ownership_id": self.mine.id,
                "effective_from": "2024-01-01",
                "targets": [{"asset_class": "unclassified", "target_percent": "100"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_editing_a_policy_replaces_its_targets(self):
        strategy = self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

        response = self.client.patch(
            f"/api/portfolio/strategies/{strategy.id}/",
            {"targets": [{"asset_class": "cash", "target_percent": "100"}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual([row["asset_class"] for row in response.data["targets"]], ["cash"])

    def test_the_allocation_reads_actual_against_target(self):
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("60", "55", "65")})

        response = self.client.get(
            f"/api/portfolio/allocation/?ownership_id={self.mine.id}&on_date=2024-12-31"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        row = next(r for r in response.data["by_class"] if r["asset_class"] == "equity")
        self.assertEqual(row["actual_percent"], "100.00")
        self.assertEqual(row["band"], "above")

    def test_solving_a_contribution_saves_nothing(self):
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

        response = self.client.post(
            "/api/portfolio/contribution/solve/",
            {"ownership_id": self.mine.id, "amount": "500", "on_date": "2024-12-31"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(ContributionBasket.objects.count(), 0)

    def test_a_basket_is_created_from_a_solve_and_can_be_discarded(self):
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

        created = self.client.post(
            "/api/portfolio/baskets/",
            {"ownership_id": self.mine.id, "amount": "500", "on_date": "2024-12-31"},
            format="json",
        )
        discarded = self.client.post(
            f"/api/portfolio/baskets/{created.data['id']}/discard/", {}, format="json"
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data["status"], "draft")
        self.assertEqual(len(created.data["lines"]), 1)
        self.assertEqual(discarded.data["status"], "discarded")

    def test_the_allocation_suggests_what_the_budget_planned_to_invest(self):
        # El importe por defecto sale de lo que ya habias planificado invertir ese mes.
        # Solo se lee: elegir otra cifra no reescribe el presupuesto.
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Aportacion mensual",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
            cashflow_role=AnnualExpenseEntry.CashflowRole.INVESTMENT,
            amount_input_period=AnnualExpenseEntry.AmountInputPeriod.MONTHLY,
            amount_annual=Decimal("6000"),
            fiscal_year=2024,
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Extra de marzo",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            expense_type=AnnualExpenseEntry.ExpenseType.ONE_OFF,
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            cashflow_role=AnnualExpenseEntry.CashflowRole.INVESTMENT,
            amount_input_period=AnnualExpenseEntry.AmountInputPeriod.ANNUAL,
            amount_annual=Decimal("1200"),
            fiscal_year=2024,
            target_month=3,
        )
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

        december = self.client.get(
            f"/api/portfolio/allocation/?ownership_id={self.mine.id}&on_date=2024-12-31"
        )
        march = self.client.get(
            f"/api/portfolio/allocation/?ownership_id={self.mine.id}&on_date=2024-03-31"
        )

        self.assertEqual(december.status_code, status.HTTP_200_OK, december.data)
        self.assertEqual(Decimal(december.data["suggested_contribution"]), Decimal("500.00"))
        # Lo puntual solo cuenta en el mes al que se apunto, no todos los meses.
        self.assertEqual(Decimal(march.data["suggested_contribution"]), Decimal("1700.00"))

    def test_the_basket_list_answers_by_scope_and_by_what_is_still_open(self):
        # La pantalla pregunta por lo que queda pendiente de decidir en un ambito, no por
        # el historico entero de propuestas de toda la cartera.
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})
        self.create_position("Cripto del niño", Decimal("100"), ownership=self.his)
        self.strategy(self.his, date(2024, 1, 1), {"equity": ("100", None, None)})
        mine = self.client.post(
            "/api/portfolio/baskets/",
            {"ownership_id": self.mine.id, "amount": "500", "on_date": "2024-12-31"},
            format="json",
        )
        self.client.post(
            "/api/portfolio/baskets/",
            {"ownership_id": self.his.id, "amount": "100", "on_date": "2024-12-31"},
            format="json",
        )
        self.client.post(f"/api/portfolio/baskets/{mine.data['id']}/discard/", {}, format="json")

        scoped = self.client.get(f"/api/portfolio/baskets/?ownership_id={self.mine.id}")
        pending = self.client.get(
            f"/api/portfolio/baskets/?ownership_id={self.mine.id}&status=draft"
        )
        everything = self.client.get("/api/portfolio/baskets/")

        self.assertEqual(scoped.status_code, status.HTTP_200_OK, scoped.data)
        self.assertEqual([row["id"] for row in scoped.data], [mine.data["id"]])
        self.assertEqual(pending.data, [])
        self.assertEqual(len(everything.data), 2)

    def test_an_amount_written_in_spanish_is_understood(self):
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

        response = self.client.post(
            "/api/portfolio/contribution/solve/",
            {"ownership_id": self.mine.id, "amount": "1.500,50", "on_date": "2024-12-31"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Decimal(response.data["amount"]), Decimal("1500.50"))

    def test_an_amount_that_is_not_a_number_is_refused(self):
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})

        response = self.client.post(
            "/api/portfolio/contribution/solve/",
            {"ownership_id": self.mine.id, "amount": "mucho"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_a_basket_without_a_source_account_is_refused_with_a_readable_message(self):
        # Confirmar sin decir de donde sale el dinero es una condicion prevista, no una
        # averia: antes salia por la API como un 500 sin mensaje que leer.
        self.strategy(self.mine, date(2024, 1, 1), {"equity": ("100", None, None)})
        created = self.client.post(
            "/api/portfolio/baskets/",
            {"ownership_id": self.mine.id, "amount": "500", "on_date": "2024-12-31"},
            format="json",
        )

        response = self.client.post(
            f"/api/portfolio/baskets/{created.data['id']}/confirm/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("source_account_id", response.data["error"]["details"])

    def test_another_users_ownership_is_not_reachable(self):
        stranger = get_user_model().objects.create_user(username="otra", password="pass")
        member = FamilyMember.objects.create(
            user=stranger, name="Ajena", role=FamilyMember.Role.ADULT
        )
        theirs = Ownership.objects.create(
            user=stranger, kind=Ownership.Kind.INDIVIDUAL, member=member
        )

        response = self.client.get(f"/api/portfolio/allocation/?ownership_id={theirs.id}")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_a_rule_and_a_commitment_are_editable(self):
        rule = self.client.post(
            "/api/portfolio/allocation-rules/",
            {"position_id": self.equity.id, "min_contribution": "500"},
            format="json",
        )
        commitment = self.client.post(
            "/api/portfolio/commitments/",
            {
                "position_id": self.equity.id,
                "period": "year",
                "amount": "1500",
                "reason": "Tope deducible",
            },
            format="json",
        )

        self.assertEqual(rule.status_code, status.HTTP_201_CREATED, rule.data)
        self.assertEqual(commitment.status_code, status.HTTP_201_CREATED, commitment.data)
        self.assertEqual(commitment.data["amount"], "1500.00")
