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
    default: 'supply_cuts'
  }
});
const emit = defineEmits(['show-detail', 'update:count']);

const { $SupplyCutApiService } = useNuxtApp();

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('service_block.cut_date_expected_start'), value: (row) => row.date_start ? formatDate(row.date_start) : '', key: 'date_start' },
  { header: t('service_block.cut_date_expected_end'), value: (row) => row.date_end ? formatDate(row.date_end) : '', key: 'date_end' },
  { header: t('service_block.cut_date_real_start'), value: (row) => row.exec_start ? formatDate(row.exec_start) : '', key: 'exec_start' },
  { header: t('service_block.cut_date_real_end'), value: (row) => row.exec_end ? formatDate(row.exec_end) : '', key: 'exec_end' },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('order_block.reason'), value: (row) => row.cause_name, key: 'cause' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
]);

const loading = ref(false);

const showDetail = function (component, id) {
  selectedId.value = id
  emit('show-detail', component, id);
  /* return navigateTo({
      path: '/fraud/frauds',
      query: {
        id: id,
      }
    }) */
}

const gridTemplateColumns = computed(() => {
  return '90px 90px 90px 90px 1fr 1fr 100px';
});

const selectedId = ref(null)
const localData = ref(null);

const getData = async () => {
  try {
    const result = await $SupplyCutApiService.getData('', [], 1, null, false, null, props.id);
    localData.value = result.results;
    emit('update:count', result.count)
  } catch (err) {
    console.log(err)
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
      <div class="group grid bg-gray-100 border-b text-left " :style="{ gridTemplateColumns: gridTemplateColumns }">
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('service_block.cut_date_expected_start') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('service_block.cut_date_expected_end') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('service_block.cut_date_real_start') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('service_block.cut_date_real_end') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.identification') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('order_block.reason') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.status') }} </span>
      </div>
      <div v-for="item in localData" class="border-b group grid text-sm leading-4 transition-all duration-100"
        :style="{ gridTemplateColumns: gridTemplateColumns }" :class="{ 'bg-yellow-50': item.id === selectedId }">
        
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ formatDate(item.date_start) }}</p>
        </div>

        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.date_end ? formatDate(item.date_end) : '-' }}</p>
        </div>

        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.exec_start ? formatDate(item.exec_start) : '' }}</p>
        </div>

        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.exec_end ? formatDate(item.exec_end) : '-' }}</p>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <button v-if="!props.isSubRegion" @click="showDetail('SupplyCutRegion', item.id)"
            class="text-start text-sky-500 underline">{{ item.token }}</button>
          <span v-else>{{ item.token }}</span>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <AtomsColorBadge :value="item.cause_name" :color="item.cause_color" />
        </div>
        
        <div class="footering text-slate-500 p-2 w-full">
          <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
        </div>
  
      </div>
    </div>
    <div v-else class="p-4">
      <div class="footering text-slate-500 p-2">
        {{ t('service_block.no_supply_cuts') }}
      </div>
    </div>
  </div>


</template>