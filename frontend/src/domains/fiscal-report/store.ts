import { defineStore } from 'pinia';
import { toApiErrorMessage } from '@/lib/errors';
import type { OwnershipRead } from '@/domains/people/types';
import {
  fiscalReportApi,
  type BrokerCredential,
  type BrokerCsvFileType,
  type BrokerCsvImportResponse,
  type BrokerName,
  type BrokerSyncStatusResponse,
  type BrokerSyncTriggerResponse,
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

    loadingCredentials: false as boolean,
    loadingReport: false as boolean,
    syncingByCredential: {} as Record<number, boolean>,
    deletingByCredential: {} as Record<number, boolean>,
    creatingCredential: false as boolean,
    importingCsv: false as boolean,

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

    async initializeLanding() {
      this.clearMessages();
      try {
        await this.fetchOwnerships();
      } catch (error) {
        this.landingError = toApiErrorMessage(error);
      }
      await this.fetchCredentials();
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
        await this.fetchCredentials();
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
      } catch (error) {
        this.reportError = toApiErrorMessage(error);
      } finally {
        this.loadingReport = false;
      }
    },
  },
});
