<script setup>
import { ref, onMounted, nextTick, computed, watch, onUnmounted } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useFixedObjectsStore } from '~/stores/useFixedObjects';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import PersonRegion from '~/components/organisms/PersonRegion.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import ManageContractsRegion from '~/components/organisms/ManageContractsRegion.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';
import { usePermissions } from '~/middleware/permission';

const fixedObjectsStore = useFixedObjectsStore();
const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const toast = useToast();
const showRegion = ref(false);
const { permissions, loading } = usePermissions();

const { $ContractApiService, $ConfiglistApiService, $ExploitationApiService, $apiManager, $DocumentManagerApiService, $ConfigProjectApiService } = useNuxtApp();
const { fetchFireUsageTypeTokens, isFireContract } = useFireUsageTypeTokens();
const { fetchSupplyPointCutStatusToken, isSupplyPointCut } = useSupplyPointCutStatusToken();
const useMultipleCompanies = ref(false);
const ACTIVE_STATUS_ID = 2;
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchAllAddressInput = ref('');
const searchByAddress = ref('');// Track which search input is active
const searchEmailInput = ref('');
const searchIbanInput = ref('');
const searchMeterInput = ref('');

const openIndexDropdown = ref(false);

const filter_status = ref([]);
const filter_variable_type = ref([]);
const filter_bonification_type = ref([]);
const filter_client_type = ref([]);
const filter_category = ref([]);
const filter_use_type = ref([]);
const filter_debt_management = ref([]);
const filter_comm_type = ref([]);
const filter_payment_type = ref([]);
const filter_company = ref([]);
const filter_block_billing = ref([]);
const selected_block_billing = ref([]);
const block_billing = ref(null);
const filter_has_debt = ref([]);
const selected_has_debt = ref([]);
const has_debt = ref(null);

const variables = ref([]);
const bonifications = ref([]);
const client_types = ref([]);
const categories = ref([]);
const use_types = ref([]);
const debt_management = ref([]);
const comm_types = ref([]);
const payment_types = ref([]);
const companies = ref([]);

const selectedFilters = ref([ACTIVE_STATUS_ID]);
const selected_elements = ref([]);
const selected_bonifications = ref([]);
const selected_client_types = ref([]);
const selected_categories = ref([]);
const selected_use_types = ref([]);
const selected_debt_management = ref([]);
const selected_comm_types = ref([]);
const selected_payment_type = ref([]);
const selected_companies = ref([]);
const selected_total_persons_min = ref([]);
const total_persons_min = ref(null);
const filter_total_persons_min = ref([]);

const sortBy = ref(null);
const sortDesc = ref(false);

const editManageRegion = ref(false);

const blockSearch = ref(true);

const isFilterOpen = ref(false);
const showAddressSearch = ref(false);
const showEmailSearch = ref(false);
const showIbanSearch = ref(false);
const showMeterSearch = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const objectPermissions = ref(null);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const loadFireUsageTypeToken = fetchFireUsageTypeTokens;

const loadUseMultipleCompanies = async () => {
  try {
    const multi = await $ConfigProjectApiService.get('use_multiple_companies');
    useMultipleCompanies.value = multi === true || multi === 'True' || multi === 'true';
  } catch {
    useMultipleCompanies.value = false;
  }
};

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ContractApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', searchAllAddress = '', filters = [], page = 1, sort = null, desc = false, load = true, searchByAddressQuery = '', totalPersonsMinQuery = null, searchEmailQuery = '', searchIbanQuery = '', searchMeterQuery = '') => {
  if (!objectPermissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = load;
  error.value = null;

  try {
    const data = await $ContractApiService.getAll(
      searchQuery, filters, page, sort,
      desc, variables.value, bonifications.value, client_types.value,
      use_types.value, categories.value, [], debt_management.value, false,
      comm_types.value, searchAllAddress, payment_types.value, [], searchByAddressQuery, totalPersonsMinQuery,
      companies.value, null, null, block_billing.value, has_debt.value, searchEmailQuery, searchIbanQuery, searchMeterQuery
    );

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || String(searchAllAddress).trim() !== '' || String(searchByAddressQuery).trim() !== '' || String(searchEmailQuery).trim() !== '' || String(searchIbanQuery).trim() !== ''
    });

    if (blockSearch.value) {
      blockSearch.value = false;
    }

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
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

const loadFilterCompanies = async () => {
  try {
    const collected = [];
    let page = 1;
    let hasNext = true;
    while (hasNext && page < 200) {
      const data = await $ExploitationApiService.getCompanies('', page, null, false);
      collected.push(...(data.results || []));
      hasNext = !!data.next;
      page += 1;
    }
    filter_company.value = collected.map((c) => ({ id: c.id, name: c.name }));
  } catch (error) {
    console.error('Error loading companies for filter:', error);
  }
};

const loadSelectData = async () => {
  await fetchConfigData('contract', 'contract-category', filter_category);
  await fetchConfigData('contract', 'variable-type', filter_variable_type);
  await fetchConfigData('contract', 'bonification-type', filter_bonification_type);
  await fetchConfigData('contract', 'contract-client-type', filter_client_type);
  await fetchConfigData('contract', 'contract-use-type', filter_use_type);
  await fetchConfigData('contract', 'contract-payment-type', filter_payment_type);
  filter_payment_type.value.unshift(
    {
      id: 'null',
      name: t('None'),
    }
  );
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ContractApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    console.error(err)
    console.log('Contract active status filter could not be established...')
    error.value = err;
  }

  if (!selectedFilters.value.length) {
    const defaultActiveStatus = filter_status.value.find(f => Number(f.id) === ACTIVE_STATUS_ID);
    if (defaultActiveStatus && !selectedFilters.value.includes(defaultActiveStatus.id)) {
      selectedFilters.value.push(defaultActiveStatus.id);
    }
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

const detail = ref(null);
const selectedItemId = ref(null);

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const toggleRegion = (force, isReload = false) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    editManageRegion.value = false;
    detail.value = null
    selectedItemId.value = null
    if (!isReload) {
      nextTick(() => {
        if (!showRegion.value && route.query.id) {
          const query = { ...route.query };
          delete query.id;
          router.replace({ path: route.path, query });
        }
      });
    }
  }
}

const handleChange = (close = false) => {
  toggleRegion(!close);
  debouncedGetData(searchInput.value, searchAllAddressInput.value, selectedFilters.value, sortBy.value, sortDesc.value, false, searchByAddress.value, total_persons_min.value, searchEmailInput.value, searchIbanInput.value, searchMeterInput.value);
}

const debouncedGetData = debounce((query, searchAllAddress, filters, sort, desc, load = true, searchByAddressQuery = '', totalPersonsMinQuery = null, searchEmailQuery = '', searchIbanQuery = '', searchMeterQuery = '') => {
  getData(query, searchAllAddress, filters, pagination.value.page, sort, desc, load, searchByAddressQuery, totalPersonsMinQuery, searchEmailQuery, searchIbanQuery, searchMeterQuery);
}, 1000);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, searchAllAddressInput.value, selectedFilters.value, sortBy.value, sortDesc.value, true, searchByAddress.value, total_persons_min.value, searchEmailInput.value, searchIbanInput.value, searchMeterInput.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, searchAllAddressInput.value, selectedFilters.value, sortBy.value, sortDesc.value, true, addressString, total_persons_min.value, searchEmailInput.value, searchIbanInput.value, searchMeterInput.value);
}

const toggleAddressFilter = () => {
  // If we are hiding the address search and there are no extra filters, close the whole extra filters area
  if (showAddressSearch.value) {
    showAddressSearch.value = false;
    if (!isFilterShown.value.length && !showEmailSearch.value && !showIbanSearch.value && !showMeterSearch.value) {
      isFilterOpen.value = false;
      return;
    }
  } else {
    // Show address search and ensure filters area is open
    showAddressSearch.value = true;
    isFilterOpen.value = true;
  }
}

const toggleEmailFilter = () => {
  if (showEmailSearch.value) {
    showEmailSearch.value = false;
    searchEmailInput.value = '';
    handleSearch();
    if (!isFilterShown.value.length && !showAddressSearch.value && !showIbanSearch.value && !showMeterSearch.value) {
      isFilterOpen.value = false;
      return;
    }
  } else {
    showEmailSearch.value = true;
    isFilterOpen.value = true;
  }
}

const toggleIbanFilter = () => {
  if (showIbanSearch.value) {
    showIbanSearch.value = false;
    searchIbanInput.value = '';
    handleSearch();
    if (!isFilterShown.value.length && !showAddressSearch.value && !showEmailSearch.value && !showMeterSearch.value) {
      isFilterOpen.value = false;
      return;
    }
  } else {
    showIbanSearch.value = true;
    isFilterOpen.value = true;
  }
}

const toggleMeterFilter = () => {
  if (showMeterSearch.value) {
    showMeterSearch.value = false;
    searchMeterInput.value = '';
    handleSearch();
    if (!isFilterShown.value.length && !showAddressSearch.value && !showEmailSearch.value && !showIbanSearch.value) {
      isFilterOpen.value = false;
      return;
    }
  } else {
    showMeterSearch.value = true;
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

const handlePaymentTypeChange = (event) => {
  selected_payment_type.value = event;
  payment_types.value = []
  selected_payment_type.value.forEach(element => {
    payment_types.value.push(element.id);
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

const handleCommTypeChange = (event) => {
  selected_comm_types.value = event;
  comm_types.value = []
  comm_types.value = [selected_comm_types.value[0].id]
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

const handleTotalPersonsMinChange = (event) => {
  selected_total_persons_min.value = event;
  total_persons_min.value = event.length > 0 ? event[0].id : null;
  pagination.value.page = 1;
  handleSearch();
}

const handleCompanyChange = (event) => {
  selected_companies.value = event;
  companies.value = [];
  selected_companies.value.forEach((element) => {
    companies.value.push(element.id);
  });
  pagination.value.page = 1;
  handleSearch();
};

const handleBlockBillingChange = (event) => {
  selected_block_billing.value = event;
  block_billing.value = event.length > 0 ? event[0].id : null;
  pagination.value.page = 1;
  handleSearch();
}

const handleHasDebtChange = (event) => {
  selected_has_debt.value = event;
  has_debt.value = event.length > 0 ? event[0].id : null;
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
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'bonification_type') && !newFilters.some(filter => filter.id === 'bonification_type')) {
    bonifications.value = [];
    selected_bonifications.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'client_type') && !newFilters.some(filter => filter.id === 'client_type')) {
    client_types.value = [];
    selected_client_types.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'category') && !newFilters.some(filter => filter.id === 'category')) {
    categories.value = [];
    selected_categories.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'use_type') && !newFilters.some(filter => filter.id === 'use_type')) {
    use_types.value = [];
    selected_use_types.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'debt_management') && !newFilters.some(filter => filter.id === 'debt_management')) {
    debt_management.value = [];
    selected_debt_management.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'comm_type') && !newFilters.some(filter => filter.id === 'comm_type')) {
    comm_types.value = [];
    selected_comm_types.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'payment_method') && !newFilters.some(filter => filter.id === 'payment_method')) {
    payment_types.value = [];
    selected_payment_type.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'total_persons_min') && !newFilters.some(filter => filter.id === 'total_persons_min')) {
    total_persons_min.value = null;
    selected_total_persons_min.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'company') && !newFilters.some(filter => filter.id === 'company')) {
    companies.value = [];
    selected_companies.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'block_billing') && !newFilters.some(filter => filter.id === 'block_billing')) {
    block_billing.value = null;
    selected_block_billing.value = [];
    handleFilterChange();
  } else if (isFilterShown.value.some(filter => filter.id === 'has_debt') && !newFilters.some(filter => filter.id === 'has_debt')) {
    has_debt.value = null;
    selected_has_debt.value = [];
    handleFilterChange();
  }
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, searchAllAddressInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value, true, searchByAddress.value, total_persons_min.value, searchEmailInput.value, searchIbanInput.value, searchMeterInput.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, searchAllAddressInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, true, searchByAddress.value, total_persons_min.value, searchEmailInput.value, searchIbanInput.value, searchMeterInput.value);
}

const resetFilters = () => {
  searchInput.value = '';
  searchAllAddressInput.value = '';
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
  comm_types.value = [];
  selected_comm_types.value = [];
  use_types.value = [];
  selected_use_types.value = [];
  debt_management.value = [];
  selected_debt_management.value = [];
  payment_types.value = [];
  selected_payment_type.value = [];
  total_persons_min.value = null;
  selected_total_persons_min.value = [];
  companies.value = [];
  selected_companies.value = [];
  block_billing.value = null;
  selected_block_billing.value = [];
  has_debt.value = null;
  selected_has_debt.value = [];
  searchEmailInput.value = '';
  searchIbanInput.value = '';
  searchMeterInput.value = '';
  isFilterShown.value = [];
  isFilterOpen.value = false;
  showAddressSearch.value = false;
  showEmailSearch.value = false;
  showIbanSearch.value = false;
  showMeterSearch.value = false;
  getData();
};

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
  } else if (route.query?.action == 'filterPage') {
    if (route.query.advance_filters) {
      isFilterOpen.value = true;
      for (let filter of route.query.advance_filters) {
        //CHECK HOW TO OPTIMIZE THIS
        if (filter == 'variable_type') {
          isFilterShown.value.push({ id: filter, name: t("variables") });
          selected_elements.value.push({ id: 1, name: t("variables") });
        }
        if (filter == 'bonification_type') {
          isFilterShown.value.push({ id: filter, name: t("bonifications") });
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
    if (route?.query?.id &&
        !(selectedItemId.value && String(selectedItemId.value) === String(route.query.id) && showRegion.value)) {
      showDetail(route.query.id);
    }
  }
}

const showDetail = (id) => {
  if (id && selectedItemId.value && String(selectedItemId.value) === String(id) && showRegion.value) {
    toggleRegion(false, true);
    nextTick(() => {
      detail.value = id;
      selectedItemId.value = id;
      toggleRegion(true);
    });
    return;
  }
  toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
  if (route.query.id !== String(id)) {
    router.replace({ path: route.path, query: { ...route.query, id: id } });
  }
}

const toggleIndexDropdown = () => {
  openIndexDropdown.value = !openIndexDropdown.value
}

const openRegion = (region) => {
  openIndexDropdown.value = false;
  toggleRegion(false)
  editManageRegion.value = region === 'manage';
  showRegion.value = true;
};

const STORAGE_KEY = 'contractsSearchState';

const saveSearchState = () => {
  const state = {
    searchInput: searchInput.value,
    searchAllAddressInput: searchAllAddressInput.value,
    searchByAddress: searchByAddress.value,
    selectedFilters: selectedFilters.value,
    variables: variables.value,
    selected_elements: selected_elements.value,
    bonifications: bonifications.value,
    selected_bonifications: selected_bonifications.value,
    client_types: client_types.value,
    selected_client_types: selected_client_types.value,
    categories: categories.value,
    selected_categories: selected_categories.value,
    use_types: use_types.value,
    selected_use_types: selected_use_types.value,
    debt_management: debt_management.value,
    selected_debt_management: selected_debt_management.value,
    comm_types: comm_types.value,
    selected_comm_types: selected_comm_types.value,
    payment_types: payment_types.value,
    selected_payment_type: selected_payment_type.value,
    companies: companies.value,
    selected_companies: selected_companies.value,
    total_persons_min: total_persons_min.value,
    selected_total_persons_min: selected_total_persons_min.value,
    sortBy: sortBy.value,
    sortDesc: sortDesc.value,
    isFilterOpen: isFilterOpen.value,
    showAddressSearch: showAddressSearch.value,
    isFilterShown: isFilterShown.value,
    page: pagination.value.page,
    block_billing: block_billing.value,
    selected_block_billing: selected_block_billing.value,
    has_debt: has_debt.value,
    selected_has_debt: selected_has_debt.value,
    searchEmailInput: searchEmailInput.value,
    searchIbanInput: searchIbanInput.value,
    showEmailSearch: showEmailSearch.value,
    showIbanSearch: showIbanSearch.value,
    searchMeterInput: searchMeterInput.value,
    showMeterSearch: showMeterSearch.value,
  };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
};

const loadSearchState = () => {
  const state = sessionStorage.getItem(STORAGE_KEY);
  if (state) {
    try {
      const parsed = JSON.parse(state);
      if (parsed.searchInput !== undefined) searchInput.value = parsed.searchInput;
      if (parsed.searchAllAddressInput !== undefined) searchAllAddressInput.value = parsed.searchAllAddressInput;
      if (parsed.searchByAddress !== undefined) searchByAddress.value = parsed.searchByAddress;
      if (parsed.selectedFilters !== undefined) selectedFilters.value = parsed.selectedFilters;
      
      if (parsed.variables !== undefined) variables.value = parsed.variables;
      if (parsed.selected_elements !== undefined) selected_elements.value = parsed.selected_elements;
      
      if (parsed.bonifications !== undefined) bonifications.value = parsed.bonifications;
      if (parsed.selected_bonifications !== undefined) selected_bonifications.value = parsed.selected_bonifications;
      
      if (parsed.client_types !== undefined) client_types.value = parsed.client_types;
      if (parsed.selected_client_types !== undefined) selected_client_types.value = parsed.selected_client_types;
      
      if (parsed.categories !== undefined) categories.value = parsed.categories;
      if (parsed.selected_categories !== undefined) selected_categories.value = parsed.selected_categories;
      
      if (parsed.use_types !== undefined) use_types.value = parsed.use_types;
      if (parsed.selected_use_types !== undefined) selected_use_types.value = parsed.selected_use_types;
      
      if (parsed.debt_management !== undefined) debt_management.value = parsed.debt_management;
      if (parsed.selected_debt_management !== undefined) selected_debt_management.value = parsed.selected_debt_management;
      
      if (parsed.comm_types !== undefined) comm_types.value = parsed.comm_types;
      if (parsed.selected_comm_types !== undefined) selected_comm_types.value = parsed.selected_comm_types;
      
      if (parsed.payment_types !== undefined) payment_types.value = parsed.payment_types;
      if (parsed.selected_payment_type !== undefined) selected_payment_type.value = parsed.selected_payment_type;

      if (parsed.companies !== undefined) companies.value = parsed.companies;
      if (parsed.selected_companies !== undefined) selected_companies.value = parsed.selected_companies;
      
      if (parsed.total_persons_min !== undefined) total_persons_min.value = parsed.total_persons_min;
      if (parsed.selected_total_persons_min !== undefined) selected_total_persons_min.value = parsed.selected_total_persons_min;
      
      if (parsed.sortBy !== undefined) sortBy.value = parsed.sortBy;
      if (parsed.sortDesc !== undefined) sortDesc.value = parsed.sortDesc;
      if (parsed.isFilterOpen !== undefined) isFilterOpen.value = parsed.isFilterOpen;
      if (parsed.showAddressSearch !== undefined) showAddressSearch.value = parsed.showAddressSearch;
      if (parsed.isFilterShown !== undefined) isFilterShown.value = parsed.isFilterShown;
      
      if (parsed.page !== undefined) pagination.value.page = parsed.page;
      if (parsed.block_billing !== undefined) block_billing.value = parsed.block_billing;
      if (parsed.selected_block_billing !== undefined) selected_block_billing.value = parsed.selected_block_billing;
      if (parsed.has_debt !== undefined) has_debt.value = parsed.has_debt;
      if (parsed.selected_has_debt !== undefined) selected_has_debt.value = parsed.selected_has_debt;
      if (parsed.searchEmailInput !== undefined) searchEmailInput.value = parsed.searchEmailInput;
      if (parsed.searchIbanInput !== undefined) searchIbanInput.value = parsed.searchIbanInput;
      if (parsed.showEmailSearch !== undefined) showEmailSearch.value = parsed.showEmailSearch;
      if (parsed.showIbanSearch !== undefined) showIbanSearch.value = parsed.showIbanSearch;
      if (parsed.searchMeterInput !== undefined) searchMeterInput.value = parsed.searchMeterInput;
      if (parsed.showMeterSearch !== undefined) showMeterSearch.value = parsed.showMeterSearch;
    } catch (e) {
      console.error('Error parsing search state', e);
    }
  }
};

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    filtersExtra.value.push(
      { name: t("variables"), id: "variable_type" },
      { name: t("bonifications"), id: "bonification_type" },
      { name: t("contract_block.client_type"), id: "client_type" },
      { name: t("contract_block.category"), id: "category" },
      { name: t("common.usage_type"), id: "use_type" },
      { name: t("common.payment_method"), id: "payment_method" },
      { name: t("contract_block.debt_management"), id: "debt_management" },
      { name: t("communication"), id: "comm_type" },
      { name: t("contract_block.total_persons"), id: "total_persons_min" },
      { name: t("service_block.companies"), id: "company" },
      { name: t("contract_block.block_billing"), id: "block_billing" },
      { name: t("common.debt"), id: "has_debt" },
    );
    filter_total_persons_min.value = [];
    for (let i = 3; i <= 10; i++) {
      filter_total_persons_min.value.push({
        id: i + 1,
        name: t('contract_block.more_than') + ' ' + i
      });
    }

    filter_comm_type.value = [{ id: 'PAPER', name: t("contract_block.short_paper_comm") }, { id: 'DIGITAL', name: t("contract_block.short_digital_comm") }]
    
    filter_block_billing.value = [
      { id: 'true', name: t('contract_block.block_billing') },
      { id: 'false', name: t('contract_block.mark_as_billable') }
    ];

    filter_has_debt.value = [
      { id: 'true', name: t('contract_block.debtor') },
      { id: 'false', name: t('contract_block.no_debtor') },
    ];
    
    // Fetch heavy config data in parallel (UI) while first list load starts immediately with active status.
    await Promise.all([
      getFilterDebtManagement(),
      loadSelectData(),
      loadFilterCompanies(),
      loadFireUsageTypeToken(),
      fetchSupplyPointCutStatusToken(),
      loadUseMultipleCompanies(),
    ]);

    // Initial list request without waiting for status labels/config token.
    loadSearchState();
    getData(searchInput.value, searchAllAddressInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, true, searchByAddress.value, total_persons_min.value, searchEmailInput.value, searchIbanInput.value, searchMeterInput.value);
    getFilterStatus();
    await checkRouteQuery();
  } else {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

// Watch for changes and save state
watch(
  () => [
    searchInput.value, searchAllAddressInput.value, searchByAddress.value, selectedFilters.value,
    variables.value, selected_elements.value, bonifications.value, selected_bonifications.value,
    client_types.value, selected_client_types.value, categories.value, selected_categories.value,
    use_types.value, selected_use_types.value, debt_management.value, selected_debt_management.value,
    comm_types.value, selected_comm_types.value,     payment_types.value, selected_payment_type.value,
    companies.value, selected_companies.value,
    total_persons_min.value, selected_total_persons_min.value, sortBy.value, sortDesc.value,
    isFilterOpen.value, showAddressSearch.value, isFilterShown.value, pagination.value.page,
    block_billing.value, selected_block_billing.value,
    has_debt.value, selected_has_debt.value,
    searchEmailInput.value, searchIbanInput.value, showEmailSearch.value, showIbanSearch.value,
    searchMeterInput.value, showMeterSearch.value
  ],
  () => {
    saveSearchState();
  },
  { deep: true }
);

/**
 * Column layout of the contracts table.
 *
 * `grow` shares the leftover horizontal space between the columns that benefit
 * from it (address and holder), so the table always fills the viewport instead
 * of leaving a gap on wide screens. `priority` decides what gets dropped first
 * when the window is too narrow: 1 is never auto-hidden, 4 goes first. The user
 * can override the selection and drag any column wider — both are remembered
 * per user in localStorage (see `useTableColumns`).
 */
const tableColumns = computed(() => [
  // Fixed-content columns are kept tight (a date is always 10 characters and a
  // token 9) so the space they free goes to the two columns that actually get
  // truncated: the supply point address and the holder name.
  { key: 'created_at', label: t('common.date'), sortKey: 'created_at', width: 82, min: 78, priority: 3 },
  {
    key: 'token', label: t('common.identification'), sortKey: 'token',
    width: 118, min: 105, priority: 1, removable: false, cellClass: 'flex items-center gap-2',
  },
  {
    key: 'supply_point', label: t('supply_point'), sortKey: 'supply_point_default__address__address_search',
    width: 260, grow: 4, min: 180, priority: 1, removable: false,
  },
  { key: 'holder', label: t('contract_block.holder'), sortKey: 'holder__name', width: 200, grow: 3, min: 140, priority: 1 },
  { key: 'meter', label: t('meter'), sortKey: 'supply_point_default__meter__code', width: 110, min: 90, grow: 1, priority: 3 },
  {
    key: 'status', label: t('common.status'), sortKey: 'status',
    width: 70, min: 62, priority: 1, cellClass: 'inline-flex gap-1 items-center',
  },
  { key: 'client_type', label: t('contract_block.client_type'), sortKey: 'client_type', width: 120, min: 90, grow: 1, priority: 4 },
  { key: 'category', label: t('contract_block.category'), sortKey: 'category', width: 140, min: 100, grow: 1.5, priority: 4 },
  { key: 'use_type', label: t('common.type'), sortKey: 'use_type', width: 130, min: 100, grow: 1, priority: 3 },
  { key: 'debt_amount', label: t('contract_block.debt_accumulated'), sortKey: 'debt_amount', width: 125, min: 100, priority: 2 },
]);

const rowClass = (item) => ({
  'bg-sky-50': item.is_checked && !item.is_pinned,
  'bg-yellow-50': item.id === selectedItemId.value,
  'bg-orange-50': item.is_pinned,
});

const downloadingExcel = ref(false);
const excelExportProgress = ref(0);
const excelExportTaskId = ref(null);
let excelExportInterval = null;

onUnmounted(() => {
  if (excelExportInterval) {
    clearInterval(excelExportInterval);
  }
});

const exportExcel = async () => {
  if (downloadingExcel.value) return;
  downloadingExcel.value = true;
  excelExportProgress.value = 0;
  
  try {
    const response = await $ContractApiService.exportExcel(
      searchInput.value,
      selectedFilters.value,
      sortBy.value,
      sortDesc.value,
      variables.value,
      bonifications.value,
      client_types.value,
      use_types.value,
      categories.value,
      [], // product_ids
      debt_management.value,
      false, // is_checked
      comm_types.value,
      searchAllAddressInput.value,
      payment_types.value,
      [], // person_ids
      searchByAddress.value,
      total_persons_min.value,
      companies.value,
      block_billing.value,
      has_debt.value,
      searchEmailInput.value,
      searchIbanInput.value,
      searchMeterInput.value
    );

    if (response && response.task_id) {
      excelExportTaskId.value = response.task_id;
      
      excelExportInterval = setInterval(async () => {
        try {
          const res = await $apiManager.checkTask(excelExportTaskId.value);
          if (res) {
            if (res.state === 'PENDING' || res.state === 'RUNNING') {
              excelExportProgress.value = res.percent || 0;
            } else if (res.state === 'SUCCESS') {
              clearInterval(excelExportInterval);
              excelExportProgress.value = 100;
              
              if (res.result && res.result.document_id) {
                const fileBlob = await $DocumentManagerApiService.viewDocument(res.result.document_id);
                const url = window.URL.createObjectURL(fileBlob);
                const a = document.createElement("a");
                a.href = url;
                a.download = res.result.filename || `contracts_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                toast.success(t('success_block.csv_exported') || 'Exportació completada');
              } else {
                toast.error(t('error_block.csv_export_failed') || 'Error en l\'exportació');
              }
              downloadingExcel.value = false;
              excelExportTaskId.value = null;
            } else if (res.state === 'FAILURE') {
              clearInterval(excelExportInterval);
              const errMsg = res.error || t('error_block.csv_export_failed') || 'Error en l\'exportació';
              toast.error(errMsg);
              downloadingExcel.value = false;
              excelExportTaskId.value = null;
            }
          }
        } catch (pollErr) {
          clearInterval(excelExportInterval);
          console.error(pollErr);
          toast.error(t('error_block.csv_export_failed') || 'Error en l\'exportació');
          downloadingExcel.value = false;
          excelExportTaskId.value = null;
        }
      }, 2000);
    } else {
      throw new Error('No s\'ha rebut task_id');
    }
  } catch (err) {
    console.error(err);
    toast.error(t('error_block.csv_export_failed') || 'Error en l\'exportació');
    downloadingExcel.value = false;
    excelExportTaskId.value = null;
  }
};
watch(() => route.query, async () => {
  await checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div @click="openIndexDropdown = false" class="flex justify-between items-center mb-1">
      <H1 class="mb-2">{{ $t('common.contracts') }}</H1>
      <!-- <NuxtLink to="/contract/persons/add" class="button-primary">{{ $t('Nova Persona') }}</NuxtLink> -->
      <!-- <div v-if="objectPermissions?.can_change" class="flex items-center gap-x-2">
        <NuxtLink class="button-default" to="/contract/contracts/payment-manage">
          {{ t("contract_block.manage_contracts_payment") }}
        </NuxtLink>
        <button class="button-primary" @click="openRegion('manage')">
          {{ t("contract_block.manage_contracts") }}
        </button>
      </div> -->
      <div class="flex items-center gap-2">
        <button 
          v-if="objectPermissions?.can_view"
          class="button-default flex items-center gap-3 relative" 
          @click="exportExcel" 
          :disabled="downloadingExcel"
          title="Exportar a Excel">
          <Icon 
            :name="downloadingExcel ? 'fa6-solid:spinner' : 'fa6-solid:file-excel'" 
            class="p-1" 
            :class="{ 'animate-spin': downloadingExcel }" />
          <span v-if="downloadingExcel">
            {{ excelExportProgress }}%
          </span>
          <span v-else>
            {{ t('export_csv') }}
          </span>
        </button>
        <div @click.stop class="relative inline-block">
          <button v-if="objectPermissions?.can_change" class="button-default flex items-center gap-3 relative"
            @click="toggleIndexDropdown()">
            <Icon name="fa6-solid:bars" class="p-1" />
            {{ t('common.operations') }}
          </button>
        <div v-if="openIndexDropdown"
          class="absolute top-full right-0 bg-white flex flex-col gap-2 rounded customers-shadow p-2 w-[300px] z-10">
          <button class="button-default" @click="openRegion('manage')">
            <div class="flex justify-between items-center">
              {{ t("contract_block.manage_contracts") }}
              <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />
            </div>
          </button>
          <NuxtLink class="button-default" to="/contract/contracts/payment-manage">
            <div class="flex justify-between items-center">
              {{ t("contract_block.manage_contracts_payment") }}
              <Icon name="fa6-solid:coins" class="display-inline mr-2" />
            </div>
          </NuxtLink>
        </div>
      </div>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-2 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">


      <span class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('contract_block.search')" :disabled="blockSearch"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
      </span>

      <div class="h-8 w-px bg-gray-300"></div>

      <span class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:house" class="text-slate-500" />
        <input v-model="searchAllAddressInput" @input="handleSearch" id="searchAllAddressInput" type="text" name="search"
          :placeholder="$t('contract_block.search_address_info')" :disabled="blockSearch"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
      </span>

      <div class="h-8 w-px bg-gray-300"></div>

      <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" :disabled="blockSearch" /> {{
            status.name }}
        </label>
      </span>

      <span class="flex items-center gap-1">
        <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="isFilterOpen = !isFilterOpen" title="show" :disabled="blockSearch">
          <Icon name="fa:filter" class="text-slate-500" />
        </button>
        <button id="filterAddress" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showAddressSearch }"
          @click="toggleAddressFilter" :disabled="blockSearch"
          :title="$t('address_block.address')">
          <span class="text-slate-500"><Icon name="fa6-solid:house"  />+</span>
        </button>
        <button id="filterEmail" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showEmailSearch }"
          @click="toggleEmailFilter" :disabled="blockSearch"
          :title="$t('contract_block.search_email_info')">
          <span class="text-slate-500"><Icon name="fa6-solid:at" />+</span>
        </button>
        <button id="filterIban" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showIbanSearch }"
          @click="toggleIbanFilter" :disabled="blockSearch"
          :title="$t('contract_block.search_iban_info')">
          <span class="text-slate-500"><Icon name="fa6-solid:building-columns" />+</span>
        </button>
        <button id="filterMeter" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showMeterSearch }"
          @click="toggleMeterFilter" :disabled="blockSearch"
          :title="$t('contract_block.search_meter_info')">
          <span class="text-slate-500"><Icon name="fa6-solid:gauge" />+</span>
        </button>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset" :disabled="blockSearch">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <div class="px-2 text-base flex flex-start gap-2 justify-start items-center flex-wrap" v-if="isFilterOpen">

      <span v-if="showAddressSearch" class="flex items-center gap-2">
        <AtomsInputAddressSearch :value="searchByAddress" @change="handleAddressChange" />
      </span>

      <span v-if="showEmailSearch" class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:at" class="text-slate-500" />
        <input v-model="searchEmailInput" @input="handleSearch" id="searchEmailInput" type="text" name="search"
          :placeholder="$t('contract_block.search_email_info')" :disabled="blockSearch"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
      </span>

      <span v-if="showIbanSearch" class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:building-columns" class="text-slate-500" />
        <input v-model="searchIbanInput" @input="handleSearch" id="searchIbanInput" type="text" name="search"
          :placeholder="$t('contract_block.search_iban_info')" :disabled="blockSearch"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
      </span>

      <span v-if="showMeterSearch" class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:gauge" class="text-slate-500" />
        <input v-model="searchMeterInput" @input="handleSearch" id="searchMeterInput" type="text" name="search"
          :placeholder="$t('contract_block.search_meter_info')" :disabled="blockSearch"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
      </span>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'variable_type')" :options="filter_variable_type"
        :filters="selected_elements" :multiple="true" :placeholder="t(`variables`)"
        @update:modelValue="handleVariableChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'bonification_type')"
        :options="filter_bonification_type" :filters="selected_bonifications" :multiple="true"
        :placeholder="t(`bonifications`)" @update:modelValue="handleBonificationChange($event)">
        <template #icon>
          <Icon name="fa6-solid:coins" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'client_type')" :options="filter_client_type"
        :filters="selected_client_types" :multiple="true" :placeholder="t(`contract_block.client_type`)"
        @update:modelValue="handleClientTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:users" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'category')" :options="filter_category"
        :filters="selected_categories" :multiple="true" :placeholder="t(`contract_block.category`)"
        @update:modelValue="handleCategoryChange($event)">
        <template #icon>
          <Icon name="fa6-solid:tag" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'use_type')" :options="filter_use_type"
        :filters="selected_use_types" :multiple="true" :placeholder="t(`common.usage_type`)"
        @update:modelValue="handleUseTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:wrench" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'payment_method')" :options="filter_payment_type"
        :filters="selected_payment_type" :multiple="true" :placeholder="t(`common.payment_method`)"
        @update:modelValue="handlePaymentTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:coins" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'comm_type')" :options="filter_comm_type"
        :filters="selected_comm_types" :multiple="false" :placeholder="t(`communication`)"
        @update:modelValue="handleCommTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:envelope" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'company')" :options="filter_company"
        :filters="selected_companies" :multiple="true" :placeholder="t('service_block.companies')"
        @update:modelValue="handleCompanyChange($event)">
        <template #icon>
          <Icon name="fa6-solid:building" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'block_billing')" :options="filter_block_billing"
        :filters="selected_block_billing" :multiple="false" :placeholder="t('contract_block.block_billing')"
        @update:modelValue="handleBlockBillingChange($event)">
        <template #icon>
          <Icon name="fa6-solid:percent" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'has_debt')" :options="filter_has_debt"
        :filters="selected_has_debt" :multiple="false" :placeholder="t('common.debt')"
        @update:modelValue="handleHasDebtChange($event)">
        <template #icon>
          <Icon name="fa6-solid:euro-sign" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'debt_management')"
        :options="filter_debt_management" :filters="selected_debt_management" :multiple="true"
        :placeholder="t(`contract_block.debt_management`)" @update:modelValue="handleDebtManagementChange($event)">
        <template #icon>
          <Icon name="fa6-solid:percent" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'total_persons_min')"
        :options="filter_total_persons_min" :filters="selected_total_persons_min" :multiple="false"
        :placeholder="t(`contract_block.total_persons`)" @update:modelValue="handleTotalPersonsMinChange($event)">
        <template #icon>
          <Icon name="fa6-solid:users" class="text-md ml-2 mr-1" size="10px" />
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
      table-key="contracts"
      :columns="tableColumns"
      :items="items"
      :row-class="rowClass"
      :current-sort-by="sortBy"
      :sort-desc="sortDesc"
      pin-column
      :pending="pending"
      :loading="loading"
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
          <span class="flex items-center gap-1 min-w-0">
            <abbr :title="item.id" class="no-underline min-w-0">
              <AtomsContractBadge class="cursor-pointer" :contract="item" :reverse="false" :color="'white'" />
            </abbr>
            <Icon v-if="isFireContract(item)" name="mdi:fire-hydrant" class="text-red-500 shrink-0"
              :title="t('common.fire_hydrant')" />
            <Icon v-if="isSupplyPointCut(item)" name="fa6-solid:droplet-slash" class="text-red-600 shrink-0"
              :title="t('service_block.active_supply_cut_warning')" />
          </span>
          <Icon name="fa6-solid:eye"
            class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
        </button>
      </template>

      <template #cell-supply_point="{ item }">
        <span class="truncate" :title="item.supply_point">{{ item.supply_point }}</span>
      </template>
      <template #cell-holder="{ item }">
        <span class="truncate" :title="`${item.holder_name} ${item.holder_surname}`">{{ item.holder_name }} {{ item.holder_surname }}</span>
      </template>
      <template #cell-meter="{ item }">{{ item.meter_code || '-' }}</template>

      <template #cell-status="{ item }">
        <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
        <abbr v-if="item.active_contract_termination" class="flex items-center"
          :title="t('contract_block.contract_in_termination')">
          <Icon name="fa-solid:exclamation-circle" class="text-orange-500 mt-auto" />
        </abbr>
      </template>

      <template #cell-client_type="{ item }">{{ item.client_type }}</template>
      <template #cell-category="{ item }">{{ item.category_name }}</template>
      <template #cell-use_type="{ item }">{{ item.use_type_name }}</template>

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
    class="fixed z-20 h-full border-l border-gray-100 top-0 transition-[right,width] duration-500 ease py-2 text-base bg-white"
    :class="[showRegion ? 'right-0' : 'right-[-2000px]', isSubRegionOpen ? 'w-[95%]' : 'w-[60%]']">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <ContractRegion v-if="detail" :id="parseInt(detail)" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="handleChange" @close-subregion="toggleRegion(false)">
      </ContractRegion>
      <ManageContractsRegion v-if="editManageRegion" @close="toggleRegion(false)"></ManageContractsRegion>
    </div>
  </div>

</template>
