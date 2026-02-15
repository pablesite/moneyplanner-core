type SummaryLike = {
  base_currency?: string;
  assets_by_category?: Record<string, string>;
  liabilities_by_category?: Record<string, string>;
};

export type ByCategoryChart = {
  unit: string;
  keys: string[];
  assets: number[];
  liabilities: number[];
};

function normalizeNumberInput(raw: unknown) {
  return String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
}

function toNumber(v: unknown) {
  const n = Number(normalizeNumberInput(v));
  return Number.isFinite(n) ? n : 0;
}

export function buildByCategoryChart(summary: SummaryLike | null, baseCurrency: string | null): ByCategoryChart {
  const unit = baseCurrency ?? summary?.base_currency ?? 'EUR';
  const assetsBy = summary?.assets_by_category ?? {};
  const liabsBy = summary?.liabilities_by_category ?? {};
  const keys = Array.from(new Set<string>([...Object.keys(assetsBy), ...Object.keys(liabsBy)]));

  return {
    unit,
    keys,
    assets: keys.map((key) => Math.max(0, toNumber(assetsBy[key]))),
    liabilities: keys.map((key) => Math.max(0, toNumber(liabsBy[key]))),
  };
}
