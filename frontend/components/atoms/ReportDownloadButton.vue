<script setup>
// Botó partit de descàrrega d'informes: acció principal (Excel) + segment quadrat per a la versió PDF.
// Colors alineats amb .button-secondary; el segment PDF és un to més fosc del mateix verd.
const props = defineProps({
  label: { type: String, required: true },
  showPdf: { type: Boolean, default: false },
  pdfTitle: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(['download']);
</script>

<template>
  <!-- Amplada fixa: tots els botons de la llista queden alineats, amb o sense PDF -->
  <div class="inline-flex w-52 shrink-0 items-stretch rounded shadow-sm">
    <button
      type="button"
      class="flex flex-1 min-w-0 items-center justify-center gap-2 px-3 py-2 font-medium text-white bg-green-500 enabled:hover:bg-green-600 disabled:opacity-75 transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-sky-500"
      :class="props.showPdf ? 'rounded-l' : 'rounded'"
      :title="props.label"
      :disabled="props.disabled"
      @click="emit('download', 'xlsx')"
    >
      <Icon name="fa6-solid:file-excel" class="shrink-0" />
      <span class="truncate">{{ props.label }}</span>
    </button>
    <button
      v-if="props.showPdf"
      type="button"
      class="flex w-10 shrink-0 items-center justify-center rounded-r border-l border-white/30 bg-green-600 text-white enabled:hover:bg-green-700 disabled:opacity-75 transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-sky-500"
      :title="props.pdfTitle"
      :aria-label="props.pdfTitle"
      :disabled="props.disabled"
      @click="emit('download', 'pdf')"
    >
      <Icon name="fa6-solid:file-pdf" />
    </button>
  </div>
</template>
