<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  preview: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['close', 'save']);

const readings = computed(() => props.preview?.readings ?? []);
const counters = computed(() => props.preview?.counters ?? {});
const matchedCount = computed(() => {
  if (counters.value.matched_meters != null) {
    return counters.value.matched_meters;
  }
  return readings.value.filter((r) => r.matched).length;
});
const totalMeters = computed(() => {
  if (counters.value.total_telecontrol_in_batch != null) {
    return counters.value.total_telecontrol_in_batch;
  }
  // One row per meter after backend fix; fall back to unique meter codes.
  const codes = new Set(readings.value.map((r) => r.meter_code).filter(Boolean));
  return codes.size || readings.value.length;
});
const readingDate = computed(() => props.preview?.reading_date ?? '');

const handleClose = () => {
  if (props.loading) return;
  emit('close');
};

const handleSave = () => {
  if (props.loading || matchedCount.value === 0) return;
  emit('save');
};
</script>

<template>
  <div v-if="show">
    <div
      class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-40"
      @click="handleClose"
    />

    <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none p-4">
      <div
        class="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col overflow-hidden relative pointer-events-auto"
        @click.stop
      >
        <div class="flex items-start justify-between gap-4 p-6 border-b border-gray-200 shrink-0">
          <div>
            <h3 class="text-xl font-bold text-slate-800 mb-1">
              {{ t('billing_block.smart_metering') }}
            </h3>
            <p class="text-slate-500 text-sm">
              {{ t('billing_block.reading_date') }}: {{ readingDate }}
              <span class="mx-2">·</span>
              {{ matchedCount }} / {{ totalMeters }} {{ t('common.meters').toLowerCase() }}
            </p>
          </div>
          <button
            type="button"
            :disabled="loading"
            class="text-gray-500 hover:text-gray-700 disabled:opacity-50"
            @click="handleClose"
          >
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
        </div>

        <div class="px-6 py-4 grid grid-cols-2 gap-3 shrink-0 bg-slate-50 border-b border-gray-100">
          <div class="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm">
            <span class="text-slate-600">{{ t('assigned_readings') }}:</span>
            <span class="ml-2 font-bold text-green-800">{{ counters.assigned_readings ?? matchedCount }}</span>
          </div>
          <div class="rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-sm">
            <span class="text-slate-600">{{ t('service_block.supplies_no_reading') }}:</span>
            <span class="ml-2 font-bold text-orange-800">{{ counters.missing_readings ?? 0 }}</span>
          </div>
        </div>

        <div class="overflow-auto flex-grow min-h-0 px-6 py-4">
          <div
            class="grid grid-cols-[1fr,2.1fr,2.2fr,0.8fr,1.2fr,0.8fr,0.9fr] gap-2 px-2 border-b border-gray-400 items-end text-sm sticky top-0 bg-white z-10 pb-2"
          >
            <span class="font-bold">{{ t('contract') }}</span>
            <span class="font-bold">{{ t('common.roles.HOLDER') }}</span>
            <span class="font-bold">{{ t('supply_point') }}</span>
            <span class="font-bold">{{ t('billing_block.last_reading') }}</span>
            <span class="font-bold">{{ t('billing_block.reading_date') }}</span>
            <span class="font-bold">{{ t('reading') }}</span>
            <span class="font-bold">{{ t('meter') }}</span>
          </div>

          <div
            v-for="(row, idx) in readings"
            :key="`${row.id}-${row.contract_id}-${idx}`"
            class="grid grid-cols-[1fr,2.1fr,2.2fr,0.8fr,1.2fr,0.8fr,0.9fr] gap-2 px-2 py-2 border-b text-sm items-center"
            :class="row.matched ? 'bg-white' : 'bg-orange-50'"
          >
            <span class="font-medium text-sky-600 truncate">{{ row.contracts?.[0]?.token || '-' }}</span>
            <span class="truncate" :title="row.contracts?.[0]?.holder_full_name || row.holder">
              {{ row.contracts?.[0]?.holder_full_name || row.holder || '-' }}
            </span>
            <span class="truncate" :title="row.address_complete">{{ row.address_complete }}</span>
            <span>{{ row.last_previous_reading_value ?? '-' }}</span>
            <span>{{ row.reading_date || row.timestamp || '-' }}</span>
            <span class="font-semibold" :class="row.matched ? 'text-slate-900' : 'text-orange-600'">
              {{ row.matched ? row.reading_value : t('service_block.supplies_no_reading') }}
            </span>
            <span class="text-slate-500">{{ row.meter_code }}</span>
          </div>

          <p v-if="!readings.length" class="text-center text-slate-500 py-8">
            {{ t('common.no_results') }}
          </p>
        </div>

        <div class="flex justify-end gap-3 p-6 border-t border-gray-200 shrink-0">
          <button
            type="button"
            :disabled="loading"
            class="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
            @click="handleClose"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            :disabled="loading || matchedCount === 0"
            class="button-primary flex items-center gap-2"
            @click="handleSave"
          >
            <Icon v-if="loading" name="fa6-solid:spinner" class="animate-spin" />
            <Icon v-else name="fa6-solid:floppy-disk" />
            {{ t('common.save') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
