from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from memberships.models import FamilyMember, Ownership, OwnershipLink


class MembershipsApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="memberships_api_user", password="pass1234"
        )
        self.client.force_authenticate(user=self.user)

    def _create_member(self, *, name: str, role: str = FamilyMember.Role.ADULT) -> FamilyMember:
        return FamilyMember.objects.create(user=self.user, name=name, role=role)

    def _create_shared_ownership(self, *members: FamilyMember) -> Ownership:
        ownership = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        split_percent = Decimal("100.00") / Decimal(str(len(members)))
        for member in members:
            ownership.splits.create(member=member, percent=split_percent)
        return ownership

    def test_ensure_primary_creates_member_and_individual_ownership_and_is_idempotent(self):
        first = self.client.post("/api/family-members/ensure-primary/", format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        self.assertEqual(FamilyMember.objects.filter(user=self.user).count(), 1)
        member = FamilyMember.objects.get(user=self.user)
        self.assertEqual(first.data["id"], member.id)
        self.assertTrue(
            Ownership.objects.filter(
                user=self.user,
                kind=Ownership.Kind.INDIVIDUAL,
                member=member,
            ).exists()
        )

        second = self.client.post("/api/family-members/ensure-primary/", format="json")
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(second.data["id"], member.id)
        self.assertEqual(FamilyMember.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Ownership.objects.filter(user=self.user).count(), 1)

    def test_family_member_create_creates_default_individual_ownership(self):
        response = self.client.post(
            "/api/family-members/",
            {"name": "Pablo", "role": FamilyMember.Role.ADULT, "is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        member = FamilyMember.objects.get(id=response.data["id"], user=self.user)
        self.assertTrue(
            Ownership.objects.filter(
                user=self.user,
                kind=Ownership.Kind.INDIVIDUAL,
                member=member,
            ).exists()
        )

    def test_ownership_create_shared_valid_and_list_returns_read_shape(self):
        member_a = self._create_member(name="Pablo")
        member_b = self._create_member(name="Ana")

        create_res = self.client.post(
            "/api/ownerships/",
            {
                "kind": Ownership.Kind.SHARED,
                "member": None,
                "splits": [
                    {"member_id": member_a.id, "percent": "50.00"},
                    {"member_id": member_b.id, "percent": "50.00"},
                ],
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        ownership_id = create_res.data["id"]
        ownership = Ownership.objects.get(id=ownership_id, user=self.user)
        self.assertEqual(ownership.kind, Ownership.Kind.SHARED)
        self.assertEqual(ownership.member_id, None)
        self.assertEqual(ownership.splits.count(), 2)

        list_res = self.client.get("/api/ownerships/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK, list_res.data)
        self.assertEqual(len(list_res.data), 1)
        row = list_res.data[0]
        self.assertEqual(row["id"], ownership_id)
        self.assertEqual(row["kind"], Ownership.Kind.SHARED)
        self.assertIsNone(row["member"])
        self.assertFalse(row["is_in_use"])
        self.assertEqual(len(row["splits"]), 2)
        self.assertEqual(
            {split["member"]["id"] for split in row["splits"]}, {member_a.id, member_b.id}
        )

    def test_ownership_create_shared_rejects_invalid_splits(self):
        member_a = self._create_member(name="Pablo")

        response = self.client.post(
            "/api/ownerships/",
            {
                "kind": Ownership.Kind.SHARED,
                "member": None,
                "splits": [
                    {"member_id": member_a.id, "percent": "60.00"},
                    {"member_id": member_a.id, "percent": "40.00"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("splits", response.data["error"]["details"])

    def test_ownership_update_and_delete_are_blocked_when_in_use(self):
        member_a = self._create_member(name="Pablo")
        member_b = self._create_member(name="Ana")
        ownership = self._create_shared_ownership(member_a, member_b)
        OwnershipLink.objects.create(
            user=self.user,
            ownership=ownership,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=101,
        )

        patch_res = self.client.patch(
            f"/api/ownerships/{ownership.id}/",
            {
                "splits": [
                    {"member_id": member_a.id, "percent": "70.00"},
                    {"member_id": member_b.id, "percent": "30.00"},
                ]
            },
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_400_BAD_REQUEST, patch_res.data)
        self.assertEqual(patch_res.data["error"]["code"], "validation_error")
        self.assertIn("detail", patch_res.data["error"]["details"])

        delete_res = self.client.delete(f"/api/ownerships/{ownership.id}/")
        self.assertEqual(delete_res.status_code, status.HTTP_400_BAD_REQUEST, delete_res.data)
        self.assertEqual(delete_res.data["error"]["code"], "validation_error")
        self.assertIn("detail", delete_res.data["error"]["details"])

    def test_ownership_links_sync_create_list_and_unset(self):
        member = self._create_member(name="Pablo")
        ownership = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=member
        )

        sync_create = self.client.post(
            "/api/ownership-links/sync/",
            {
                "target_type": OwnershipLink.TargetType.ASSET,
                "target_id": 777,
                "ownership_id": ownership.id,
            },
            format="json",
        )
        self.assertEqual(sync_create.status_code, status.HTTP_200_OK, sync_create.data)
        self.assertEqual(sync_create.data, {"ok": True, "ownership_id": ownership.id})

        list_res = self.client.get("/api/ownership-links/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK, list_res.data)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["target_type"], OwnershipLink.TargetType.ASSET)
        self.assertEqual(list_res.data[0]["target_id"], 777)
        self.assertEqual(list_res.data[0]["ownership_id"], ownership.id)

        sync_delete = self.client.post(
            "/api/ownership-links/sync/",
            {
                "target_type": OwnershipLink.TargetType.ASSET,
                "target_id": 777,
                "ownership_id": None,
            },
            format="json",
        )
        self.assertEqual(sync_delete.status_code, status.HTTP_200_OK, sync_delete.data)
        self.assertEqual(sync_delete.data, {"ok": True, "ownership_id": None})
        self.assertFalse(
            OwnershipLink.objects.filter(
                user=self.user,
                target_type=OwnershipLink.TargetType.ASSET,
                target_id=777,
            ).exists()
        )

    def test_ownership_links_sync_rejects_foreign_ownership(self):
        other_user = get_user_model().objects.create_user(username="other", password="pass1234")
        other_member = FamilyMember.objects.create(user=other_user, name="Otro", role="adult")
        foreign_ownership = Ownership.objects.create(
            user=other_user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=other_member,
        )

        response = self.client.post(
            "/api/ownership-links/sync/",
            {
                "target_type": OwnershipLink.TargetType.LIABILITY,
                "target_id": 3,
                "ownership_id": foreign_ownership.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("ownership_id", response.data["error"]["details"])

    def test_family_member_delete_is_blocked_when_used_in_shared_ownership(self):
        member_a = self._create_member(name="Pablo")
        member_b = self._create_member(name="Ana")
        self._create_shared_ownership(member_a, member_b)

        response = self.client.delete(f"/api/family-members/{member_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("detail", response.data["error"]["details"])
        self.assertTrue(FamilyMember.objects.filter(id=member_a.id, user=self.user).exists())
