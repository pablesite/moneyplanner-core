from django.db import transaction
from rest_framework import serializers

from memberships.models import FamilyMember
from net_worth.models import Asset

from .dates import date_at_age
from .models import (
    FinancialPlan,
    Finding,
    PlanAssetFunction,
    PlanEvent,
    ProjectionSnapshot,
    Recommendation,
    Scenario,
    ScenarioEvent,
)


class FinancialPlanSerializer(serializers.ModelSerializer):
    member_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=True,
    )
    members = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FinancialPlan
        fields = [
            "id",
            "household_type",
            "target_date",
            "target_monthly_income_today_eur",
            "projection_end_date",
            "preservation_target_eur",
            "preserved_asset_ids",
            "profile",
            "status",
            "member_ids",
            "members",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_members(self, obj):
        return PlanFamilyMemberSerializer(obj.members.all(), many=True).data

    def validate_member_ids(self, value):
        request = self.context["request"]
        members = list(
            FamilyMember.objects.filter(
                user=request.user,
                id__in=value,
                role=FamilyMember.Role.ADULT,
                is_active=True,
            )
        )
        if len(members) != len(set(value)):
            raise serializers.ValidationError(
                "Only active adult members owned by the user can be linked."
            )
        if len(members) > 2:
            raise serializers.ValidationError("A financial plan can include at most two adults.")
        return value

    def validate(self, attrs):
        target_date = attrs.get("target_date", getattr(self.instance, "target_date", None))
        projection_end_date = attrs.get(
            "projection_end_date",
            getattr(self.instance, "projection_end_date", None),
        )
        if target_date and projection_end_date and projection_end_date < target_date:
            raise serializers.ValidationError(
                {"projection_end_date": "Must be greater than or equal to target_date."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        member_ids = validated_data.pop("member_ids", None)
        request = self.context["request"]
        plan, _created = FinancialPlan.objects.update_or_create(
            user=request.user,
            defaults=validated_data,
        )
        if member_ids is not None:
            plan.members.set(FamilyMember.objects.filter(user=request.user, id__in=member_ids))
        return plan

    @transaction.atomic
    def update(self, instance, validated_data):
        member_ids = validated_data.pop("member_ids", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.full_clean()
        instance.save()
        if member_ids is not None:
            instance.members.set(FamilyMember.objects.filter(user=instance.user, id__in=member_ids))
        return instance


class PlanFamilyMemberSerializer(serializers.ModelSerializer):
    employment_end_age = serializers.IntegerField(
        min_value=18, max_value=100, required=False, write_only=True
    )
    pension_start_age = serializers.IntegerField(
        min_value=18, max_value=100, required=False, write_only=True
    )

    class Meta:
        model = FamilyMember
        fields = [
            "id",
            "name",
            "role",
            "is_active",
            "birth_date",
            "employment_end_age",
            "employment_income_end_date",
            "pension_start_age",
            "pension_start_date",
            "estimated_monthly_pension_today_eur",
            "other_future_income_today_eur",
        ]
        read_only_fields = ["id"]

    def validate_role(self, value):
        if value != FamilyMember.Role.ADULT:
            raise serializers.ValidationError("Only adults can be linked to a financial plan.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["role"] = FamilyMember.Role.ADULT
        self._derive_retirement_dates(validated_data)
        # FamilyMember es una identidad compartida con Patrimonio/titularidades:
        # si el usuario ya tiene a esta persona registrada con el mismo nombre
        # (uniq_member_name_per_user_memberships), reutilizamos su registro en
        # vez de chocar con la restricción única y devolver un 500.
        existing = FamilyMember.objects.filter(
            user=request.user, name=validated_data["name"]
        ).first()
        if existing:
            if existing.role != FamilyMember.Role.ADULT:
                raise serializers.ValidationError(
                    {"name": "Ya existe una persona menor con este nombre en tu cuenta."}
                )
            for key, value in validated_data.items():
                setattr(existing, key, value)
            existing.full_clean()
            existing.save()
            member = existing
        else:
            member = FamilyMember.objects.create(user=request.user, **validated_data)
        plan = FinancialPlan.objects.filter(user=request.user).first()
        if plan:
            if plan.members.count() >= 2 and not plan.members.filter(id=member.id).exists():
                raise serializers.ValidationError(
                    "A financial plan can include at most two adults."
                )
            plan.members.add(member)
        return member

    def update(self, instance, validated_data):
        self._derive_retirement_dates(validated_data, instance=instance)
        request = self.context.get("request")
        existing = None
        if request and "name" in validated_data:
            existing = (
                FamilyMember.objects.filter(
                    user=request.user,
                    name=validated_data["name"],
                )
                .exclude(pk=instance.pk)
                .first()
            )
        if existing:
            if existing.role != FamilyMember.Role.ADULT:
                raise serializers.ValidationError(
                    {"name": "Ya existe una persona menor con este nombre en tu cuenta."}
                )
            with transaction.atomic():
                for key, value in validated_data.items():
                    setattr(existing, key, value)
                existing.full_clean()
                existing.save()
                plans = FinancialPlan.objects.filter(
                    user=request.user,
                    members=instance,
                )
                for plan in plans:
                    plan.members.remove(instance)
                    plan.members.add(existing)
            return existing

        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.full_clean()
        instance.save()
        return instance

    @staticmethod
    def _derive_retirement_dates(validated_data, instance=None):
        birth_date = validated_data.get("birth_date", getattr(instance, "birth_date", None))
        employment_age = validated_data.pop("employment_end_age", None)
        pension_age = validated_data.pop("pension_start_age", None)
        if birth_date:
            if employment_age is not None:
                validated_data["employment_income_end_date"] = date_at_age(
                    birth_date, employment_age
                )
            elif instance is None or not getattr(instance, "employment_income_end_date", None):
                validated_data["employment_income_end_date"] = date_at_age(birth_date)
            if pension_age is not None:
                validated_data["pension_start_date"] = date_at_age(birth_date, pension_age)
            elif instance is None or not getattr(instance, "pension_start_date", None):
                validated_data["pension_start_date"] = date_at_age(birth_date)
        elif "birth_date" in validated_data:
            validated_data["employment_income_end_date"] = None
            validated_data["pension_start_date"] = None


class ProjectionSnapshotSerializer(serializers.ModelSerializer):
    assumption_set = serializers.CharField(source="assumption_set.name")

    class Meta:
        model = ProjectionSnapshot
        fields = [
            "id",
            "assumption_set",
            "calculated_at",
            "input_hash",
            "quality_level",
            "is_official",
            "result_json",
        ]


class ScenarioEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScenarioEvent
        fields = [
            "id",
            "start_date",
            "end_date",
            "initial_outflow",
            "monthly_expense_delta",
            "monthly_income_delta",
            "monthly_contribution_delta",
            "monthly_contribution_destination",
            "new_asset_value",
            "new_asset_type",
            "new_debt_principal",
            "new_debt_interest_rate",
            "new_debt_term_months",
            "metadata_json",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "Must be greater than or equal to start_date."}
            )
        metadata = attrs.get("metadata_json", getattr(self.instance, "metadata_json", {})) or {}
        one_off_items = metadata.get("one_off_items", [])
        if not isinstance(one_off_items, list):
            raise serializers.ValidationError({"metadata_json": "one_off_items must be a list."})
        if one_off_items:
            total = 0
            for index, item in enumerate(one_off_items):
                if not isinstance(item, dict) or not str(item.get("name", "")).strip():
                    raise serializers.ValidationError(
                        {"metadata_json": f"One-off item {index + 1} requires a name."}
                    )
                try:
                    amount = serializers.DecimalField(
                        max_digits=14, decimal_places=2
                    ).run_validation(item.get("amount"))
                except serializers.ValidationError as exc:
                    raise serializers.ValidationError(
                        {"metadata_json": f"One-off item {index + 1} has an invalid amount."}
                    ) from exc
                if amount <= 0:
                    raise serializers.ValidationError(
                        {"metadata_json": f"One-off item {index + 1} must be greater than zero."}
                    )
                total += amount
            attrs["initial_outflow"] = total
        return attrs


class ScenarioSerializer(serializers.ModelSerializer):
    events = ScenarioEventSerializer(many=True, required=False)

    class Meta:
        model = Scenario
        fields = [
            "id",
            "name",
            "source_recommendation",
            "template_type",
            "status",
            "events",
            "created_at",
            "accepted_at",
        ]
        read_only_fields = [
            "id",
            "source_recommendation",
            "status",
            "created_at",
            "accepted_at",
        ]

    @transaction.atomic
    def create(self, validated_data):
        events = validated_data.pop("events", [])
        request = self.context["request"]
        plan = FinancialPlan.objects.get(user=request.user)
        scenario = Scenario.objects.create(plan=plan, **validated_data)
        for event in events:
            ScenarioEvent.objects.create(scenario=scenario, **event)
        return scenario

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.status != Scenario.Status.DRAFT:
            raise serializers.ValidationError("Only draft scenarios can be edited.")
        events = validated_data.pop("events", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if events is not None:
            instance.events.all().delete()
            for event in events:
                ScenarioEvent.objects.create(scenario=instance, **event)
        return instance


class PlanEventSerializer(serializers.ModelSerializer):
    linked_asset_ids = serializers.PrimaryKeyRelatedField(
        source="linked_assets", many=True, read_only=True
    )
    linked_liability_ids = serializers.PrimaryKeyRelatedField(
        source="linked_liabilities", many=True, read_only=True
    )

    class Meta:
        model = PlanEvent
        fields = [
            "id",
            "source_scenario",
            "name",
            "event_type",
            "planned_date",
            "actual_date",
            "effective_end_date",
            "status",
            "planned_impact_json",
            "actual_impact_json",
            "linked_asset_ids",
            "linked_liability_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "source_scenario",
            "effective_end_date",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if "actual_impact_json" in attrs and attrs.get("status") != PlanEvent.Status.OCCURRED:
            attrs["status"] = PlanEvent.Status.OCCURRED
        return attrs


class PlanEventCloseSerializer(serializers.Serializer):
    effective_date = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class PlanEventMaterializeSerializer(serializers.Serializer):
    actual_date = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class OccurredEventRegisterSerializer(serializers.Serializer):
    """Alta de una decision ya tomada, adoptando las lineas de presupuesto que generó."""

    name = serializers.CharField(max_length=140)
    event_type = serializers.ChoiceField(choices=Scenario.TemplateType.choices)
    decision_date = serializers.DateField()
    expense_entry_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    income_entry_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    # Se enlazan, no se adoptan: Patrimonio sigue generando sus lineas de presupuesto.
    asset_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    liability_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AssetFunctionUpdateSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(min_value=1)
    function = serializers.ChoiceField(choices=PlanAssetFunction.Function.choices, allow_null=True)

    def validate_asset_id(self, value):
        request = self.context["request"]
        if not Asset.objects.filter(user=request.user, id=value, is_active=True).exists():
            raise serializers.ValidationError("Asset not found.")
        return value


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = [
            "id",
            "code",
            "severity",
            "period",
            "evidence_json",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RecommendationSerializer(serializers.ModelSerializer):
    finding = serializers.IntegerField(source="finding_id", read_only=True)

    class Meta:
        model = Recommendation
        fields = [
            "id",
            "finding",
            "code",
            "priority",
            "action_json",
            "impact_json",
            "alternatives_json",
            "status",
            "snoozed_until",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RecommendationSnoozeSerializer(serializers.Serializer):
    snoozed_until = serializers.DateField()

    def validate_snoozed_until(self, value):
        from django.utils import timezone

        if value <= timezone.localdate():
            raise serializers.ValidationError("Must be a future date.")
        return value
