import { computed, type ComputedRef, type Ref } from 'vue';

type PositionType = 'asset' | 'liability' | null;

type AssetValuation = {
  id: number;
  valuation_date: string;
  value: string;
  source: string;
  note?: string | null;
};

type InvestmentEvent = {
  id: number;
  event_date: string;
  event_type: string;
  amount: string;
  is_reinvested?: boolean;
  note?: string | null;
};

type LiquidityEvent = {
  id: number;
  event_date: string;
  event_type: string;
  amount: string;
  note?: string | null;
};

type LiabilityValuation = {
  id: number;
  valuation_date: string;
  value: string;
  source: string;
  note?: string | null;
};

type LiabilityEvent = {
  id: number;
  event_date: string;
  event_type: string;
  amount: string;
  note?: string | null;
};

export type PositionActivityRow = {
  id: string;
  date: string;
  label: string;
  kind: 'valuation' | 'event';
  amount: number;
  meta: string;
  note: string;
};

export function useNetWorthPositionActivity(params: {
  selectedPositionType: ComputedRef<PositionType> | Ref<PositionType>;
  assetValuations: ComputedRef<AssetValuation[]>;
  investmentEvents: ComputedRef<InvestmentEvent[]>;
  liquidityEvents: ComputedRef<LiquidityEvent[]>;
  liabilityValuations: ComputedRef<LiabilityValuation[]>;
  liabilityEvents: ComputedRef<LiabilityEvent[]>;
  toNumber: (raw: unknown) => number;
}) {
  const positionActivityRows = computed<PositionActivityRow[]>(() => {
    if (params.selectedPositionType.value === 'asset') {
      const valuations = params.assetValuations.value.map((row) => ({
        id: `valuation-${row.id}`,
        date: row.valuation_date,
        label: 'Checkpoint',
        kind: 'valuation' as const,
        amount: params.toNumber(row.value),
        meta: row.source,
        note: row.note ?? '',
      }));
      const investmentEvents = params.investmentEvents.value.map((row) => ({
        id: `investment-${row.id}`,
        date: row.event_date,
        label: row.event_type,
        kind: 'event' as const,
        amount: params.toNumber(row.amount),
        meta:
          row.event_type === 'passive_income' && row.is_reinvested === false
            ? 'passive_income · no reinvertido'
            : row.event_type,
        note: row.note ?? '',
      }));
      const liquidityEvents = params.liquidityEvents.value.map((row) => ({
        id: `liquidity-${row.id}`,
        date: row.event_date,
        label: row.event_type,
        kind: 'event' as const,
        amount: params.toNumber(row.amount),
        meta: row.event_type,
        note: row.note ?? '',
      }));
      return [...valuations, ...investmentEvents, ...liquidityEvents].sort((a, b) =>
        b.date.localeCompare(a.date),
      );
    }

    const valuations = params.liabilityValuations.value.map((row) => ({
      id: `valuation-${row.id}`,
      date: row.valuation_date,
      label: 'Checkpoint',
      kind: 'valuation' as const,
      amount: params.toNumber(row.value),
      meta: row.source,
      note: row.note ?? '',
    }));
    const events = params.liabilityEvents.value.map((row) => ({
      id: `liability-event-${row.id}`,
      date: row.event_date,
      label: row.event_type,
      kind: 'event' as const,
      amount: params.toNumber(row.amount),
      meta: row.event_type,
      note: row.note ?? '',
    }));
    return [...valuations, ...events].sort((a, b) => b.date.localeCompare(a.date));
  });

  return {
    positionActivityRows,
  };
}
