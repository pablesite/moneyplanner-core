from django.contrib import admin

from .models import (
    FamilyMember,
    Ownership,
    OwnershipAllocationSnapshot,
    OwnershipAllocationSnapshotShare,
    OwnershipIncomeRule,
    OwnershipLink,
    OwnershipSplit,
)

admin.site.register(FamilyMember)
admin.site.register(Ownership)
admin.site.register(OwnershipSplit)
admin.site.register(OwnershipIncomeRule)
admin.site.register(OwnershipAllocationSnapshot)
admin.site.register(OwnershipAllocationSnapshotShare)
admin.site.register(OwnershipLink)
