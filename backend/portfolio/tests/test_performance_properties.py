from datetime import date
from decimal import Decimal
from random import Random

from django.test import SimpleTestCase

from portfolio.performance_math import DatedAmount, DatedValue, chained_twr, monetary_result


class PerformancePropertyTests(SimpleTestCase):
    def test_monetary_result_always_reconciles(self):
        random = Random(20260816)
        for _ in range(100):
            opening = Decimal(random.randrange(0, 100000))
            flows = [
                DatedAmount(date(2024, month, 1), Decimal(random.randrange(-5000, 10000)))
                for month in range(2, 12, 2)
            ]
            result = Decimal(random.randrange(-10000, 30000))
            closing = opening + sum((row.amount for row in flows), Decimal("0")) + result

            calculated = monetary_result(
                opening_value=opening,
                closing_value=closing,
                external_flows=flows,
            )

            self.assertEqual(calculated, result)

    def test_internal_transfer_does_not_change_household_result(self):
        opening = Decimal("1000")
        closing = Decimal("1125")
        external = [DatedAmount(date(2024, 6, 1), Decimal("100"))]

        before = monetary_result(
            opening_value=opening,
            closing_value=closing,
            external_flows=external,
        )
        after = monetary_result(
            opening_value=opening,
            closing_value=closing,
            external_flows=external,
        )

        self.assertEqual(before, Decimal("25"))
        self.assertEqual(after, before)

    def test_twr_chain_equals_product_of_independent_period_factors(self):
        valuations = [
            DatedValue(date(2024, 1, 1), Decimal("200")),
            DatedValue(date(2024, 4, 1), Decimal("230")),
            DatedValue(date(2024, 9, 1), Decimal("207")),
            DatedValue(date(2024, 12, 31), Decimal("248.4")),
        ]
        flows = [
            DatedAmount(date(2024, 4, 1), Decimal("20")),
            DatedAmount(date(2024, 9, 1), Decimal("-10")),
        ]

        calculated = chained_twr(valuations=valuations, external_flows=flows)
        independent = (Decimal("230") - Decimal("20")) / Decimal("200") * (
            (Decimal("207") + Decimal("10")) / Decimal("230")
        ) * (Decimal("248.4") / Decimal("207")) - Decimal("1")

        self.assertEqual(calculated, independent)

    def test_twr_refuses_to_fake_precision_without_flow_date_valuation(self):
        calculated = chained_twr(
            valuations=[
                DatedValue(date(2024, 1, 1), Decimal("100")),
                DatedValue(date(2024, 12, 31), Decimal("160")),
            ],
            external_flows=[DatedAmount(date(2024, 6, 1), Decimal("50"))],
        )

        self.assertIsNone(calculated)
