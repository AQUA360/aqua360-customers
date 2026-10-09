<script setup>
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';
import { formatDate } from '~/utils/date';
import FilterSelect from '../atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
const { t } = useI18n();

const props = defineProps({
  id: Number,    //Process id
  person_ids: Array, //Person ids
  contract_id: {
    type: Number,
    default: null
  }, //Contract id
  isSubRegion: {
    type: Boolean,
    default: false
  },
  reload: {
    type: Boolean,
    default: false
  },
  max_height: {
    type: String,
    default: '40vh'
  },
  // Show a "Download XLSX" button that exports exactly the rows/columns shown.
  exportable: {
    type: Boolean,
    default: true
  },
  exportFileName: {
    type: String,
    default: 'communications'
  }
});
const emit = defineEmits(['show-detail', 'update:count']);

const { $CommunicationApiService, $ConfiglistApiService } = useNuxtApp();

const loading = ref(false);

const selectedFilters = ref([]);
const filter_status = ref([]);
const statuses = ref([]);

const filter_types = ref([]);
const types = ref([]);
const selected_types = ref([]);

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

const adjustedMaxHeight = computed(() => {
  const match = props.max_height?.match(/^calc\(100vh - (\d+)px\)$/);
  if (!match) return props.max_height;
  const currentOffset = Number(match[1]);
  return `calc(100vh - ${currentOffset + 150}px)`;
});

// NOTE: this now always returns exactly as many tracks as there are
// rendered columns (see the header/body v-if conditions below), so the
// header and the data rows never fall out of sync again.
const gridTemplateColumns = computed(() => {
  if (props.person_ids && props.person_ids.length > 0) {
    // Ident | Canal | Assumpte | Estat | Enviat
    return '120px 180px minmax(220px, 1fr) 120px 130px';
  }
  // Ident | Destinatari | Canal | Estat | Enviat
  return '120px minmax(220px, 1fr) 180px 120px 130px';
});

const selectedId = ref(null)
const localData = ref([]);

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => {
  const cols = [
    { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  ];
  if (!props.person_ids || props.person_ids.length == 0) {
    cols.push({ header: t('customer_service_block.recipient'), value: (row) => row.person_name, key: 'person_name' });
    cols.push({ header: t('common.person_id'), value: (row) => row.person_token, key: 'person_token' });
  }
  cols.push({ header: t('customer_service_block.channel'), value: (row) => row.type_names, key: 'type_names' });
  if (props.person_ids && props.person_ids.length > 0) {
    cols.push({ header: t('customer_service_block.subject'), value: (row) => row.message_subject, key: 'message_subject' });
  }
  cols.push({ header: t('common.status'), value: (row) => row.status_name, key: 'status' });
  cols.push({ header: t('customer_service_block.sent'), value: (row) => row.sent_at ? formatDate(row.sent_at) : '', key: 'sent_at' });
  return cols;
});

const searchQuery = ref('');
const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getData = async (skip_clear = false, targetPage = pagination.value.page) => {
  loading.value = true;
  try {
    const result = await $CommunicationApiService.getAll(
      searchQuery.value, [statuses.value], targetPage, null,
      false, props.id, props.person_ids, null,
      [types.value], props.contract_id
    );

    if (skip_clear) localData.value = [];
    localData.value = result.results || [];
    
    pagination.value.page = targetPage;
    Object.assign(pagination.value, {
      total: result.count,
      totalPages: Math.ceil(result.count / pagination.value.perPage),
      previous: result.previous,
      next: result.next,
      isFiltered: String(searchQuery.value).trim() !== ''
    });
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const getFilterStatus = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('communication/communication-status');
    filter_status.value = data.results;
  } catch (err) {
    console.error(err);
  }
}

const getFilterTypes = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('communication/message-type');
    filter_types.value = data.results;
  } catch (err) {
    console.error(err);
  }
}

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  statuses.value = event[0].id;
  pagination.value.page = 1;
  handleSearch();
}

const handleTypeChange = (event) => {
  selected_types.value = event;
  types.value = event[0].id;
  pagination.value.page = 1;
  handleSearch();
}

const handleSearch = () => {
  debouncedGetData(true);
}

const debouncedGetData = debounce((clear = false) => {
  getData(clear, pagination.value.page);
}, 300);

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(false, newPage);
}

// Backend column filters expect a flat list of ids. The status/type refs hold
// either [] (no filter) or a single id once the user picks one.
const asFilterList = (value) => {
  if (Array.isArray(value)) return value.filter((v) => v !== null && v !== undefined && v !== '');
  return value ? [value] : [];
};

const exportCommunications = (columns) => $CommunicationApiService.exportData(
  searchQuery.value,
  asFilterList(statuses.value),
  null,
  false,
  props.id ?? null,
  props.person_ids || [],
  null,
  asFilterList(types.value),
  props.contract_id,
  null,
  columns,
);

const resetFilters = () => {
  searchQuery.value = '';
  selectedFilters.value = [];
  statuses.value = [];
  types.value = [];
  selected_types.value = [];
  pagination.value.page = 1;
  getData();
}

onMounted(async () => {
  await getFilterStatus();
  await getFilterTypes();
  await getData();
  emit('update:count', pagination.value.total);
})

watch(() => props.reload, async (newVal) => {
  pagination.value.page = 1;
  await getData(true)
})

watch(() => props.item, (newVal) => {
  getData()
});

</script>
<template>



  <div class="h-content overflow-y-auto" :style="{ maxHeight: props.max_height }">
    <div class="sticky top-0 z-10 bg-white border-b border-slate-200 px-4 py-2 grid grid-cols-[1fr,1fr] gap-x-2">
      <span class="input-group flex flex-start items-center gap-2 w-full">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchQuery" @input="handleSearch" id="communicationSearchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>
      <div class="flex flex-row-reverse items-center gap-x-2">
        <span>
          <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
            @click="resetFilters" title="reset">
            <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
          </button>
        </span>
        <FilterSelect :options="filter_status" :filters="selectedFilters" :multiple="false"
          :placeholder="t(`common.statuses`)" @update:modelValue="handleStatusChange($event)">
          <template #icon>
            <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
          </template>
        </FilterSelect>

        <FilterSelect :options="filter_types" :filters="selected_types" :multiple="false"
          :placeholder="t(`common.type`)" @update:modelValue="handleTypeChange($event)">
          <template #icon>
            <Icon name="fa6-solid:users" class="text-md ml-2 mr-1" size="10px" />
          </template>
        </FilterSelect>

      </div>
    </div>
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
        <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName"
          :total-pages="pagination.totalPages" :server-export-fn="exportCommunications" />
      </div>
      <!-- overflow-x-auto: if the viewport is narrower than the sum of the
           column tracks below, the table scrolls horizontally instead of
           squeezing every column. -->
      <div class="overflow-x-auto">
      <div v-if="localData && localData.length > 0" class="min-w-full text-sm text-slate-800 mt-2" :style="{
        minHeight: adjustedMaxHeight,
      }">
        <div class="group grid bg-gray-100 text-left " :style="{ gridTemplateColumns: gridTemplateColumns }">
          <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.identification') }} </span>
          <span v-if="!props.person_ids || props.person_ids.length == 0"
            class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('customer_service_block.recipient') }}
          </span>
          <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('customer_service_block.channel') }}
          </span>
          <span v-if="props.person_ids && props.person_ids.length > 0"
            class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('customer_service_block.subject') }} </span>
          <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.status') }} </span>
          <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('customer_service_block.sent') }}
          </span>
        </div>
        <div v-for="item in localData" class="border-t group grid text-sm leading-4 transition-all duration-100"
          :style="{ gridTemplateColumns: gridTemplateColumns }" :class="{ 'bg-yellow-50': item.id === selectedId }">

          <div class="footering text-slate-500 p-2 w-full flex items-center gap-x-1">
            <button v-if="!props.isSubRegion" @click="showDetail('CommunicationRegion', item.id)"
              class="text-start text-sky-500 underline">{{ item.token }}</button>
            <span v-else>{{ item.token }}</span>
            <AtomsRedirectButton :id="item.id" :path="'/communication/communications/'" />
          </div>

          <div v-if="!props.person_ids || props.person_ids.length == 0" class="footering text-slate-500 p-2 w-full">
            <p class="truncate">{{ item.person_name }} ({{ item.person_token }})</p>
            <p v-if="props.id && !item.message_ids.every(id => item.process_message_ids.includes(id))">
              <AtomsColorBadge :value="t('customer_service_block.with_custom_msg')" color="green" class="truncate" />
            </p>
          </div>
          
          <div class="footering text-slate-500 p-2 w-full">
            <p class="truncate">{{ item.type_names }}</p>
          </div>
          
          <div v-if="props.person_ids && props.person_ids.length > 0" class="footering text-slate-500 p-2 w-full">
            <p class="truncate">{{ item.message_subject || t('customer_service_block.no_content') }}</p>
          </div>

          <div class="footering text-slate-500 p-2 w-full">
            <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
          </div>

          <div class="footering text-slate-500 p-2 w-full">
            <p>{{ item.sent_at ? formatDate(item.sent_at) : '-' }}</p>
          </div>

        </div>
      </div>
      <div v-else class="footering text-slate-500 p-2" :style="{
        minHeight: adjustedMaxHeight,
      }">
        {{ t('customer_service_block.no_comms') }}
      </div>
      </div>
    </div>

    <div class="mt-2 sticky bottom-0 z-10 bg-white border-t border-slate-200 px-4 py-2">
      <Pagination v-if="localData.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div>


</template>