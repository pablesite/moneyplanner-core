from django.contrib import admin

from .models import (
    ContainerCashAccount,
    Instrument,
    InstrumentPrice,
    InstrumentProviderMapping,
    InvestmentContainer,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionValuation,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
)

admin.site.register(Portfolio)
admin.site.register(InvestmentContainer)
admin.site.register(ContainerCashAccount)
admin.site.register(Instrument)
admin.site.register(InstrumentProviderMapping)
admin.site.register(InstrumentPrice)
admin.site.register(PortfolioPosition)
admin.site.register(PositionValuation)
admin.site.register(PositionOwnershipPeriod)
admin.site.register(PositionOwnershipShare)
admin.site.register(PortfolioMigrationIssue)
