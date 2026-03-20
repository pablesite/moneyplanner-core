import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue';
import {
  buildImportPreviewMessage,
  buildPortableFilename,
  parsePortableDataBundle,
  type ImportMode,
  type PortableAnnualExpenseRecord,
  type PortableAnnualIncomeRecord,
  type PortableAssetRecord,
  type PortableDataBundle,
  type PortableFamilyMemberRecord,
  type PortableLiabilityRecord,
  type PortableOwnershipLinkRecord,
  type PortableOwnershipRecord,
  type PortableSettingsRecord,
  type PortableSnapshotRecord,
  toPortableAnnualExpenseRecord,
  toPortableAnnualIncomeRecord,
  toPortableAssetRecord,
  toPortableLiabilityRecord,
  toPortableOwnershipRecord,
} from '@/domains/data-input/portableBundle';
import { dataInputPageApi, toApiErrorMessage } from '@/domains/data-input/pageApi';

type PortableDataMeta = { app_version: string };

type PortableImportResponse = {
  ok: boolean;
  mode: ImportMode;
  meta: {
    schema_version: number;
    source_app: 'core' | 'saas';
    exported_at: string;
    exported_app_version?: string;
    imported_into_app_version: string;
  };
  counts: {
    annual_income: number;
    annual_expense: number;
    assets: number;
    liabilities: number;
    snapshots: number;
    family_members: number;
    ownerships: number;
    ownership_links: number;
  };
};

type UsePortableDataTransferOptions = {
  externalBusy?: Ref<boolean>;
  onImportCompleted?: () => Promise<void>;
};

export function usePortableDataTransfer(options: UsePortableDataTransferOptions = {}) {
  const dataTransferBusy = ref(false);
  const dataTransferBusyLabel = ref<string | null>(null);
  const dataTransferStatus = ref<string | null>(null);
  const dataTransferError = ref<string | null>(null);
  const dataTransferToastMessage = ref<string | null>(null);
  const dataTransferToastKind = ref<'success' | 'error'>('success');
  const importFileInputRef = ref<HTMLInputElement | null>(null);
  const pendingImportMode = ref<ImportMode>('append');
  const portableDataAppVersion = ref<string | null>(null);
  let dataTransferToastTimer: number | null = null;

  const dataTransferUiBusy = computed(
    () => dataTransferBusy.value || Boolean(options.externalBusy?.value),
  );

  function clearDataTransferFeedback(): void {
    dataTransferStatus.value = null;
    dataTransferError.value = null;
  }

  function clearDataTransferToast(): void {
    if (dataTransferToastTimer != null) {
      window.clearTimeout(dataTransferToastTimer);
      dataTransferToastTimer = null;
    }
    dataTransferToastMessage.value = null;
  }

  function showDataTransferToast(message: string, kind: 'success' | 'error' = 'success'): void {
    clearDataTransferToast();
    dataTransferToastKind.value = kind;
    dataTransferToastMessage.value = message;
    dataTransferToastTimer = window.setTimeout(() => {
      dataTransferToastMessage.value = null;
      dataTransferToastTimer = null;
    }, 5000);
  }

  function triggerImportDialog(mode: ImportMode = 'append'): void {
    clearDataTransferFeedback();
    pendingImportMode.value = mode;
    importFileInputRef.value?.click();
  }

  async function ensurePortableDataAppVersion(): Promise<string> {
    if (portableDataAppVersion.value) return portableDataAppVersion.value;
    const response = await dataInputPageApi.get<PortableDataMeta>('/api/core/portable-data/meta/');
    portableDataAppVersion.value = response.data.app_version;
    return portableDataAppVersion.value;
  }

  async function exportDataBundle(): Promise<void> {
    clearDataTransferFeedback();
    dataTransferBusyLabel.value = 'Exportando datos...';
    dataTransferBusy.value = true;
    try {
      const appVersion = await ensurePortableDataAppVersion();
      const [
        incomeRes,
        expenseRes,
        assetsRes,
        liabilitiesRes,
        snapshotsRes,
        settingsRes,
        membersRes,
        ownershipsRes,
        linksRes,
      ] = await Promise.all([
        dataInputPageApi.get<PortableAnnualIncomeRecord[]>('/api/budget/annual-income/'),
        dataInputPageApi.get<PortableAnnualExpenseRecord[]>('/api/budget/annual-expense/'),
        dataInputPageApi.get<PortableAssetRecord[]>('/api/net-worth/assets/'),
        dataInputPageApi.get<PortableLiabilityRecord[]>('/api/net-worth/liabilities/'),
        dataInputPageApi.get<PortableSnapshotRecord[]>('/api/net-worth/snapshots/'),
        dataInputPageApi.get<PortableSettingsRecord>('/api/auth/settings/'),
        dataInputPageApi.get<PortableFamilyMemberRecord[]>('/api/family-members/'),
        dataInputPageApi.get<PortableOwnershipRecord[]>('/api/ownerships/'),
        dataInputPageApi.get<PortableOwnershipLinkRecord[]>('/api/ownership-links/'),
      ]);

      const payload: PortableDataBundle = {
        schema_version: 1,
        exported_at: new Date().toISOString(),
        source_app: 'core',
        exported_app_version: appVersion,
        settings: settingsRes.data ?? undefined,
        data: {
          annual_income: (incomeRes.data ?? []).map(toPortableAnnualIncomeRecord),
          annual_expense: (expenseRes.data ?? []).map(toPortableAnnualExpenseRecord),
          assets: (assetsRes.data ?? []).map((row) => toPortableAssetRecord(row)),
          liabilities: (liabilitiesRes.data ?? []).map((row) => toPortableLiabilityRecord(row)),
          snapshots: (snapshotsRes.data ?? []).slice(),
        },
        premium: {
          family_members: (membersRes.data ?? []).slice(),
          ownerships: (ownershipsRes.data ?? []).map((row) => toPortableOwnershipRecord(row)),
          ownership_links: (linksRes.data ?? []).slice(),
        },
      };

      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = buildPortableFilename();
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      dataTransferStatus.value = `Exportacion completada: ${payload.data.annual_income.length} ingresos, ${payload.data.annual_expense.length} gastos, ${payload.data.assets.length} activos, ${payload.data.liabilities.length} pasivos, ${payload.data.snapshots?.length ?? 0} snapshots, ${payload.premium?.family_members.length ?? 0} miembros y ${payload.premium?.ownerships.length ?? 0} titularidades.`;
    } catch (e: unknown) {
      dataTransferError.value = `No se pudo exportar: ${toApiErrorMessage(e)}`;
    } finally {
      dataTransferBusy.value = false;
      dataTransferBusyLabel.value = null;
    }
  }

  function setDataImportBusyState(importMode: ImportMode) {
    dataTransferBusyLabel.value =
      importMode === 'replace'
        ? 'Reemplazando datos... Esto puede tardar unos segundos.'
        : 'Importando datos...';
    dataTransferBusy.value = true;
  }

  function buildImportCompletionStatus(params: {
    importMode: ImportMode;
    response: PortableImportResponse;
  }): string {
    const { importMode, response } = params;
    const counts = response.counts;
    return importMode === 'replace'
      ? `Reemplazo completado: ${counts.annual_income} ingresos, ${counts.annual_expense} gastos, ${counts.assets} activos, ${counts.liabilities} pasivos, ${counts.snapshots} snapshots, ${counts.family_members} miembros, ${counts.ownerships} titularidades y ${counts.ownership_links} enlaces de titularidad.`
      : `Importacion completada: ${counts.annual_income} ingresos, ${counts.annual_expense} gastos, ${counts.assets} activos, ${counts.liabilities} pasivos, ${counts.snapshots} snapshots, ${counts.family_members} miembros, ${counts.ownerships} titularidades y ${counts.ownership_links} enlaces de titularidad.`;
  }

  async function importDataFromFile(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) return;

    clearDataTransferFeedback();

    try {
      const appVersion = await ensurePortableDataAppVersion();
      const content = await file.text();
      const bundle = parsePortableDataBundle(content);
      const importMode = pendingImportMode.value;

      const proceed = window.confirm(buildImportPreviewMessage(bundle, importMode, appVersion));
      if (!proceed) return;

      setDataImportBusyState(importMode);

      const response = await dataInputPageApi.post<PortableImportResponse>(
        '/api/core/portable-data/import/',
        {
          mode: importMode,
          bundle,
        },
      );

      if (options.onImportCompleted) {
        await options.onImportCompleted();
      }

      dataTransferStatus.value = buildImportCompletionStatus({
        importMode,
        response: response.data,
      });
    } catch (e: unknown) {
      dataTransferError.value = `No se pudo importar: ${toApiErrorMessage(e)}`;
    } finally {
      dataTransferBusy.value = false;
      dataTransferBusyLabel.value = null;
      if (input) input.value = '';
    }
  }

  watch(dataTransferStatus, (message) => {
    if (message) showDataTransferToast(message, 'success');
  });

  watch(dataTransferError, (message) => {
    if (message) showDataTransferToast(message, 'error');
  });

  onBeforeUnmount(() => {
    clearDataTransferToast();
  });

  return {
    dataTransferBusy,
    dataTransferBusyLabel,
    dataTransferStatus,
    dataTransferError,
    dataTransferToastMessage,
    dataTransferToastKind,
    dataTransferUiBusy,
    importFileInputRef,
    triggerImportDialog,
    exportDataBundle,
    importDataFromFile,
  };
}
