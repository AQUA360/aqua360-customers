<script setup>
import { formatDate } from '~/utils/date';

const { t } = useI18n();

const props = defineProps({
  item: {
    type: Array,
    default: () => [],
  },
  contracts: {
    type: Array,
    default: () => [],
  },
  isSubRegion: {
    type: Boolean,
    default: false,
  },
  // Show a "Download XLSX" button that exports exactly the rows/columns shown.
  exportable: {
    type: Boolean,
    default: true,
  },
  exportFileName: {
    type: String,
    default: 'readings',
  },
});

const emit = defineEmits(['show-detail']);
const selectedId = ref(null);

const showDetail = (component, id) => {
  selectedId.value = id;
  emit('show-detail', component, id);
};

const gridTemplateColumns = '100px 1fr 80px 80px 1fr 100px 80px 50px 50px';

const localData = ref([]);

const contractToken = (element) => {
  if (!element.contract) return '-';
  return typeof element.contract === 'string' ? element.contract : element.contract.token;
};

const contractId = (element) => {
  if (element.contract?.id) return element.contract.id;
  const token = contractToken(element);
  if (token === '-') return null;
  return props.contracts.find((c) => c.token === token)?.id ?? null;
};

const meterCode = (element) => element.meter_code || element.meter?.code || '-';

const meterId = (element) => {
  if (typeof element.meter === 'number') return element.meter;
  return element.meter?.id ?? null;
};

const batchLabel = (element) => {
  if (element.batch == null) return '-';
  return typeof element.batch === 'object' ? element.batch.name : element.batch;
};

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('common.date'), value: (row) => row.reading_date ? formatDate(row.reading_date) : '', key: 'reading_date' },
  { header: t('contract'), value: (row) => contractToken(row) },
  { header: t('reading'), value: (row) => row.reading_value ? parseInt(row.reading_value) : '', key: 'reading_value' },
  { header: t('billing_block.reading_batch'), value: (row) => batchLabel(row) },
  { header: t('common.origin'), value: (row) => row.origin || '', key: 'origin' },
  { header: t('meter'), value: (row) => meterCode(row) },
  { header: t('billing_block.consumption'), value: (row) => row.calculated_value ? parseInt(row.calculated_value) : '', key: 'calculated_value' },
  { header: t('billing_block.estimated'), value: (row) => row.is_estimated ? 'X' : '', key: 'is_estimated' },
  { header: t('billing_block.short_control_reading'), value: (row) => row.is_control ? 'X' : '', key: 'is_control' },
]);

watch(
  () => props.item,
  (newVal) => {
    localData.value = newVal ?? [];
  },
  { immediate: true },
);
</script>

<template>
  <div v-if="exportable && localData?.length > 0" class="flex justify-end mb-1">
    <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName"
      :sheet-name="t('reading')" />
  </div>
  <div v-if="localData.length > 0" class="min-w-full text-sm text-slate-800 mt-2">
    <div class="group grid bg-gray-100 border-b text-left" :style="{ gridTemplateColumns }">
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('common.date') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('contract') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('reading') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('billing_block.reading_batch') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('common.origin') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('meter') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('billing_block.consumption') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('billing_block.estimated') }}</span>
      <span class="p-2 pl-2 text-slate-900 font-bold flex items-center">{{ t('billing_block.short_control_reading')
        }}</span>
    </div>
    <div v-for="element in localData" :key="element.id"
      class="border-b group grid text-sm leading-4 transition-all duration-100" :style="{ gridTemplateColumns }" :class="{
        'bg-yellow-50': element.id === selectedId,
        'bg-red-50': element.is_close,
        'bg-green-50': element.is_initial,
      }">
      <div class="footering text-slate-500 p-2 w-full">
        {{ element.reading_date ? formatDate(element.reading_date) : '-' }}
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        <button v-if="!isSubRegion && contractId(element)" class="text-start text-sky-500 underline"
          @click="showDetail('ContractRegion', contractId(element))">
          {{ contractToken(element) }}
        </button>
        <span v-else>{{ contractToken(element) }}</span>
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        {{ element.reading_value ? parseInt(element.reading_value) : '-' }}
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        {{ batchLabel(element) }}
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        {{ element.origin || '-' }}
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        <button v-if="!isSubRegion && meterId(element)" class="text-start text-sky-500 underline"
          @click="showDetail('MeterRegion', meterId(element))">
          {{ meterCode(element) }}
        </button>
        <span v-else>{{ meterCode(element) }}</span>
      </div>
      <div class="footering text-slate-500 p-2 w-full min-w-[80px]">
        <span>{{ element.calculated_value ? parseInt(element.calculated_value) : '-' }}</span>
        <abbr v-if="element.estimated_used" :title="t('billing_block.estimated_correction')"
          class="text-yellow-600 font-semibold">
          - {{ parseInt(element.estimated_used) }}
        </abbr>
        <span v-if="element.calculated_value"> m3</span>
        <div v-if="element.leak_value && element.leak_value > 0" class="text-xs font-bold">
          <p class="text-red-600">
            {{ t('billing_block.leak') }}: {{ parseInt(element.leak_value) }} m3
          </p>
        </div>
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        <Icon v-if="element.is_estimated" name="fa6-solid:check" class="text-xl text-green-600" />
        <span v-else>-</span>
      </div>
      <div class="footering text-slate-500 p-2 w-full">
        <Icon v-if="element.is_control" name="fa6-solid:check" class="text-xl text-green-600" />
        <span v-else>-</span>
      </div>
    </div>
  </div>
  <div v-else class="footering text-slate-500 p-2">
    {{ t('common.no_records') }}
  </div>
</template>
