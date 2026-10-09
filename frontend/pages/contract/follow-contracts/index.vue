<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useFixedObjectsStore } from '~/stores/useFixedObjects';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import PersonRegion from '~/components/organisms/PersonRegion.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import ManageContractsRegion from '~/components/organisms/ManageContractsRegion.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const fixedObjectsStore = useFixedObjectsStore();
const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const toast = useToast();
const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    editManageRegion.value = false;
    detail.value = null
    selectedItemId.value = null
  }
}

const { $ContractApiService, $ConfiglistApiService, $ConfigProjectApiService, $ObservationApiService } = useNuxtApp();

const lastObservations = ref({});
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');

const filter_status = ref([]);
const filter_variable_type = ref([]);
const filter_bonification_type = ref([]);
const filter_client_type = ref([]);
const filter_category = ref([]);
const filter_use_type = ref([]);
const filter_debt_management = ref([]);

const permissions = ref(null);

const variables = ref([]);
const bonifications = ref([]);
const client_types = ref([]);
const categories = ref([]);
const use_types = ref([]);
const debt_management = ref([]);

const selectedFilters = ref([]);
const selected_elements = ref([]);
const selected_bonifications = ref([]);
const selected_client_types = ref([]);
const selected_categories = ref([]);
const selected_use_types = ref([]);
const selected_debt_management = ref([]);

const sortBy = ref(null);
const sortDesc = ref(false);

const editManageRegion = ref(false);

const isFilterOpen = ref(false);
const showAddressSearch = ref(false);
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
    const data = await $ContractApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, load = true, searchByAddressQuery = '') => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = load;
  error.value = null;

  try {
    const data = await $ContractApiService.getAll(
      searchQuery, filters, page, sort,
      desc, variables.value, bonifications.value, client_types.value,
      use_types.value, categories.value, [], debt_management.value, true,
      [], '', [], [], searchByAddressQuery
    );

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || String(searchByAddressQuery).trim() !== ''
    });

    loadLastObservations(items.value);

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }

}

const loadLastObservations = async (contractList) => {
  lastObservations.value = {};
  try {
    await Promise.all(
      contractList.map(async (contract) => {
        try {
          const result = await $ObservationApiService.getObservations(
            '' + contract.id, 'contract', 'contract', 'contract'
          );
          if (result?.results?.length) {
            const sorted = [...result.results].sort(
              (a, b) => new Date(b.created_at) - new Date(a.created_at)
            );
            lastObservations.value[contract.id] = sorted[0];
          } else {
            lastObservations.value[contract.id] = null;
          }
        } catch {
          lastObservations.value[contract.id] = null;
        }
      })
    );
  } catch (err) {
    console.error('Error loading observations:', err);
  }
}

const fetchConfigData = async (service, entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];
    if (data.results) {
      targetArray.value = data.results;
    }
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

const loadSelectData = async () => {
  await fetchConfigData('contract', 'contract-category', filter_category);
  await fetchConfigData('contract', 'variable-type', filter_variable_type);
  await fetchConfigData('contract', 'bonification-type', filter_bonification_type);
  await fetchConfigData('contract', 'contract-client-type', filter_client_type);
  await fetchConfigData('contract', 'contract-use-type', filter_use_type);

}


const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ContractApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }

  try {
    const data = await $ConfigProjectApiService.get('contract_active_token')
    if (data) {
      selectedFilters.value.push(filter_status.value.filter(f => f.token == data)[0].id)
    }
  } catch (err) {
    console.error(err)
    console.log('Contract active status filter could not be established...')
  }
}


const getFilterDebtManagement = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-debt-management');
    filter_debt_management.value = data.results;
    filter_debt_management.value.unshift(
      {
        name: t("contract_block.no_debt_management"),
        id: 'null',
      }
    );
  } catch (err) {
    error.value = err;
  }
}

const handleChange = () => {
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, false);
}

const debouncedGetData = debounce((query, filters, sort, desc, load = true, searchByAddressQuery = '') => {
  getData(query, filters, pagination.value.page, sort, desc, load, searchByAddressQuery);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, true, searchByAddress.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, true, addressString);
}

const toggleAddressFilter = () => {
  if (showAddressSearch.value) {
    showAddressSearch.value = false;
    if (!isFilterShown.value.length) {
      isFilterOpen.value = false;
      return;
    }
  } else {
    showAddressSearch.value = true;
    isFilterOpen.value = true;
  }
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handleVariableChange = (event) => {
  selected_elements.value = event;
  variables.value = []
  selected_elements.value.forEach(element => {
    variables.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleBonificationChange = (event) => {
  selected_bonifications.value = event;
  bonifications.value = []
  selected_bonifications.value.forEach(element => {
    bonifications.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleClientTypeChange = (event) => {
  selected_client_types.value = event;
  client_types.value = []
  selected_client_types.value.forEach(element => {
    client_types.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleCategoryChange = (event) => {
  selected_categories.value = event;
  categories.value = []
  selected_categories.value.forEach(element => {
    categories.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleUseTypeChange = (event) => {
  selected_use_types.value = event;
  use_types.value = []
  selected_use_types.value.forEach(element => {
    use_types.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleDebtManagementChange = (event) => {
  selected_debt_management.value = event;
  debt_management.value = []
  selected_debt_management.value.forEach(element => {
    debt_management.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleFiltersChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'variable_type') && !newFilters.some(filter => filter.id === 'variable_type')) {
    variables.value = [];
    selected_elements.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'bonification_type') && !newFilters.some(filter => filter.id === 'bonification_type')) {
    bonifications.value = [];
    selected_bonifications.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'client_type') && !newFilters.some(filter => filter.id === 'client_type')) {
    client_types.value = [];
    selected_client_types.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'category') && !newFilters.some(filter => filter.id === 'category')) {
    categories.value = [];
    selected_categories.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'use_type') && !newFilters.some(filter => filter.id === 'use_type')) {
    use_types.value = [];
    selected_use_types.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'debt_management') && !newFilters.some(filter => filter.id === 'debt_management')) {
    debt_management.value = [];
    selected_debt_management.value = [];
    getData();
  }
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value, true, searchByAddress.value);
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
  searchByAddress.value = '';
  pagination.value.page = 1;
  variables.value = [];
  selected_elements.value = [];
  bonifications.value = [];
  selected_bonifications.value = [];
  client_types.value = [];
  selected_client_types.value = [];
  categories.value = [];
  selected_categories.value = [];
  use_types.value = [];
  selected_use_types.value = [];
  debt_management.value = [];
  selected_debt_management.value = [];
  isFilterShown.value = [];
  isFilterOpen.value = false;
  showAddressSearch.value = false;
  getData();
};

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    filtersExtra.value.push(
      { name: t("variables"), id: "variable_type" },
      { name: t("bonifications"), id: "bonification_type" },
      { name: t("contract_block.client_type"), id: "client_type" },
      { name: t("contract_block.category"), id: "category" },
      { name: t("common.usage_type"), id: "use_type" },
      { name: t("contract_block.debt_management"), id: "debt_management" }
    );
    await loadSelectData();
    await getFilterStatus();
    await getData('', selectedFilters.value);
    await getFilterDebtManagement();
    checkRouteQuery()
  } else {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
  } else if (route.query?.action == 'filterPage') {
    if (route.query.advance_filters) {
      console.log(route.query)
      isFilterOpen.value = true;
      for (let filter of route.query.advance_filters) {
        //CHECK HOW TO OPTIMIZE THIS
        if (filter == 'variable_type') {
          isFilterShown.value.push({ id: filter, name: t('variables') });
          selected_elements.value.push({ id: 1, name: t('variables') });
        }
        if (filter == 'bonification_type') {
          isFilterShown.value.push({ id: filter, name: t('bonifications') });
        }
      }
      variables.value = route.query.variables;
      handleFilterChange();
    } else {
      selectedFilters.value = route.query.variables
      handleFilterChange();
    }
  }
  else {
    if (route.query.id) {
      showDetail(route.query.id);
    }
  }
}


const showDetail = async (id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const openRegion = (region) => {
  toggleRegion(false)
  editManageRegion.value = region === 'manage';
  showRegion.value = true;
};

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

/**
 * Column layout of the follow-up contracts table.
 *
 * `grow` shares the leftover horizontal space between the columns that benefit
 * from it (supply point, holder and the observation text), so the table always
 * fills the viewport instead of leaving a gap on wide screens. `priority`
 * decides what gets dropped first when the window is too narrow: 1 is never
 * auto-hidden, 4 goes first. The user can override the selection and drag any
 * column wider — both are remembered per user in localStorage (see
 * `useTableColumns`).
 */
const tableColumns = computed(() => [
  { key: 'created_at', label: t('common.date'), sortKey: 'created_at', width: 82, min: 78, priority: 3 },
  {
    key: 'token', label: t('common.identification'), sortKey: 'token',
    width: 150, min: 120, priority: 1, removable: false,
  },
  {
    key: 'supply_point', label: t('supply_point'), sortKey: 'supply_point_default',
    width: 250, grow: 3, min: 180, priority: 1, removable: false,
  },
  { key: 'holder', label: t('contract_block.holder'), sortKey: 'holder', width: 180, grow: 2, min: 130, priority: 1 },
  {
    key: 'status', label: t('common.status'), sortKey: 'status',
    width: 80, min: 62, priority: 1, cellClass: 'inline-flex gap-1 items-center',
  },
  { key: 'debt_amount', label: t('contract_block.debt_accumulated'), sortKey: 'debt_amount', width: 125, min: 100, priority: 2 },
  // The observation renders on two lines (date + text), so it opts out of the
  // single-line truncation the table applies to every other cell.
  {
    key: 'last_observation', label: t('common.last_observation'),
    width: 220, grow: 2, min: 150, priority: 2, cellClass: 'data-table-no-truncate text-slate-600 text-sm',
  },
]);

const rowClass = (item) => ({
  'bg-yellow-50': item.id === selectedItemId.value,
  'bg-orange-50': item.is_pinned,
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-1">
      <H1 class="mb-2">{{ $t('customer_service_block.follow_contracts') }}</H1>
    </div>
    <form id="form_filter" role="search"
      class="mb-2 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
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

      <span class="flex items-center gap-1">
        <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="isFilterOpen = !isFilterOpen" title="show">
          <Icon name="fa:filter" class="text-slate-500" />
        </button>
        <button id="filterAddress" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showAddressSearch }"
          @click="toggleAddressFilter"
          :title="$t('address_block.address')">
          <Icon name="fa6-solid:house" class="text-slate-500" />
        </button>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <div class="px-2 text-base flex flex-start gap-2 justify-start items-center flex-wrap" v-if="isFilterOpen">

      <span v-if="showAddressSearch" class="flex items-center gap-2">
        <AtomsInputAddressSearch :value="searchByAddress" @change="handleAddressChange" />
      </span>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'variable_type')" :options="filter_variable_type"
        :filters="selected_elements" :multiple="true" :placeholder="t('variables')"
        @update:modelValue="handleVariableChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'bonification_type')"
        :options="filter_bonification_type" :filters="selected_bonifications" :multiple="true"
        :placeholder="t('bonifications')" @update:modelValue="handleBonificationChange($event)">
        <template #icon>
          <Icon name="fa6-solid:coins" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'client_type')" :options="filter_client_type"
        :filters="selected_client_types" :multiple="true" :placeholder="t('contract_block.client_type')"
        @update:modelValue="handleClientTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:users" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'category')" :options="filter_category"
        :filters="selected_categories" :multiple="true" :placeholder="t('contract_block.category')"
        @update:modelValue="handleCategoryChange($event)">
        <template #icon>
          <Icon name="fa6-solid:tag" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'use_type')" :options="filter_use_type"
        :filters="selected_use_types" :multiple="true" :placeholder="t('common.usage_type')"
        @update:modelValue="handleUseTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:wrench" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'debt_management')"
        :options="filter_debt_management" :filters="selected_debt_management" :multiple="true"
        :placeholder="t('contract_block.debt_management')" @update:modelValue="handleDebtManagementChange($event)">
        <template #icon>
          <Icon name="fa6-solid:percent" class="text-md ml-2 mr-1" size="10px" />
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
      table-key="follow-contracts"
      :columns="tableColumns"
      :items="items"
      :row-class="rowClass"
      :current-sort-by="sortBy"
      :sort-desc="sortDesc"
      pin-column
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @sort="handleSort"
      @retry="getData">
      <template #pin="{ item }">
        <span class="flex items-center justify-center" aria-hidden="true">
          <Icon v-if="item.is_pinned" name="ic:sharp-push-pin" class="w-3 h-3 text-red-500" />
        </span>
      </template>

      <template #cell-created_at="{ item }">{{ formatDate(item.created_at) }}</template>

      <template #cell-token="{ item }">
        <button class="group flex justify-between w-full items-center text-sky-500 text-nowrap text-left"
          @click="showDetail(item.id);">
          <abbr :title="item.id" class="no-underline min-w-0">
            <AtomsContractBadge class="cursor-pointer" :contract="item" :reverse="false" :color="'white'" />
          </abbr>
          <Icon name="fa6-solid:eye"
            class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
        </button>
      </template>

      <template #cell-supply_point="{ item }">{{ item.supply_point }}</template>
      <template #cell-holder="{ item }">{{ item.holder_name }} {{ item.holder_surname }}</template>

      <template #cell-status="{ item }">
        <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
        <abbr v-if="item.active_contract_termination" class="flex items-center"
          :title="t('contract_block.contract_in_termination')">
          <Icon name="fa-solid:exclamation-circle" class="text-orange-500 mt-auto" />
        </abbr>
      </template>

      <template #cell-debt_amount="{ item }">{{ formatMoneyWithCurrency(item.debt_amount) }}</template>

      <template #cell-last_observation="{ item }">
        <template v-if="lastObservations[item.id]">
          <span class="block text-slate-400 text-xs">{{ formatDate(lastObservations[item.id].created_at) }}</span>
          <abbr :title="lastObservations[item.id].observation" class="no-underline block truncate">
            {{ lastObservations[item.id].observation }}
          </abbr>
        </template>
        <span v-else class="text-slate-300">—</span>
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <ContractRegion v-if="detail" :id="parseInt(detail)" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="handleChange" @close-subregion="toggleRegion(false)"></ContractRegion>
      <ManageContractsRegion v-if="editManageRegion" @close="toggleRegion(false)"></ManageContractsRegion>
    </div>
  </div>

</template>
