from django.urls import path

from .views import (
    BrokerCredentialDeleteView,
    BrokerCredentialListCreateView,
    BrokerCsvImportView,
    BrokerSyncStatusView,
    BrokerSyncTriggerView,
)

urlpatterns = [
    path("credentials/", BrokerCredentialListCreateView.as_view()),
    path("credentials/<int:credential_id>/", BrokerCredentialDeleteView.as_view()),
    path("sync/<int:credential_id>/", BrokerSyncTriggerView.as_view()),
    path("sync/<int:credential_id>/status/", BrokerSyncStatusView.as_view()),
    path("csv-import/", BrokerCsvImportView.as_view()),
]
