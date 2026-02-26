from django.contrib import admin

from .models import FamilyMember, Ownership, OwnershipLink, OwnershipSplit

admin.site.register(FamilyMember)
admin.site.register(Ownership)
admin.site.register(OwnershipSplit)
admin.site.register(OwnershipLink)
