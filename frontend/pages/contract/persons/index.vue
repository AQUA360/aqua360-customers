<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import PersonRegion from '~/components/organisms/PersonRegion.vue';
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
    selectedItemId.value = null
  }
}

const route = useRoute();
const router = useRouter();
const { $PersonApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref(null);
const sortDesc = ref(false);
const permissions = ref(null);

const filter_is_juridic = ref([]);//filter options
const selected_is_juridic_filter = ref(null);//selected value 
// Només persones amb un procés d'insolvència obert
const insolvencyFilter = ref(false);
const extraFilters = () => (insolvencyFilter.value ? { insolvency: 'true' } : {});

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
    const data = await $PersonApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.name'), value: (row) => row.name, key: 'name' },
  { header: t('common.surname'), value: (row) => row.surname, key: 'surname' },
  { header: t('contract_block.is_juridic'), value: (row) => row.is_juridic ? t('common.yes') : t('common.no'), key: 'is_juridic' },
  { header: t('contract_block.vulnerability'), value: (row) => row.vulnerability_level, key: 'vulnerability_level' },
  { header: t('common.debt'), value: (row) => row.debt_amount, key: 'debt_amount' },
]);

const exportPersons = (columns) => $PersonApiService.exportData(
  searchInput.value, [], sortBy.value, sortDesc.value,
  selected_is_juridic_filter.value ? [selected_is_juridic_filter.value] : [], columns, extraFilters()
);

const getData = async (searchQuery = '', filters = [], juridicFilter = null, page = 1, sort = null, desc = false) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $PersonApiService.getAll(searchQuery, filters, page, sort, desc, juridicFilter ? [juridicFilter] : [], extraFilters());

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || insolvencyFilter.value
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

const debouncedGetData = debounce((query, filters, juridicFilter, sort, desc) => {
  getData(query, filters, juridicFilter, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, [] ,selected_is_juridic_filter.value, sortBy.value, sortDesc.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, [], selected_is_juridic_filter.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, [], selected_is_juridic_filter.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  selected_is_juridic_filter.value = null;
  insolvencyFilter.value = false;
  getData();
};

onMounted(async() => {
  await getPermissions();
  if (permissions.value?.can_view) {

    filter_is_juridic.value = [
      { id: 'true', name: t('common.yes') },
      { id: 'false', name: t('common.no') },
    ]

    getData();
    checkRouteQuery()
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
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
const rowClass = (item) => ({
  'bg-yellow-50': item.id === selectedItemId.value,
});

const tableColumns = computed(() => [
  {
    key: 'token', label: t('common.identification'), sortKey: 'token',
    width: 130, min: 105, priority: 1, removable: false,
  },
  { key: 'name', label: t('common.name'), sortKey: 'name', width: 160, grow: 1, min: 100, priority: 1, removable: false },
  { key: 'surname', label: t('common.surname'), sortKey: 'surname', width: 160, grow: 1, min: 100, priority: 1 },
  {
    key: 'is_juridic', label: t('contract_block.is_juridic'), sortKey: 'is_juridic',
    width: 150, min: 90, priority: 2, cellClass: 'flex items-center justify-center', headerClass: 'justify-center',
  },
  {
    key: 'vulnerability', label: t('contract_block.vulnerability'),
    width: 100, min: 80, priority: 3, cellClass: 'flex items-center justify-center', headerClass: 'justify-center',
  },
  {
    key: 'debt_amount', label: t('common.debt'),
    width: 125, min: 100, priority: 2, cellClass: 'flex items-center justify-center', headerClass: 'justify-center',
  },
]);

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('common.persons') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="persons"
          :total-pages="pagination.totalPages" :server-export-fn="exportPersons" :sheet-name="t('common.persons')" />
        <NuxtLink v-if="permissions?.can_add" to="/contract/persons/add" class="button-primary">{{
          $t('contract_block.new_person') }}</NuxtLink>
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

      <div class="h-8 w-px bg-gray-300"></div>

      <span class="flex gap-3">
        <label class="text-slate-800 text-base flex items-center gap-1">
          {{ $t('contract_block.is_juridic') }}
        </label>
        <label v-for="option in filter_is_juridic" :key="option.id" class="text-slate-800 text-base flex
         items-center gap-1">
          <input type="radio" v-model="selected_is_juridic_filter" name="juridic_filter_radio" :value="option.id"
            @change="handleFilterChange" />
          {{ option.name }}
        </label>
      </span>

      <div class="h-8 w-px bg-gray-300"></div>

      <label class="text-slate-800 text-base flex items-center gap-1">
        <input type="checkbox" v-model="insolvencyFilter" @change="handleFilterChange" />
        {{ $t('insolvency.filter_started') }}
      </label>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>
    <DataTable
      table-key="persons"
      :columns="tableColumns"
      :items="items"
      :row-class="rowClass"
      :current-sort-by="sortBy"
      :sort-desc="sortDesc"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @sort="handleSort"
      @retry="getData">
      <template #cell-token="{ item }">
        <button class="group flex justify-between w-full items-center text-sky-500 text-nowrap text-left"
          @click="showDetail(item.id);">
          <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
          <Icon name="fa6-solid:eye"
            class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
        </button>
      </template>

      <template #cell-name="{ item }">
        <span class="truncate" :title="item.name">{{ item.name }}</span>
      </template>

      <template #cell-surname="{ item }">
        <span class="truncate" :title="item.surname">{{ item.surname }}</span>
      </template>

      <template #cell-is_juridic="{ item }">
        <AtomsColorBadge :value="item.is_juridic ? t('common.yes') : t('common.no')"
          :color="item.is_juridic ? 'green' : 'gray'" />
      </template>

      <template #cell-vulnerability="{ item }">
        <AtomsVulnerabilityCheck :vulnerability_level="item.vulnerability_level" :small="true" />
      </template>

      <template #cell-debt_amount="{ item }">
        <span
          :class="Number(item.debt_amount) !== 0 ? 'inline-flex items-center px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-sm font-semibold' : ''">
          {{ formatMoneyWithCurrency(item.debt_amount) }}
        </span>
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 z-30 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <PersonRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
        @close-subregion="toggleRegion(false)"></PersonRegion>
    </div>
  </div>

</template>
