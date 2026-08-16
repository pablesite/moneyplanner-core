from django.contrib import admin

from .models import (
    ContainerCashAccount,
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
)

admin.site.register(Portfolio)
admin.site.register(InvestmentContainer)
admin.site.register(ContainerCashAccount)
admin.site.register(Instrument)
admin.site.register(PortfolioPosition)
admin.site.register(PositionOwnershipPeriod)
admin.site.register(PositionOwnershipShare)
admin.site.register(PortfolioMigrationIssue)
