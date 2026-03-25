import { computed, reactive, ref, watch } from 'vue';
import { useAccountingPage } from '@/domains/accounting/composables';

export function useAccountingMovementsPage() {
  const {
    loading,
    accountCreationLoading,
    accountActivationLoading,
    transactionCreationLoading,
    importPreviewLoading,
    importCommitLoading,
    error,
    successMessage,
    accounts,
    moneyWizImportPreview,
    selectedYear,
    yearOptions,
    monthOptions,
    accountTypeOptions,
    manualPositionTypeOptions,
    quickMovementTypeOptions,
    editMovementTypeOptions,
    editAccountOptions,
    editCounterpartyOptions,
    editCounterpartyMissingHint,
    editKindNeedsCounterparty,
    editKindNeedsClassification,
    editCounterpartyLabel,
    editSelectedAccountCurrentBalance,
    editCategoryOptions,
    editSubcategoryOptions,
    activationForm,
    moneyWizImportFile,
    ownershipOptions,
    quickEntryForm,
    editTransactionForm,
    activityFilters,
    cuentasFilters,
    liquidityAccounts,
    availableManualPositionOptions,
    accountDisplayName,
    accountPositionMetaByAccountId,
    hasAvailableManualPositions,
    annualIncomeOptionsCompatible,
    annualExpenseOptionsCompatible,
    quickEntryNeedsClassification,
    quickCategoryOptions,
    quickSubcategoryOptions,
    filterCategoryOptions,
    filterSubcategoryOptions,
    cuentasFilterCategoryOptions,
    cuentasFilterSubcategoryOptions,
    transferCounterpartyOptions,
    investmentCounterpartyOptions,
    liabilityCounterpartyOptions,
    debtInterestOptions,
    revaluationAccountOptions,
    revaluationCurrentBalance,
    revaluationDelta,
    quickEntryReady,
    editEntryReady,
    summaryRows,
    hasImportedTransactions,
    activeTab,
    cuentasSelectedAccountId,
    cuentasSelectedAccount,
    cuentasDateFrom,
    cuentasDateTo,
    cuentasTransactions,
    cuentasTotalCount,
    cuentasLoading,
    cuentasLoadingMore,
    cuentasHasMore,
    loadMoreCuentas,
    todosDateFrom,
    todosDateTo,
    todosTransactions,
    todosTotalCount,
    todosLoading,
    todosLoadingMore,
    todosHasMore,
    loadMoreTodos,
    transactionMainAmount,
    activityKindLabel,
    transactionOwnershipLabel,
    transactionClassificationLabel,
    transactionAccountTrailLabel,
    reloadPeriod,
    activateNetWorthPositions,
    removeNetWorthTracking,
    deleteAccount,
    deleteTransaction,
    deleteImportedTransactions,
    openTransactionForEditing,
    setMoneyWizImportFile,
    previewMoneyWizImport,
    commitMoneyWizImport,
    submitQuickEntry,
    submitEditedTransaction,
  } = useAccountingPage();

  function toNumber(raw: string): number {
    const normalized = String(raw ?? '')
      .trim()
      .replace(',', '.');
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function formatDate(isoDate: string): string {
    const d = new Date(isoDate + 'T00:00:00');
    return new Intl.DateTimeFormat('es-ES', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(d);
  }

  function formatMoney(value: number, currency = 'EUR'): string {
    const normalizedCurrency = currency.trim().toUpperCase();
    const isBtc = normalizedCurrency === 'BTC';
    return new Intl.NumberFormat('es-ES', {
      style: 'currency',
      currency: normalizedCurrency,
      minimumFractionDigits: isBtc ? 6 : normalizedCurrency === 'EUR' ? 2 : undefined,
      maximumFractionDigits: isBtc ? 8 : 2,
    }).format(value);
  }

  function formatCompact(raw: string, currency = 'EUR'): string {
    return formatMoney(toNumber(raw), currency);
  }

  function monthLabel(month: number): string {
    return (
      monthOptions.find((option) => option.value === month)?.label.slice(0, 3) ??
      String(month).padStart(2, '0')
    );
  }

  const accountsByType = computed(() => {
    const groups = new Map<string, typeof accounts.value>();
    accounts.value.forEach((account) => {
      const existing = groups.get(account.account_type) ?? [];
      existing.push(account);
      groups.set(account.account_type, existing);
    });
    return groups;
  });
  const accountingAssetsTotal = computed(() =>
    (accountsByType.value.get('asset') ?? []).reduce(
      (total, account) => total + toNumber(account.current_balance),
      0,
    ),
  );
  const accountingLiabilitiesTotal = computed(() =>
    (accountsByType.value.get('liability') ?? []).reduce(
      (total, account) => total + toNumber(account.current_balance),
      0,
    ),
  );
  const accountingNetBalance = computed(
    () => accountingAssetsTotal.value - accountingLiabilitiesTotal.value,
  );
  const operationalAccountTypeOptions = computed(() =>
    accountTypeOptions.filter((type) => type.value === 'asset' || type.value === 'liability'),
  );
  const operationalAccounts = computed(() =>
    operationalAccountTypeOptions.value.flatMap(
      (type) => accountsByType.value.get(type.value) ?? [],
    ),
  );
  const technicalAccountTypeOptions = computed(() =>
    accountTypeOptions.filter((type) => type.value !== 'asset' && type.value !== 'liability'),
  );
  const hasTechnicalAccounts = computed(() =>
    technicalAccountTypeOptions.value.some(
      (type) => (accountsByType.value.get(type.value)?.length ?? 0) > 0,
    ),
  );
  const groupedCuentasAccounts = computed(() => {
    type Group = {
      key: string;
      label: string;
      positionType: 'asset' | 'liability';
      accounts: (typeof operationalAccounts.value)[number][];
    };
    const groups = new Map<string, Group>();
    for (const account of operationalAccounts.value) {
      const meta = accountPositionMetaByAccountId.value.get(account.id);
      const posType: 'asset' | 'liability' =
        (meta?.position_type as 'asset' | 'liability') ??
        (account.account_type === 'asset' ? 'asset' : 'liability');
      const category = meta?.category ?? 'other';
      const key = `${posType}:${category}`;
      if (!groups.has(key)) {
        const labels =
          posType === 'asset' ? assetActivationCategoryLabels : liabilityActivationCategoryLabels;
        groups.set(key, {
          key,
          label: labels[category] ?? category,
          positionType: posType,
          accounts: [],
        });
      }
      groups.get(key)!.accounts.push(account);
    }
    for (const group of groups.values()) {
      group.accounts.sort((a, b) =>
        accountDisplayName(a).localeCompare(accountDisplayName(b), 'es', { sensitivity: 'base' }),
      );
    }
    const allOrderedKeys = [
      ...assetActivationCategoryOrder.map((k) => `asset:${k}`),
      ...liabilityActivationCategoryOrder.map((k) => `liability:${k}`),
    ];
    const ordered = [
      ...allOrderedKeys.filter((k) => groups.has(k)),
      ...Array.from(groups.keys()).filter((k) => !allOrderedKeys.includes(k)),
    ];
    return ordered.filter((k) => groups.has(k)).map((k) => groups.get(k)!);
  });
  function formatSignedMoney(value: number, currency = 'EUR'): string {
    if (value > 0) return `+${formatMoney(value, currency)}`;
    if (value < 0) return `-${formatMoney(Math.abs(value), currency)}`;
    return formatMoney(0, currency);
  }

  type DatePreset = 'all' | 'this_month' | 'last_month' | 'last_3_months' | 'this_year' | 'custom';
  const datePresetOptions: { value: DatePreset; label: string }[] = [
    { value: 'all', label: 'Período' },
    { value: 'this_month', label: 'Este mes' },
    { value: 'last_month', label: 'Mes anterior' },
    { value: 'last_3_months', label: 'Últimos 3m' },
    { value: 'this_year', label: 'Este año' },
    { value: 'custom', label: 'Personalizado' },
  ];
  const todosDatePreset = ref<DatePreset>('all');
  const cuentasDatePreset = ref<DatePreset>('all');

  function applyDatePreset(preset: DatePreset) {
    todosDatePreset.value = preset;
    if (preset === 'custom') return;
    const now = new Date();
    const fmt = (d: Date) => d.toISOString().slice(0, 10);
    if (preset === 'all') {
      todosDateFrom.value = '';
      todosDateTo.value = '';
      return;
    }
    if (preset === 'this_month') {
      todosDateFrom.value = fmt(new Date(now.getFullYear(), now.getMonth(), 1));
      todosDateTo.value = '';
      return;
    }
    if (preset === 'last_month') {
      const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const last = new Date(now.getFullYear(), now.getMonth(), 0);
      todosDateFrom.value = fmt(first);
      todosDateTo.value = fmt(last);
      return;
    }
    if (preset === 'last_3_months') {
      todosDateFrom.value = fmt(new Date(now.getFullYear(), now.getMonth() - 2, 1));
      todosDateTo.value = '';
      return;
    }
    if (preset === 'this_year') {
      todosDateFrom.value = fmt(new Date(now.getFullYear(), 0, 1));
      todosDateTo.value = '';
      return;
    }
  }

  function applyCuentasDatePreset(preset: DatePreset) {
    cuentasDatePreset.value = preset;
    if (preset === 'custom') return;
    const now = new Date();
    const fmt = (d: Date) => d.toISOString().slice(0, 10);
    if (preset === 'all') {
      cuentasDateFrom.value = '';
      cuentasDateTo.value = '';
      return;
    }
    if (preset === 'this_month') {
      cuentasDateFrom.value = fmt(new Date(now.getFullYear(), now.getMonth(), 1));
      cuentasDateTo.value = '';
      return;
    }
    if (preset === 'last_month') {
      const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const last = new Date(now.getFullYear(), now.getMonth(), 0);
      cuentasDateFrom.value = fmt(first);
      cuentasDateTo.value = fmt(last);
      return;
    }
    if (preset === 'last_3_months') {
      cuentasDateFrom.value = fmt(new Date(now.getFullYear(), now.getMonth() - 2, 1));
      cuentasDateTo.value = '';
      return;
    }
    if (preset === 'this_year') {
      cuentasDateFrom.value = fmt(new Date(now.getFullYear(), 0, 1));
      cuentasDateTo.value = '';
      return;
    }
  }

  const showActivationModal = ref(false);
  const showEditTransactionModal = ref(false);
  const showMoneyWizImportModal = ref(false);
  const showQuickEntryModal = ref(false);
  const activationQuery = ref('');
  const activationOperationalOnly = ref(true);
  const selectedActivationIds = ref<number[]>([]);
  const assetActivationCategoryOrder = [
    'cash',
    'investments',
    'real_estate',
    'furnishings',
    'other',
  ];
  const assetActivationCategoryLabels: Record<string, string> = {
    cash: 'Liquidez',
    investments: 'Inversiones',
    real_estate: 'Inmuebles',
    furnishings: 'Mobiliario',
    other: 'Otros',
  };
  const liabilityActivationCategoryOrder = ['mortgage', 'personal_loan', 'credit_card', 'other'];
  const liabilityActivationCategoryLabels: Record<string, string> = {
    mortgage: 'Hipoteca',
    personal_loan: 'Prestamo personal',
    credit_card: 'Tarjeta',
    other: 'Otros',
  };
  const activationOperationalCategories = new Set(['cash', 'investments']);
  const filteredManualPositionOptions = computed(() => {
    const base =
      activationForm.position_type === 'liability'
        ? availableManualPositionOptions.value
        : activationOperationalOnly.value
          ? availableManualPositionOptions.value.filter((position) =>
              activationOperationalCategories.has(String(position.category ?? '').trim()),
            )
          : availableManualPositionOptions.value;
    const query = activationQuery.value.trim().toLowerCase();
    if (!query) return base;
    return base.filter((position) =>
      `${position.name} ${position.currency}`.toLowerCase().includes(query),
    );
  });
  const activationExcludedByOperationalFilter = computed(() => {
    if (activationForm.position_type === 'liability') return 0;
    if (!activationOperationalOnly.value) return 0;
    return Math.max(
      availableManualPositionOptions.value.length - filteredManualPositionOptions.value.length,
      0,
    );
  });
  const groupedManualPositionOptions = computed(() => {
    const groups = new Map<string, typeof filteredManualPositionOptions.value>();
    filteredManualPositionOptions.value.forEach((position) => {
      const key = String(position.category ?? 'other').trim() || 'other';
      const existing = groups.get(key) ?? [];
      existing.push(position);
      groups.set(key, existing);
    });
    const order =
      activationForm.position_type === 'asset'
        ? assetActivationCategoryOrder
        : liabilityActivationCategoryOrder;
    const labels =
      activationForm.position_type === 'asset'
        ? assetActivationCategoryLabels
        : liabilityActivationCategoryLabels;
    const orderedKeys = [
      ...order.filter((key) => groups.has(key)),
      ...Array.from(groups.keys()).filter((key) => !order.includes(key)),
    ];
    return orderedKeys.map((key) => ({
      key,
      label: labels[key] ?? key,
      positions: (groups.get(key) ?? []).slice().sort((a, b) => a.name.localeCompare(b.name, 'es')),
    }));
  });
  const allFilteredSelected = computed(
    () =>
      filteredManualPositionOptions.value.length > 0 &&
      filteredManualPositionOptions.value.every((position) =>
        selectedActivationIds.value.includes(position.id),
      ),
  );

  function openActivationModal() {
    selectedActivationIds.value = [];
    activationQuery.value = '';
    activationOperationalOnly.value = true;
    showActivationModal.value = true;
  }

  function toggleSelectAllFiltered() {
    if (allFilteredSelected.value) {
      const filteredIds = new Set(
        filteredManualPositionOptions.value.map((position) => position.id),
      );
      selectedActivationIds.value = selectedActivationIds.value.filter(
        (id) => !filteredIds.has(id),
      );
      return;
    }
    const merged = new Set(selectedActivationIds.value);
    filteredManualPositionOptions.value.forEach((position) => merged.add(position.id));
    selectedActivationIds.value = Array.from(merged);
  }

  async function activatePositionFromModal() {
    if (!selectedActivationIds.value.length) return;
    await activateNetWorthPositions(
      activationForm.position_type,
      selectedActivationIds.value.map((id) => Number(id)),
    );
    selectedActivationIds.value = [];
    activationQuery.value = '';
    showActivationModal.value = false;
  }

  async function submitQuickEntryFromModal() {
    await submitQuickEntry();
    showQuickEntryModal.value = false;
  }

  function handleMoneyWizFileChange(event: Event) {
    const input = event.target as HTMLInputElement | null;
    const file = input?.files?.[0] ?? null;
    setMoneyWizImportFile(file);
  }

  const moneyWizPreviewRows = computed(() => moneyWizImportPreview.value?.rows.slice(0, 6) ?? []);
  const moneyWizPreviewWarnings = computed(() => moneyWizImportPreview.value?.warnings ?? []);
  const moneyWizCanCommit = computed(
    () =>
      moneyWizImportFile.value != null &&
      moneyWizImportPreview.value != null &&
      moneyWizImportPreview.value.error_row_count === 0,
  );

  const moneyWizAccountMap = ref<Record<string, number | null>>({});

  function normalizeForMatch(name: string): string {
    return name
      .toLowerCase()
      .trim()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }

  function significantWords(normalized: string): string[] {
    return normalized.split(/[\s()]+/).filter((w) => w.length >= 3);
  }

  function fuzzyMatchScore(csvNorm: string, accNorm: string): number {
    const csvWords = significantWords(csvNorm);
    const accWords = significantWords(accNorm);
    if (csvWords.length === 0 || accWords.length === 0) return 0;
    // All words of the shorter name must appear in the longer name
    const [shorter, longer] =
      csvWords.length <= accWords.length ? [csvWords, accNorm] : [accWords, csvNorm];
    if (!shorter.every((w) => longer.includes(w))) return 0;
    return shorter.length / Math.max(csvWords.length, accWords.length);
  }

  function autoMatchMoneyWizAccount(detected: {
    name: string;
    account_type: string;
    role: string;
  }): number | null {
    const normalizedCsv = normalizeForMatch(detected.name);
    // Search across asset + liability regardless of detected type (MoneyWiz may misclassify)
    const candidates = accounts.value.filter(
      (a) => a.account_type === 'asset' || a.account_type === 'liability',
    );

    // Pass 1: exact normalized match, unique winner only
    const exactMatches = candidates.filter(
      (a) => normalizeForMatch(accountDisplayName(a)) === normalizedCsv,
    );
    if (exactMatches.length === 1) return exactMatches[0]!.id;
    if (exactMatches.length > 1) return null; // ambiguous duplicates

    // Pass 2: fuzzy word-score match, unique winner only
    const scored = candidates
      .map((a) => ({
        a,
        score: fuzzyMatchScore(normalizedCsv, normalizeForMatch(accountDisplayName(a))),
      }))
      .filter(({ score }) => score > 0)
      .sort((x, y) => y.score - x.score);
    if (scored.length === 0) return null;
    const top = scored[0]!;
    const second = scored[1];
    // Accept only if the top candidate is clearly better than the second
    if (!second || top.score > second.score) return top.a.id;
    return null;
  }

  watch(moneyWizImportPreview, () => {
    const newMap: Record<string, number | null> = {};
    if (moneyWizImportPreview.value) {
      for (const detected of moneyWizImportPreview.value.detected_accounts) {
        if (/^moneywiz counterparty/i.test(detected.name)) continue;
        const match = autoMatchMoneyWizAccount(detected);
        if (match !== null) newMap[detected.name] = match;
      }
    }
    moneyWizAccountMap.value = newMap;
  });

  function updateMoneyWizAccountMap(csvName: string, value: string) {
    moneyWizAccountMap.value[csvName] = value ? Number(value) : null;
  }

  async function previewMoneyWizImportFromModal() {
    await previewMoneyWizImport();
  }

  async function commitMoneyWizImportFromModal() {
    const accountIdMap: Record<string, number> = {};
    for (const [csvName, accountId] of Object.entries(moneyWizAccountMap.value)) {
      if (accountId != null) {
        accountIdMap[csvName] = accountId;
      }
    }
    const result = await commitMoneyWizImport(accountIdMap);
    if (result) {
      showMoneyWizImportModal.value = false;
    }
  }

  function openEditTransactionModal(transactionId: number) {
    if (openTransactionForEditing(transactionId)) {
      showEditTransactionModal.value = true;
    }
  }

  async function submitEditedTransactionFromModal() {
    const saved = await submitEditedTransaction();
    if (saved) {
      showEditTransactionModal.value = false;
    }
  }

  async function deleteTransactionFromTimeline(transactionId: number, description: string) {
    await deleteTransaction(transactionId, description);
  }

  const page = reactive({
    loading,
    accountCreationLoading,
    accountActivationLoading,
    transactionCreationLoading,
    importPreviewLoading,
    importCommitLoading,
    error,
    successMessage,
    accounts,
    moneyWizImportPreview,
    accountsByType,
    accountingAssetsTotal,
    accountingLiabilitiesTotal,
    accountingNetBalance,
    selectedYear,
    yearOptions,
    monthOptions,
    accountTypeOptions,
    manualPositionTypeOptions,
    quickMovementTypeOptions,
    editMovementTypeOptions,
    editAccountOptions,
    editCounterpartyOptions,
    editCounterpartyMissingHint,
    editKindNeedsCounterparty,
    editKindNeedsClassification,
    editCounterpartyLabel,
    editSelectedAccountCurrentBalance,
    editCategoryOptions,
    editSubcategoryOptions,
    activationForm,
    moneyWizImportFile,
    ownershipOptions,
    quickEntryForm,
    editTransactionForm,
    activityFilters,
    cuentasFilters,
    liquidityAccounts,
    availableManualPositionOptions,
    accountDisplayName,
    accountPositionMetaByAccountId,
    hasAvailableManualPositions,
    annualIncomeOptionsCompatible,
    annualExpenseOptionsCompatible,
    quickEntryNeedsClassification,
    quickCategoryOptions,
    quickSubcategoryOptions,
    filterCategoryOptions,
    filterSubcategoryOptions,
    cuentasFilterCategoryOptions,
    cuentasFilterSubcategoryOptions,
    transferCounterpartyOptions,
    investmentCounterpartyOptions,
    liabilityCounterpartyOptions,
    debtInterestOptions,
    revaluationAccountOptions,
    revaluationCurrentBalance,
    revaluationDelta,
    quickEntryReady,
    editEntryReady,
    summaryRows,
    hasImportedTransactions,
    activeTab,
    groupedCuentasAccounts,
    cuentasSelectedAccountId,
    cuentasSelectedAccount,
    cuentasDateFrom,
    cuentasDateTo,
    cuentasDatePreset,
    applyCuentasDatePreset,
    cuentasTransactions,
    cuentasTotalCount,
    cuentasLoading,
    cuentasLoadingMore,
    cuentasHasMore,
    loadMoreCuentas,
    todosDateFrom,
    todosDateTo,
    todosDatePreset,
    datePresetOptions,
    applyDatePreset,
    todosTransactions,
    todosTotalCount,
    todosLoading,
    todosLoadingMore,
    todosHasMore,
    loadMoreTodos,
    transactionMainAmount,
    activityKindLabel,
    transactionOwnershipLabel,
    transactionClassificationLabel,
    transactionAccountTrailLabel,
    reloadPeriod,
    activateNetWorthPositions,
    removeNetWorthTracking,
    deleteAccount,
    deleteTransaction,
    deleteImportedTransactions,
    openTransactionForEditing,
    showActivationModal,
    showEditTransactionModal,
    showMoneyWizImportModal,
    showQuickEntryModal,
    activationQuery,
    activationOperationalOnly,
    selectedActivationIds,
    allFilteredSelected,
    groupedManualPositionOptions,
    activationExcludedByOperationalFilter,
    operationalAccounts,
    technicalAccountTypeOptions,
    hasTechnicalAccounts,
    moneyWizAccountMap,
    moneyWizPreviewRows,
    moneyWizPreviewWarnings,
    moneyWizCanCommit,
    formatDate,
    formatMoney,
    formatCompact,
    formatSignedMoney,
    monthLabel,
    toggleSelectAllFiltered,
    activatePositionFromModal,
    submitQuickEntryFromModal,
    handleMoneyWizFileChange,
    updateMoneyWizAccountMap,
    previewMoneyWizImportFromModal,
    commitMoneyWizImportFromModal,
    submitEditedTransactionFromModal,
    deleteTransactionFromTimeline,
    openActivationModal,
    openEditTransactionModal,
  });

  watch(availableManualPositionOptions, (options) => {
    const optionIds = new Set(options.map((option) => option.id));
    selectedActivationIds.value = selectedActivationIds.value.filter((id) => optionIds.has(id));
  });

  return page;
}

export type AccountingMovementsPageState = ReturnType<typeof useAccountingMovementsPage>;
