<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  report: {
    type: Object,
    required: true
  },
  queueItem: {
    type: Object,
    default: null
  },
  selectedBilling: {
    type: Object,
    default: null
  }
});

const emit = defineEmits([
  'download',
  'select-billing',
  'unselect-billing'
]);

const { t } = useI18n();

const form = ref({
  date_range: null,
  billing_id: null,
  include_preinvoices: false,
});

watch(() => props.selectedBilling, (newBilling) => {
  form.value.billing_id = newBilling ? newBilling.id : null;
}, { immediate: true });

const onDownload = () => {
  emit('download', props.report, form.value);
};
</script>

<template>
  <div class="space-y-4 bg-slate-50 p-5 rounded-lg border border-slate-200 mt-2 shadow-inner">
    <div class="bg-blue-50 border-l-4 border-blue-500 p-3 rounded mb-2">
      <p class="text-xs text-blue-800 font-semibold uppercase tracking-wider mb-1">Configuració Personalitzada - Tarifes</p>
      <p class="text-xs text-blue-700">Aquest informe genera el resum dels imports facturats desglossats per tarifes.</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- Date range -->
      <div class="flex flex-col">
        <label class="text-sm font-semibold text-slate-700 mb-1">
          {{ t('reports_block.select_dates') || 'Selecciona dates' }}
        </label>
        <Datepicker
          v-model="form.date_range"
          range
          :enableTimePicker="false"
          :format="'dd-MM-yyyy'"
          class="custom-datepicker"
          placeholder="Selecciona les dates"
        />
      </div>
    </div>

    <!-- Billing selector -->
    <div class="flex flex-col">
      <label class="text-sm font-semibold text-slate-700 mb-1">
        {{ t('reports_block.billing') || 'Facturació' }}
      </label>
      <div class="flex items-center gap-2">
        <ButtonOutline type="button" @click="emit('select-billing')">
          {{ t('reports_block.select_billing') }}
        </ButtonOutline>
        <div v-if="selectedBilling" class="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-300 rounded text-xs font-medium text-green-800">
          <span>{{ selectedBilling.name }} ({{ selectedBilling.token }})</span>
          <button type="button" @click="emit('unselect-billing')" class="text-red-500 hover:text-red-700 font-bold ml-1">
            &times;
          </button>
        </div>
        <span v-else class="text-xs text-slate-400 italic">Cap facturació seleccionada</span>
      </div>
    </div>

    <!-- Checkboxes -->
    <div class="flex flex-wrap gap-5 mt-2">
      <div class="flex items-center gap-2 bg-white px-3 py-2 rounded border border-slate-100 shadow-sm">
        <input
          v-model="form.include_preinvoices"
          type="checkbox"
          id="rates_include_preinvoices"
          class="checkbox rounded border-slate-300 text-sky-600 focus:ring-sky-500"
        />
        <label for="rates_include_preinvoices" class="text-sm font-medium text-slate-700 cursor-pointer">
          {{ t('reports_block.include_preinvoices') }}
        </label>
      </div>
    </div>

    <!-- Action button / badge -->
    <div class="pt-3 flex flex-col items-end gap-2 border-t border-slate-200/60 w-full">
      <template v-if="props.queueItem && props.queueItem.status === 'pending'">
        <div class="flex items-center gap-2">
          <Icon name="mdi:loading" class="animate-spin text-sky-500 text-lg" />
          <span class="text-xs text-slate-500">Esperant el seu torn a la cua...</span>
        </div>
      </template>
      <template v-else-if="props.queueItem && props.queueItem.status === 'running'">
        <div class="w-full">
          <div class="flex justify-between items-center text-xs text-sky-700 mb-1 px-1">
            <span class="font-medium flex items-center gap-1">
              <Icon name="mdi:loading" class="animate-spin text-sky-500" />
              Generant informe...
            </span>
            <span>{{ props.queueItem.percent || 0 }}% ({{ props.queueItem.processed_items || 0 }} / {{ props.queueItem.total_items || 0 }})</span>
          </div>
          <div class="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
            <div class="bg-sky-500 h-full transition-all duration-300 ease-out" :style="{ width: (props.queueItem.percent || 0) + '%' }"></div>
          </div>
        </div>
      </template>
      <template v-else>
        <button
          type="button"
          class="button-secondary flex items-center gap-2 shadow-sm font-medium"
          @click="onDownload"
        >
          <Icon name="fa6-solid:file-excel" />
          <span>{{ report.download_button_name || t('common.download') }}</span>
        </button>
      </template>
    </div>
  </div>
</template>
