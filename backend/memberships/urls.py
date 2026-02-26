from rest_framework.routers import DefaultRouter

from .views import FamilyMemberViewSet, OwnershipLinkViewSet, OwnershipViewSet

router = DefaultRouter()
router.register(r"family-members", FamilyMemberViewSet, basename="family-member")
router.register(r"ownerships", OwnershipViewSet, basename="ownership")
router.register(r"ownership-links", OwnershipLinkViewSet, basename="ownership-link")

urlpatterns = router.urls
