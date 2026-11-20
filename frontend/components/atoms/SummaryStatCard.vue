<script setup>
// Cel·la d'una franja de resum: etiqueta petita a dalt i número a sota.
// Va dins d'un contenidor `flex divide-x divide-slate-200` (rounded + border), que dibuixa
// les línies divisòries. Totes les cel·les del contenidor tenen la mateixa amplada.
// Si és `clickable`, es pinta com un botó amb una fletxa dins d'un cercle a la dreta i emet `click`.
defineProps({
  value: {
    type: [String, Number],
    default: 0
  },
  label: {
    type: String,
    required: true
  },
  clickable: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  }
});

defineEmits(['click']);
</script>

<template>
  <button v-if="clickable" type="button" :title="title || label" @click="$emit('click')"
    class="group flex min-w-0 flex-1 items-center gap-2 bg-white px-4 py-3 text-left transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-slate-400">
    <div class="min-w-0 flex-1">
      <div class="truncate text-xs font-medium text-slate-500">{{ label }}</div>
      <div class="truncate text-2xl font-semibold leading-tight tabular-nums text-slate-800">{{ value }}</div>
    </div>
    <span
      class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-400 transition-colors group-hover:bg-slate-200 group-hover:text-slate-600">
      <Icon name="fa6-solid:chevron-right" class="text-[10px]" />
    </span>
  </button>
  <div v-else :title="title || label" class="min-w-0 flex-1 bg-white px-4 py-3">
    <div class="truncate text-xs font-medium text-slate-500">{{ label }}</div>
    <div class="truncate text-2xl font-semibold leading-tight tabular-nums text-slate-800">{{ value }}</div>
  </div>
</template>
