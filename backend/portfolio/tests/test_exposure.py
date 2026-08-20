from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount
from net_worth.models import Asset
from portfolio.exposure import build_exposure, overlap_percent
from portfolio.models import (
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioPosition,
    PositionExposure,
    PositionValuation,
)

TODAY = date(2024, 12, 31)


class ExposureFixture:
    """Dos productos que parecen distintos y por dentro son casi lo mismo."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="exposure", password="pass")
        self.portfolio = Portfolio.objects.create(user=self.user, base_currency="EUR")
        self.container = InvestmentContainer.objects.create(
            portfolio=self.portfolio,
            name="MyInvestor",
            container_type=InvestmentContainer.ContainerType.BANK,
        )

    def create_position(self, name: str, value: Decimal) -> PortfolioPosition:
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
            asset_class=Instrument.AssetClass.EQUITY,
            instrument_type=Instrument.InstrumentType.FUND,
            quote_currency="EUR",
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
            instrument=instrument,
            asset=asset,
            ledger_account=account,
            opened_on=date(2024, 1, 1),
        )
        PositionValuation.objects.create(
            position=position,
            valuation_date=date(2024, 12, 31),
            value=value,
            currency="EUR",
            source=PositionValuation.Source.MANUAL,
        )
        return position

    def declare(self, position, dimension, weights: dict[str, str]):
        for bucket, percent in weights.items():
            PositionExposure.objects.create(
                position=position,
                dimension=dimension,
                bucket=bucket,
                percent=Decimal(percent),
                observed_on=date(2024, 11, 30),
            )


class ExposureTests(ExposureFixture, TestCase):
    def test_the_split_is_computed_over_what_is_declared_not_over_the_whole_portfolio(self):
        # Media cartera sin declarar no hace que la otra media pese menos: el reparto se
        # calcula sobre lo cubierto y la cobertura se publica aparte. Si no, las partes
        # no suman cien y el grafico miente por los dos lados.
        declared = self.create_position("Indexado global", Decimal("6000"))
        self.create_position("Crowdfunding", Decimal("4000"))
        self.declare(
            declared,
            PositionExposure.Dimension.GEOGRAPHY,
            {"north_america": "70", "europe": "30"},
        )

        result = build_exposure(portfolio=self.portfolio, on_date=TODAY)
        geography = next(row for row in result["dimensions"] if row["dimension"] == "geography")

        self.assertEqual(Decimal(geography["covered_percent"]), Decimal("60.00"))
        self.assertEqual(geography["status"], "partial")
        rows = {row["bucket"]: Decimal(row["percent"]) for row in geography["rows"]}
        self.assertEqual(rows["north_america"], Decimal("70.00"))
        self.assertEqual(rows["europe"], Decimal("30.00"))

    def test_a_dimension_nobody_declared_says_so_instead_of_drawing_nothing(self):
        self.create_position("Indexado global", Decimal("6000"))

        result = build_exposure(portfolio=self.portfolio, on_date=TODAY)
        sector = next(row for row in result["dimensions"] if row["dimension"] == "sector")

        self.assertEqual(sector["status"], "insufficient")
        self.assertEqual(sector["rows"], [])

    def test_a_position_that_only_declares_part_of_itself_covers_only_that_part(self):
        # Una ficha que reparte el 90% y calla el resto no cubre ese resto.
        position = self.create_position("Fondo mixto", Decimal("10000"))
        self.declare(
            position, PositionExposure.Dimension.GEOGRAPHY, {"north_america": "60", "europe": "30"}
        )

        result = build_exposure(portfolio=self.portfolio, on_date=TODAY)
        geography = next(row for row in result["dimensions"] if row["dimension"] == "geography")

        self.assertEqual(Decimal(geography["covered_percent"]), Decimal("90.00"))

    def test_two_products_bought_as_different_things_show_their_overlap(self):
        # La pregunta que se hace uno mirando el indexado global y el fondo US del
        # roboadvisor: cuanto de esto es en realidad lo mismo.
        left = self.create_position("Indexado global", Decimal("8000"))
        right = self.create_position("Fondo US", Decimal("4000"))
        self.declare(
            left, PositionExposure.Dimension.GEOGRAPHY, {"north_america": "70", "europe": "30"}
        )
        self.declare(right, PositionExposure.Dimension.GEOGRAPHY, {"north_america": "100"})

        result = build_exposure(portfolio=self.portfolio, on_date=TODAY)
        pair = next(row for row in result["overlap"] if row["dimension"] == "geography")

        # Comparten el 70 que los dos tienen en Norteamerica.
        self.assertEqual(Decimal(pair["percent"]), Decimal("70.00"))
        # Y en dinero, el 70% del menor de los dos: 2.800 expuestos dos veces a lo mismo.
        self.assertEqual(Decimal(pair["shared_value"]), Decimal("2800.00"))

    def test_products_that_share_little_are_not_reported_as_a_finding(self):
        left = self.create_position("Europa", Decimal("5000"))
        right = self.create_position("Emergentes", Decimal("5000"))
        self.declare(left, PositionExposure.Dimension.GEOGRAPHY, {"europe": "90", "emerging": "10"})
        self.declare(
            right, PositionExposure.Dimension.GEOGRAPHY, {"emerging": "90", "europe": "10"}
        )

        result = build_exposure(portfolio=self.portfolio, on_date=TODAY)

        self.assertEqual(result["overlap"], [])

    def test_sharing_a_wrapper_is_not_an_overlap(self):
        # Dos ETFs comparten el 100% de su vehiculo por definicion. Publicarlo llenaba la
        # lista de hallazgos que no dicen nada y tapaba los que si.
        left = self.create_position("ETF uno", Decimal("5000"))
        right = self.create_position("ETF dos", Decimal("5000"))
        self.declare(left, PositionExposure.Dimension.VEHICLE, {"etf": "100"})
        self.declare(right, PositionExposure.Dimension.VEHICLE, {"etf": "100"})

        result = build_exposure(portfolio=self.portfolio, on_date=TODAY)

        self.assertEqual(result["overlap"], [])

    def test_concentration_reports_the_weight_of_the_biggest_positions(self):
        self.create_position("Grande", Decimal("8000"))
        self.create_position("Pequena", Decimal("2000"))

        result = build_exposure(portfolio=self.portfolio, on_date=TODAY)

        concentration = result["concentration"]
        self.assertEqual(concentration["top_positions"][0]["name"], "Grande")
        self.assertEqual(Decimal(concentration["top_positions"][0]["percent"]), Decimal("80.00"))
        self.assertEqual(Decimal(concentration["top_five_percent"]), Decimal("100.00"))
        # 0,8^2 + 0,2^2 = 0,68. Con dos posiciones el reparto perfecto es 0,5, asi que
        # el indice es (1 - 0,68) / (1 - 0,5) = 0,64.
        self.assertEqual(Decimal(concentration["diversification_index"]), Decimal("0.640"))
        # Y en legible: esta cartera equivale a 1,47 posiciones iguales.
        self.assertEqual(Decimal(concentration["effective_positions"]), Decimal("1.47"))

    def test_overlap_of_identical_splits_is_total(self):
        weights = {"north_america": Decimal("60"), "europe": Decimal("40")}

        self.assertEqual(overlap_percent(weights, dict(weights)), Decimal("100.00"))


class ExposureApiTests(ExposureFixture, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)
        self.position = self.create_position("Indexado global", Decimal("10000"))

    def test_a_split_is_written_and_read_back(self):
        created = self.client.post(
            "/api/portfolio/exposures/",
            {
                "position_id": self.position.id,
                "dimension": "geography",
                "bucket": "north_america",
                "percent": "70",
                "observed_on": "2024-11-30",
            },
            format="json",
        )
        listed = self.client.get(f"/api/portfolio/exposures/?position_id={self.position.id}")

        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(len(listed.data), 1)

    def test_a_dimension_cannot_be_split_beyond_one_hundred(self):
        self.declare(self.position, PositionExposure.Dimension.GEOGRAPHY, {"north_america": "70"})

        response = self.client.post(
            "/api/portfolio/exposures/",
            {
                "position_id": self.position.id,
                "dimension": "geography",
                "bucket": "europe",
                "percent": "40",
                "observed_on": "2024-11-30",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_the_aggregate_is_reachable_and_scoped_to_its_owner(self):
        stranger = get_user_model().objects.create_user(username="otra", password="pass")
        Portfolio.objects.create(user=stranger, base_currency="EUR")

        mine = self.client.get("/api/portfolio/exposure/?on_date=2024-12-31")
        self.client.force_authenticate(stranger)
        theirs = self.client.get("/api/portfolio/exposure/?on_date=2024-12-31")

        self.assertEqual(mine.status_code, status.HTTP_200_OK, mine.data)
        self.assertEqual(Decimal(mine.data["total_value"]), Decimal("10000.00"))
        self.assertEqual(Decimal(theirs.data["total_value"]), Decimal("0.00"))
