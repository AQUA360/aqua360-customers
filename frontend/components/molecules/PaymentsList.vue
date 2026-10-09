<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import Pagination from '~/components/molecules/Pagination.vue';
import H1Region from '../atoms/H1Region.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import PaymentRegion from '~/components/organisms/PaymentRegion.vue';
import InvoiceRegion from '../organisms/InvoiceRegion.vue';
import CommitmentDepositRegion from '../organisms/CommitmentDepositRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();

const props = defineProps({
  remittance_id: {
    type: String,
    required: true
  },
  info: Object,
  // Show a "Download XLSX" button that exports exactly the rows/columns shown.
  exportable: {
    type: Boolean,
    default: true
  },
  exportFileName: {
    type: String,
    default: 'payments'
  }
});

const route = useRoute();
const router = useRouter();
const { $PaymentApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);

const statuses = ref([])

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const showRegion = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

// Column definitions for the XLSX export — mirror the visible columns above.
const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('invoice'), value: (row) => row.invoice ? row.invoice.serie_final : t('commitment_deposit') },
  { header: t('common.total'), value: (row) => Number(row.amount ?? 0), key: 'amount' },
  { header: t('billing_block.payment'), value: (row) => row.payment_date ? formatDate(row.payment_date) : '', key: 'payment_date' },
  { header: t('common.status'), value: (row) => row.status?.name, key: 'status' },
  { header: t('common.limit'), value: (row) => row.due_date ? formatDate(row.due_date) : '', key: 'due_date' },
]);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    detail.value = null
    selectedItemId.value = null
    selectedItemComponent.value = null
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $PaymentApiService.getAll(
      searchQuery, filters, page, sort, desc,
      null, null, null, null,
      [], null, null, null,
      [], false, null, props.remittance_id
    );

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      document.getElementById('searchInput').focus();
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/payment-status')
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value);
}

const handleFiltersChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'status') && !newFilters.some(filter => filter.id === 'status')) {
    statuses.value = [];
    selectedFilters.value = [];
    getData();
  }
}

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  statuses.value = []
  selectedFilters.value.forEach(element => {
    statuses.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, statuses.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  sortBy.value = null
  selectedFilters.value = []
  statuses.value = []
  isFilterShown.value = []
  isFilterOpen.value = false
  pagination.value.page = 1;
  getData();
};

onMounted(() => {
  filtersExtra.value.push(
    { name: t("common.status"), id: "status" },
  );
  console.log(props)
  getData();
  getFilterStatus();
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
    router.replace({
      path: route.path
    });
  }
});

const detail = ref(null);
const selectedItemId = ref(null);
const selectedItemComponent = ref(null);
const showDetail = async (component, id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  selectedItemComponent.value = component;
  toggleRegion(true);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

</script>

<template>
  <div id="wrapper" class="region__content">
    <div class="transition-all duration-500 ease" :class="{ 'mr-[48%]': showRegion }">
      <H1Region>
        {{ $t('billing_block.payments') }}:
        <span v-if="info.date">({{ formatDate(info.date) }})</span>
      </H1Region>
      <span class="truncate text-slate-400 text-sm mb-2">{{ info?.token }}</span>

      <form id="form_filter" role="search"
        class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
        @submit.prevent="handleSearch">

        <span class="input-group flex flex-start items-center gap-2 w-80">
          <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
          <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
            :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
            autocomplete="off" />
        </span>

        <span>
          <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
            @click="isFilterOpen = !isFilterOpen" title="show">
            <Icon name="fa:filter" class="text-slate-500" />
          </button>
        </span>

        <span>
          <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
            @click="resetFilters" title="reset">
            <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
          </button>
        </span>
      </form>

      <div class="mb-2 px-2 text-base flex flex-start gap-2 justify-start items-center" v-if="isFilterOpen">

        <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'status')" :options="filter_status"
          :filters="selectedFilters" :multiple="true" :placeholder="t('common.statuses')"
          @update:modelValue="handleStatusChange($event)">
          <template #icon>
            <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
          </template>
        </FilterSelect>


        <FilterSelect :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
          :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
          <template #icon>
            <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
          </template>
        </FilterSelect>

      </div>

      <div v-if="exportable && items?.length > 0" class="flex justify-end mb-1">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" :file-name="exportFileName" />
      </div>

      <div id="list" :style="{
        overflowY: 'auto',
        width: 'calc(-295px + 100vw)',
        maxWidth: '100%',
        minHeight: 'calc(100vh - 200px)',
        maxHeight: 'calc(100vh - 200px)',
      }">
        <div
          class="heading sticky top-0 bg-white grid grid-cols-[120px,150px,100px,80px,100px,80px] gap-3 text-base border-b items-center">
          <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('invoice')" sortKey="invoice" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('common.total')" sortKey="amount" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('billing_block.payment')" sortKey="payment_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('common.limit')" sortKey="due_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <span></span>
        </div>

        <div v-if="pending">
          <AppLoading :text="$t('common.loading')" :size="40" />
        </div>
        <div v-else-if="error">
          <p>Error: {{ error.message }}</p>
          <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
              }}</button></p>
        </div>
        <div v-else>
          <div v-for="item in items" :key="item.id"
            class="grid grid-cols-[120px,150px,100px,80px,100px,80px] gap-3 text-base border-b items-center"
            :class="{ 'bg-yellow-50': item.id === selectedItemId, 'bg-purple-50': item.is_excluded && !(item.id === selectedItemId) }">
            <span>
              <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                @click="showDetail(item.invoice ? 'InvoiceRegion' : 'CommitmentDepositRegion', item.invoice ? item.invoice.id : item.commitment_deposit.id);">
                <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
                <Icon name="fa6-solid:eye"
                  class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
              </button>
            </span>

            <span v-if="item.invoice" class="p-1 truncate">{{ item.invoice.serie_final 
              }}</span>
            <span v-else class="p-1 truncate">{{ t('commitment_deposit') }}</span>
            <span class="p-1">{{ formatMoneyWithCurrency(item.amount) }}</span>

            <span class="p-1">{{ item.payment_date ? formatDate(item.payment_date) : '-' }}</span>
            <span class="p-1">
              <AtomsColorBadge :value="item.status?.name" :color="item.status?.color">
              </AtomsColorBadge>
            </span>
            <span class="p-1">{{ item.due_date ? formatDate(item.due_date) : '-' }}</span>
          </div><!-- end for items -->

          <div v-if="items.length === 0" class="my-3">
            <p class="text-">{{ $t('common.no_records') }}</p>
          </div>

        </div><!-- else no-error no-pending -->
      </div><!-- end list -->
      <div id="list__footer">
        <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
      </div>
    </div>
    <div role="region" id="subregion"
      class="fixed top-0 right-0 text-base w-[48%] z-10 overflow-y-auto overflow-x-hidden h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <InvoiceRegion v-if="selectedItemComponent == 'InvoiceRegion'" :id="detail" :isSubRegion="true" />
        <CommitmentDepositRegion v-if="selectedItemComponent == 'CommitmentDepositRegion'" :id="detail" :isSubRegion="true" />
      </div>
    </div>
  </div><!-- end wrapper -->
</template>
