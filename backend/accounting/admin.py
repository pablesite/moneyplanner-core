from django.contrib import admin

from .models import LedgerAccount, LedgerEntry, LedgerTransaction

admin.site.register(LedgerAccount)
admin.site.register(LedgerTransaction)
admin.site.register(LedgerEntry)
