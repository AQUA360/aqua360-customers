<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';
import IBAN from '../atoms/IBAN.vue';
const { t } = useI18n();

const props = defineProps({
  contract_id: Number,    //Contract id
  contract_request_id: Number,    //Contract request id
  connection_request_id: Number,    //Connection request id
  connection_id: Number,    //Connection id
  incident_id: Number,    //Incident id
  supply_point_ids: {    //Supply point ids of the contract, to also show orders linked directly to them
    type: Array,
    default: () => []
  },
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
    default: 'orders'
  }
});
const emit = defineEmits(['show-detail', 'update:count']);

const { $OrderApiService } = useNuxtApp();

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('common.creation'), value: (row) => row.created_at ? formatDate(row.created_at) : '', key: 'created_at' },
  { header: t('common.completion'), value: (row) => row.completed_at ? formatDate(row.completed_at) : '', key: 'completed_at' },
  { header: t('common.type'), value: (row) => row.type_name ? row.type_name : row.type?.name, key: 'type' },
  { header: t('common.contract'), value: (row) => row.related_contract_token || '', key: 'related_contract_token' },
  { header: t('common.status'), value: (row) => row.status?.name, key: 'status' },
  { header: t('common.operators'), value: (row) => (row?.operators?.length > 0) ? row.operators.map(operator => `${operator.name} ${operator.surname} (${operator.token})`).join(', ') : '' },
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
  return '100px 100px 150px 120px 150px 1fr';
});

const selectedId = ref(null)
const localData = ref(null);

const getData = async () => {
  try {
    if (props.connection_id) {
      const result = await $OrderApiService.getFilterConnection(props.connection_id);
      localData.value = result;
      emit('update:count', result.length)
      return;
    }
    const result = await $OrderApiService.getAll(
      '', [], 1, null, false, null, [],
      props.contract_id, props.contract_request_id, props.connection_request_id, props.incident_id,
      '', '', null, [], [], props.supply_point_ids
    );
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

watch(() => [props.incident_id, props.contract_id, props.contract_request_id, props.connection_request_id, props.connection_id, props.supply_point_ids], () => {
  getData()
}, { deep: true });

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
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.creation') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.completion') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t("common.type") }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.contract') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.status') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.operators') }} </span>
      </div>
      <div v-for="item in localData" class="border-b group grid text-sm leading-4 transition-all duration-100"
        :style="{ gridTemplateColumns: gridTemplateColumns }" :class="{ 'bg-yellow-50': item.id === selectedId }">
        
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ formatDate(item.created_at) }}</p>
        </div>

        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.completed_at?formatDate(item.completed_at):'-' }}</p>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full truncate">
          <button v-if="!props.isSubRegion" @click="showDetail('OrderRegion', item.id)"
            class="text-start text-sky-500 underline truncate">{{ item.type_name? item.type_name : item.type?.name }}</button>
          <span v-else class="truncate">{{ item.type_name? item.type_name : item.type?.name }}</span>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full truncate">
          <p class="truncate">{{ item.related_contract_token || '-' }}</p>
        </div>

        <div class="footering text-slate-500 p-2 w-full">
          <AtomsColorBadge :value="item.status?.name" :color="item.status?.color" />
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <p v-if="item?.operators?.length > 0" class="truncate">{{ item.operators.map(operator => `${operator.name} ${operator.surname} (${operator.token})`).join(', ') }}</p>
          <p v-else class="truncate">-</p>
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