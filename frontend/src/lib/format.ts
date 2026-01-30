type FormatOpts = {
  currency?: string;     // "EUR" | "USD" | "BTC" | "ETH" ...
  maxDecimals?: number;  // override manual
};

const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};

export function normalizeNumberInput(raw: unknown) {
  return String(raw ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
}

export function getMaxDecimals(currency?: string) {
  if (!currency) return 2;
  return decimalsByCurrency[currency] ?? 2;
}

// Para cantidades (con separador de miles, sin símbolo)
export function formatAmount(value: unknown, opts: FormatOpts = {}) {
  const s = normalizeNumberInput(value);
  const n = Number(s);
  if (Number.isNaN(n)) return String(value ?? "");

  const max = opts.maxDecimals ?? getMaxDecimals(opts.currency);

  return new Intl.NumberFormat("es-ES", {
    useGrouping: true,
    minimumFractionDigits: 0,
    maximumFractionDigits: max,
  }).format(n);
}

// Para dinero fiat con símbolo opcional (si lo quieres)
export function formatMoney(value: unknown, currency: "EUR" | "USD" = "EUR") {
  const s = normalizeNumberInput(value);
  const n = Number(s);
  if (Number.isNaN(n)) return String(value ?? "");

  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency,
    currencyDisplay: "symbol",
    useGrouping: true,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}
