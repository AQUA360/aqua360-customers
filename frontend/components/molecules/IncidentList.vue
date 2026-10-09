<script setup>
import { formatDate } from '~/utils/date';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
const { t } = useI18n();

const props = defineProps({
  contract_id: {
    type: Number,
    default: null
  },
  invoice_id: {
    type: Number,
    default: null
  },
  commitment_id: {
    type: Number,
    default: null
  },
  order_id: {
    type: Number,
    default: null
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
    default: 'incidents'
  },
});

const { $IncidentApiService, $ConfigProjectApiService } = useNuxtApp();

const emit = defineEmits(['show-detail', 'update:count', 'update:pending']);


const data = ref([]);
const SubRegion = ref(props.isSubRegion);
const loading = ref(false);
const getData = async () => {
  loading.value = true
  try {
    const response = await $IncidentApiService.getAll('', [], 1, null, false, props.contract_id, props.invoice_id, [], props.commitment_id, props.order_id);
    data.value = [];
    data.value = response.results;
    emit('update:count', response.count)
  } catch (error) {
    console.log(error)
  } finally {
    loading.value = false
  }
}

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('common.date'), value: (row) => row.due_date ? formatDate(row.due_date) : (row.created_at ? formatDate(row.created_at) : '') },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.title'), value: (row) => row.name, key: 'name' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
]);

onMounted(async () => {
  getData();
});

watch(() => props.contract_id, () => {
  getData();
}, { immediate: true });

watch(() => props.person_id, () => {
  getData();
}, { immediate: true });

</script>

<template>
  <div v-if="loading" class="py-4">
    <AppLoading :text="$t('common.loading')" :size="40" />
  </div>
  <div v-else>
    <div v-if="data.length == 0" class="">
      <div class="footering text-slate-500 p-2">
        <span>{{ t('common.no_records') }}</span>
      </div>
    </div>
    <div v-else>
      <div v-if="exportable && data?.length > 0" class="flex justify-end mb-1">
        <AtomsDownloadXlsxButton :rows="data" :columns="exportColumns" :file-name="exportFileName" />
      </div>
      <table class="min-w-full text-sm text-slate-800 mt-2">
        <thead>
          <tr class="bg-gray-100 border-b text-left">
            <th class="p-2">{{ t('common.date') }}</th>
            <th class="p-2">{{ t('common.identification') }}</th>
            <th class="p-2">{{ t('common.title') }}</th>
            <th class="p-2">{{ t('common.status') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(element, index) in data" :key="element.id" class="border-b">
            <td class="p-2">{{ element.due_date ? formatDate(element.due_date) : formatDate(element.created_at) }}</td>
            <td class="p-2">
              <div v-if="!props.isSubRegion" class="flex gap-2">
                <button @click="showDetail('IncidentRegion', element.id)"
                  class="text-start text-sky-500 underline flex items-center gap-2">
                  {{ element.token }}
                </button>
                <AtomsRedirectButton :id="element.id" :path="'/incident/incidents/'" />
              </div>
              <span v-else>
                {{ element.token }}
              </span>
            </td>
            <td class="p-2">
              <span>
                {{ element.name }}
              </span>
            </td>
            <td class="p-2">
              <AtomsColorBadge :value="element.status_name" :color="element.status_color" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

</template>