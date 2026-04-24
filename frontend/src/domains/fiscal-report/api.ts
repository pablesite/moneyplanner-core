import { coreApi } from '@/lib/api';
import type { OwnershipRead } from '@/domains/people/types';

export type BrokerName = 'pionex' | 'binance';

export type BrokerCsvFileType =
  | 'pionex_trading'
  | 'pionex_futures'
  | 'pionex_staking'
  | 'pionex_others'
  | 'pionex_dust'
  | 'binance_transactions'
  | 'binance_convert'
  | 'binance_recurring';

export type BrokerCredential = {
  id: number;
  broker: BrokerName;
  label: string;
  ownership_id: number;
  api_key_masked: string;
  has_secret: boolean;
  last_sync_at: string | null;
  created_at: string;
  updated_at: string;
};

export type BrokerSyncStats = {
  new_trades: number;
  updated_trades: number;
  new_bot_results: number;
  updated_bot_results: number;
  new_income_events: number;
  updated_income_events: number;
  gaps: { source: string; reason: string; code?: string }[];
};

export type BrokerSyncTriggerResponse = {
  year: number;
  stats: BrokerSyncStats;
};

export type BrokerSyncStatusResponse = {
  last_sync: string | null;
  stats: Partial<BrokerSyncStats>;
  gaps_detected: boolean;
  gaps: { source: string; reason: string; code?: string }[];
};

export type BrokerCsvImportResponse = {
  broker: BrokerName;
  file_type: BrokerCsvFileType;
  created: number;
  updated: number;
  skipped: number;
};

export type FiscalCapitalMobiliarioRow = {
  fuente: string;
  asset: string;
  importe_eur: number;
  casilla: string;
};

export type FiscalBotResultRow = {
  bot_label: string;
  bot_type: string;
  periodo: string;
  ganancia_neta_eur: number;
  casilla: string;
  aviso_simplificacion: boolean;
};

export type FiscalFuturesRow = {
  position_id: string;
  symbol: string;
  side: string;
  open_time: string;
  close_time: string;
  net_pnl_eur: number;
  casilla: string;
  aviso_derivados: boolean;
};

export type FiscalTradeLotRow = {
  buy_date: string | null;
  sell_date: string;
  exchange_buy: string;
  exchange_sell: string;
  symbol: string;
  quantity: number;
  cost_eur: number;
  proceeds_eur: number;
  gain_loss_eur: number;
  hold_days: number;
  casilla: string;
};

export type FiscalTradeSectionRow = {
  denominacion: string;
  casilla: string;
  valor_transmision_eur: number;
  valor_adquisicion_eur: number;
  ganancia_eur: number;
  perdida_eur: number;
  lotes: FiscalTradeLotRow[];
};

export type FiscalDataSources = {
  pionex_api: boolean;
  pionex_csv_fallback: string[];
  binance_api: boolean;
  binance_csv_fallback: string[];
};

export type FiscalResumen = {
  total_capital_mobiliario_eur: number;
  total_ganancias_eur: number;
  total_perdidas_eur: number;
  neto_ganancias_perdidas_eur: number;
};

export type FiscalReportPayload = {
  fiscal_year: number;
  capital_mobiliario: FiscalCapitalMobiliarioRow[];
  ganancias_perdidas_bots: FiscalBotResultRow[];
  ganancias_perdidas_futuros: FiscalFuturesRow[];
  ganancias_perdidas_trades: FiscalTradeSectionRow[];
  avisos: string[];
  data_sources: FiscalDataSources;
  resumen: FiscalResumen;
};

export const fiscalReportApi = {
  getOwnerships() {
    return coreApi.get<OwnershipRead[]>('/api/ownerships/');
  },
  getCredentials() {
    return coreApi.get<BrokerCredential[]>('/api/v1/broker/credentials/');
  },
  createCredential(payload: {
    broker: BrokerName;
    label: string;
    ownership_id: number;
    api_key: string;
    api_secret: string;
  }) {
    return coreApi.post<BrokerCredential>('/api/v1/broker/credentials/', payload);
  },
  deleteCredential(id: number) {
    return coreApi.delete<void>(`/api/v1/broker/credentials/${id}/`);
  },
  triggerSync(credentialId: number, year: number) {
    return coreApi.post<BrokerSyncTriggerResponse>(`/api/v1/broker/sync/${credentialId}/`, {
      year,
    });
  },
  getSyncStatus(credentialId: number) {
    return coreApi.get<BrokerSyncStatusResponse>(`/api/v1/broker/sync/${credentialId}/status/`);
  },
  importCsv(payload: { broker: BrokerName; file_type: BrokerCsvFileType; file: File }) {
    const formData = new FormData();
    formData.append('broker', payload.broker);
    formData.append('file_type', payload.file_type);
    formData.append('file', payload.file);
    return coreApi.post<BrokerCsvImportResponse>('/api/v1/broker/csv-import/', formData);
  },
  getFiscalReport(params: { year: number; ownership_id?: number | null }) {
    return coreApi.get<FiscalReportPayload>('/api/v1/broker/fiscal-report/', {
      params: {
        year: params.year,
        ...(params.ownership_id ? { ownership_id: params.ownership_id } : {}),
      },
    });
  },
};
