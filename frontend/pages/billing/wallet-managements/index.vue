<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import PaymentRegion from '~/components/organisms/PaymentRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import AddSEPAManagement from '~/components/molecules/AddSEPAManagement.vue';
import SEPARemittanceList from '~/components/organisms/SEPARemittanceList.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';
const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    detail.value = null
    openSEPA.value = false;
    selectedItemId.value = null
  }
}

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
const regionComponent = ref(null)
const openSEPA = ref(false)
const openIndexDropdown = ref(false)
const permissions = ref(null);
const statuses = ref([])
const selected_payment_types = ref([])
const payment_types = ref([])
const filter_payment_type = ref([])

const filter_payment_origin = ref([
 { id: 'box_office', name: t('billing_block.box_office') },
 { id: 'post_office', name: t('billing_block.post_office') }
])
const selected_payment_origins = ref([])
const payment_origins = ref([])

const filter_return_reasons = ref([]);
const selected_return_reasons = ref([]);
const return_reasons = ref([]);

const selectedPaymentDate = ref([]);
const payment_date = ref({});

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $PaymentApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, pay_type = [], ret_reasons = [], pay_origin = []) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const startDate =
      payment_date.value?.start_date && payment_date.value?.end_date
        ? payment_date.value.start_date
        : null;
    const endDate =
      payment_date.value?.start_date && payment_date.value?.end_date
        ? payment_date.value.end_date
        : null;

    const data = await $PaymentApiService.getAll( searchQuery, filters, page, sort, desc, null, null, null, null, [], startDate, endDate, null, pay_type, false, null, null, null, ret_reasons, pay_origin);

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

// XLSX export — columns mirror the visible table columns (in display order).
const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('invoice'), value: (row) => row.name, key: 'name' },
  { header: t('common.total'), value: (row) => row.amount, key: 'amount' },
  { header: t('billing_block.payment'), value: (row) => row.payment_date ? formatDate(row.payment_date) : '', key: 'payment_date' },
  { header: t('common.payment_method'), value: (row) => row.payment_type, key: 'payment_type' },
  { header: t('common.status'), value: (row) => row.status?.name, key: 'status' },
  { header: t('billing_block.payment_origin'), value: (row) => row.payment_origin === 'box_office' ? t('billing_block.box_office') : (row.payment_origin === 'post_office' ? t('billing_block.post_office') : '') },
  { header: t('common.limit'), value: (row) => row.due_date ? formatDate(row.due_date) : '', key: 'due_date' },
  { header: t('common.return_reason'), value: (row) => row.reject?.name || row.reject?.token || '' },
]);

// Hybrid export: single page → client-side; multiple pages → server (all-pages, filter-aware).
const exportWalletManagements = (columns) => {
  const startDate = payment_date.value?.start_date && payment_date.value?.end_date ? payment_date.value.start_date : null;
  const endDate = payment_date.value?.start_date && payment_date.value?.end_date ? payment_date.value.end_date : null;
  return $PaymentApiService.exportData(
    searchInput.value, statuses.value, sortBy.value, sortDesc.value, null, null, null, null,
    [], startDate, endDate, null, payment_types.value, false, null, null, null,
    return_reasons.value, payment_origins.value, columns
  );
};

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/payment-status')
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterPaymentType = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    //filter_payment_type.value = data.results;
    filter_payment_type.value = [
      {
        id: null,
        token: '',
        name: t('None'),
      },
      ...(data.results || []), // Ensure data.results exists and is an array
    ];
  } catch (err) {
    error.value = err;
  }
}

const getFilterReturnReasons = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/reject-motive');

    filter_return_reasons.value = (data.results || []).map(rr => ({
      id: Number(rr.id),
      name: rr.name,
      token: rr.token
    }));
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc, pay_type, ret_reasons, pay_origin) => {
  getData(query, filters, pagination.value.page, sort, desc, pay_type, ret_reasons, pay_origin);
}, 300);

const handlePaymentDateChange = (event) => {
  payment_date.value = event || {};
  pagination.value.page = 1;
  handleSearch();
};

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value, payment_types.value, return_reasons.value, payment_origins.value);
}

const handleFiltersChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'payment_type') && !newFilters.some(filter => filter.id === 'payment_type')) {
    payment_types.value = [];
    selected_payment_types.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'status') && !newFilters.some(filter => filter.id === 'status')) {
    statuses.value = [];
    selectedFilters.value = [];
    getData();
  } 
  else if (isFilterShown.value.some(filter => filter.id === 'return_reason') && !newFilters.some(filter => filter.id === 'return_reason')) {
      return_reasons.value = [];
      selected_return_reasons.value = [];
      getData();
  }
  else if (isFilterShown.value.some(filter => filter.id === 'payment_origin') && !newFilters.some(filter => filter.id === 'payment_origin')) {
    payment_origins.value = [];
    selected_payment_origins.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'payment_date') && !newFilters.some(filter => filter.id === 'payment_date')) {
    payment_date.value = {};
    selectedPaymentDate.value = [];
    getData();
  }
}

const handlePayTypeChange = (event) => {
  selected_payment_types.value = event;
  payment_types.value = []
  selected_payment_types.value.forEach(element => {
    payment_types.value.push(element.id);
  })

  pagination.value.page = 1;
  handleSearch();
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

const handleReturnReasonChange = (event) => {
  selected_return_reasons.value = event;
  return_reasons.value = [];

  selected_return_reasons.value.forEach(el => {
    return_reasons.value.push(el.id);
  });

  pagination.value.page = 1;
  handleSearch();
};

const handlePayOriginChange = (event) => {
  selected_payment_origins.value = event;
  payment_origins.value = [];

  selected_payment_origins.value.forEach(el => {
    payment_origins.value.push(el.id);
  });

  pagination.value.page = 1;
  handleSearch();
};

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, statuses.value, newPage, sortBy.value, sortDesc.value, payment_types.value, return_reasons.value, payment_origins.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value, payment_types.value, return_reasons.value, payment_origins.value);
}

const resetFilters = () => {
  searchInput.value = '';
  sortBy.value = null;
  selectedFilters.value = [];
  statuses.value = [];
  selected_payment_types.value = [];
  selected_return_reasons.value = [];
  return_reasons.value = [];
  selected_payment_origins.value = [];
  payment_origins.value = [];
  payment_date.value = {};
  selectedPaymentDate.value = [];
  isFilterShown.value = [];
  isFilterOpen.value = false;
  pagination.value.page = 1;
  getData();
};


const showDetail = async (id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    filtersExtra.value.push(
      { name: t('common.status'), id: "status" },
      { name: t('common.payment_method'), id: "payment_type" },
      { name: t('common.return_reason'), id: "return_reason" },
      { name: t('billing_block.payment_origin'), id: "payment_origin" },
      { name: t('billing_block.payment_date'), id: "payment_date" },
    );
    getData();
    getFilterStatus();
    getFilterPaymentType();
    await getFilterReturnReasons();
    checkRouteQuery()
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
  }
  else {
    console.log("route.query", route.query);
    if (route?.query?.id) {
      console.log("found id");
      showDetail(route.query.id);
    }
  }
};

const openSEPARemittances = async () => {
  await toggleRegion(false);
  openIndexDropdown.value = false;
  openSEPA.value = true;
  toggleRegion(true);
}

const toggleIndexDropdown = () => {
  openIndexDropdown.value = !openIndexDropdown.value
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('payment') }}</H1>

      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="wallet_managements"
          :total-pages="pagination.totalPages" :server-export-fn="exportWalletManagements" :sheet-name="t('payment')" />

        <div class="relative inline-block">
          <button v-if="permissions?.can_add" class="button-default flex items-center gap-3 relative" @click="toggleIndexDropdown()">
            <Icon name="fa6-solid:bars" class="p-1" />
            {{ t('common.operations') }}
          </button>

          <div v-if="openIndexDropdown"
            class="absolute top-full right-0 bg-white flex flex-col gap-2 rounded customers-shadow p-2 w-[300px] z-10">
            <!-- <NuxtLink to="/billing/wallet-managements/manage-sii" class="button-default">
              <div class="flex justify-between items-center">
                {{ $t('billing_block.mng_sii') }}
                <Icon name="fa6-solid:file-export" class="display-inline mr-2" />
              </div>
            </NuxtLink> -->
            <!-- <NuxtLink to="/billing/wallet-managements/manage" class="button-default">
              <div class="flex justify-between items-center">
                {{ $t('billing_block.short_mng_sepa') }}
                <Icon name="fa6-solid:file-export" class="display-inline mr-2" />
              </div>
            </NuxtLink>
            <button @click="openSEPARemittances" class="button-default">
              <div class="flex justify-between items-center">
                {{ $t('billing_block.send_sepa') }}
                <Icon name="fa-solid:share" class="display-inline mr-2" />
              </div>
            </button>
            <NuxtLink to="/billing/wallet-managements/return-sepa" class="button-default">
              <div class="flex justify-between items-center">
                {{ $t('billing_block.short_mng_return_sepa') }}
                <Icon name="fa6-solid:money-bill-transfer" class="display-inline mr-2" />
              </div>
            </NuxtLink> -->
            <NuxtLink to="/billing/wallet-managements/return-bank" class="button-default">
              <div class="flex justify-between items-center">
                {{ $t('billing_block.short_mng_return_bank') }}
                <Icon name="fa6-solid:money-bill-transfer" class="display-inline mr-2" />
              </div>
            </NuxtLink>
            <NuxtLink to="/billing/deliquency-requests/add" class="button-default">
              <div class="flex justify-between items-center">
                {{ $t('billing_block.short_mng_delinquent') }}
                <Icon name="fa6-solid:user-slash" class="display-inline mr-2" />
              </div>
            </NuxtLink>
            <!-- <NuxtLink to="/billing/reports/add" class="button-default">
              <div class="flex justify-between items-center">
                {{ $t('common.reports') }}
                <Icon name="fa6-solid:coins" class="display-inline mr-2" />
              </div>
            </NuxtLink> -->
          </div>
        </div>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <!-- <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
      </span> -->

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

    <div class="px-2 text-base flex flex-start gap-2 justify-start items-center" v-if="isFilterOpen">

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'payment_date')" :datePick="true"
        :filters="selectedPaymentDate" :placeholder="t(`billing_block.payment_date`)"
        @update:modelValue="handlePaymentDateChange($event)">
        <template #icon>
          <Icon name="fa6-solid:calendar" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'status')" :options="filter_status"
        :filters="selectedFilters" :multiple="true" :placeholder="t(`common.statuses`)"
        @update:modelValue="handleStatusChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'payment_type')" :options="filter_payment_type"
        :filters="selected_payment_types" :multiple="false" :placeholder="t(`common.type`)"
        @update:modelValue="handlePayTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:cube" class="text-slate-500 " />
        </template>
      </FilterSelect>

      
      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'return_reason')" :options="filter_return_reasons" 
        :filters="selected_return_reasons" :multiple="true" :placeholder="t('common.return_reason')"
        @update:modelValue="handleReturnReasonChange($event)">
        <template #icon>
          <Icon name="fa6-solid:arrow-rotate-left" class="text-slate-500" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'payment_origin')" :options="filter_payment_origin" 
        :filters="selected_payment_origins" :multiple="true" :placeholder="t('billing_block.payment_origin')"
        @update:modelValue="handlePayOriginChange($event)">
        <template #icon>
          <Icon name="fa6-solid:money-bill-transfer" class="text-slate-500" />
        </template>
      </FilterSelect>


      <FilterSelect :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
        :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>
    <DataTable
      grid-template="110px,2fr,90px,110px,130px,110px,110px,110px,1.5fr,100px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('invoice')" sortKey="invoice" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.total')" sortKey="amount" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.payment')" sortKey="payment_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.payment_method')" sortKey="payment_type" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.payment_origin')" sortKey="payment_origin" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.limit')" sortKey="due_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.return_reason')" sortKey="reject__name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <span></span>
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId, 'bg-purple-50': item.is_excluded && !(item.id === selectedItemId) }">
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>

          <span class="p-1">{{ item.name }}</span>
          <span class="p-1">{{ formatMoneyWithCurrency(item.amount) }}</span>

          <span class="p-1">{{ item.payment_date ? formatDate(item.payment_date) : '-' }}</span>
          <span class="p-1">
            {{ item.payment_type }}
          </span>
          <span class="p-1">
            <AtomsColorBadge :value="item.status?.name" :color="item.status?.color">
            </AtomsColorBadge>
          </span>
          <span class="p-1">
            {{ item.payment_origin === 'box_office' ? t('billing_block.box_office') : (item.payment_origin === 'post_office' ? t('billing_block.post_office') : '-') }}
          </span>
          <span v-if="!item.is_late"> {{ item.due_date ? formatDate(item.due_date) : '-' }}</span>
          <span v-else>
            <AtomsColorBadge :value="formatDate(item.due_date)" :color="'red'">
            </AtomsColorBadge>
          </span>
          <span class="p-1">
            {{ item.reject?.name || item.reject?.token || '-' }}
          </span>
          <span class="p-1">
            <AtomsColorBadge v-if="item.is_excluded" :value="$t('billing_block.excluded')" :color="'purple'" />
          </span>
        </div><!-- end for items -->
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[50%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div v-if="showRegion" class="pl-10 h-full">
      <PaymentRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="getData" @close-subregion="toggleRegion(false)" />
      <SEPARemittanceList v-if="openSEPA" :id="openSEPA" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="getData" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>
