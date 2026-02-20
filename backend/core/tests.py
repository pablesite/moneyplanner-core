from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.utils import override_settings

from .models import FxRate, InflationIndex
from .services import (
    _get_inflation_index,
    _normalize_month_start,
    adjust_for_inflation,
    convert_currency,
    get_latest_inflation_period,
    normalize_currency_code,
    validate_fx_currency_pair,
    validate_inflation_period_start,
)


class CoreServicesTests(TestCase):
    def test_normalize_currency_code(self):
        self.assertEqual(normalize_currency_code(" eur "), "EUR")
        self.assertEqual(normalize_currency_code(None), "")

    def test_validate_fx_currency_pair_rejects_invalid_codes(self):
        with self.assertRaises(ValidationError):
            validate_fx_currency_pair(from_currency="EU", to_currency="USD")

    def test_validate_inflation_period_start_rejects_non_first_day(self):
        with self.assertRaises(ValidationError):
            validate_inflation_period_start(period=date(2026, 2, 2))

    def test_normalize_month_start_from_string_and_invalid_type(self):
        self.assertEqual(_normalize_month_start("2026-02-18"), date(2026, 2, 1))
        with self.assertRaises(ValidationError):
            _normalize_month_start(123)

    def test_get_inflation_index_requires_region_and_has_fallback(self):
        with self.assertRaises(ValidationError):
            _get_inflation_index("", date(2026, 2, 1))

        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 3, 1),
            index=Decimal("102.0000"),
        )
        # Querying earlier than first known period should fallback to first row.
        self.assertEqual(_get_inflation_index("ES", date(2026, 1, 1)), Decimal("102.0000"))

    def test_convert_currency_direct_rate(self):
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.90"),
            rate_date=date(2026, 2, 1),
        )

        amount = convert_currency(Decimal("100"), "USD", "EUR", date=date(2026, 2, 15))
        self.assertEqual(amount, Decimal("90.00"))

    def test_convert_currency_inverse_rate(self):
        FxRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("1.25"),
            rate_date=date(2026, 2, 1),
        )

        amount = convert_currency(Decimal("125"), "USD", "EUR", date=date(2026, 2, 15))
        self.assertEqual(amount, Decimal("100.00"))

    @override_settings()
    def test_convert_currency_uses_pivot_triangulation(self):
        FxRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("1.10"),
            rate_date=date(2026, 2, 1),
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="JPY",
            rate=Decimal("150"),
            rate_date=date(2026, 2, 1),
        )

        amount = convert_currency(Decimal("2"), "EUR", "JPY", date=date(2026, 2, 10))
        self.assertEqual(amount, Decimal("330.00"))

    def test_convert_currency_raises_when_pair_missing(self):
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "EUR", "GBP", date=date(2026, 2, 10))

    def test_convert_currency_validates_amount_and_code(self):
        with self.assertRaises(ValidationError):
            convert_currency(None, "EUR", "USD", date=date(2026, 2, 10))
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "EU", "USD", date=date(2026, 2, 10))

    def test_convert_currency_same_currency_shortcut(self):
        amount = convert_currency(Decimal("10.126"), "EUR", "EUR", date=date(2026, 2, 10))
        self.assertEqual(amount, Decimal("10.13"))

    def test_convert_currency_inverse_zero_rate_raises(self):
        FxRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("0"),
            rate_date=date(2026, 2, 1),
        )
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "USD", "EUR", date=date(2026, 2, 10))

    @override_settings(FX_PIVOT="EUR")
    def test_convert_currency_raises_when_pivot_matches_pair(self):
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "EUR", "JPY", date=date(2026, 2, 10))

    @override_settings(FX_PIVOT="USD")
    def test_convert_currency_triangulation_with_inverse_legs(self):
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.80"),
            rate_date=date(2026, 2, 1),
        )
        FxRate.objects.create(
            from_currency="JPY",
            to_currency="USD",
            rate=Decimal("0.01"),
            rate_date=date(2026, 2, 1),
        )
        amount = convert_currency(Decimal("10"), "EUR", "JPY", date=date(2026, 2, 10))
        self.assertEqual(amount, Decimal("1250.00"))

    @override_settings(FX_PIVOT="USD")
    def test_convert_currency_triangulation_zero_leg_raises(self):
        FxRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("0"),
            rate_date=date(2026, 2, 1),
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="JPY",
            rate=Decimal("100"),
            rate_date=date(2026, 2, 1),
        )
        with self.assertRaises(ValidationError):
            convert_currency(Decimal("10"), "EUR", "JPY", date=date(2026, 2, 10))

    def test_adjust_for_inflation_uses_latest_period_by_default(self):
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 1, 1),
            index=Decimal("100.0000"),
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 2, 1),
            index=Decimal("110.0000"),
        )

        adjusted = adjust_for_inflation(
            Decimal("110"),
            date=date(2026, 1, 15),
            region=InflationIndex.Region.ES,
        )
        self.assertEqual(adjusted, Decimal("121.00"))

    def test_adjust_for_inflation_raises_when_index_is_zero(self):
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 1, 1),
            index=Decimal("0.0000"),
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 2, 1),
            index=Decimal("100.0000"),
        )

        with self.assertRaises(ValidationError):
            adjust_for_inflation(
                Decimal("100"),
                date=date(2026, 1, 15),
                region=InflationIndex.Region.ES,
                base_period=date(2026, 2, 1),
            )

    def test_get_latest_inflation_period_returns_latest(self):
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 1, 1),
            index=Decimal("99.0000"),
        )
        InflationIndex.objects.create(
            region=InflationIndex.Region.ES,
            period=date(2026, 3, 1),
            index=Decimal("101.0000"),
        )

        self.assertEqual(get_latest_inflation_period(), date(2026, 3, 1))

    def test_get_latest_inflation_period_raises_when_missing(self):
        with self.assertRaises(ValidationError):
            get_latest_inflation_period(region="ES")

    def test_adjust_for_inflation_validates_amount_and_missing_base(self):
        with self.assertRaises(ValidationError):
            adjust_for_inflation(None, date=date(2026, 2, 1), region="ES")

        with self.assertRaises(ValidationError):
            adjust_for_inflation(Decimal("10"), date=date(2026, 2, 1), region="ES")
