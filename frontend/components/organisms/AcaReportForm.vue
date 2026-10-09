<script setup>
import { computed } from 'vue';

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
  },
  globalDateRange: {
    type: Array,
    default: () => null
  },
  globalExploitationId: {
    type: [String, Number],
    default: 'all'
  },
  globalIncludePreinvoices: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits([
  'download'
]);

const { t } = useI18n();

const onDownload = (version) => {
  emit('download', props.report, {
    date_range: props.globalDateRange,
    exploitation_id: props.globalExploitationId,
    billing_id: props.selectedBilling ? props.selectedBilling.id : null,
    include_preinvoices: props.globalIncludePreinvoices,
    version
  });
};
</script>

<template>
  <div class="space-y-4 bg-slate-50 p-5 rounded-lg border border-slate-200 mt-2 shadow-inner animate-fadeIn">
    <div class="bg-sky-50 border-l-4 border-sky-500 p-3 rounded mb-2">
      <p class="text-xs text-sky-800 font-semibold uppercase tracking-wider mb-1">Informe Cànon de l'Aigua ACA</p>
      <p class="text-xs text-sky-700">Aquest informe es generarà utilitzant els filtres globals de data i explotació que hagis configurat.</p>
    </div>

    <!-- Actions -->
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
        <div class="flex gap-3">
          <button
            type="button"
            class="button-secondary flex items-center gap-2 shadow-sm font-medium"
            @click="onDownload(1)"
          >
            <Icon name="fa6-solid:file-excel" />
            <span>{{ t('common.download') }} {{ t('reports_block.manual_csv') }}</span>
          </button>

          <button
            type="button"
            class="button-secondary flex items-center gap-2 shadow-sm font-medium"
            @click="onDownload(2)"
          >
            <Icon name="fa6-solid:file-excel" />
            <span>{{ t('common.download') }} {{ t('reports_block.auto_file').toLowerCase() }}</span>
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-5px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fadeIn {
  animation: fadeIn 0.3s ease-out forwards;
}
</style>
