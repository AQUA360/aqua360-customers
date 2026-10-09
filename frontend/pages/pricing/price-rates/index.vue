<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
//import OrderRegion from '~/components/organisms/OrderRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import PriceRateRegion from '~/components/organisms/PriceRateRegion.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const route = useRoute()
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
    selectedItemId.value = null
  }
}

const router = useRouter();
const { $PriceRateApiService, $ConfiglistApiService, $ProductApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_prod = ref([]);
//const selectedProduct = ref(null);
const selected_elements = ref([]);
const selectedFilters = ref([]);
const filter_origin = ref([]);
const selected_origins = ref([]);
const origins = ref([]);
const sortBy = ref('product');
const sortDesc = ref(false);
const permissions = ref(null);
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
    const data = await $PriceRateApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'product', desc = false) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;

  try {
    const data = await $PriceRateApiService.getAll(searchQuery, filters, page, sort, desc, null, origins.value);
    items.value = data.results;
    // muntem la paginacio
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

const getFilterProducts = async () => {
  error.value = null;
  try {
    const data = await $ProductApiService.getAll();
    filter_prod.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterOrigins = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('pricing/product-origin');
    //filter_origin.value = data.results;
    data.results.forEach(item => {
      filter_origin.value.push({
        name: item.name,
        id: item.token
      })
    })
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value);
}

const handleFiltersSelectChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'product') && !newFilters.some(filter => filter.id === 'product')) {
    filter_origin.value = [];
    selected_origins.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'origin') && !newFilters.some(filter => filter.id === 'origin')) {
    origins.value = [];
    selected_origins.value = [];
    getData();
  }
}

const handleFilterProductChange = (event) => {
  selected_elements.value = event;
  selectedFilters.value = []
  selected_elements.value.forEach(element => {
    selectedFilters.value.push(element.id);
  })

  pagination.value.page = 1;
  handleSearch();
}

const handleFilterOriginChange = (event) => {
  selected_origins.value = event;
  origins.value = []
  selected_origins.value.forEach(element => {
    origins.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  selected_elements.value = []
  selected_origins.value = []
  origins.value = [];
  isFilterShown.value = [];
  pagination.value.page = 1;
  isFilterOpen.value = false
  getData();
};

const onChangeRegion = (event) => {
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
}

// XLSX export — columns mirror the visible table columns (in display order).
const exportColumns = computed(() => [
  { header: t('common.creation'), value: (row) => row.created_at ? formatDate(row.created_at) : '', key: 'created_at' },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.name'), value: (row) => row.name, key: 'name' },
  { header: t('product'), value: (row) => row.product?.name || '', key: 'product' },
]);

// Hybrid export: single page → client-side; multiple pages → server (all-pages, filter-aware).
const exportPriceRates = (columns) => $PriceRateApiService.exportData(
  searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, null, origins.value,
  undefined, columns,
);

const showDetail = async (id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    if (route.query?.pr_id) {
      showDetail(route.query.pr_id)
    } 
  } else {
    if (route?.query?.id) {
      showDetail(route.query.id);
    }
  }
}

onMounted(async() => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  filtersExtra.value.push(
    { name: t('common.products'), id: "product" },
    { name: t('common.origins'), id: "origin" },
  );
  await getFilterOrigins()
  await getData();
  await getFilterProducts();
  checkRouteQuery()
});

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
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
      <H1 class="mb-2">{{ t('pricing') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="price-rates"
          :total-pages="pagination.totalPages" :server-export-fn="exportPriceRates" :sheet-name="t('pricing')" />
        <NuxtLink v-if="permissions?.can_change" to="/pricing/price-rates/add" class="button-primary">{{ t('pricing_block.new_price_rate') }}</NuxtLink>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
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

    <div class="px-2 text-base flex flex-start gap-2 justify-start items-center" v-if="isFilterOpen">

      <FilterSelect :options="filter_prod" v-if="isFilterShown.some(filter => filter.id === 'product')"
        :filters="selected_elements" :multiple="false" :placeholder="t(`common.products`)"
        @update:modelValue="handleFilterProductChange($event)">
        <template #icon>
          <Icon name="fa6-solid:cube" class="text-slate-500 " />
        </template>
      </FilterSelect>

      <FilterSelect :options="filter_origin" v-if="isFilterShown.some(filter => filter.id === 'origin')"
        :filters="selected_origins" :multiple="true" :placeholder="t(`common.origins`)"
        @update:modelValue="handleFilterOriginChange($event)">
        <template #icon>
          <!-- icon for origin that is not cube -->
          <Icon name="fa6-solid:circle-info" class="text-slate-500 " />
        </template>
      </FilterSelect>

      <FilterSelect :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
        :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersSelectChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>

    <DataTable
      grid-template="80px,1fr,1fr,1fr"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="t('common.creation')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="t('product')" sortKey="product" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span class="p-1 text-nowrap" :title="formatDate(item.created_at)">{{ formatDate(item.created_at) }}</span>
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.product.name" class="no-underline">{{ item.token }}</abbr>
            </button>
          </span>
          <span class="p-1 text-nowrap" :title="item.name">{{ item.name }}</span>
          <span class="p-1 text-nowrap"><abbr :title="item.product?.token || null">{{ item.product?.name || null
          }}</abbr></span>
        </div><!-- end for items -->
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all overflow-x-hidden duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <PriceRateRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="onChangeRegion" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>
