<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import ProductRegion from '~/components/organisms/ProductRegion.vue';
import Draggable from 'vuedraggable';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const route = useRoute()
const toast = useToast();
const config = useRuntimeConfig();
const apiHost = config.public.apiHost;
const showRegion = ref(false);
const isSorting = ref(false);

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
const { $ProductApiService, $apiManager } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('order_priority');
const sortDesc = ref(false);
const apiUrl = ref(apiHost + '/pricing/product/');
const permissions = ref(null);

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
    const data = await $ProductApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    // Si no hi ha ordenació específica, aplicar ordenació per defecte
    let defaultSort = null;
    if (!sort) {
      defaultSort = 'order_priority';
    } else {
      defaultSort = sort;
    }
    
    const data = await $ProductApiService.getList(searchQuery, filters, page, defaultSort, desc);
    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    console.log('items', items.value);

    nextTick(() => {
      document.getElementById('searchInput').focus();
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value);
}

const handleFilterChange = () => {
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

const gridTemplate = computed(() => '100px,120px,80px,2.5fr,1.5fr,100px,1fr');

// XLSX export — columns mirror the visible table columns (in display order).
const exportColumns = computed(() => [
  { header: t('common.creation_date'), value: (row) => row.created_at ? formatDate(row.created_at) : '', key: 'created_at' },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('pricing_block.order_priority'), value: (row) => row.order_priority ?? '', key: 'order_priority' },
  { header: t('common.name'), value: (row) => row.name, key: 'name' },
  { header: t('exploitation'), value: (row) => row.exploitation_name, key: 'exploitation' },
  { header: t('common.origin'), value: (row) => row.origin_name, key: 'origin' },
  { header: t('common.related'), value: (row) => row.product_related_name || '', key: 'product_related' },
]);

// Hybrid export: single page → client-side; multiple pages → server (all-pages, filter-aware).
const exportProducts = (columns) => $ProductApiService.exportData(
  searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, columns,
);

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  sortBy.value = 'order_priority';
  sortDesc.value = false;
  pagination.value.page = 1;
  getData();
};
function onDraggableEnd(event) {
  const items_positions = items.value.map(item => item.id);
  $apiManager.fetch(apiUrl.value + 'update-positions/', 'POST', JSON.stringify(items_positions));
}

const onChangeRegion = (event) => {
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
}

onMounted(async() => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getData('', [], 1, 'order_priority', false);
  //getFilterStatus();
  checkRouteQuery()
});

const checkRouteQuery = () => {
  if (route.query?.id) {
    showDetail(route.query.id)
  }
}

const showDetail = async (id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

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
      <H1 class="mb-2">{{ $t('common.products') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="products"
          :total-pages="pagination.totalPages" :server-export-fn="exportProducts" :sheet-name="$t('common.products')" />
        <div v-if="permissions?.can_change">
          <button class="button-default mr-2" @click="isSorting = !isSorting">
            <Icon name="fa6-solid:arrow-up-a-z" class="text-slate-500" />
          <!--   {{ $t('Ordena') }} -->
          </button>
          <NuxtLink to="/pricing/products/add" class="button-primary">{{ $t('pricing_block.new_product') }}</NuxtLink>
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

      <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>
    <DataTable
      :grid-template="gridTemplate"
      :pin-column="isSorting"
      pin-column-width="40px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.creation_date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('pricing_block.order_priority')" sortKey="order_priority" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('exploitation')" :sortable="false" />
        <TableHeader :label="$t('common.origin')" sortKey="origin" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.related')" sortKey="product_related" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <Draggable v-if="permissions?.can_view" v-model="items" itemKey="id" handle=".handle-move" class="dragArea" @end="onDraggableEnd">
          <template #item="{ element: item }">
            <div class="gap-3 text-base border-b items-center bg-white" :style="gridStyle">
              <span v-if="isSorting" class="text-slate-900 p-1 border-r">
                <button class="handle-move cursor-move">
                  <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500 block-inline mr-1" />
                  <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500" />
                </button>
              </span>
              <span class="p-1 text-nowrap truncate min-w-0" :title="formatDate(item.created_at)">{{ formatDate(item.created_at) }}</span>
              <span class="text-slate-900 p-1 cursor_pointer relative truncate min-w-0">
                <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-left truncate min-w-0"
                  @click="showDetail(item.id);">
                  <abbr :title="item.token" class="no-underline truncate min-w-0">{{ item.token }}</abbr>
                </button>
              </span>
              <span class="text-slate-900 p-1 cursor_pointer relative truncate min-w-0">
                <span class="p-1 text-nowrap">{{ item.order_priority || '-' }}</span>
              </span>
              <span class="text-slate-900 p-1 cursor_pointer relative truncate min-w-0" :title="item.name">
                <span class="p-1 truncate block min-w-0">{{ item.name }}</span>
              </span>
              <span class="text-slate-900 p-1 cursor_pointer relative truncate min-w-0" :title="item.exploitation_name">
                <span class="p-1 truncate block min-w-0">{{ item.exploitation_name }}</span>
              </span>
              <span class="text-slate-900 p-1 font-semibold truncate min-w-0" :title="item.origin_name">
                <span class="p-1 truncate block min-w-0">{{ item.origin_name }}</span>
              </span>
              <span class="text-slate-900 p-1 truncate min-w-0" :title="item.product_related_name">
                <span class="p-1 truncate block min-w-0" v-if="item.product_related_name">{{ item.product_related_name }}</span>
                <span class="p-1 text-nowrap" v-else>{{ ' - ' }}</span>
              </span>
            </div>
          </template>
        </Draggable>
      </template>
    </DataTable>
    
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-40"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <ProductRegion v-if="detail" :id="parseInt(detail)" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="onChangeRegion" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>
