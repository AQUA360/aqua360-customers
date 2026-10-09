<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1 from '~/components/atoms/H1.vue';
import { debounce } from 'lodash';

const { t } = useI18n();

const props = defineProps({
  billing: Object
});

const emit = defineEmits(['change', 'show-subregion', 'readings-assigned']);
const { $BillingApiService, $ReadingBatchApiService, $ConfigProjectApiService } = useNuxtApp();

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const pagination = ref({
  page: 1,
  perPage: 10,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const searchInput = ref('');
const search_filter = ref('');
const loadingReadings = ref(false);
const assigning = ref(false)

const readingsAssigned = ref(false);

const showDialog = ref(false);
const canClose = ref(false);

const selectedReadingBatches = ref([]);
const readingBatches = ref(null);

const routes = ref([]);
const showReadings = ref([]);

const showingRoute = ref(null);

const openDialog = () => {
  if (!showDialog.value) {
    canClose.value = false;
    showDialog.value = true;
    setTimeout(() => {
      canClose.value = true;
      getReadingBatches()
    }, 1)
  }
}

const clickOutside = () => {
  if (canClose.value) {
    showDialog.value = false;
    canClose.value = false;
  }
}
const view_readings = async (item) => {
  showRegion.value = true;

  if (item.route)
    showingRoute.value = item.route;

  getReadings('', 1);
};

const getReadings = async (query = null, page = 1) => {
  loadingReadings.value = true;
  try {
    if (page === 1) {
      showReadings.value = [] // Replace data on initial load
    }

    if (showingRoute.value) {
      search_filter.value = 'route=' + showingRoute.value.id
    }

    const result = await $BillingApiService.getReadings(props.billing.id, query, page, search_filter.value);
    if (page === 1) {
      showReadings.value = result.results; // Replace data on initial load
    } else {
      showReadings.value = [...showReadings.value, ...result.results]; // Append data on subsequent loads
    }


    Object.assign(pagination.value, {
      total: result.count,
      totalPages: Math.ceil(result.count / pagination.value.perPage),
      previous: result.previous,
      next: result.next,
      isFiltered: false
    });

  } catch (err) {
    console.error(err);
  } finally {
    loadingReadings.value = false;
  }
}

const loadMore = async () => {
  if (loadingInvoices.value || !pagination.value.next) return;

  pagination.value.page++;
  await getData(searchInput.value, pagination.value.page);
};

const getReadingBatches = async () => {
  readingBatches.value = null;
  const statusToken = await $ConfigProjectApiService.get('reading_batch_billing_pending_token');
  const batches = await $ReadingBatchApiService.getPendingBilling(statusToken);
  readingBatches.value = batches.results.map(batch => ({
    code: batch.id,
    label: batch.token + ' - ' + batch.name
  }));
  return batches;
}

const emitChange = () => {

  if (routes.value) {
    const reading_batches = routes.value.map(r => r.batch).filter(r => r !== null);

    let data = {
      reading_batches: reading_batches
    }

    emit('change', data);
  }
};

const assignReadings = async () => {
  if (confirm(t('confirmation_text_block.confirm_assign_batch'))) {
    assigning.value = true;
    try {
      const data = {
        reading_batch_ids: selectedReadingBatches.value.map(batch => batch.code)
      }
      const response = await $BillingApiService.assignReadings(props.billing.id, data);
      emit('readings-assigned');
      showDialog.value = false;
      readingsAssigned.value = true;
      loadData();
    } catch (err) {
      console.error(err);
    } finally {
      assigning.value = false;
    }
  }
}

  const handleSearch = () => {
    pagination.value.page = 1;
    debouncedGetData(searchInput.value);
  }

  const debouncedGetData = debounce((query) => {
    getReadings(query, pagination.value.page);
  }, 300);

  const loadData = async () => {
    routes.value = await $BillingApiService.getRoutes(props.billing.id);
    emitChange();
  };

  const excludeReading = async (reading_id) => {
    if (confirm(t('confirmation_text_block.confirm_exclude_reading'))) {
      const response = await $BillingApiService.exclude({ billing_id: props.billing.id, reading_id: reading_id });

      showReadings.value = showReadings.value.filter(reading => reading.id !== reading_id);

      loadData();
    }
  }

  onMounted(() => {
    loadData();
    checkReadingsAssigned();
  });

  const checkReadingsAssigned = () => {
    if (props.billing.total_readings && props.billing.total_readings > 0) {
      readingsAssigned.value = true;
    } else {
      readingsAssigned.value = false;
    }
  }

  watch(showDialog, (val) => {
    if (!val) {
      canClose.value = false;
    }
  });

  watch(props.billing, () => {
    checkReadingsAssigned();
  });

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center">
      <h2 class="text-xl font-semibold mb-4">{{ $t('billing_block.batches_to_bill') }}</h2>
      <!-- <button v-if="!readingsAssigned" @click="openDialog" class="button-primary"> -->
      <button @click.stop="openDialog" class="button-primary">
        {{ t('billing_block.select_reading_batch') }}
      </button>
    </div>

    <div class="mb-4">
      <div class="footering">
        <div :class="{ 'mt-1': routes.length != 0 }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="routes.length != 0" class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('route') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.date') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('readings') }}
            </span>
          </div>
          <div v-for="item in routes">
            <div v-if="item.route" class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
              <div class="p-2 text-slate-800">{{ item.route.name ?? item.route.token }}</div>
              <div class="p-2 text-slate-800 relative">
                {{ item.processed_at ? formatDate(item.processed_at) : t('billing_block.unprocessed_batch') }}
              </div>
              <div class="p-2 text-slate-800 relative">
                <span v-if="item.batch == null">{{ item.processed_readings ? item.processed_readings : 0 }}</span>
                <span v-else>{{ item.processed_readings ? item.processed_readings : 0 }} / {{
                  item.route.num_total_readings }}</span>

                <div v-if="readingsAssigned && item.warning" :title="$t('billing_block.missing_readings')"
                  class="absolute shadow-sm text-sm w-6 h-6 bg-yellow-400 right-8 top-1 rounded-full text-white">
                  <Icon name="fa6-solid:triangle-exclamation" class="mt-1" />
                </div>

                <button v-if="readingsAssigned" @click="view_readings(item)"
                  :title="`${t('common.check')} ${t('common.supplys')}`"
                  class="absolute shadow-sm text-sm w-6 h-6 bg-sky-400 right-1 top-1 rounded-full text-white transition-all duration-200 hover:bg-sky-600">
                  <Icon name="fa6-solid:eye" class="mt-1" />
                </button>
              </div>
            </div>
          </div>
        </div>

      </div>

      <Transition enter-active-class="transition duration-300 ease-out" enter-from-class="transform scale-95 opacity-0"
        enter-to-class="transform scale-100 opacity-100" leave-active-class="transition duration-200 ease-in"
        leave-from-class="transform scale-100 opacity-100" leave-to-class="transform scale-95 opacity-0">
        <div v-if="showDialog" v-click-outside="clickOutside"
          class="w-1/4 h-50 bg-white z-50 fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 rounded-md shadow-md">
          <div class="flex justify-between items-center p-4">
            <h2 class="text-xl font-semibold">{{ $t('billing_block.select_batch') }}</h2>
            <button @click="showDialog = false" class="hover:text-slate-700 p-2">
              <Icon name="fa6-solid:xmark" />
            </button>
          </div>
          <div class="p-4">
            <div class="mb-4">
              <div v-if="readingBatches?.length > 0" class="field mb-3">
                <label for="readingBatch" class="inline-block mb-1">{{ $t('billing_block.batches_to_bill')
                }}:</label>
                <v-select id="readingBatch" v-model="selectedReadingBatches" :options="readingBatches" multiple
                  class="input" :placeholder="$t('billing_block.select_reading_batch')" />
              </div>
              <div v-else-if="readingBatches?.length == 0" class="text-center text-yellow-500">
                <p>{{ $t('billing_block.no_batches_to_bill') }}</p>
                <Icon name="fa6-solid:triangle-exclamation" class="text-yellow-500" />
              </div>
              <div v-else class="flex justify-center items-center">
                <Icon name="fa6-solid:spinner" class="animate-spin" />
                <span class="ml-2">{{ $t('common.loading') }}...</span>
              </div>
            </div>
            <div class="flex justify-end">
              <button class="button-primary flex items-center" :disabled="selectedReadingBatches.length === 0 || assigning"
                @click="assignReadings">
                <Icon :name="assigning ? 'fa6-solid:spinner' : 'fa6-solid:plus'" class="mr-2" :class="assigning ? 'animate-spin' : ''" />
                <span v-if="!assigning">
                  {{ t('common.add') }} {{ t('readings') }}
                </span>
                <span v-else>
                  {{ t('common.loading') }}...
                </span>
              </button>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Regió lateral per formularis -->
      <div role="region" id="right_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
        :class="{
          'translate-x-0': showRegion,
          'translate-x-[2000px]': !showRegion,
          'w-[95%]': isSubRegionOpen,
          'w-[70%]': !isSubRegionOpen
        }">
        <div id="region_nav" class="mb-3 px-3">
          <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="px-10">
          <div class="flex flex-col h-full"> <!-- Added h-full here -->
            <H1>{{ t('readings') }}</H1>
            <span class="input-group flex flex-start items-center gap-2 w-80">
              <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
              <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
                :placeholder="$t('dashboard.search')"
                class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
            </span>
            <div>
              <div
                class="grid grid-cols-[3fr,2fr,2fr,2fr,1fr,50px] gap-2 px-4 divide-x divide-gray-200 border-b border-gray-400 items-center">
                <span class="p-3 font-bold">{{ t('contract') }}</span>
                <span class="p-3 font-bold">{{ t('reading') }}</span>
                <span class="p-3 font-bold">{{ t('billing_block.consumption') }}</span>
                <span class="p-3 font-bold">{{ t('billing_block.reading_date') }}</span>
                <span class="p-3 font-bold">{{ t('billing_block.estimated_reading') }}</span>
                <span class="p-3 font-bold">{{ t('billing_block.exclude') }}</span>
              </div>
            </div>
            <div class="overflow-y-auto flex-grow pb-10">
              <div v-for="reading in showReadings" :key="reading.id"
                class="grid grid-cols-[3fr,2fr,2fr,2fr,1fr,50px] gap-2 px-4 divide-x divide-gray-200 border-b border-gray-400 items-center">
                <div class="p-3">{{ reading.contract }}</div>
                <div class="p-3">{{ reading.reading_value }}</div>
                <div class="p-3">{{ reading.calculated_value }}</div>
                <div class="p-3">{{ reading.reading_date }}</div>
                <div class="p-3">
                  <Icon v-if="reading.is_estimated" name="fa6-solid:check" class="text-green-500" />
                  <span class="text-slate-400" v-else> - </span>
                </div>
                <div class="p-3">
                  <button class="h-6 w-6 bg-red-500 rounded-full text-white" @click="excludeReading(reading.id)">
                    <Icon name="fa6-solid:trash" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
