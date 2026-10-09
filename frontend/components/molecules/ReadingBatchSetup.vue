<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { format } from 'date-fns';
import { useToast } from 'vue-toastification';
import ReadingFileSelect from '~/components/molecules/ReadingFileSelect.vue';

const PENDING_READING_DOCUMENT_KEY = 'avsis.pendingReadingDocument';

const { t } = useI18n();
const toast = useToast();
const route = useRoute();
const { $ConfigProjectApiService, $ReadingDocumentApiService } = useNuxtApp();

const props = defineProps({
  batch_id: Number,
  num_supplies: Number,
  num_contracts: Number,
  num_no_meters: Number,
  counters: Object,
  missing_billing_data: Object,
  smartMeteringLoading: {
    type: Boolean,
    default: false,
  },
  smartMeteringTaskId: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(['change', 'show-subregion', 'open-smart-metering', 'smart-metering-preview-refresh']);

const readingFiles = ref([]);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const selectingFile = ref(false);

const selectedOriginType = ref(null);
const reading_date = ref(null);
const smart_metering_date = ref(null);
const smartMeteringEnabled = ref(false);
const minimum_date = ref(null);
const has_missing_billing_data = ref(false);

const regularCounters = computed(() => {
  if (!props.counters) return null;
  const { reader_alert_breakdown, ...rest } = props.counters;
  return rest;
});

const totalReaderAlerts = computed(() => {
  const breakdown = props.counters?.reader_alert_breakdown || {};
  return Object.values(breakdown).reduce((sum, count) => sum + Number(count || 0), 0);
});

const closeAllRegions = () => {
  selectingFile.value = false;
  showRegion.value = false;
};

const emitChange = () => {
  if (!selectedOriginType.value) {
    emit('change', { origin_type: null });
    return;
  }

  let data;

  if (selectedOriginType.value === 'FILE') {
    data = {
      reading_files: readingFiles.value.map(r => r.id),
      not_billed: false,
      minimum_date: minimum_date.value,
    };
  } else {
    data = {
      reading_date: reading_date.value,
      not_billed: selectedOriginType.value === 'NOT_BILLED',
      minimum_date: minimum_date.value,
    };
  }

  data.origin_type = selectedOriginType.value;
  emit('change', data);
};

const onSelectedFile = (item) => {
  closeAllRegions();
  readingFiles.value = [item];
  emitChange();
};
const openReadingFileRegion = () => {
  closeAllRegions();
  selectingFile.value = true;
  showRegion.value = true;
};

const openNewFilePage = () => {
  const returnTo = route.fullPath || `/reading/reading-batches/edit/${props.batch_id}`;
  navigateTo({
    path: '/reading/readings/add',
    query: { returnTo },
  });
};

const applyPendingReadingDocument = async () => {
  let raw = null;
  try {
    raw = sessionStorage.getItem(PENDING_READING_DOCUMENT_KEY);
    if (!raw) return;
    sessionStorage.removeItem(PENDING_READING_DOCUMENT_KEY);
  } catch (err) {
    console.error(err);
    return;
  }

  try {
    const parsed = JSON.parse(raw);
    let document = parsed;
    if (parsed?.id && !parsed?.file) {
      document = await $ReadingDocumentApiService.getDetail(parsed.id);
    }
    if (!document?.id) return;
    readingFiles.value = [document];
    selectedOriginType.value = 'FILE';
    emitChange();
  } catch (err) {
    console.error(err);
  }
};

const removeFile = async (item) => {
  var index = readingFiles.value.findIndex(r => r.token == item.token);
  if (index > -1) {
    readingFiles.value.splice(index, 1);
  }
};

const openSmartMetering = () => {
  if (!smart_metering_date.value) {
    toast.error(t('billing_block.reading_date'));
    return;
  }
  emit('open-smart-metering', { reading_date: smart_metering_date.value });
};

const loadData = async () => {
  if (props.counters) {
    selectedOriginType.value = 'APP';
  }
};

const checkSmartMeteringEnabled = async () => {
  try {
    const configs = await $ConfigProjectApiService.getAll('smart_metering_authentication_token');
    const smartMeteringConfig = configs.find((item) => item.token === 'smart_metering_authentication_token');
    smartMeteringEnabled.value = Boolean(String(smartMeteringConfig?.value ?? '').trim());
  } catch {
    smartMeteringEnabled.value = false;
  }
};

onMounted(async () => {
  has_missing_billing_data.value = props.missing_billing_data && props.missing_billing_data?.missing_billing;
  if (has_missing_billing_data.value) {
    selectedOriginType.value = 'MISSING_BILLING';
  }
  minimum_date.value = format(new Date(new Date().setMonth(new Date().getMonth() - 4)), 'yyyy-MM-dd');
  smart_metering_date.value = format(new Date(), 'yyyy-MM-dd');
  loadData();
  checkSmartMeteringEnabled();
  await applyPendingReadingDocument();
});

// Observa canvis per emetre l'esdeveniment
watch([selectedOriginType, reading_date, readingFiles, minimum_date], () => {
  emitChange();
}, { immediate: true });

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-start mb-4">
      <h2 class="text-xl font-semibold my-2">{{ $t('common.load') }} {{ $t('readings') }}</h2>

      <div class="flex items-center flex-wrap gap-x-6 gap-y-2">
        <div class="flex items-center space-x-2 text-sm">
          <Icon name="fa6-solid:street-view" class="text-slate-400" />
          <span class="text-slate-700">{{ $t('common.supply_points') }}</span>
          <span class="text-slate-500">:</span>
          <span class="font-bold text-slate-900">{{ num_supplies }}</span>
        </div>
        <div class="flex items-center space-x-2 text-sm">
          <Icon name="fa6-solid:file-contract" class="text-slate-400" />
          <span class="text-slate-700">{{ $t('common.contracts') }}</span>
          <span class="text-slate-500">:</span>
          <span class="font-bold text-slate-900">{{ num_contracts }}</span>
        </div>
        <div class="flex items-center space-x-2 text-sm">
          <Icon name="fa6-solid:file-contract" class="text-slate-400" />
          <span class="text-slate-700">{{ $t('common.no_meters') }}</span>
          <span class="text-slate-500">:</span>
          <span class="font-bold text-slate-900">{{ num_no_meters }}</span>
        </div>
        <div v-if="props.counters?.no_route_supply_points_count" class="flex items-center space-x-2 text-sm">
          <Icon name="fa6-solid:route" class="text-orange-400" />
          <span class="text-slate-700">{{ $t('billing_block.no_route_supply_points') }}</span>
          <span class="text-slate-500">:</span>
          <span class="font-bold text-orange-600">{{ props.counters.no_route_supply_points_count }}</span>
        </div>
      </div>
    </div>
    <div v-if="has_missing_billing_data" class="mb-4">
      <div class="flex items-center space-x-2 text-sm text-slate-500">
        <span>{{ $t('billing') }}</span>
        <span class="font-bold"> {{ props.missing_billing_data.missing_billing.name }}</span>
        <AtomsRedirectButton :id="props.missing_billing_data.missing_billing.id" :path="'/billing/billing/'" />
      </div>
    </div>

    <div
      v-if="!has_missing_billing_data && smartMeteringEnabled"
      class="flex justify-start items-end gap-2 mb-3"
    >
      <AtomsInputDate
        v-model="smart_metering_date"
        :label="t('billing_block.reading_date')"
        class="max-w-[11rem] !mb-0 shrink-0"
        :disabled="!!smartMeteringTaskId || smartMeteringLoading"
      />
      <AtomsProcessColorBadge
        v-if="smartMeteringTaskId"
        class="!inline-flex items-center h-[42px] px-4 text-sm font-medium shrink-0"
        :value="t('billing_block.smart_metering_loading_preview')"
        color="blue"
        :taskId="smartMeteringTaskId"
        @refresh="emit('smart-metering-preview-refresh')"
      />
      <button
        v-else
        type="button"
        class="inline-flex items-center h-[42px] px-4 text-sm font-medium text-white bg-sky-600 hover:bg-sky-700 rounded-md shadow-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
        :disabled="smartMeteringLoading"
        @click="openSmartMetering"
      >
        <Icon
          :name="smartMeteringLoading ? 'fa6-solid:spinner' : 'fa6-solid:tower-broadcast'"
          class="mr-2 shrink-0"
          :class="{ 'animate-spin': smartMeteringLoading }"
        />
        {{ $t('billing_block.smart_metering') }}
      </button>
    </div>

    <!-- Selecció de Tipus -->
    <div class="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4 py-2">
      <label v-if="!has_missing_billing_data" class="flex items-center">
        <input type="radio" value="FILE" v-model="selectedOriginType" class="mr-2">
        {{ $t('billing_block.load_by_file') }}
      </label>
      <label v-if="!has_missing_billing_data" class="flex items-center">
        <input type="radio" value="DATE" v-model="selectedOriginType" class="mr-2">
        {{ $t('billing_block.load_by_date') }}
      </label>
      <label v-if="!has_missing_billing_data" class="flex items-center">
        <input type="radio" value="APP" v-model="selectedOriginType" class="mr-2">
        {{ $t('billing_block.load_by_app') }}
        <AtomsLecturappHelpLink icon-only class="ml-1" />
      </label>
      <label v-if="!has_missing_billing_data" class="flex items-center">
        <input type="radio" value="NOT_BILLED" v-model="selectedOriginType" class="mr-2">
        {{ $t('billing_block.load_by_not_billed') }}
      </label>
      <label v-if="has_missing_billing_data" class="flex items-center">
        <input type="radio" value="MISSING_BILLING" v-model="selectedOriginType" class="mr-2">
        {{ $t('billing_block.load_by_missing_billing') }}
        <span class="text-slate-500 font-semibold ml-2">
          {{ formatDate(props.missing_billing_data.missing_start) }} - {{ formatDate(props.missing_billing_data.missing_end) }}
        </span>
      </label>
    </div>
    <!-- /end Selecció de Tipus -->

    <div v-if="selectedOriginType == 'FILE'" class="mb-4">
      <div class="footering">

        <div :class="{ 'mt-1': readingFiles.length > 0 }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="readingFiles.length > 0"
            class="group grid  grid-cols-[3fr,1fr,1fr] divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('common.doc') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.date') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('readings') }}
            </span>
          </div>
          <div v-for="item in readingFiles"
            class="group grid grid-cols-[3fr,1fr,1fr] divide-x text-sm text-center leading-4 ">
            <div class="p-2">
              <a class="text-sky-500 hover:text-sky-700" :href="item.file"><span>{{ item.file.split('/').pop()
                  }}</span></a>
            </div>
            <div class="p-2 text-slate-800 relative">
              {{ formatDate(item.created_at) }}
            </div>
            <div class="p-2 text-slate-800 relative"
              :title="item.num_readings < num_contracts ? 'Falten lectures' : item.num_readings == num_contracts ? 'Lectures correctes' : 'El fitxer té més lectures de les necessàries'">
              <span
                :class="{ 'text-red-500': item.num_readings < num_contracts, 'text-green-500': item.num_readings == num_contracts, 'text-yellow-500': item.num_readings > num_contracts }">
                {{ item.num_readings }} / {{ num_contracts }}
                <Icon name="fa6-solid:circle-info" v-if="item.num_readings != num_contracts" />
              </span>
              <button @click="removeFile(item)"
                class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
          </div>
          <div v-if="readingFiles.length == 0" class="footering flex">
            <button @click="openReadingFileRegion"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:pencil" class="text-slate-400 mx-2" /> {{ $t('common.select') }} {{ $t('billing_block.readings_file') }}
            </button>
            <button @click="openNewFilePage"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400 mx-2" /> {{ $t('common.add') }} {{ $t('readings') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="selectedOriginType == 'DATE'" class="mb-4">
      <AtomsInputDate v-model="reading_date" :label="t('billing_block.approx_date')" class="max-w-md mb-2" />
    </div>
    <div v-else-if="selectedOriginType == 'APP'" class="mb-4">
    </div>
    <div v-else-if="selectedOriginType == 'NOT_BILLED'" class="mb-4">
      <AtomsInputDate v-model="minimum_date" :label="t('billing_block.minimum_date')" class="max-w-md mb-2" />
    </div>
    <div v-if="counters && !has_missing_billing_data"  class="p-4 border rounded-lg bg-gray-50">
      <h3 class="text-lg font-medium mb-3">{{ $t('billing_block.batch_readings') }}</h3>
      <div class="grid gap-3">
        <div v-for="(counter, key) in regularCounters" :key="key" class="flex justify-between items-center p-3 bg-white rounded border">
          <span class="font-medium">{{ t(key) }}</span>
          <span class="text-gray-600">{{ counter }}</span>
        </div>
        <div
          v-if="totalReaderAlerts > 0"
          class="flex justify-between items-center p-3 bg-white rounded border"
        >
          <span class="font-medium flex items-center gap-2">
            {{ t('billing_block.reader_alerts') }}
            <button
              type="button"
              class="text-red-500 hover:text-red-700"
              :title="t('billing_block.view_alert_readings')"
              @click="emit('show-subregion', { type: 'reader-alerts' })"
            >
              <Icon name="fa6-solid:triangle-exclamation" />
            </button>
          </span>
          <span class="text-gray-600">{{ totalReaderAlerts }}</span>
        </div>
      </div>
    </div>


    <!-- Regió lateral per formularis -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-1/2': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ReadingFileSelect v-if="selectingFile" v-model="readingFiles" @item-clicked="onSelectedFile" />
      </div>
    </div>
  </div>
</template>
