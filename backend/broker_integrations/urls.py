from django.urls import path

from .views import (
    BrokerBotResultDetailView,
    BrokerBotResultListView,
    BrokerCredentialDeleteView,
    BrokerCredentialListCreateView,
    BrokerCsvImportView,
    BrokerFiscalReportView,
    BrokerIncomeEventListView,
    ManualCostBasisDeleteView,
    ManualCostBasisListCreateView,
    BrokerSyncRunDetailView,
    BrokerSyncRunListView,
    BrokerSyncStatusView,
    BrokerSyncTriggerView,
    BrokerTradeListView,
)

urlpatterns = [
    path("credentials/", BrokerCredentialListCreateView.as_view()),
    path("credentials/<int:credential_id>/", BrokerCredentialDeleteView.as_view()),
    path("sync/<int:credential_id>/", BrokerSyncTriggerView.as_view()),
    path("sync/<int:credential_id>/status/", BrokerSyncStatusView.as_view()),
    path("sync-runs/", BrokerSyncRunListView.as_view()),
    path("sync-runs/<int:sync_run_id>/", BrokerSyncRunDetailView.as_view()),
    path("trades/", BrokerTradeListView.as_view()),
    path("income-events/", BrokerIncomeEventListView.as_view()),
    path("bot-results/", BrokerBotResultListView.as_view()),
    path("bot-results/<int:bot_result_id>/", BrokerBotResultDetailView.as_view()),
    path("manual-cost-basis/", ManualCostBasisListCreateView.as_view()),
    path("manual-cost-basis/<int:row_id>/", ManualCostBasisDeleteView.as_view()),
    path("csv-import/", BrokerCsvImportView.as_view()),
    path("fiscal-report/", BrokerFiscalReportView.as_view()),
]
