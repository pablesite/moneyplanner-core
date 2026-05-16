"""
Cross-user isolation tests.

Verifies that each module's API enforces user-level data isolation:
- Unauthenticated requests → 401
- Authenticated user A cannot read, write, or delete user B's records
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerTransaction
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from memberships.models import FamilyMember, Ownership
from net_worth.models import Asset, Liability

User = get_user_model()


def _make_user(username, password="pass1234"):
    return User.objects.create_user(username=username, password=password)


class UnauthenticatedAccessTests(APITestCase):
    """All authenticated endpoints must return 401 when no token is provided."""

    PROTECTED_ENDPOINTS = [
        "/api/net-worth/assets/",
        "/api/net-worth/liabilities/",
        "/api/accounting/accounts/",
        "/api/accounting/transactions/",
        "/api/budget/annual-income/",
        "/api/budget/annual-expense/",
        "/api/family-members/",
        "/api/ownerships/",
        "/api/auth/me/",
    ]

    def test_unauthenticated_get_returns_401(self):
        for url in self.PROTECTED_ENDPOINTS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_401_UNAUTHORIZED,
                    f"Expected 401 on GET {url}, got {response.status_code}",
                )


class NetWorthIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = _make_user("isolation_a_nw")
        self.user_b = _make_user("isolation_b_nw")
        self.asset_b = Asset.objects.create(
            user=self.user_b,
            name="B asset",
            category="cash",
            amount="100000.00",
            currency="EUR",
        )
        self.liability_b = Liability.objects.create(
            user=self.user_b,
            name="B liability",
            category="mortgage",
            amount="50000.00",
            currency="EUR",
        )
        self.client.force_authenticate(user=self.user_a)

    def test_asset_list_excludes_other_user(self):
        response = self.client.get("/api/net-worth/assets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data]
        self.assertNotIn(self.asset_b.id, ids)

    def test_asset_detail_returns_404_for_other_user(self):
        response = self.client.get(f"/api/net-worth/assets/{self.asset_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_asset_patch_returns_404_for_other_user(self):
        response = self.client.patch(
            f"/api/net-worth/assets/{self.asset_b.id}/",
            {"name": "hijacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_asset_delete_returns_404_for_other_user(self):
        response = self.client.delete(f"/api/net-worth/assets/{self.asset_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Asset.objects.filter(id=self.asset_b.id).exists())

    def test_liability_list_excludes_other_user(self):
        response = self.client.get("/api/net-worth/liabilities/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data]
        self.assertNotIn(self.liability_b.id, ids)

    def test_liability_detail_returns_404_for_other_user(self):
        response = self.client.get(f"/api/net-worth/liabilities/{self.liability_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_liability_patch_returns_404_for_other_user(self):
        response = self.client.patch(
            f"/api/net-worth/liabilities/{self.liability_b.id}/",
            {"name": "hijacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_liability_delete_returns_404_for_other_user(self):
        response = self.client.delete(f"/api/net-worth/liabilities/{self.liability_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Liability.objects.filter(id=self.liability_b.id).exists())


class AccountingIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = _make_user("isolation_a_acc")
        self.user_b = _make_user("isolation_b_acc")
        self.account_b = LedgerAccount.objects.create(
            user=self.user_b,
            name="B account",
            account_type="asset",
            currency="EUR",
        )
        self.transaction_b = LedgerTransaction.objects.create(
            user=self.user_b,
            booking_date="2024-01-15",
            value_date="2024-01-15",
            description="B transaction",
            status="posted",
        )
        self.client.force_authenticate(user=self.user_a)

    def test_accounts_list_excludes_other_user(self):
        response = self.client.get("/api/accounting/accounts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data]
        self.assertNotIn(self.account_b.id, ids)

    def test_account_detail_returns_404_for_other_user(self):
        response = self.client.get(f"/api/accounting/accounts/{self.account_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_account_patch_returns_404_for_other_user(self):
        response = self.client.patch(
            f"/api/accounting/accounts/{self.account_b.id}/",
            {"name": "hijacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_account_delete_returns_404_for_other_user(self):
        response = self.client.delete(f"/api/accounting/accounts/{self.account_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(LedgerAccount.objects.filter(id=self.account_b.id).exists())

    def test_transactions_list_excludes_other_user(self):
        response = self.client.get("/api/accounting/transactions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data["results"]]
        self.assertNotIn(self.transaction_b.id, ids)

    def test_transaction_detail_returns_404_for_other_user(self):
        response = self.client.get(f"/api/accounting/transactions/{self.transaction_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_transaction_patch_returns_404_for_other_user(self):
        response = self.client.patch(
            f"/api/accounting/transactions/{self.transaction_b.id}/",
            {"description": "hijacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_transaction_delete_returns_404_for_other_user(self):
        response = self.client.delete(f"/api/accounting/transactions/{self.transaction_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(LedgerTransaction.objects.filter(id=self.transaction_b.id).exists())

    def test_cannot_create_transaction_with_other_users_account_in_entries(self):
        response = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2024-02-01",
                "value_date": "2024-02-01",
                "description": "A tx",
                "entries": [
                    {"account_id": self.account_b.id, "side": "debit", "amount": "100.00"},
                    {"account_id": self.account_b.id, "side": "credit", "amount": "100.00"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class BudgetIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = _make_user("isolation_a_bud")
        self.user_b = _make_user("isolation_b_bud")
        self.income_b = AnnualIncomeEntry.objects.create(
            user=self.user_b,
            name="B income",
            fiscal_year=2024,
            amount_annual="30000.00",
            currency="EUR",
            category="salary",
            subcategory="",
        )
        self.expense_b = AnnualExpenseEntry.objects.create(
            user=self.user_b,
            name="B expense",
            fiscal_year=2024,
            amount_annual="1200.00",
            currency="EUR",
            category="consumption_expenses",
            subcategory="",
        )
        self.client.force_authenticate(user=self.user_a)

    def test_income_list_excludes_other_user(self):
        response = self.client.get("/api/budget/annual-income/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data]
        self.assertNotIn(self.income_b.id, ids)

    def test_income_detail_returns_404_for_other_user(self):
        response = self.client.get(f"/api/budget/annual-income/{self.income_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_income_patch_returns_404_for_other_user(self):
        response = self.client.patch(
            f"/api/budget/annual-income/{self.income_b.id}/",
            {"name": "hijacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_income_delete_returns_404_for_other_user(self):
        response = self.client.delete(f"/api/budget/annual-income/{self.income_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(AnnualIncomeEntry.objects.filter(id=self.income_b.id).exists())

    def test_expense_list_excludes_other_user(self):
        response = self.client.get("/api/budget/annual-expense/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data]
        self.assertNotIn(self.expense_b.id, ids)

    def test_expense_detail_returns_404_for_other_user(self):
        response = self.client.get(f"/api/budget/annual-expense/{self.expense_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_expense_delete_returns_404_for_other_user(self):
        response = self.client.delete(f"/api/budget/annual-expense/{self.expense_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(AnnualExpenseEntry.objects.filter(id=self.expense_b.id).exists())


class MembershipsIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = _make_user("isolation_a_mem")
        self.user_b = _make_user("isolation_b_mem")
        self.member_b = FamilyMember.objects.create(
            user=self.user_b,
            name="B member",
            role="primary",
        )
        self.ownership_b = Ownership.objects.create(
            user=self.user_b,
            kind="individual",
            member=self.member_b,
        )
        self.client.force_authenticate(user=self.user_a)

    def test_family_members_list_excludes_other_user(self):
        response = self.client.get("/api/family-members/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data]
        self.assertNotIn(self.member_b.id, ids)

    def test_family_member_detail_returns_404_for_other_user(self):
        response = self.client.get(f"/api/family-members/{self.member_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_family_member_delete_returns_404_for_other_user(self):
        response = self.client.delete(f"/api/family-members/{self.member_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(FamilyMember.objects.filter(id=self.member_b.id).exists())

    def test_ownerships_list_excludes_other_user(self):
        response = self.client.get("/api/ownerships/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.data]
        self.assertNotIn(self.ownership_b.id, ids)

    def test_ownership_detail_returns_404_for_other_user(self):
        response = self.client.get(f"/api/ownerships/{self.ownership_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_ownership_delete_returns_404_for_other_user(self):
        response = self.client.delete(f"/api/ownerships/{self.ownership_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Ownership.objects.filter(id=self.ownership_b.id).exists())
