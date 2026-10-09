<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';
import IBAN from '../atoms/IBAN.vue';
const { t } = useI18n();

const props = defineProps({
  id: Number,    //Order id
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
    default: 'order_reports'
  }
});
const emit = defineEmits(['show-detail']);

const { $OrderApiService } = useNuxtApp();

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('common.date'), value: (row) => row.report_date ? formatDate(row.report_date) : '', key: 'report_date' },
  { header: t('common.report_detail'), value: (row) => row.token, key: 'token' },
  { header: `${t('common.dedicated')}(min)`, value: (row) => row.time_dedicated, key: 'time_dedicated' },
  { header: t('common.docs'), value: (row) => row?.active_documents || 0, key: 'active_documents' },
  { header: t('operator'), value: (row) => row.operator_full_name ? row.operator_full_name : row?.operator?.token },
]);

const loading = ref(false);

const showDetail = function (component, id) {
  selectedId.value = id
  emit('show-detail', component, id);
}

const gridTemplateColumns = computed(() => {
  return '100px 1fr 100px 100px 1fr';
});

const selectedId = ref(null)
const localData = ref(null);

const getData = async () => {
  try {
    const result = await $OrderApiService.getReports(props.id);
    localData.value = result.results;
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
    <div v-if="exportable && localData?.length > 0" class="flex justify-end items-center gap-2 mt-3 mb-2">
      <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName" />
    </div>
    <div v-if="localData && localData.length > 0" class="min-w-full text-sm text-slate-800 mt-2">
      <div class="group grid bg-gray-100 border-b text-left " :style="{ gridTemplateColumns: gridTemplateColumns }">
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.date') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.report_detail') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.dedicated') }}(min) </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t("common.docs") }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('operator') }} </span>
      </div>
      <div v-for="item in localData" class="border-b group grid text-sm leading-4 transition-all duration-100"
        :style="{ gridTemplateColumns: gridTemplateColumns }" :class="{ 'bg-yellow-50': item.id === selectedId }">
        
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ formatDate(item.report_date) }}</p>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <button @click="showDetail('OrderReportEdit', item.id)"
            class="text-start text-sky-500 underline">{{ item.token }}</button>
        </div>
        
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.time_dedicated }}</p>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item?.active_documents || 0 }}</p>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.operator_full_name? item.operator_full_name : item?.operator?.token }}</p>
        </div>
  
      </div>
    </div>
    <div v-else class="p-4">
      <div class="footering text-slate-500 p-2">
        {{ t('common.no_records') }}
      </div>
    </div>
  </div>


</template>