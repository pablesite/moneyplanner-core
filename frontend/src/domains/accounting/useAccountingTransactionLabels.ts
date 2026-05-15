import type { ComputedRef } from 'vue';
import type {
  LedgerAccount,
  LedgerAccountBalanceSummaryItem,
  LedgerTransaction,
} from '@/domains/accounting/models';
import type { OwnershipRead } from '@/domains/people/store';
import {
  type ActivityFilter,
  incomeCategories,
  expenseCategories,
  incomeSubcategories,
  expenseSubcategories,
} from '@/domains/accounting/useTransactionClassification';

function toNumber(raw: string): number {
  const parsed = Number(raw.replace(',', '.').trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

export function getInvestmentDirection(
  transaction: LedgerTransaction,
): 'inflow' | 'outflow' | 'reinvestment' {
  if (
    transaction.investment_direction === 'inflow' ||
    transaction.investment_direction === 'outflow' ||
    transaction.investment_direction === 'reinvestment'
  ) {
    return transaction.investment_direction;
  }
  const investmentEntry = transaction.entries.find((entry) => entry.asset_id != null);
  if (!investmentEntry) return 'inflow';
  return investmentEntry.side === 'credit' ? 'outflow' : 'inflow';
}

export function getTransactionActivityKind(
  transaction: LedgerTransaction,
): Exclude<ActivityFilter, 'all'> | 'other' {
  if (transaction.activity_kind === 'investment_purchase') return 'investment';
  if (transaction.activity_kind === 'income') return 'income';
  if (transaction.activity_kind === 'expense') return 'expense';
  if (transaction.activity_kind === 'transfer') return 'transfer';
  if (transaction.activity_kind === 'adjustment') return 'adjustment';
  if (transaction.activity_kind === 'debt_payment') return 'debt_payment';
  if (transaction.activity_kind === 'opening_balance') return 'opening_balance';
  if (transaction.activity_kind === 'revaluation') return 'revaluation';
  return 'other';
}

export function useAccountingTransactionLabels(
  accountMap: ComputedRef<Map<number, LedgerAccount>>,
  ownershipById: ComputedRef<Map<number, OwnershipRead>>,
  ownershipLabel: (ownership: OwnershipRead) => string,
) {
  function activityKindLabel(transaction: LedgerTransaction): string {
    const kind = getTransactionActivityKind(transaction);
    if (kind === 'income') return 'Ingreso';
    if (kind === 'expense') return 'Gasto';
    if (kind === 'transfer') return 'Transferencia';
    if (kind === 'adjustment') return 'Ajuste';
    if (kind === 'investment') {
      const direction = getInvestmentDirection(transaction);
      if (direction === 'outflow') return 'Retirada inversion';
      if (direction === 'reinvestment') return 'Reinversion';
      return 'Aporte inversion';
    }
    if (kind === 'debt_payment') return 'Pago deuda';
    if (kind === 'opening_balance') return 'Saldo inicial';
    if (kind === 'revaluation') return 'Revalorizacion';
    return 'Asiento';
  }

  function transactionOwnershipLabel(transaction: LedgerTransaction): string | null {
    if (transaction.ownership_id == null) return null;
    const ownership = ownershipById.value.get(transaction.ownership_id);
    if (!ownership) return `Titularidad #${transaction.ownership_id}`;
    return ownershipLabel(ownership);
  }

  function transactionClassificationLabel(transaction: LedgerTransaction): string | null {
    const classifiedEntry =
      transaction.entries.find(
        (entry) =>
          Boolean(entry.flow_family) &&
          Boolean(entry.category_key) &&
          Boolean(entry.subcategory_key),
      ) ?? null;
    if (!classifiedEntry) return null;
    const categoryKey = classifiedEntry.category_key;
    const subcategoryKey = classifiedEntry.subcategory_key;
    if (classifiedEntry.flow_family === 'income') {
      const categoryLabel =
        incomeCategories.find((row) => row.value === categoryKey)?.label ?? categoryKey;
      const subcategoryLabel =
        incomeSubcategories.find(
          (row) => row.category === categoryKey && row.value === subcategoryKey,
        )?.label ?? subcategoryKey;
      return `${categoryLabel} -> ${subcategoryLabel}`;
    }
    const categoryLabel =
      expenseCategories.find((row) => row.value === categoryKey)?.label ?? categoryKey;
    const subcategoryLabel =
      expenseSubcategories.find(
        (row) => row.category === categoryKey && row.value === subcategoryKey,
      )?.label ?? subcategoryKey;
    return `${categoryLabel} -> ${subcategoryLabel}`;
  }

  function transactionAccountTrailLabel(transaction: LedgerTransaction): string {
    const operationalEntries = transaction.entries.filter((entry) => {
      const account = accountMap.value.get(entry.account_id);
      return account?.account_type === 'asset' || account?.account_type === 'liability';
    });
    if (!operationalEntries.length) {
      return '-';
    }
    const uniqueDebit = Array.from(
      new Set(
        operationalEntries
          .filter((entry) => entry.side === 'debit')
          .map((entry) => entry.account_name.trim())
          .filter((name) => name.length > 0),
      ),
    );
    const uniqueCredit = Array.from(
      new Set(
        operationalEntries
          .filter((entry) => entry.side === 'credit')
          .map((entry) => entry.account_name.trim())
          .filter((name) => name.length > 0),
      ),
    );
    const kind = getTransactionActivityKind(transaction);
    if (kind === 'income') return uniqueDebit.join(' + ') || uniqueCredit.join(' + ') || '-';
    if (kind === 'expense') return uniqueCredit.join(' + ') || uniqueDebit.join(' + ') || '-';
    const from = uniqueCredit.join(' + ');
    const to = uniqueDebit.join(' + ');
    if (from && to) return `${from} -> ${to}`;
    return from || to || '-';
  }

  function liquidityBalanceDeltaTone(
    row: Pick<LedgerAccountBalanceSummaryItem, 'account_type'> & { period_net_change: string },
  ): 'positive' | 'negative' | 'neutral' {
    const value = toNumber(row.period_net_change);
    if (value === 0) return 'neutral';
    if (row.account_type === 'asset' || row.account_type === 'expense') {
      return value > 0 ? 'positive' : 'negative';
    }
    return value > 0 ? 'negative' : 'positive';
  }

  return {
    activityKindLabel,
    transactionOwnershipLabel,
    transactionClassificationLabel,
    transactionAccountTrailLabel,
    liquidityBalanceDeltaTone,
  };
}
