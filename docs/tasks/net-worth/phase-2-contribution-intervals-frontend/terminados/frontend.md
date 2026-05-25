# Task: Contribution Intervals — Frontend

## Title
Periodic contribution intervals in investment assets (frontend)

## Context
After completing Phase 1 (backend), the `Asset` model exposes `contribution_intervals` as a nested list. This phase replaces the flat fields of the investment form (`monthly_contribution_amount`, `investment_contribution_frequency`, `investment_contribution_currency`, `expected_end_date`, selector `investment_contribution_mode`) with an inline interval manager in the asset creation/editing modal.

**Prerrequisito:** Phase 1 completada y desplegada en Core.

## Area
`frontend`

## Stack
`core` + espejado en `external`

## Scope

### En scope
1. Nuevo tipo `ContributionInterval` en `models.ts`
2. Gestor de intervalos inline en `ItemForm.vue` (Core)
3. Removal of the 4 flat investment fields from the form
4. Update composable `composables.ts` to map `contribution_intervals` in edit mode
5. Espejado de todos los cambios en `frontend/src/` (Core)

### Fuera de scope
- Cambios en backend (Phase 1)
- Overlap validation on server (done in backend; frontend only shows response error)
- Display of intervals in the estate view (create/edit form only)

## Plan

### 1. Tipos (`core/frontend/src/domains/net-worth/models.ts`)

```typescript
export type ContributionInterval = {
  id?: number;
  start_date: string;
  end_date: string | null;
  amount: string;
  frequency: 'monthly' | 'weekly';
  currency: string | null;
};

// En el tipo Asset, añadir:
contribution_intervals?: ContributionInterval[];
```

### 2. Composable (`core/frontend/src/domains/net-worth/composables.ts`)

En `buildEditInvestmentFields()` (o equivalente):
- Map `asset.contribution_intervals ?? []` to the local state of the form
- Remove extraction of `investment_contribution_mode`, `monthly_contribution_amount`, etc. of the asset for the init of the contributions section

### 3. Formulario `ItemForm.vue` (`core/frontend/src/domains/net-worth/components/ItemForm.vue`)

**Delete** (from investments section, only visible when `category === 'investments'`):
- Selector `investment_contribution_mode` (one_time / periodic_contribution)
- Campo `monthly_contribution_amount`
- Campo `investment_contribution_frequency`
- Campo `investment_contribution_currency`
- Campo `expected_end_date`
- Computed `showInvestmentPeriodicFields`

**Add** instead:

Home state:
```typescript
const contributionIntervals = ref<ContributionIntervalDraft[]>([])

type ContributionIntervalDraft = {
  _key: string           // clave local para v-for (uuid o index)
  id?: number
  start_date: string
  end_date: string
  amount: string
  frequency: 'monthly' | 'weekly'
  currency: string
}
```

Funciones:
```typescript
function addInterval(): void {
  contributionIntervals.value.push({
    _key: crypto.randomUUID(),
    start_date: '',
    end_date: '',
    amount: '',
    frequency: 'monthly',
    currency: form.currency || 'EUR',
  })
}

function removeInterval(key: string): void {
  contributionIntervals.value = contributionIntervals.value.filter(i => i._key !== key)
}
```

Al inicializar en modo edit:
```typescript
contributionIntervals.value = (asset.contribution_intervals ?? []).map(i => ({
  _key: String(i.id ?? crypto.randomUUID()),
  id: i.id,
  start_date: i.start_date,
  end_date: i.end_date ?? '',
  amount: i.amount,
  frequency: i.frequency,
  currency: i.currency ?? form.currency ?? 'EUR',
}))
```

Al hacer submit, incluir en el payload:
```typescript
contribution_intervals: contributionIntervals.value
  .filter(i => i.start_date && i.amount)
  .map(i => ({
    ...(i.id ? { id: i.id } : {}),
    start_date: i.start_date,
    end_date: i.end_date || null,
    amount: i.amount,
    frequency: i.frequency,
    currency: i.currency || null,
  }))
```

**UI del gestor de intervalos** (visible solo cuando `category === 'investments'`):

```vue
<div v-if="isInvestmentCategory" class="grid gap-2">
  <div class="text-sm font-medium text-white/70">Aportaciones periódicas</div>

  <div
    v-for="interval in contributionIntervals"
    :key="interval._key"
    class="grid grid-cols-[1fr_1fr_1fr_auto_auto_auto] gap-2 items-end rounded-xl border border-white/10 bg-white/[0.03] p-3"
  >
    <!-- Desde -->
    <div>
      <label class="text-xs text-white/50">Desde</label>
      <input type="date" v-model="interval.start_date" class="form-input" />
    </div>
    <!-- Hasta (opcional) -->
    <div>
      <label class="text-xs text-white/50">Hasta (opcional)</label>
      <input type="date" v-model="interval.end_date" class="form-input" />
    </div>
    <!-- Cuota -->
    <div>
      <label class="text-xs text-white/50">Cuota</label>
      <input type="text" inputmode="decimal" v-model="interval.amount" class="form-input" />
    </div>
    <!-- Moneda -->
    <div>
      <label class="text-xs text-white/50">Moneda</label>
      <select v-model="interval.currency" class="form-select">
        <option v-for="c in currencyOptions" :key="c" :value="c">{{ c }}</option>
      </select>
    </div>
    <!-- Frecuencia -->
    <div>
      <label class="text-xs text-white/50">Frecuencia</label>
      <select v-model="interval.frequency" class="form-select">
        <option value="monthly">Mensual</option>
        <option value="weekly">Semanal</option>
      </select>
    </div>
    <!-- Eliminar -->
    <button type="button" class="btn btn-ghost btn-sm self-end" @click="removeInterval(interval._key)">×</button>
  </div>

  <button type="button" class="btn btn-ghost btn-sm self-start" @click="addInterval">
    + Añadir intervalo
  </button>

  <p v-if="!contributionIntervals.length" class="text-xs text-white/40">
    Sin intervalos = activo sin aportaciones periódicas previstas.
  </p>
</div>
```

**Clases CSS**: usar las mismas que el resto del formulario. No introducir nuevas clases.

### 4. Espejado Core

Aplicar exactamente los mismos cambios en:
- `frontend/src/domains/net-worth/models.ts`
- `frontend/src/domains/net-worth/components/ItemForm.vue`
- `frontend/src/domains/net-worth/composables.ts` (si existe el equivalente)

## Validation

```bash
# Typecheck
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose exec frontend npm run typecheck

# Lint
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose exec frontend npm run lint

# Prueba manual (con backend Phase 1 activo):
# 1. Crear activo de inversión sin intervalos → guardar → sin gastos generados en presupuesto
# 2. Crear activo con 2 intervalos no solapados → guardar → modal de revisión de gastos
# 3. Crear activo con intervalos solapados → API devuelve 400 → error visible en formulario
# 4. Editar activo existente (migrado) → intervalos pre-populados desde datos legacy
# 5. Eliminar un intervalo y guardar → modal de revisión muestra cambio
```

## Required Documentation Updates

- [ ] `core/docs/project-status.md` — update task status to ✅ and move spec to `terminados/`
- [ ] `core/docs/frontend/net-worth-ux-notes.md` — documentar el gestor de intervalos si hay notas UX relevantes

## Risks

- **Data loss in edit mode:** if `buildEditInvestmentFields` does not correctly map `contribution_intervals`, existing intervals are lost when saving. Verify with an asset that has real intervals (migrated from Phase 1).
- **Empty payload vs. null:** ensure that sending `contribution_intervals: []` clears all existing ranges (`set` pattern in backend). Test it explicitly.
- **Core Compatibility:** If the Core frontend consumes a cached version of type `Asset` without `contribution_intervals`, the typecheck will fail. Keep the local type contract updated.

## Completion Criteria

- [ ] Flat inversion fields (`monthly_contribution_amount`, etc.) removed from the form
- [ ] Functional interval manager: add, edit, delete without saving
- [ ] Al guardar con intervalos: payload incluye `contribution_intervals` correctamente formateado
- [ ] When editing active with existing intervals: pre-population correct
- [ ] Generated expense review modal appears after creating/editing periodic asset (feature implemented in previous session)
- [ ] Typecheck y lint sin errores en Core
- [ ] Espejado en Core verificado
- [ ] Spec movida a `terminados/`
- [ ] Commit Conventional: `feat(net-worth): interval-based investment contribution form`
