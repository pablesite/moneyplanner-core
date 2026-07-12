from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class FinancialPlan(models.Model):
    class HouseholdType(models.TextChoices):
        SINGLE = "single", "Individual"
        FAMILY = "family", "Familiar"

    class Profile(models.TextChoices):
        SECURITY = "security", "Seguridad"
        BALANCED = "balanced", "Equilibrado"
        GROWTH = "growth", "Crecimiento"

    class Status(models.TextChoices):
        ACTIVE = "active", "Activo"
        ARCHIVED = "archived", "Archivado"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_plan",
    )
    household_type = models.CharField(
        max_length=16,
        choices=HouseholdType.choices,
        default=HouseholdType.SINGLE,
    )
    target_date = models.DateField()
    target_monthly_income_today_eur = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    projection_end_date = models.DateField()
    preservation_target_eur = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    preserved_asset_ids = models.JSONField(null=True, blank=True)
    profile = models.CharField(
        max_length=16,
        choices=Profile.choices,
        default=Profile.BALANCED,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    members = models.ManyToManyField(
        "memberships.FamilyMember",
        blank=True,
        related_name="financial_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
        ]
        ordering = ["-updated_at"]

    def clean(self) -> None:
        if self.projection_end_date and self.target_date:
            if self.projection_end_date < self.target_date:
                raise ValidationError("projection_end_date must be >= target_date.")

    def __str__(self) -> str:
        return f"{self.user_id} - financial plan"


class PlanAssetFunction(models.Model):
    class Function(models.TextChoices):
        PRODUCTIVE = "productive", "Productivo"
        SECURITY = "security", "Seguridad"
        SHORT_TERM_GOAL = "short_term_goal", "Objetivo corto plazo"
        FAMILY_USE = "family_use", "Uso familiar"
        UNKNOWN = "unknown", "Desconocido"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plan_asset_functions",
    )
    asset = models.ForeignKey(
        "net_worth.Asset",
        on_delete=models.CASCADE,
        related_name="plan_function_overrides",
    )
    function = models.CharField(max_length=32, choices=Function.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "asset"], name="uniq_plan_asset_function_user")
        ]
        indexes = [models.Index(fields=["user", "function"])]

    def clean(self) -> None:
        if self.asset_id and self.user_id and self.asset.user_id != self.user_id:
            raise ValidationError("Asset does not belong to this user.")

    def __str__(self) -> str:
        return f"{self.user_id} - asset:{self.asset_id} -> {self.function}"


class AssumptionSet(models.Model):
    name = models.CharField(max_length=32, unique=True)
    inflation_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    productive_return_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    non_productive_appreciation_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    income_growth_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    contribution_growth_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    withdrawal_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    default_liability_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_default"])]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Scenario(models.Model):
    class TemplateType(models.TextChoices):
        HOUSING = "housing", "Vivienda"
        VEHICLE = "vehicle", "Vehiculo"
        STUDIES = "studies", "Estudios"
        RENOVATION = "renovation", "Reforma"
        SABBATICAL = "sabbatical", "Excedencia"
        REDUCED_HOURS = "reduced_hours", "Reduccion de jornada"
        BUSINESS = "business", "Negocio"
        DEBT_PAYOFF = "debt_payoff", "Amortizacion de deuda"
        GENERIC = "generic", "Generico"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        ACCEPTED = "accepted", "Aceptado"
        DISCARDED = "discarded", "Descartado"

    plan = models.ForeignKey(
        FinancialPlan,
        on_delete=models.CASCADE,
        related_name="scenarios",
    )
    name = models.CharField(max_length=140)
    template_type = models.CharField(
        max_length=32,
        choices=TemplateType.choices,
        default=TemplateType.GENERIC,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["plan", "status"]),
            models.Index(fields=["plan", "-created_at"]),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.plan_id} - {self.name}"


class ScenarioEvent(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        related_name="events",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    initial_outflow = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monthly_expense_delta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monthly_income_delta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monthly_contribution_delta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    new_asset_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    new_asset_type = models.CharField(
        max_length=32,
        choices=PlanAssetFunction.Function.choices,
        null=True,
        blank=True,
    )
    new_debt_principal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    new_debt_interest_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    new_debt_term_months = models.PositiveIntegerField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["scenario", "start_date"])]
        ordering = ["start_date", "id"]

    def clean(self) -> None:
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("end_date must be >= start_date.")

    def __str__(self) -> str:
        return f"{self.scenario_id} - {self.start_date}"


class PlanEvent(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planificado"
        OCCURRED = "occurred", "Ocurrido"
        CANCELLED = "cancelled", "Cancelado"

    plan = models.ForeignKey(
        FinancialPlan,
        on_delete=models.CASCADE,
        related_name="events",
    )
    source_scenario = models.ForeignKey(
        Scenario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plan_events",
    )
    name = models.CharField(max_length=140)
    event_type = models.CharField(max_length=32, choices=Scenario.TemplateType.choices)
    planned_date = models.DateField()
    actual_date = models.DateField(null=True, blank=True)
    effective_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    # Activos y pasivos reales que trajo la decision. El evento los *apunta*, no los
    # gobierna: sus lineas de presupuesto las sigue generando Patrimonio. Reetiquetarlas
    # al evento romperia la sincronizacion del activo/pasivo y duplicaria el gasto.
    linked_assets = models.ManyToManyField(
        "net_worth.Asset",
        blank=True,
        related_name="plan_events",
    )
    linked_liabilities = models.ManyToManyField(
        "net_worth.Liability",
        blank=True,
        related_name="plan_events",
    )
    planned_impact_json = models.JSONField(default=dict, blank=True)
    actual_impact_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["plan", "status"]),
            models.Index(fields=["plan", "planned_date"]),
        ]
        ordering = ["planned_date", "id"]

    def __str__(self) -> str:
        return f"{self.plan_id} - {self.name}"


class Finding(models.Model):
    class Code(models.TextChoices):
        EMERGENCY_FUND_BELOW_TARGET = (
            "EMERGENCY_FUND_BELOW_TARGET",
            "Fondo de emergencia bajo objetivo",
        )
        NEGATIVE_CASH_FLOW = "NEGATIVE_CASH_FLOW", "Flujo de caja negativo"
        HIGH_COST_DEBT = "HIGH_COST_DEBT", "Deuda cara"
        RETIREMENT_TARGET_OFF_TRACK = (
            "RETIREMENT_TARGET_OFF_TRACK",
            "Objetivo principal desviado",
        )
        SECONDARY_GOAL_UNDERFUNDED = (
            "SECONDARY_GOAL_UNDERFUNDED",
            "Objetivo secundario infrafinanciado",
        )
        PRODUCTIVE_CAPITAL_STAGNANT = (
            "PRODUCTIVE_CAPITAL_STAGNANT",
            "Capital productivo estancado",
        )
        DATA_INCOMPLETE = "DATA_INCOMPLETE", "Datos incompletos"

    class Severity(models.TextChoices):
        INFO = "info", "Informativo"
        WARNING = "warning", "Atencion"
        CRITICAL = "critical", "Critico"

    class Status(models.TextChoices):
        OPEN = "open", "Abierto"
        RESOLVED = "resolved", "Resuelto"
        DISMISSED = "dismissed", "Descartado"

    plan = models.ForeignKey(
        FinancialPlan,
        on_delete=models.CASCADE,
        related_name="findings",
    )
    code = models.CharField(max_length=64, choices=Code.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    period = models.CharField(max_length=16)
    evidence_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "code", "period"], name="uniq_finding_period")
        ]
        indexes = [
            models.Index(fields=["plan", "status"]),
            models.Index(fields=["plan", "period"]),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.plan_id} - {self.code} ({self.period})"


class Recommendation(models.Model):
    class Code(models.TextChoices):
        REBUILD_EMERGENCY_FUND = "REBUILD_EMERGENCY_FUND", "Reconstruir fondo"
        REDUCE_HIGH_COST_DEBT = "REDUCE_HIGH_COST_DEBT", "Reducir deuda cara"
        INCREASE_CONTRIBUTION = "INCREASE_CONTRIBUTION", "Aumentar aportacion"
        ADJUST_TARGET_DATE = "ADJUST_TARGET_DATE", "Ajustar fecha objetivo"
        ADJUST_TARGET_INCOME = "ADJUST_TARGET_INCOME", "Ajustar nivel de vida"
        RESCHEDULE_SECONDARY_GOAL = "RESCHEDULE_SECONDARY_GOAL", "Reprogramar objetivo"
        REDUCE_EVENT_OUTFLOW = "REDUCE_EVENT_OUTFLOW", "Reducir desembolso"
        COMPLETE_DATA = "COMPLETE_DATA", "Completar datos"

    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        ACCEPTED = "accepted", "Aceptada"
        DISMISSED = "dismissed", "Descartada"
        SNOOZED = "snoozed", "Pospuesta"

    finding = models.ForeignKey(
        Finding,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    code = models.CharField(max_length=64, choices=Code.choices)
    priority = models.PositiveSmallIntegerField(default=100)
    action_json = models.JSONField(default=dict, blank=True)
    impact_json = models.JSONField(default=dict, blank=True)
    alternatives_json = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["finding", "code"], name="uniq_recommendation_finding_code"
            )
        ]
        indexes = [
            models.Index(fields=["finding", "status"]),
            models.Index(fields=["status", "priority"]),
        ]
        ordering = ["priority", "-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.finding_id} - {self.code}"


class ProjectionSnapshot(models.Model):
    plan = models.ForeignKey(
        FinancialPlan,
        on_delete=models.CASCADE,
        related_name="projection_snapshots",
    )
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projection_snapshots",
    )
    assumption_set = models.ForeignKey(
        AssumptionSet,
        on_delete=models.PROTECT,
        related_name="projection_snapshots",
    )
    assumption_values = models.JSONField()
    calculated_at = models.DateTimeField(auto_now_add=True)
    input_hash = models.CharField(max_length=64)
    result_json = models.JSONField()
    quality_level = models.CharField(max_length=32)
    is_official = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["plan", "-calculated_at"]),
            models.Index(fields=["plan", "is_official"]),
            models.Index(fields=["input_hash"]),
        ]
        ordering = ["-calculated_at", "-id"]

    def __str__(self) -> str:
        return f"{self.plan_id} - {self.assumption_set.name} - {self.calculated_at}"
