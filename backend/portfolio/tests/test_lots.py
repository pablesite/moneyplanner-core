from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from portfolio.lots import UnitMovement, build_pockets, member_share_at

SHARED, MINE = 4, 1
ANA, PABLO = 3, 1
SHARES = {
    SHARED: {ANA: Decimal("0.5"), PABLO: Decimal("0.5")},
    MINE: {PABLO: Decimal("1")},
}


def buy(day, units, owner):
    return UnitMovement(on_date=day, units=Decimal(units), ownership_id=owner)


def sell(day, units, owner):
    return UnitMovement(on_date=day, units=-Decimal(units), ownership_id=owner)


class OwnershipPocketTests(SimpleTestCase):
    def test_each_purchase_lands_in_the_pocket_that_paid_for_it(self):
        book = build_pockets([buy(date(2021, 1, 1), "2", SHARED), buy(date(2023, 1, 1), "6", MINE)])

        self.assertEqual(book.at(date(2022, 1, 1)), {SHARED: Decimal("2")})
        self.assertEqual(book.at(date(2024, 1, 1)), {SHARED: Decimal("2"), MINE: Decimal("6")})

    def test_the_share_follows_units_not_a_fixed_percentage(self):
        # Es justo lo que un tramo con porcentaje no sabe decir: la proporcion cambia con
        # cada compra, y sin comprar nada no se mueve aunque el precio se dispare.
        book = build_pockets([buy(date(2021, 1, 1), "2", SHARED), buy(date(2023, 1, 1), "6", MINE)])
        kwargs = {"pockets": book, "shares_by_ownership": SHARES}

        early = member_share_at(target=date(2022, 1, 1), member_id=ANA, **kwargs)
        late = member_share_at(target=date(2024, 1, 1), member_id=ANA, **kwargs)

        self.assertEqual(early, Decimal("0.5"))
        self.assertEqual(late, Decimal("1") / Decimal("8"))

    def test_a_sale_takes_from_the_pocket_that_sold(self):
        book = build_pockets(
            [
                buy(date(2021, 1, 1), "2", SHARED),
                buy(date(2023, 1, 1), "6", MINE),
                sell(date(2024, 1, 1), "4", MINE),
            ]
        )

        self.assertEqual(book.at(date(2024, 6, 1)), {SHARED: Decimal("2"), MINE: Decimal("2")})
        self.assertEqual(book.unreconciled, Decimal("0"))

    def test_selling_more_than_you_have_spills_over_and_is_reported(self):
        # El historico se etiqueto a mano: una venta puede decir que es tuya cuando en el
        # bote solo quedaban monedas compartidas. Se reparte a prorrata y queda anotado, en
        # lugar de dejar un bolsillo en negativo o una participacion que nadie decidio.
        book = build_pockets(
            [
                buy(date(2021, 1, 1), "8", SHARED),
                buy(date(2023, 1, 1), "2", MINE),
                sell(date(2024, 1, 1), "6", MINE),
            ]
        )

        state = book.at(date(2024, 6, 1))
        self.assertEqual(state[MINE], Decimal("0"))
        self.assertEqual(state[SHARED], Decimal("4"))
        self.assertEqual(book.unreconciled, Decimal("0"))

    def test_an_untagged_withdrawal_comes_out_of_everyone(self):
        book = build_pockets(
            [
                buy(date(2021, 1, 1), "6", SHARED),
                buy(date(2023, 1, 1), "2", MINE),
                UnitMovement(on_date=date(2024, 1, 1), units=Decimal("-4"), ownership_id=None),
            ]
        )

        state = book.at(date(2024, 6, 1))
        self.assertEqual(state[SHARED], Decimal("3"))
        self.assertEqual(state[MINE], Decimal("1"))

    def test_an_empty_pot_has_no_share_to_report(self):
        book = build_pockets(
            [buy(date(2021, 1, 1), "2", SHARED), sell(date(2022, 1, 1), "2", SHARED)]
        )

        self.assertIsNone(
            member_share_at(
                pockets=book,
                target=date(2023, 1, 1),
                member_id=ANA,
                shares_by_ownership=SHARES,
            )
        )
