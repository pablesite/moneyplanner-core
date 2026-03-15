from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LedgerAccountViewSet, LedgerEntryViewSet, LedgerTransactionViewSet

router = DefaultRouter()
router.register(r"accounts", LedgerAccountViewSet, basename="ledger-accounts")
router.register(r"transactions", LedgerTransactionViewSet, basename="ledger-transactions")
router.register(r"entries", LedgerEntryViewSet, basename="ledger-entries")

urlpatterns = [
    path("", include(router.urls)),
]
