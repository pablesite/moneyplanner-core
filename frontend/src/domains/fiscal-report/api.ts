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
  gaps: BrokerSyncGap[];
};

export type BrokerSyncTriggerResponse = {
  year: number;
  stats: BrokerSyncStats;
};

export type BrokerSyncStatusResponse = {
  last_sync: string | null;
  stats: Partial<BrokerSyncStats>;
  gaps_detected: boolean;
  gaps: BrokerSyncGap[];
};

export type BrokerCsvImportResponse = {
  broker: BrokerName;
  credential_id: number | null;
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

export type BrokerSyncGap = {
  source: string;
  reason: string;
  code?: string;
  asset?: string;
  expected?: number;
  actual?: number;
  diff?: number;
};

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type BrokerSyncRunStatus = 'running' | 'ok' | 'partial' | 'failed';

export type SyncRunSummary = {
  id: number;
  credential_id: number;
  year: number;
  status: BrokerSyncRunStatus;
  started_at: string;
  finished_at: string | null;
  stats: Partial<BrokerSyncStats>;
  gaps: BrokerSyncGap[];
  new_trade_ids: number[];
  updated_trade_ids: number[];
  new_income_event_ids: number[];
  updated_income_event_ids: number[];
  new_bot_result_ids: number[];
  updated_bot_result_ids: number[];
};

export type BrokerTradeDrilldownRow = {
  id: number;
  credential_id: number;
  bot_id: string | null;
  source: string;
  trade_id: string;
  symbol: string;
  base_asset: string;
  quote_asset: string;
  side: 'buy' | 'sell';
  price: string;
  price_eur: string | null;
  quantity: string;
  fee: string;
  fee_eur: string | null;
  fee_asset: string;
  tax_id: string;
  eur_rate_source: string;
  timestamp: string;
};

export type CsvTaxIdGroup = {
  tax_id: string;
  count: number;
  symbols: string[];
  first_timestamp: string;
  last_timestamp: string;
};

export type IncomeEventDrilldownRow = {
  id: number;
  credential_id: number;
  source: string;
  income_type: string;
  asset: string;
  amount: string;
  timestamp: string;
  description: string;
};

export type BotResultDrilldownRow = {
  id: number;
  credential_id: number;
  bot_id: string;
  bot_type: string;
  label: string;
  base_asset: string;
  quote_asset: string;
  realized_profit: string;
  bot_profit_quote: string;
  grid_profit: string;
  total_profit_quote: string | null;
  total_fee_base: string;
  total_fee_quote: string;
  period_start: string;
  period_end: string;
  synced_at: string;
  fill_count: number;
};

export type BotResultDetail = BotResultDrilldownRow & {
  fills: PaginatedResponse<BrokerTradeDrilldownRow>;
};

export type BalanceReconciliationEntry = {
  asset: string;
  expected: number;
  actual: number;
  diff: number;
  status: 'ok' | 'mismatch';
  sync_run_id: number;
  sync_run_finished_at: string | null;
};

export type FiscalMatchedLotRow = {
  buy_trade_id: number | null;
  manual_cost_basis_id: number | null;
  deposit_withdrawal_id?: number | null;
  buy_date: string | null;
  buy_exchange: string | null;
  buy_symbol: string | null;
  quantity_consumed: number;
  unit_price_eur: number;
  cost_eur: number;
  fee_eur_allocated: number;
  gain_loss_eur: number;
  hold_days: number;
  has_complete_cost_basis?: boolean;
};

export type GapReason = 'pre_period_buy' | 'missing_data' | 'balance_transfer_in';

export type FifoSaleMatch = {
  sell_trade_id: number;
  sell_date: string;
  sell_exchange: string;
  sell_symbol: string;
  quantity_sold: number;
  proceeds_eur: number;
  fee_eur: number;
  matched_lots: FiscalMatchedLotRow[];
  gap_quantity: number;
  gap_reason: GapReason | null;
};

export type FiscalTradeSectionRow = {
  denominacion: string;
  casilla: string;
  valor_transmision_eur: number;
  valor_adquisicion_eur: number;
  ganancia_eur: number;
  perdida_eur: number;
  has_pending_cost_basis?: boolean;
  sales: FifoSaleMatch[];
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
  schema_version?: number;
  fiscal_year: number;
  capital_mobiliario: FiscalCapitalMobiliarioRow[];
  ganancias_perdidas_bots: FiscalBotResultRow[];
  ganancias_perdidas_futuros: FiscalFuturesRow[];
  ganancias_perdidas_trades: FiscalTradeSectionRow[];
  avisos: string[];
  data_sources: FiscalDataSources;
  resumen: FiscalResumen;
};

export type SyncRunDetail = SyncRunSummary & {
  trades: PaginatedResponse<BrokerTradeDrilldownRow>;
  income_events: PaginatedResponse<IncomeEventDrilldownRow>;
  bot_results: PaginatedResponse<BotResultDrilldownRow>;
};

export type ManualCostBasisRow = {
  id: number;
  ownership_id: number;
  asset: string;
  quantity: string;
  quantity_remaining: string;
  acquired_at: string;
  cost_eur: string;
  exchange_origin: string;
  notes: string;
  created_at: string;
};

export type ManualCostBasisInput = {
  ownership_id?: number;
  asset: string;
  quantity: string;
  acquired_at: string;
  cost_eur: string;
  exchange_origin?: string;
  notes?: string;
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
  getSyncRuns(params: { credential?: number; year?: number; page?: number }) {
    return coreApi.get<PaginatedResponse<SyncRunSummary>>('/api/v1/broker/sync-runs/', {
      params: {
        ...(typeof params.credential === 'number' ? { credential: params.credential } : {}),
        ...(typeof params.year === 'number' ? { year: params.year } : {}),
        ...(typeof params.page === 'number' ? { page: params.page } : {}),
      },
    });
  },
  getSyncRun(syncRunId: number) {
    return coreApi.get<SyncRunDetail>(`/api/v1/broker/sync-runs/${syncRunId}/`);
  },
  getTrades(params: {
    credential?: number;
    year?: number;
    source?: string;
    symbol?: string;
    tax_id?: string;
    side?: 'buy' | 'sell';
    bot_id?: string;
    sync_run?: number;
    page?: number;
  }) {
    return coreApi.get<PaginatedResponse<BrokerTradeDrilldownRow>>('/api/v1/broker/trades/', {
      params,
    });
  },
  getIncomeEvents(params: {
    credential?: number;
    year?: number;
    source?: string;
    sync_run?: number;
    page?: number;
  }) {
    return coreApi.get<PaginatedResponse<IncomeEventDrilldownRow>>(
      '/api/v1/broker/income-events/',
      {
        params,
      },
    );
  },
  getBotResults(params: {
    credential?: number;
    year?: number;
    bot_id?: string;
    sync_run?: number;
    page?: number;
  }) {
    return coreApi.get<PaginatedResponse<BotResultDrilldownRow>>('/api/v1/broker/bot-results/', {
      params,
    });
  },
  getBotResult(botResultId: number, page?: number) {
    return coreApi.get<BotResultDetail>(`/api/v1/broker/bot-results/${botResultId}/`, {
      params: typeof page === 'number' ? { page } : undefined,
    });
  },
  importCsv(payload: {
    broker: BrokerName;
    credential_id?: number;
    file_type: BrokerCsvFileType;
    file: File;
  }) {
    const formData = new FormData();
    formData.append('broker', payload.broker);
    if (typeof payload.credential_id === 'number') {
      formData.append('credential_id', String(payload.credential_id));
    }
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
  getManualCostBasis(asset?: string) {
    return coreApi.get<PaginatedResponse<ManualCostBasisRow>>('/api/v1/broker/manual-cost-basis/', {
      params: asset ? { asset } : undefined,
    });
  },
  createManualCostBasis(payload: ManualCostBasisInput) {
    return coreApi.post<ManualCostBasisRow>('/api/v1/broker/manual-cost-basis/', payload);
  },
  deleteManualCostBasis(id: number) {
    return coreApi.delete<void>(`/api/v1/broker/manual-cost-basis/${id}/`);
  },
  downloadFiscalReportExport(params: {
    year: number;
    format: 'csv' | 'pdf';
    ownership_id?: number | null;
  }) {
    return coreApi.get<Blob>('/api/v1/broker/fiscal-report/export/', {
      params: {
        year: params.year,
        format: params.format,
        ...(params.ownership_id ? { ownership_id: params.ownership_id } : {}),
      },
      responseType: 'blob',
    });
  },
};
