import { computed, ref, watch, type Ref } from 'vue';
import {
  sanitizeAmount,
  addMonthsPreserveDayIso,
  monthsBetweenPreserveDayIso,
  todayIsoDate,
} from './itemFormUtils';

type LiabilityScheduleFormFields = {
  term_months: string;
  expected_end_date: string;
  start_date: string;
  payment_start_date: string;
  payment_frequency: string;
  rate_type: string;
  amortization_system: string;
  amount: string;
  annual_interest_tae: string;
  cancellation_forecast_enabled: boolean;
  cancellation_date: string;
  cancellation_include_payment_month: boolean;
  cancellation_fee_amount: string;
};

export function useLiabilitySchedule(
  form: LiabilityScheduleFormFields,
  showLiabilityAdvancedFields: Ref<boolean>,
  showMortgageCancellationForecastFields: Ref<boolean>,
  maxDecimals: Ref<number>,
) {
  const activeLiabilityFieldGroup = ref<'term' | 'end' | null>(null);
  let syncingScheduleFields = false;

  function getLiabilityScheduleAnchorDate(): string {
    const paymentStartDate = String(form.payment_start_date ?? '').trim();
    if (paymentStartDate) return paymentStartDate;
    return String(form.start_date ?? '').trim();
  }

  const liabilityDatesError = computed(() => {
    if (!showLiabilityAdvancedFields.value) return '';
    const paymentStartDate = getLiabilityScheduleAnchorDate();
    if (
      String(form.start_date ?? '').trim() &&
      paymentStartDate &&
      paymentStartDate < String(form.start_date).trim()
    ) {
      return 'Fecha inicio pago debe ser >= fecha contratación.';
    }
    if (!form.expected_end_date || !paymentStartDate) return '';
    return form.expected_end_date < paymentStartDate
      ? 'Fecha fin debe ser >= fecha inicio pago'
      : '';
  });

  // eslint-disable-next-line complexity
  function validateLiabilityScheduleFields(): string {
    const hasTerm = String(form.term_months ?? '').trim().length > 0;
    const hasEndDate = String(form.expected_end_date ?? '').trim().length > 0;
    const paymentFrequency = String(form.payment_frequency ?? '').trim();
    const scheduleAnchorDate = getLiabilityScheduleAnchorDate();
    if (
      String(form.payment_start_date ?? '').trim() &&
      String(form.start_date ?? '').trim() &&
      scheduleAnchorDate < String(form.start_date ?? '').trim()
    ) {
      return 'Fecha inicio pago debe ser >= fecha contratación.';
    }
    if (!hasTerm && !hasEndDate) return 'Indica cuotas o fecha fin (uno de los dos es obligatorio)';
    if (hasTerm) {
      const term = Number(String(form.term_months).trim());
      if (!Number.isInteger(term) || term <= 0) return 'Cuotas/plazo debe ser un entero > 0';
      if (paymentFrequency === 'quarterly' && term % 3 !== 0) {
        return 'En frecuencia trimestral, el plazo se indica en meses y debe ser múltiplo de 3 (ej: 12, 24).';
      }
    }
    if (hasEndDate) {
      const inferredMonths = monthsBetweenPreserveDayIso(
        scheduleAnchorDate,
        String(form.expected_end_date),
      );
      if (inferredMonths == null && !liabilityDatesError.value) {
        return 'La fecha fin no encaja con la fecha inicio y una cuota mensual exacta';
      }
    }
    if (hasTerm && hasEndDate) {
      const expectedFromTerm = addMonthsPreserveDayIso(
        scheduleAnchorDate,
        Number(String(form.term_months).trim()),
      );
      if (expectedFromTerm && expectedFromTerm !== String(form.expected_end_date)) {
        return 'Cuotas y fecha fin no coinciden';
      }
    }
    return '';
  }

  // eslint-disable-next-line complexity
  function estimateLiabilityPayment(): number | null {
    const paymentFrequency = String(form.payment_frequency ?? '').trim();
    if (paymentFrequency !== 'monthly' && paymentFrequency !== 'quarterly') return null;
    if (String(form.rate_type ?? '') !== 'fixed') return null;
    const amortSystem = String(form.amortization_system ?? '').trim();
    if (amortSystem && amortSystem !== 'french' && amortSystem !== 'manual') return null;

    const periodMonths = paymentFrequency === 'quarterly' ? 3 : 1;
    const periodsPerYear = paymentFrequency === 'quarterly' ? 4 : 12;
    const amountSanitized = sanitizeAmount(form.amount, maxDecimals.value);
    const principal = Number(String(amountSanitized.value ?? '').replace(',', '.'));
    const term = Number(String(form.term_months ?? '').trim());
    const tae = Number(
      String(form.annual_interest_tae ?? '')
        .trim()
        .replace(',', '.'),
    );
    const hasInvalidPrincipal =
      !amountSanitized.value ||
      amountSanitized.error ||
      !Number.isFinite(principal) ||
      principal <= 0;
    const hasInvalidTerm =
      !Number.isFinite(term) || term <= 0 || !Number.isInteger(term) || term % periodMonths !== 0;
    const hasInvalidTae = !Number.isFinite(tae) || tae < 0;
    if (hasInvalidPrincipal || hasInvalidTerm || hasInvalidTae) return null;

    const installments = term / periodMonths;
    if (tae === 0) return principal / installments;

    const periodicRate = tae / 100 / periodsPerYear;
    const denominator = 1 - Math.pow(1 + periodicRate, -installments);
    if (!Number.isFinite(denominator) || denominator === 0) return null;
    const payment = (principal * periodicRate) / denominator;
    return Number.isFinite(payment) ? payment : null;
  }

  const liabilityScheduleError = computed(() => {
    if (!showLiabilityAdvancedFields.value) return '';
    return validateLiabilityScheduleFields();
  });

  const cancellationForecastError = computed(() => {
    if (!showMortgageCancellationForecastFields.value) return '';
    if (!form.cancellation_forecast_enabled) return '';
    const cancellationDate = String(form.cancellation_date ?? '').trim();
    if (!cancellationDate) return 'Indica la fecha prevista de cancelación.';
    const referenceDate = getLiabilityScheduleAnchorDate() || String(form.start_date ?? '').trim();
    if (referenceDate && cancellationDate < referenceDate) {
      return 'Fecha de cancelación debe ser >= fecha inicio.';
    }
    const feeSanitized = sanitizeAmount(form.cancellation_fee_amount, maxDecimals.value);
    if (
      String(form.cancellation_fee_amount ?? '').trim() &&
      (feeSanitized.error || !feeSanitized.value)
    ) {
      return feeSanitized.error || 'Comisión de cancelación inválida.';
    }
    return '';
  });

  const estimatedMonthlyPaymentPreviewText = computed(() => {
    if (!showLiabilityAdvancedFields.value) return null;
    const value = estimateLiabilityPayment();
    if (value == null) return null;
    return new Intl.NumberFormat('es-ES', {
      minimumFractionDigits: 2,
      maximumFractionDigits: maxDecimals.value,
    }).format(value);
  });

  const estimatedPaymentPreviewLabel = computed(() => {
    const paymentFrequency = String(form.payment_frequency ?? '').trim();
    if (paymentFrequency === 'quarterly') return 'Cuota trimestral estimada';
    return 'Cuota mensual estimada';
  });

  const liabilityTermFieldLabel = computed(() => {
    const paymentFrequency = String(form.payment_frequency ?? '').trim();
    if (paymentFrequency === 'quarterly') return 'Plazo total (meses)';
    return 'Cuotas (meses)';
  });

  const liabilityTermFieldPlaceholder = computed(() => {
    const paymentFrequency = String(form.payment_frequency ?? '').trim();
    if (paymentFrequency === 'quarterly') return 'Ej: 12 o 24 (múltiplo de 3)';
    return 'Ej: 24';
  });

  const liabilityTermFieldHint = computed(() => {
    const paymentFrequency = String(form.payment_frequency ?? '').trim();
    if (paymentFrequency !== 'quarterly') return null;
    return 'Trimestral: introduce plazo total en meses (ej: 24 = 8 cuotas trimestrales).';
  });

  function syncExpectedEndDateFromTerm(): void {
    if (!showLiabilityAdvancedFields.value) return;
    const startDate = getLiabilityScheduleAnchorDate();
    const termRaw = String(form.term_months ?? '').trim();
    if (!startDate || !termRaw) return;
    const term = Number(termRaw);
    if (!Number.isInteger(term) || term <= 0) return;
    const computedEndDate = addMonthsPreserveDayIso(startDate, term);
    if (computedEndDate && form.expected_end_date !== computedEndDate) {
      form.expected_end_date = computedEndDate;
    }
  }

  function syncTermFromExpectedEndDate(): void {
    if (!showLiabilityAdvancedFields.value) return;
    const startDate = getLiabilityScheduleAnchorDate();
    const endDate = String(form.expected_end_date ?? '').trim();
    if (!startDate || !endDate) return;
    const inferredMonths = monthsBetweenPreserveDayIso(startDate, endDate);
    if (inferredMonths == null || inferredMonths <= 0) return;
    const nextTerm = String(inferredMonths);
    if (String(form.term_months ?? '') !== nextTerm) {
      form.term_months = nextTerm;
    }
  }

  function syncLinkedLiabilityScheduleField(source: 'term' | 'end'): void {
    if (syncingScheduleFields) return;
    syncingScheduleFields = true;
    try {
      if (source === 'term') syncExpectedEndDateFromTerm();
      else syncTermFromExpectedEndDate();
    } finally {
      syncingScheduleFields = false;
    }
  }

  function onLiabilityTermInput(): void {
    activeLiabilityFieldGroup.value = 'term';
    syncLinkedLiabilityScheduleField('term');
  }

  function onLiabilityEndDateInput(): void {
    activeLiabilityFieldGroup.value = 'end';
    syncLinkedLiabilityScheduleField('end');
  }

  function onLiabilityPaymentStartDateInput(): void {
    if (activeLiabilityFieldGroup.value === 'end') {
      syncLinkedLiabilityScheduleField('end');
      return;
    }
    syncLinkedLiabilityScheduleField('term');
  }

  watch(
    () => form.cancellation_forecast_enabled,
    (enabled) => {
      if (!enabled) {
        form.cancellation_date = '';
        form.cancellation_include_payment_month = true;
        form.cancellation_fee_amount = '';
      } else if (!String(form.cancellation_date ?? '').trim()) {
        form.cancellation_date = getLiabilityScheduleAnchorDate() || todayIsoDate();
      }
    },
  );

  watch([() => form.start_date, () => form.payment_start_date], () => {
    if (!showLiabilityAdvancedFields.value || syncingScheduleFields) return;
    if (activeLiabilityFieldGroup.value === 'end') {
      syncLinkedLiabilityScheduleField('end');
      return;
    }
    if (String(form.term_months ?? '').trim()) {
      syncLinkedLiabilityScheduleField('term');
      return;
    }
    if (String(form.expected_end_date ?? '').trim()) {
      syncLinkedLiabilityScheduleField('end');
    }
  });

  return {
    activeLiabilityFieldGroup,
    liabilityDatesError,
    liabilityScheduleError,
    cancellationForecastError,
    estimatedMonthlyPaymentPreviewText,
    estimatedPaymentPreviewLabel,
    liabilityTermFieldLabel,
    liabilityTermFieldPlaceholder,
    liabilityTermFieldHint,
    onLiabilityTermInput,
    onLiabilityEndDateInput,
    onLiabilityPaymentStartDateInput,
  };
}
