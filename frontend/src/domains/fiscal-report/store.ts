import { defineStore } from 'pinia';
import { toApiErrorMessage } from '@/lib/errors';
import type { OwnershipRead } from '@/domains/people/types';
import {
  fiscalReportApi,
  type BalanceReconciliationEntry,
  type BotResultDetail,
  type BotResultDrilldownRow,
  type BrokerCredential,
  type BrokerCsvFileType,
  type BrokerCsvImportResponse,
  type BrokerName,
  type BrokerSyncStatusResponse,
  type BrokerSyncTriggerResponse,
  type BrokerTradeDrilldownRow,
  type IncomeEventDrilldownRow,
  type ManualCostBasisInput,
  type ManualCostBasisRow,
  type SyncRunSummary,
  type FiscalReportPayload,
} from './api';

type CredentialCreatePayload = {
  broker: BrokerName;
  label: string;
  ownership_id: number;
  api_key: string;
  api_secret: string;
};

type CsvImportPayload = {
  broker: BrokerName;
  file_type: BrokerCsvFileType;
  file: File;
};

type SyncRunDrilldownFilters = {
  source: string;
  symbol: string;
  side: '' | 'buy' | 'sell';
};

function toReconciliationEntries(runs: SyncRunSummary[]): BalanceReconciliationEntry[] {
  const map = new Map<string, BalanceReconciliationEntry>();
  for (const run of runs) {
    for (const gap of run.gaps ?? []) {
      if (gap.source !== 'balance_reconciliation') continue;
      const asset = String(gap.asset ?? '')
        .trim()
        .toUpperCase();
      if (!asset) continue;
      const expected = Number(gap.expected ?? 0);
      const actual = Number(gap.actual ?? 0);
      const diff = Number(gap.diff ?? actual - expected);
      const key = asset;
      if (map.has(key)) continue;
      map.set(key, {
        asset,
        expected,
        actual,
        diff,
        status: Math.abs(diff) > 0 ? 'mismatch' : 'ok',
        sync_run_id: run.id,
        sync_run_finished_at: run.finished_at,
      });
    }
  }
  return Array.from(map.values()).sort((a, b) => a.asset.localeCompare(b.asset));
}

function resolveFilenameFromDisposition(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const filenameStarMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch?.[1]) {
    return decodeURIComponent(filenameStarMatch[1]);
  }
  const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);
  if (filenameMatch?.[1]) return filenameMatch[1];
  return fallback;
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const useFiscalReportStore = defineStore('fiscal-report', {
  state: () => ({
    initialized: false as boolean,
    selectedYear: new Date().getFullYear(),
    credentials: [] as BrokerCredential[],
    ownerships: [] as OwnershipRead[],
    syncStatusByCredential: {} as Record<number, BrokerSyncStatusResponse | undefined>,
    lastSyncRunByCredential: {} as Record<number, BrokerSyncTriggerResponse | undefined>,
    csvImportResults: [] as BrokerCsvImportResponse[],
    report: null as FiscalReportPayload | null,

    syncRuns: [] as SyncRunSummary[],
    syncRunsCount: 0 as number,
    syncRunsPage: 1 as number,
    activeSyncRunId: null as number | null,
    activeSyncRun: null as SyncRunSummary | null,
    syncRunFilters: {
      source: '',
      symbol: '',
      side: '',
    } as SyncRunDrilldownFilters,
    syncRunTrades: [] as BrokerTradeDrilldownRow[],
    syncRunTradesCount: 0 as number,
    syncRunTradesPage: 1 as number,
    syncRunIncomeEvents: [] as IncomeEventDrilldownRow[],
    syncRunIncomeEventsCount: 0 as number,
    syncRunIncomeEventsPage: 1 as number,
    syncRunBotResults: [] as BotResultDrilldownRow[],
    syncRunBotResultsCount: 0 as number,
    syncRunBotResultsPage: 1 as number,
    botResultDetailById: {} as Record<number, BotResultDetail | undefined>,
    balanceReconciliation: [] as BalanceReconciliationEntry[],
    botResultsForYear: [] as BotResultDrilldownRow[],
    manualCostBasisAsset: null as string | null,
    manualCostBases: [] as ManualCostBasisRow[],

    loadingCredentials: false as boolean,
    loadingReport: false as boolean,
    syncingByCredential: {} as Record<number, boolean>,
    deletingByCredential: {} as Record<number, boolean>,
    creatingCredential: false as boolean,
    importingCsv: false as boolean,
    loadingSyncRuns: false as boolean,
    loadingSyncRunDrilldown: false as boolean,
    loadingBalanceReconciliation: false as boolean,
    loadingManualCostBases: false as boolean,
    creatingManualCostBasis: false as boolean,
    deletingManualCostBasisById: {} as Record<number, boolean>,
    downloadingExport: false as boolean,

    landingError: null as string | null,
    reportError: null as string | null,
    successMessage: null as string | null,
  }),

  getters: {
    ownershipOptions(state) {
      return state.ownerships.map((ownership) => {
        const memberName = ownership.member?.name ?? '';
        const splitText =
          ownership.kind === 'shared'
            ? ownership.splits.map((split) => `${split.member.name} ${split.percent}%`).join(' · ')
            : '';
        const label =
          ownership.kind === 'individual'
            ? `Individual${memberName ? ` · ${memberName}` : ''}`
            : `Shared${splitText ? ` · ${splitText}` : ''}`;
        return { value: ownership.id, label };
      });
    },
  },

  actions: {
    clearMessages() {
      this.landingError = null;
      this.reportError = null;
      this.successMessage = null;
    },

    setSelectedYear(year: number) {
      this.selectedYear = year;
    },

    setSyncRunFilters(filters: Partial<SyncRunDrilldownFilters>) {
      this.syncRunFilters = {
        ...this.syncRunFilters,
        ...filters,
      };
      this.syncRunTradesPage = 1;
    },

    async fetchOwnerships() {
      const { data } = await fiscalReportApi.getOwnerships();
      this.ownerships = data;
    },

    async fetchCredentials() {
      this.loadingCredentials = true;
      this.landingError = null;
      try {
        const { data } = await fiscalReportApi.getCredentials();
        this.credentials = data;
        const statusResponses = await Promise.allSettled(
          data.map((credential) => fiscalReportApi.getSyncStatus(credential.id)),
        );
        const nextSyncStatusByCredential: Record<number, BrokerSyncStatusResponse | undefined> = {};
        statusResponses.forEach((response, index) => {
          if (response.status !== 'fulfilled') return;
          const credential = data[index];
          if (!credential) return;
          nextSyncStatusByCredential[credential.id] = response.value.data;
        });
        this.syncStatusByCredential = nextSyncStatusByCredential;
      } catch (error) {
        this.landingError = toApiErrorMessage(error);
      } finally {
        this.loadingCredentials = false;
      }
    },

    async fetchSyncRuns(page = 1) {
      this.loadingSyncRuns = true;
      try {
        const { data } = await fiscalReportApi.getSyncRuns({
          year: this.selectedYear,
          page,
        });
        this.syncRuns = data.results;
        this.syncRunsCount = data.count;
        this.syncRunsPage = page;
        this.balanceReconciliation = toReconciliationEntries(data.results);
      } finally {
        this.loadingSyncRuns = false;
      }
    },

    async fetchSyncRunDetail(syncRunId: number) {
      const { data } = await fiscalReportApi.getSyncRun(syncRunId);
      this.activeSyncRun = data;
      this.activeSyncRunId = syncRunId;
    },

    async fetchActiveRunDrilldown() {
      if (!this.activeSyncRunId) return;
      this.loadingSyncRunDrilldown = true;
      try {
        const [tradesResponse, incomeResponse, botResponse] = await Promise.all([
          fiscalReportApi.getTrades({
            year: this.selectedYear,
            sync_run: this.activeSyncRunId,
            source: this.syncRunFilters.source || undefined,
            symbol: this.syncRunFilters.symbol || undefined,
            side: this.syncRunFilters.side || undefined,
            page: this.syncRunTradesPage,
          }),
          fiscalReportApi.getIncomeEvents({
            year: this.selectedYear,
            sync_run: this.activeSyncRunId,
            source: this.syncRunFilters.source || undefined,
            page: this.syncRunIncomeEventsPage,
          }),
          fiscalReportApi.getBotResults({
            year: this.selectedYear,
            sync_run: this.activeSyncRunId,
            page: this.syncRunBotResultsPage,
          }),
        ]);
        this.syncRunTrades = tradesResponse.data.results;
        this.syncRunTradesCount = tradesResponse.data.count;
        this.syncRunIncomeEvents = incomeResponse.data.results;
        this.syncRunIncomeEventsCount = incomeResponse.data.count;
        this.syncRunBotResults = botResponse.data.results;
        this.syncRunBotResultsCount = botResponse.data.count;
      } finally {
        this.loadingSyncRunDrilldown = false;
      }
    },

    async openSyncRun(syncRunId: number) {
      this.syncRunTradesPage = 1;
      this.syncRunIncomeEventsPage = 1;
      this.syncRunBotResultsPage = 1;
      await this.fetchSyncRunDetail(syncRunId);
      await this.fetchActiveRunDrilldown();
    },

    async fetchBotResultDetail(botResultId: number) {
      if (this.botResultDetailById[botResultId]) return this.botResultDetailById[botResultId];
      const { data } = await fiscalReportApi.getBotResult(botResultId);
      this.botResultDetailById = {
        ...this.botResultDetailById,
        [botResultId]: data,
      };
      return data;
    },

    async fetchManualCostBases(asset?: string) {
      this.loadingManualCostBases = true;
      if (asset) {
        this.manualCostBasisAsset = asset.trim().toUpperCase();
      }
      try {
        const targetAsset = asset ?? this.manualCostBasisAsset ?? undefined;
        const { data } = await fiscalReportApi.getManualCostBasis(targetAsset);
        this.manualCostBases = data.results;
      } finally {
        this.loadingManualCostBases = false;
      }
    },

    async createManualCostBasis(payload: ManualCostBasisInput) {
      this.creatingManualCostBasis = true;
      this.reportError = null;
      try {
        await fiscalReportApi.createManualCostBasis(payload);
        await Promise.all([this.fetchManualCostBases(payload.asset), this.generateReport()]);
        this.successMessage = 'Coste manual asignado y reporte recalculado.';
      } catch (error) {
        this.reportError = toApiErrorMessage(error);
      } finally {
        this.creatingManualCostBasis = false;
      }
    },

    async deleteManualCostBasis(id: number, asset?: string) {
      this.deletingManualCostBasisById = {
        ...this.deletingManualCostBasisById,
        [id]: true,
      };
      this.reportError = null;
      try {
        await fiscalReportApi.deleteManualCostBasis(id);
        await Promise.all([this.fetchManualCostBases(asset), this.generateReport()]);
        this.successMessage = 'Coste manual eliminado y reporte recalculado.';
      } catch (error) {
        this.reportError = toApiErrorMessage(error);
      } finally {
        this.deletingManualCostBasisById = {
          ...this.deletingManualCostBasisById,
          [id]: false,
        };
      }
    },

    async downloadFiscalExport(format: 'csv' | 'pdf') {
      this.downloadingExport = true;
      this.reportError = null;
      try {
        const response = await fiscalReportApi.downloadFiscalReportExport({
          year: this.selectedYear,
          format,
        });
        const disposition = String(response.headers['content-disposition'] ?? '');
        const fallback = `fiscal-${this.selectedYear}.${format}`;
        const filename = resolveFilenameFromDisposition(disposition, fallback);
        triggerBlobDownload(response.data, filename);
      } catch (error) {
        this.reportError = toApiErrorMessage(error);
      } finally {
        this.downloadingExport = false;
      }
    },

    async fetchBotResultsForYear() {
      const { data } = await fiscalReportApi.getBotResults({
        year: this.selectedYear,
      });
      this.botResultsForYear = data.results;
    },

    async initializeLanding() {
      this.clearMessages();
      try {
        await this.fetchOwnerships();
      } catch (error) {
        this.landingError = toApiErrorMessage(error);
      }
      await Promise.all([this.fetchCredentials(), this.fetchSyncRuns()]);
      this.initialized = true;
    },

    async createCredential(payload: CredentialCreatePayload) {
      this.creatingCredential = true;
      this.landingError = null;
      this.successMessage = null;
      try {
        await fiscalReportApi.createCredential(payload);
        await this.fetchCredentials();
        this.successMessage = 'Credencial guardada.';
      } catch (error) {
        this.landingError = toApiErrorMessage(error);
      } finally {
        this.creatingCredential = false;
      }
    },

    async deleteCredential(credentialId: number) {
      this.deletingByCredential = {
        ...this.deletingByCredential,
        [credentialId]: true,
      };
      this.landingError = null;
      this.successMessage = null;
      try {
        await fiscalReportApi.deleteCredential(credentialId);
        this.credentials = this.credentials.filter((credential) => credential.id !== credentialId);
        const nextSyncStatusByCredential = { ...this.syncStatusByCredential };
        delete nextSyncStatusByCredential[credentialId];
        this.syncStatusByCredential = nextSyncStatusByCredential;
        this.successMessage = 'Credencial eliminada.';
      } catch (error) {
        this.landingError = toApiErrorMessage(error);
      } finally {
        this.deletingByCredential = {
          ...this.deletingByCredential,
          [credentialId]: false,
        };
      }
    },

    async syncCredential(credentialId: number) {
      this.syncingByCredential = {
        ...this.syncingByCredential,
        [credentialId]: true,
      };
      this.landingError = null;
      this.successMessage = null;
      try {
        const response = await fiscalReportApi.triggerSync(credentialId, this.selectedYear);
        this.lastSyncRunByCredential = {
          ...this.lastSyncRunByCredential,
          [credentialId]: response.data,
        };
        const statusResponse = await fiscalReportApi.getSyncStatus(credentialId);
        this.syncStatusByCredential = {
          ...this.syncStatusByCredential,
          [credentialId]: statusResponse.data,
        };
        await Promise.all([this.fetchCredentials(), this.fetchSyncRuns()]);
        this.successMessage = 'Sync completado.';
      } catch (error) {
        this.landingError = toApiErrorMessage(error);
      } finally {
        this.syncingByCredential = {
          ...this.syncingByCredential,
          [credentialId]: false,
        };
      }
    },

    async importCsv(payload: CsvImportPayload) {
      this.importingCsv = true;
      this.landingError = null;
      this.successMessage = null;
      try {
        const response = await fiscalReportApi.importCsv(payload);
        this.csvImportResults = [response.data, ...this.csvImportResults].slice(0, 12);
        this.successMessage = 'CSV procesado correctamente.';
      } catch (error) {
        this.landingError = toApiErrorMessage(error);
      } finally {
        this.importingCsv = false;
      }
    },

    async generateReport() {
      this.loadingReport = true;
      this.reportError = null;
      try {
        const response = await fiscalReportApi.getFiscalReport({ year: this.selectedYear });
        this.report = response.data;
        await Promise.all([this.fetchBotResultsForYear(), this.fetchManualCostBases()]);
      } catch (error) {
        this.reportError = toApiErrorMessage(error);
      } finally {
        this.loadingReport = false;
      }
    },
  },
});
