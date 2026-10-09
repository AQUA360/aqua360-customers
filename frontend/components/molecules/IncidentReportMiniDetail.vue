<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';
import IBAN from '../atoms/IBAN.vue';
const { t } = useI18n();

const props = defineProps({
  id: Number,    //Incident id
  isSubRegion: {
    type: Boolean,
    default: false
  }
});
const emit = defineEmits(['show-detail', 'update:count']);

const { $IncidentReportApiService } = useNuxtApp();

const loading = ref(false);

const showDetail = function (component, id) {
  selectedId.value = id
  emit('show-detail', component, id);
}

const gridTemplateColumns = computed(() => {
  return '100px 1fr 100px 100px';
});

const selectedId = ref(null)
const localData = ref(null);

const getData = async () => {
  try {
    const result = await $IncidentReportApiService.getReports(props.id);
    localData.value = result.results;
    emit('update:count', result.count)
  } catch (err) {
    error.value = err;
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
    <div v-if="localData && localData.length > 0" class="min-w-full text-sm text-slate-800 mt-2">
      <div class="group grid bg-gray-100 border-b text-left " :style="{ gridTemplateColumns: gridTemplateColumns }">
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.date') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.report_detail') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.documentation') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('user') }} </span>
      </div>
      <div v-for="item in localData" class="border-b group grid text-sm leading-4 transition-all duration-100"
        :style="{ gridTemplateColumns: gridTemplateColumns }" :class="{ 'bg-yellow-50': item.id === selectedId }">
        
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.incident_data? formatDate(item.incident_data) : '-' }}</p>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <button v-if="!props.isSubRegion" @click="showDetail('IncidentReportEdit', item.id)"
            class="text-start text-sky-500 underline">{{ item.token }}</button>
          <span v-else>{{ item.token }}</span>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.total_documents }}</p>
        </div>
  
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.user_username? item.user_username : t('common.admin') }}</p>
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