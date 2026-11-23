<script setup>
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

const { t } = useI18n();

const props = defineProps({
  id: Number, // Supply Point id
  isSubRegion: {
    type: Boolean,
    default: false
  },
  exportable: {
    type: Boolean,
    default: true
  },
  exportFileName: {
    type: String,
    default: 'meter_changes'
  }
});
const emit = defineEmits(['show-detail', 'update:count']);

const { $SupplyPointApiService } = useNuxtApp();

const loading = ref(true);
const localData = ref([]);

const formatReading = (value) => {
  if (value === null || value === undefined || value === '') return '-';
  const number = Number(value);
  return Number.isNaN(number) ? value : number.toLocaleString(undefined, { maximumFractionDigits: 2 });
};

const sourceLabel = (source) => source ? t(`service_block.meter_history_source_${source}`) : '-';

const exportColumns = computed(() => [
  { header: t('service_block.meter_change_date'), value: (row) => row.change_date ? formatDate(row.change_date) : '', key: 'change_date' },
  { header: t('service_block.old_meter'), value: (row) => row.old_meter_code || '', key: 'old_meter' },
  { header: t('service_block.meter_history_old_reading'), value: (row) => row.old_reading ?? '', key: 'old_reading' },
  { header: t('service_block.new_meter'), value: (row) => row.new_meter_code || '', key: 'new_meter' },
  { header: t('service_block.meter_history_new_reading'), value: (row) => row.new_reading ?? '', key: 'new_reading' },
  { header: t('service_block.meter_history_source'), value: (row) => sourceLabel(row.source), key: 'source' },
  { header: t('order'), value: (row) => row.order_token || '', key: 'order' },
  { header: t('user'), value: (row) => row.user_name || '', key: 'user' },
  { header: t('common.observation'), value: (row) => row.observation || '', key: 'observation' },
]);

const gridTemplateColumns = '100px 1fr 110px 1fr 110px 130px 110px 1fr 1.5fr';

const showMeter = (meterId) => {
  if (meterId) emit('show-detail', 'MeterRegion', meterId);
};

const getData = async () => {
  loading.value = true;
  try {
    const result = await $SupplyPointApiService.getMeterHistory(props.id);
    localData.value = result?.results || [];
    emit('update:count', result?.count || 0);
  } catch (err) {
    console.log(err);
  } finally {
    loading.value = false;
  }
};

onMounted(getData);

watch(() => props.id, getData);

defineExpose({ refresh: getData });
</script>

<template>
  <div v-if="loading" class="p-4">
    <div class="flex justify-center items-center">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>

  <div v-else>
    <div v-if="exportable && localData.length > 0" class="flex justify-end mb-1">
      <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName" />
    </div>

    <div v-if="localData.length > 0" class="min-w-full text-sm text-slate-800 mt-2 overflow-x-auto">
      <div class="group grid bg-gray-100 border-b text-left" :style="{ gridTemplateColumns }">
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('service_block.meter_change_date') }}</span>
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('service_block.old_meter') }}</span>
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('service_block.meter_history_old_reading') }}</span>
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('service_block.new_meter') }}</span>
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('service_block.meter_history_new_reading') }}</span>
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('service_block.meter_history_source') }}</span>
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('order') }}</span>
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('user') }}</span>
        <span class="p-2 text-slate-900 font-bold flex items-center">{{ t('common.observation') }}</span>
      </div>

      <div v-for="item in localData" :key="item.id" class="border-b group grid text-sm leading-4"
        :style="{ gridTemplateColumns }">
        <div class="text-slate-500 p-2">{{ item.change_date ? formatDate(item.change_date) : '-' }}</div>

        <div class="text-slate-500 p-2">
          <button v-if="item.old_meter && !props.isSubRegion" @click="showMeter(item.old_meter)"
            class="text-start text-sky-500 underline">{{ item.old_meter_code }}</button>
          <span v-else>{{ item.old_meter_code || '-' }}</span>
        </div>

        <div class="text-slate-500 p-2">{{ formatReading(item.old_reading) }}</div>

        <div class="text-slate-500 p-2">
          <button v-if="item.new_meter && !props.isSubRegion" @click="showMeter(item.new_meter)"
            class="text-start text-sky-500 underline">{{ item.new_meter_code }}</button>
          <span v-else>{{ item.new_meter_code || '-' }}</span>
        </div>

        <div class="text-slate-500 p-2">{{ formatReading(item.new_reading) }}</div>
        <div class="text-slate-500 p-2">{{ sourceLabel(item.source) }}</div>
        <div class="text-slate-500 p-2">{{ item.order_token || '-' }}</div>
        <div class="text-slate-500 p-2">{{ item.user_name || '-' }}</div>
        <div class="text-slate-500 p-2 whitespace-pre-line">{{ item.observation || '' }}</div>
      </div>
    </div>

    <div v-else class="p-4 text-slate-500">
      {{ t('service_block.no_meter_changes') }}
    </div>
  </div>
</template>
