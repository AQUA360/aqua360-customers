<script setup>
import { formatDate } from '~/utils/date';
import { format } from 'date-fns';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
const { t } = useI18n();

const props = defineProps({
  reading: Object,
  show: {
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
    default: 'readings_detail',
  },
});

const emit = defineEmits(['open-region', 'exclude']);
const { $ReadingApiService, $ReadingBatchApiService, $OrderApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();

const detail = ref({});
const data = ref([]);
const loaded = ref(false);

const historyPage = ref(1);
const historyTotal = ref(0);
const historyHasMore = ref(false);
const loadingMore = ref(false);
const scrollContainer = ref(null);

// Bumped on every getData()/close so late responses from a superseded load
// (e.g. user closes and reopens the detail before the previous incremental
// load finished) get discarded instead of appending onto the wrong list.
let requestToken = 0;

const orderStatuses = ref([]);
const orderTypes = ref([]);
const orderTypeReadMeter = ref(null);

const disableOrderButton = ref(false);
const showPhotoModal = ref(false);

const getData = async () => {
  const token = ++requestToken;

  await setupData()
  if (token !== requestToken) return; // superseded while awaiting setupData()

  data.value = [];
  historyPage.value = 1;
  historyTotal.value = 0;
  historyHasMore.value = false;

  const result = await $ReadingApiService.getReadingDetail(props.reading.id, 1)
  if (token !== requestToken) return; // superseded while awaiting the request

  detail.value = result;
  data.value = result.reading_history?.results || [];
  historyTotal.value = result.reading_history?.count || 0;
  historyHasMore.value = data.value.length < historyTotal.value;
  loaded.value = true;

  await fillContainer(token);
};

// With a small page size (5), the first page(s) may not fill the scrollable
// container's height, so no scrollbar ever appears and the user has no way
// to trigger `onHistoryScroll`. Keep loading pages until either the content
// overflows (a real scrollbar takes over) or there's nothing left to load.
const fillContainer = async (token) => {
  await nextTick();
  if (token !== requestToken) return;
  const el = scrollContainer.value;
  if (!el || !historyHasMore.value) return;
  if (el.scrollHeight <= el.clientHeight) {
    await loadMoreHistory(token);
    await fillContainer(token);
  }
};

const loadMoreHistory = async (token = requestToken) => {
  if (token !== requestToken || loadingMore.value || !historyHasMore.value) return;
  loadingMore.value = true;
  try {
    const nextPage = historyPage.value + 1;
    const result = await $ReadingApiService.getReadingDetail(props.reading.id, nextPage);
    if (token !== requestToken) return; // superseded while awaiting the request
    const newResults = result.reading_history?.results || [];
    data.value = [...data.value, ...newResults];
    historyPage.value = nextPage;
    historyTotal.value = result.reading_history?.count ?? historyTotal.value;
    historyHasMore.value = data.value.length < historyTotal.value;
  } finally {
    loadingMore.value = false;
  }
};

const onHistoryScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollTop + clientHeight >= scrollHeight - 20) {
    loadMoreHistory();
  }
};

const openPhotoModal = () => {
  showPhotoModal.value = true;
}
const closePhotoModal = () => {
  showPhotoModal.value = false;
}

const photoSrc = computed(() => {
  if (!detail.value) return '';
  const photo = detail.value?.photo;
  if (!photo) return '';
  if (typeof photo !== 'string') return '';
  if (photo.startsWith('data:') || photo.startsWith('http')) return photo;
  return `data:image/jpeg;base64,${photo}`;
});

const setupData = async () => {
  const order_types = await $ConfiglistApiService.getAll('order/order-type');
  orderTypes.value = order_types.results;
  const order_type_token = await $ConfigProjectApiService.get('order_type_read_meter_token');
  orderTypeReadMeter.value = order_types.results.find(item => item.token == order_type_token);

  // carreguem els status de orders
  const order_statuses = await $ConfiglistApiService.getAll('order/order-status');
  orderStatuses.value = order_statuses.results;
};

const createOrderReadMeter = async () => {
  const defaultOrderStatus = orderStatuses.value.find(s => s.is_default == true);
  // creem un order del tipus lectura, si cal després l'usuari l'eliminarà
  const order_data = {
    token: format(new Date(), 'yyyyMMddHHmmss'),
    contract: detail.value.contract?.id,
    supply_point: detail.value.supply_point?.id,
    type: orderTypeReadMeter.value.id,
    status: defaultOrderStatus.id || orderStatuses.value[0].id,
    requested_at: format(new Date(), 'yyyy-MM-dd HH:mm:ss')
  }

  if (confirm(t("confirmation_text_block.confirm_gen_order_reading_check"))) {
    const order_saved = await $OrderApiService.save(order_data);
    disableOrderButton.value = true;
  }
}

const excludeFromBatch = () => {
  if (confirm(t("confirmation_text_block.confirm_exclude_reading_long"))) {
    const exclude = $ReadingBatchApiService.excludeReading({ id: props.reading.id });
    emit('exclude')
  }
}

const openRegion = (entity, id) => {
  emit('open-region', { entity: entity, id: id });
}

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('common.date'), value: (row) => row.reading_date ? formatDate(row.reading_date) : '', key: 'reading_date' },
  { header: t('reading'), value: (row) => row.reading_value ? parseInt(row.reading_value) : '', key: 'reading_value' },
  { header: t('billing_block.consumption'), value: (row) => row.calculated_value ? parseInt(row.calculated_value) : '', key: 'calculated_value' },
  { header: t('common.origin'), value: (row) => row.origin || '', key: 'origin' },
  { header: t('meter'), value: (row) => row.meter_code || '', key: 'meter_code' },
  { header: t('contract'), value: (row) => row.contract || '', key: 'contract' },
  { header: t('billing_block.estimated'), value: (row) => row.is_estimated ? 'X' : '', key: 'is_estimated' },
  { header: t('billing_block.short_control_reading'), value: (row) => row.is_control ? 'X' : '', key: 'is_control' },
]);

onMounted(() => {

});

watch(() => props.show, (newValue) => {
  if (newValue) {
    getData();
  }
  else {
    requestToken++; // invalidate any in-flight request from this open
    data.value = [];
    loaded.value = false;
    historyPage.value = 1;
    historyTotal.value = 0;
    historyHasMore.value = false;
  }
});

</script>

<template>
  <div>
    <div class="overflow-hidden transition-all duration-300 ease-in-out"
      :style="{ height: loaded ? '400px' : '0px', opacity: loaded ? '1' : '0', marginBottom: loaded ? '1rem' : '0', padding: loaded ? '1rem' : '0' }">
      <div class="grid grid-cols-2 gap-2 mb-2">
        <div class="flex flex-col">
          <AtomsFieldDetail :label="$t('contract')" :value="detail?.contract?.token">
            <a href="#" class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
              @click="openRegion('contract', detail?.contract?.id)">{{ detail?.contract?.token }}</a>
          </AtomsFieldDetail>
        </div>
        <div class="flex flex-col">
          <AtomsFieldDetail :label="$t('common.short_supply')" :value="detail?.supply_point?.address_complete">
            <a href="#" class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
              @click="openRegion('supply_point', detail?.supply_point?.id)">{{ detail?.supply_point?.address_complete
              }}</a>
          </AtomsFieldDetail>
        </div>
        <div class="flex flex-col">
          <AtomsFieldDetail :label="$t('contract_block.holder')" :value="detail?.contract?.holder_full_name">
            <a href="#" class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
              @click="openRegion('person', detail?.holder_id)">{{ detail?.contract?.holder_full_name }}</a>
          </AtomsFieldDetail>
        </div>
        <div>
          <button @click="createOrderReadMeter" :disabled="disableOrderButton" class="button-primary mr-2">
            {{ t('common.generate') }} {{ t('common.work_order') }}</button>
          <button @click="excludeFromBatch" class="button-warning"> {{ t('billing_block.exclude') }}</button>
          <button v-if="detail?.photo" @click="openPhotoModal" class="button-default ml-2"> 
            <div class="flex items-center gap-x-2">
              <Icon name="fa6-solid:images" />
                {{ t('common.view') }}
            </div>
          </button>
          
        </div>
      </div>
      <div v-if="exportable && data?.length > 0" class="flex justify-end mb-1">
        <AtomsDownloadXlsxButton :rows="data" :columns="exportColumns" :file-name="exportFileName"
          :sheet-name="t('reading')" />
      </div>
      <div class="overflow-x-auto">
        <!-- Table Wrapper -->
        <div class="relative">
          <!-- Table Header -->
          <table class="min-w-full table-fixed border-collapse">
            <thead class="bg-gray-100 border-b">
              <tr>
                <th class="p-2">{{ t('common.date') }}</th>
                <th class="p-2">{{ t('reading') }}</th>
                <th class="p-2">{{ t('billing_block.consumption') }}</th>
                <th class="p-2">{{ t('common.origin') }}</th>
                <th class="p-2">{{ t('meter') }}</th>
                <th class="p-2">{{ t('contract') }}</th>
                <th class="p-2">{{ t('billing_block.estimated') }}</th>
                <th class="p-2">{{ t('billing_block.short_control_reading') }}</th>
              </tr>
            </thead>
          </table>

          <!-- Scrollable Table Body -->
          <div ref="scrollContainer" class="max-h-[260px] overflow-y-auto" @scroll="onHistoryScroll">
            <div class="min-w-full table-fixed border-collapse">
              <div>
                <div v-for="(element, index) in data" :key="element.id" class="border-b grid grid-cols-8 w-full">
                  <div class="p-2">{{ element.reading_date ? formatDate(element.reading_date) : '-' }}</div>
                  <div class="p-2 flex items-center gap-1">
                    <span>{{ element.reading_value ? parseInt(element.reading_value) : '-' }}</span>
                    <Icon v-if="element.is_fire" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
                  </div>
                  <div class="p-2">
                    <div>
                      <span>
                        {{ element.calculated_value ? parseInt(element.calculated_value) + ' m3' : '-' }}
                      </span>
                      <span v-if="element.estimated_used" class="text-sky-600 font-semibold">
                        - {{ parseInt(element.estimated_used) + ' m3'}}
                      </span>
                    </div>
                    <div v-if="element.leak_value && element.leak_value > 0" class="text-xs font-bold">
                      <p class="text-red-600">
                        {{ t('billing_block.leak') }}: {{ element.leak_value ? parseInt(element.leak_value) + ' m3' :
                        '-' }}
                      </p>
                      <p class="text-green-600">
                        {{ t('common.real') }}: {{ element.real_consumption ? parseInt(element.real_consumption) + ' m3'
                          : element.calculated_value - element.leak_value + ' m3' }}
                      </p>
                    </div>
                  </div>
                  <div class="p-2">{{ element.origin ? element.origin : '-' }}</div>

                  <div class="p-2">{{ element.meter_code ? element.meter_code : '-' }}</div>
                  <div class="p-2">{{ element.contract ? element.contract : '-' }}</div>
                  <div class="p-2" v-if="element.is_estimated">
                    <Icon name="fa6-solid:check" class="text-xl text-green-600" />
                  </div>
                  <div class="p-2" v-else>
                    -
                  </div>
                  <div class="p-2" v-if="element.is_control">
                    <Icon name="fa6-solid:check" v-show="element.is_control" class="text-xl text-green-600" />
                  </div>
                  <div class="p-2" v-else>
                    -
                  </div>
                </div>
                <div v-if="data.length == 0" class="text-center py-4">
                  <span class="text-slate-500">{{ t('common.no_records') }}</span>
                </div>
                <div v-if="loadingMore" class="flex items-center justify-center gap-2 text-slate-400 text-sm py-2">
                  <Icon name="fa6-solid:spinner" class="animate-spin" />
                  <span>{{ t('common.loading') }}...</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showPhotoModal" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/60" @click="closePhotoModal"></div>
    <div class="relative bg-white rounded-lg shadow-lg max-w-3xl w-[90vw] max-h-[90vh] p-2">
      <button :title="t('common.close')" class="absolute top-2 right-2 w-8 h-8 bg-slate-600 text-white rounded-full flex items-center justify-center hover:bg-slate-500" @click="closePhotoModal">
        <Icon name="fa6-solid:xmark" />
      </button>
      <img :src="photoSrc" alt="Photo" class="block max-h-[80vh] w-auto object-contain mx-auto" />
    </div>
  </div>
  </div>
</template>