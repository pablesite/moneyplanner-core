from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from ..models import (
    Asset,
    Liability,
)
from ..serializers import (
    AssetSerializer,
    AssetValuationSerializer,
    InvestmentAssetEventSerializer,
    LiabilitySerializer,
    LiabilityEventSerializer,
    LiabilityValuationSerializer,
    LiquidityAssetEventSerializer,
)

class NetWorthSerializerUnitTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="serializer_user", password="pass1234"
        )
        self.factory = APIRequestFactory()
        self.request = self.factory.post("/api/net-worth/assets/")
        self.request.user = self.user

    def test_asset_serializer_create_and_validate(self):
        serializer = AssetSerializer(
            data={
                "name": "Cuenta",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "tracking_mode": Asset.TrackingMode.MANUAL,
                "currency": "EUR",
                "annual_interest_tae": "0.50",
                "amount": "100.00",
            },
            context={"request": self.request, "base_currency": "EUR"},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        asset = serializer.save()
        self.assertEqual(asset.user_id, self.user.id)

    def test_asset_serializer_requires_short_term_deposit_duration(self):
        serializer = AssetSerializer(
            data={
                "name": "Deposito corto",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.SHORT_TERM_DEPOSIT,
                "tracking_mode": Asset.TrackingMode.MANUAL,
                "currency": "EUR",
                "annual_interest_tae": "2.10",
                "amount": "100.00",
            },
            context={"request": self.request, "base_currency": "EUR"},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("deposit_term_months", serializer.errors)

    def test_liability_serializer_context_queryset_and_validate(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Casa",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            amount=Decimal("200000.00"),
            is_active=True,
        )
        serializer = LiabilitySerializer(
            data={
                "name": "Hipoteca",
                "category": Liability.Category.MORTGAGE,
                "tracking_mode": Liability.TrackingMode.MANUAL,
                "currency": "EUR",
                "annual_interest_tae": "2.50",
                "amount": "150000.00",
                "financed_asset_id": asset.id,
            },
            context={
                "request": self.request,
                "base_currency": "EUR",
                "financed_asset_queryset": Asset.objects.filter(user=self.user),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        liability = serializer.save()
        self.assertTrue(liability.is_asset_backed)

    def test_liability_serializer_exposes_estimated_monthly_payment_amount(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            annual_interest_tae=Decimal("6.00"),
            amount=Decimal("10000.00"),
            term_months=24,
            rate_type=Liability.RateType.FIXED,
            payment_frequency=Liability.PaymentFrequency.MONTHLY,
            amortization_system=Liability.AmortizationSystem.FRENCH,
            is_active=True,
        )
        serializer = LiabilitySerializer(
            liability,
            context={
                "request": self.request,
                "base_currency": "EUR",
                "financed_asset_queryset": Asset.objects.filter(user=self.user),
            },
        )
        self.assertIsNotNone(serializer.data["estimated_monthly_payment_amount"])

    def test_asset_valuation_serializer_create(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        serializer = AssetValuationSerializer(
            data={
                "asset_id": asset.id,
                "valuation_date": "2026-02-28",
                "value": "1100.00",
                "source": "manual_checkpoint",
            },
            context={
                "request": self.request,
                "asset_queryset": Asset.objects.filter(user=self.user),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        valuation = serializer.save()
        self.assertEqual(valuation.user_id, self.user.id)

    def test_investment_asset_event_serializer_create(self):
        asset = Asset.objects.create(
            user=self.user,
            name="ETF",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        serializer = InvestmentAssetEventSerializer(
            data={
                "asset_id": asset.id,
                "event_date": "2026-02-28",
                "event_type": "passive_income",
                "amount": "25.00",
                "is_reinvested": False,
            },
            context={
                "request": self.request,
                "investment_asset_queryset": Asset.objects.filter(user=self.user),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        event = serializer.save()
        self.assertEqual(event.user_id, self.user.id)

    def test_liquidity_asset_event_serializer_create(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("1000.00"),
            annual_interest_tae=Decimal("0.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        serializer = LiquidityAssetEventSerializer(
            data={
                "asset_id": asset.id,
                "event_date": "2026-02-28",
                "event_type": "interest",
                "amount": "5.00",
            },
            context={
                "request": self.request,
                "liquidity_event_asset_queryset": Asset.objects.filter(user=self.user),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        event = serializer.save()
        self.assertEqual(event.user_id, self.user.id)

    def test_liability_event_serializer_create(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Visa",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            annual_interest_tae=Decimal("18.00"),
            amount=Decimal("500.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        serializer = LiabilityEventSerializer(
            data={
                "liability_id": liability.id,
                "event_date": "2026-02-28",
                "event_type": "payment",
                "amount": "50.00",
            },
            context={
                "request": self.request,
                "liability_event_queryset": Liability.objects.filter(user=self.user),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        event = serializer.save()
        self.assertEqual(event.user_id, self.user.id)

    def test_liability_valuation_serializer_create(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo",
            category=Liability.Category.OTHER,
            currency="EUR",
            amount=Decimal("500.00"),
            is_active=True,
        )
        serializer = LiabilityValuationSerializer(
            data={
                "liability_id": liability.id,
                "valuation_date": "2026-02-28",
                "value": "450.00",
                "source": "manual_checkpoint",
            },
            context={
                "request": self.request,
                "liability_queryset": Liability.objects.filter(user=self.user),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        valuation = serializer.save()
        self.assertEqual(valuation.user_id, self.user.id)

