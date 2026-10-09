<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';
import IBAN from '../atoms/IBAN.vue';
const { t } = useI18n();

const props = defineProps({
  id: Number,    //Supply Point id
  isSubRegion: {
    type: Boolean,
    default: false
  },
  // Show a "Download XLSX" button that exports exactly the rows/columns shown.
  exportable: {
    type: Boolean,
    default: true
  },
  exportFileName: {
    type: String,
    default: 'frauds'
  },
});
const emit = defineEmits(['show-detail', 'update:count']);

const { $FraudApiService } = useNuxtApp();

const loading = ref(false);

const showDetail = function (component, id) {
  selectedId.value = id
  emit('show-detail', component, id);
}

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('customer_service_block.detection'), value: (row) => row.detection_date ? formatDate(row.detection_date) : '', key: 'detection_date' },
  { header: t('billing_block.record'), value: (row) => row.token, key: 'token' },
  { header: t('common.type'), value: (row) => row.type_name, key: 'type' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
]);

const selectedId = ref(null)
const localData = ref(null);

const getData = async () => {
  try {
    const result = await $FraudApiService.getAll('', [], 1, null, false, props.id);
    localData.value = result.results;
    emit('update:count', result.count)
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  getData()
})

watch(() => props.item, (newVal) => {
  getData()
});

</script>
<template>

  <div v-if="loading">
    <div class="p-4">
      <div class="flex justify-center items-center">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        <span class="ml-2">{{ $t('common.loading') }}...</span>
      </div>
    </div>
  </div>

  <div v-else>
    <div v-if="exportable && localData?.length > 0" class="flex justify-end mb-1">
      <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName" />
    </div>
    <div v-if="localData && localData.length > 0" class="min-w-full text-sm text-slate-800 mt-2">
      <table class="w-full border-collapse">
        <thead>
          <tr class="bg-gray-100 border-b">
            <th class="p-2 pl-2 text-slate-900 font-bold text-left w-24">{{ t('customer_service_block.detection') }}</th>
            <th class="p-2 pl-2 text-slate-900 font-bold text-left w-24">{{ t('billing_block.record') }}</th>
            <th class="p-2 pl-2 text-slate-900 font-bold text-left">{{ t("common.type") }}</th>
            <th class="p-2 pl-2 text-slate-900 font-bold text-left w-24">{{ t('common.status') }}</th>
            <th class="p-2 pl-2 text-slate-900 font-bold text-left w-20"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in localData" 
              class="border-b transition-all duration-100 hover:bg-gray-50"
              :class="{ 'bg-yellow-50': item.id === selectedId }">
            
            <td class="p-2 text-slate-500">
              {{ formatDate(item.detection_date) }}
            </td>
      
            <td class="p-2 text-slate-500">
              <button v-if="!props.isSubRegion" @click="showDetail('FraudRegion', item.id)"
                class="text-start text-sky-500 underline">
                {{ item.token }}
              </button>
              <span v-else>{{ item.token }}</span>
            </td>
      
            <td class="p-2 text-slate-500">
              <span class="truncate block" :title="item.type_name">{{ item.type_name }}</span>
            </td>
      
            <td class="p-2 text-slate-500">
              <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
            </td>
            
            <td class="p-2 text-slate-500">
              <AtomsColorBadge v-if="item.is_dismissed" :value="t('common.dismissed')" :color="null" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="p-4">
      <div class="footering text-slate-500 p-2">
        {{ t('common.no_records') }}
      </div>
    </div>
  </div>

</template>