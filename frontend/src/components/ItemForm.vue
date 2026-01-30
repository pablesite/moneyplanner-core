<script setup lang="ts">
import { computed, reactive } from "vue";

type Ownership = {
  id: number;
  kind: "individual" | "shared";
  member: { id: number; name: string; role: "adult" | "child" } | null;
  splits: { member: { id: number; name: string; role: "adult" | "child" }; percent: string }[];
  notes: string;
};

type Props = {
  title: string;
  categories: { value: string; label: string }[];
  ownerships: Ownership[];
  onSubmit: (payload: any) => Promise<void>;
};

const props = defineProps<Props>();

const currencies = [
  { value: "EUR", label: "EUR" },
  { value: "USD", label: "USD" },
  { value: "BTC", label: "BTC" },
  { value: "ETH", label: "ETH" },
];

const ownershipLabel = (o: Ownership) => {
  if (o.kind === "individual") {
    return o.member ? `Individual · ${o.member.name}` : "Individual";
  }
  const parts = (o.splits || []).map((s) => `${s.member.name} ${s.percent}%`);
  return `Compartido · ${parts.join(" · ") || "sin splits"}`;
};

const ownershipOptions = computed(() => {
  return [
    { value: null, label: "— Sin asignar —" },
    ...(props.ownerships || []).map((o) => ({ value: o.id, label: ownershipLabel(o) })),
  ];
});

/** -------------------------
 * Amount handling
 * - Accept thousands separators (1.234,56 or 1,234.56)
 * - Normalize to dot decimal for API
 * - Limit decimals by currency
 * ------------------------- */
const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};

const form = reactive({
  name: "",
  category: "",
  amount: "",
  notes: "",
  currency: "EUR",
  tracking_mode: "manual",
  is_active: true,
  ownership_id: null as number | null,
});

const maxDecimals = computed(() => decimalsByCurrency[form.currency] ?? 2);

function normalizeLooseNumber(raw: unknown) {
  // Allow only digits and separators, remove spaces (including NBSP)
  let s = String(raw ?? "").trim().replace(/\s/g, "");
  s = s.replace(/[^\d.,]/g, "");
  return s;
}

function sanitizeAmount(raw: unknown, decimals: number) {
  let s = normalizeLooseNumber(raw);

  if (!s) return { value: "", error: "" };

  // If contains both ',' and '.', assume last separator is decimal and the other is thousands
  const lastComma = s.lastIndexOf(",");
  const lastDot = s.lastIndexOf(".");
  if (lastComma !== -1 && lastDot !== -1) {
    const decimalSep = lastComma > lastDot ? "," : ".";
    const thousandSep = decimalSep === "," ? "." : ",";
    s = s.split(thousandSep).join(""); // remove thousand separators
    s = s.replace(decimalSep, "."); // normalize decimal to dot
  } else {
    // Only comma -> decimal comma
    s = s.replace(/,/g, ".");
  }

  // More than one dot => invalid
  if ((s.match(/\./g) || []).length > 1) return { value: "", error: "Importe inválido" };

  // Limit decimals
  const [intPart, decPart = ""] = s.split(".");
  const limitedDec = decPart.slice(0, decimals);
  const normalized = decPart.length ? `${intPart}.${limitedDec}` : intPart;

  // Avoid weird states
  if (!normalized || normalized === ".") return { value: "", error: "" };

  // If starts with dot, prefix 0
  const finalValue = normalized.startsWith(".") ? `0${normalized}` : normalized;

  // Validate numeric
  if (Number.isNaN(Number(finalValue))) return { value: "", error: "Importe inválido" };

  // Block negatives (we removed '-' already, but keep for safety)
  if (finalValue.includes("-")) return { value: "", error: "No se permiten importes negativos" };

  return { value: finalValue, error: "" };
}

const amountError = computed(() => {
  const { error } = sanitizeAmount(form.amount, maxDecimals.value);
  return error;
});

const amountHint = computed(() => {
  return form.currency === "BTC" || form.currency === "ETH"
    ? `Hasta ${maxDecimals.value} decimales (ej: 0.00123456)`
    : `Hasta ${maxDecimals.value} decimales`;
});

async function submit() {
  if (!form.name || !form.category || !form.amount) return;

  const { value: normalizedAmount, error } = sanitizeAmount(form.amount, maxDecimals.value);
  if (!normalizedAmount || error) return;

  await props.onSubmit({
    name: form.name,
    category: form.category,
    amount: normalizedAmount, // normalized dot-decimal string
    notes: form.notes,
    currency: form.currency,
    tracking_mode: form.tracking_mode,
    is_active: form.is_active,
    ownership_id: form.ownership_id,
  });

  form.name = "";
  form.category = "";
  form.amount = "";
  form.notes = "";
  form.ownership_id = null;
}
</script>

<template>
  <div class="card" style="margin-bottom: 12px;">
    <h3 class="h3">{{ title }}</h3>

    <div class="form-grid">
      <input v-model="form.name" placeholder="Nombre" class="input" />

      <select v-model="form.category" class="select">
        <option value="" disabled>Selecciona categoría</option>
        <option v-for="c in categories" :key="c.value" :value="c.value">
          {{ c.label }}
        </option>
      </select>

      <select v-model="form.currency" class="select">
        <option v-for="c in currencies" :key="c.value" :value="c.value">
          {{ c.label }}
        </option>
      </select>

      <input
        v-model="form.amount"
        inputmode="decimal"
        placeholder="Importe"
        class="input"
      />

      <div style="grid-column: 1 / -1; font-size: 12px; opacity: 0.75;">
        {{ amountHint }}
      </div>

      <div v-if="amountError" style="grid-column: 1 / -1; font-size: 12px; color: #b00020;">
        {{ amountError }}
      </div>

      <!-- Ownership -->
      <select v-model="form.ownership_id" class="select">
        <option v-for="o in ownershipOptions" :key="String(o.value)" :value="o.value">
          {{ o.label }}
        </option>
      </select>

      <textarea v-model="form.notes" placeholder="Notas" rows="2" class="textarea"></textarea>

      <button @click="submit" class="btn btn-primary" :disabled="!!amountError">
        Crear
      </button>
    </div>
  </div>
</template>
