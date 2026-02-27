from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError

from memberships.models import FamilyMember, Ownership, OwnershipLink
from memberships.services import (
    assert_ownership_can_be_deleted,
    ensure_primary_family_member_for_user,
    sync_ownership_link,
    validate_ownership_payload,
)


class MembershipsServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="memberships_services_user", password="pass1234"
        )

    def test_ensure_primary_family_member_for_user_is_idempotent_and_creates_ownership(self):
        member_1 = ensure_primary_family_member_for_user(user=self.user)
        member_2 = ensure_primary_family_member_for_user(user=self.user)

        self.assertEqual(member_1.id, member_2.id)
        self.assertEqual(FamilyMember.objects.filter(user=self.user).count(), 1)
        self.assertTrue(
            Ownership.objects.filter(
                user=self.user,
                kind=Ownership.Kind.INDIVIDUAL,
                member=member_1,
            ).exists()
        )

    def test_validate_ownership_payload_rejects_child_and_invalid_total(self):
        adult = FamilyMember.objects.create(
            user=self.user, name="Adulto", role=FamilyMember.Role.ADULT
        )
        child = FamilyMember.objects.create(
            user=self.user, name="Nino", role=FamilyMember.Role.CHILD
        )

        with self.assertRaises(DRFValidationError):
            validate_ownership_payload(
                user=self.user,
                kind=Ownership.Kind.SHARED,
                member=None,
                splits=[
                    {"member_id": adult.id, "percent": Decimal("50.00")},
                    {"member_id": child.id, "percent": Decimal("50.00")},
                ],
            )

        with self.assertRaises(DRFValidationError):
            validate_ownership_payload(
                user=self.user,
                kind=Ownership.Kind.SHARED,
                member=None,
                splits=[{"member_id": adult.id, "percent": Decimal("80.00")}],
            )

    def test_assert_ownership_can_be_deleted_rejects_individual(self):
        member = FamilyMember.objects.create(
            user=self.user, name="Pablo", role=FamilyMember.Role.ADULT
        )
        ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=member,
        )
        with self.assertRaises(DRFValidationError):
            assert_ownership_can_be_deleted(ownership)

    def test_sync_ownership_link_creates_and_removes_link(self):
        member = FamilyMember.objects.create(
            user=self.user, name="Pablo", role=FamilyMember.Role.ADULT
        )
        ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=member,
        )

        created = sync_ownership_link(
            user=self.user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=999,
            ownership=ownership,
        )
        self.assertEqual(created, {"ok": True, "ownership_id": ownership.id})
        self.assertTrue(
            OwnershipLink.objects.filter(
                user=self.user,
                target_type=OwnershipLink.TargetType.ASSET,
                target_id=999,
                ownership=ownership,
            ).exists()
        )

        removed = sync_ownership_link(
            user=self.user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=999,
            ownership=None,
        )
        self.assertEqual(removed, {"ok": True, "ownership_id": None})
        self.assertFalse(
            OwnershipLink.objects.filter(
                user=self.user,
                target_type=OwnershipLink.TargetType.ASSET,
                target_id=999,
            ).exists()
        )
