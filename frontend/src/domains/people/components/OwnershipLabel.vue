<script setup lang="ts">
type MemberMini = { id: number; name: string; role: 'adult' | 'child' };
type Split = { member: MemberMini; percent: string };

const props = defineProps<{
  kind: 'individual' | 'shared';
  member: MemberMini | null;
  splits: Split[];
}>();

function fmtPercent(p: string) {
  const n = Number(String(p).replace(',', '.'));
  if (Number.isNaN(n)) return p;
  return (
    new Intl.NumberFormat('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(
      n,
    ) + '%'
  );
}
</script>

<template>
  <div>
    <template v-if="props.kind === 'individual'">
      <span class="subtle">Individual</span>
      <span style="margin-left: 8px">{{ props.member?.name ?? '-' }}</span>
    </template>

    <template v-else>
      <span class="subtle">Compartido</span>
      <span style="margin-left: 8px">
        <span v-for="(s, i) in props.splits" :key="s.member.id">
          {{ s.member.name }} {{ fmtPercent(s.percent)
          }}<span v-if="i < props.splits.length - 1"> · </span>
        </span>
      </span>
    </template>
  </div>
</template>
