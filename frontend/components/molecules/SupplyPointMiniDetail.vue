<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';
import IBAN from '../atoms/IBAN.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
const { t } = useI18n();

const props = defineProps({
  id: Number,    //Contract id
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
    default: 'supply_points'
  }
});
const emit = defineEmits(['show-detail', 'update:count']);

const { $SupplyPointApiService } = useNuxtApp();

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('address_block.address'), value: (row) => row.address_complete, key: 'address_complete' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
]);

const loading = ref(false);

const showDetail = function (component, id) {
  selectedId.value = id
  emit('show-detail', component, id);
}

const gridTemplateColumns = computed(() => {
  return '1fr 1fr 1fr';
});

const selectedId = ref(null)
const localData = ref(null);

const getData = async () => {
  try {
    const result = await $SupplyPointApiService.getByContract([props.id]);
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
    <AppLoading :text="$t('common.loading')" :size="40" />
  </div>

  <div v-else>
    <div v-if="exportable && localData?.length > 0" class="flex justify-end mb-1">
      <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName" />
    </div>
    <div v-if="localData && localData.length > 0" class="min-w-full text-sm text-slate-800 mt-2">
      <div class="group grid bg-gray-100 border-b text-left " :style="{ gridTemplateColumns: gridTemplateColumns }">
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.identification') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('address_block.address') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.status') }} </span>
      </div>
      <div v-for="item in localData" class="border-b group grid text-sm leading-4 transition-all duration-100"
        :style="{ gridTemplateColumns: gridTemplateColumns }" :class="{ 'bg-yellow-50': item.id === selectedId }">
        
        <div class="footering text-slate-500 p-2 w-full">
          <button v-if="!props.isSubRegion" @click="showDetail('SupplyPointRegion', item.id)"
            class="text-start text-sky-500 underline">{{ item.token }}</button>
          <span v-else>{{ item.token }}</span>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.address_complete }}</p>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
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