<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import PaymentRegion from '~/components/organisms/PaymentRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import AddSEPAManagement from '~/components/molecules/AddSEPAManagement.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();

const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    editingSEPA.value = false
  }
}

const route = useRoute();
const router = useRouter();
const { $MessageApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const regionComponent = ref(null)
const editingSEPA = ref(false)

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $MessageApiService.getAll(searchQuery, filters, page, sort, desc);

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

const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('invoice'), value: (row) => [row.invoice?.title_final, row.invoice?.token].filter(Boolean).join(' ') },
  { header: t('common.total'), value: (row) => Number(row.amount ?? 0), key: 'amount' },
  { header: t('billing_block.payment'), value: (row) => row.due_date ? formatDate(row.due_date) : '', key: 'due_date' },
  { header: t('common.status'), value: (row) => row.status?.name, key: 'status' },
  { header: t('billing_block.paid'), value: (row) => row.payment_date ? formatDate(row.payment_date) : '', key: 'payment_date' },
]);

const exportMessages = (columns) => $MessageApiService.exportData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, undefined, columns);

const resetFilters = () => {
  searchInput.value = '';
  sortBy.value = null
  selectedFilters.value = []
  pagination.value.page = 1;
  getData();
};

onMounted(() => {
  getData();
  checkRouteQuery()
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
  }
}

const showDetail = (id) => {
  detail.value = id;
  selectedItemId.value = id;
  editingSEPA.value = false;
  toggleRegion(true);
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
      <H1 class="mb-2">{{ $t('messages') }}</H1>
      <span>
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="messages"
          :total-pages="pagination.totalPages" :server-export-fn="exportMessages" />
      </span>
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
      grid-template="150px,250px,100px,150px,100px,100px,100px"
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
        <TableHeader :label="$t('billing_block.payment')" sortKey="due_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.paid')" sortKey="payment_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <span></span>
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId, 'bg-purple-50': item.is_excluded && !(item.id === selectedItemId)  }">
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>

          <span class="p-1">{{ item.invoice.title_final + ' ' + item.invoice.token }}</span>
          <span class="p-1">{{ item.amount }}</span>

          <span v-if="!item.is_late"> {{ item.due_date ? formatDate(item.due_date) : '-' }}</span>
          <span v-else>
            <AtomsColorBadge :value="formatDate(item.due_date)" :color="'red'">
            </AtomsColorBadge>
          </span>
          <span class="p-1">
            <AtomsColorBadge :value="item.status?.name" :color="item.status?.color">
            </AtomsColorBadge>
          </span>
          <span class="p-1">{{ item.payment_date ? formatDate(item.payment_date) : '-' }}</span>
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
    <div v-if="showRegion" class="px-10">
      <PaymentRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
        @changed="getData" />
    </div>
  </div>

</template>
