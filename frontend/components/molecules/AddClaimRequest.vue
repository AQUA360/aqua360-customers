<script setup>
// Selector de gestions d'impagats (regió de «Selecciona una gestió» del procés de comunicació).
import { ref, onMounted, nextTick, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { $ClaimRequestApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
// Les gestions més noves primer (l'identificador és correlatiu)
const sortBy = ref('token');
const sortDesc = ref(true);
const selectedClaimRequest = ref([]);

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const filter_steps = ref([]);
const selected_steps = ref([]);
const steps = ref([]);

const { t } = useI18n();
const emits = defineEmits(['item-clicked']);

const props = defineProps({
  step_has_documents: {
    type: Boolean,
    default: false
  },
  selected_items: {
    type: Array,
    default: () => []
  },
  multiple: {
    type: Boolean,
    default: true
  },
  show: {
    type: Boolean,
    default: false
  },
  is_comm: {
    type: Boolean,
    default: false
  }
});

// Mateixes columnes a la capçalera i a les files
const GRID_COLUMNS = '105px minmax(80px, 1fr) 95px 60px 60px 95px 85px';

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const claimRequestClicked = ((claimRequest) => {
  if (props.multiple) {
    if (selectedClaimRequest.value.includes(claimRequest.id)) {
      var index = selectedClaimRequest.value.indexOf(claimRequest.id);
      if (index > -1) {
        selectedClaimRequest.value.splice(index, 1);
      }
    }
    else
      selectedClaimRequest.value.push(claimRequest.id)
  }
  else {
    selectedClaimRequest.value = [claimRequest.id]
  }

  emits('item-clicked', claimRequest);

})

// Sempre amb la cerca, els filtres i l'ordre actuals
const getData = async (page = pagination.value.page) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $ClaimRequestApiService.getAll(searchInput.value, selectedFilters.value, page,
      sortBy.value, sortDesc.value, steps.value, null, null, props.is_comm);

    items.value = data.results;
    Object.assign(pagination.value, {
      page,
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchInput.value).trim() !== '' || selectedFilters.value.length > 0
    });

    nextTick(() => {
      document.getElementById('searchInput')?.focus();
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
    const data = await $ConfiglistApiService.getAll('claimrequest/claim-request-status');
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getClaimSteps = async () => {
  error.value = null;
  try {
    const data = await $ClaimRequestApiService.getClaimRequestStepTemplates();
    filter_steps.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce(() => getData(1), 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData();
}

const handleFilterChange = () => {
  handleSearch();
}

const handleStepFiltersChange = (event) => {
  // L'API espera una llista d'ids de pas
  steps.value = (event || []).map(step => step.id);
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
  if (isFilterShown.value.some(filter => filter.id === 'step') && !newFilters.some(filter => filter.id === 'step')) {
    selected_steps.value = [];
    steps.value = [];
    getData(1);
  }
}

const handlePageChange = (newPage) => {
  getData(newPage);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(1);
}

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  selected_steps.value = []
  steps.value = []
  isFilterShown.value = [];
  isFilterOpen.value = false
  getData(1);
};

onMounted(async () => {
  filtersExtra.value.push(
    { name: t("billing_block.step"), id: "step" },
  );
  await getFilterStatus();
  await getClaimSteps();
  await getData(1);
  loadSelected();
});

const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (!selectedClaimRequest.value.includes(item.id)) {
      selectedClaimRequest.value.push(item.id)
    }
  });
};

watch(searchInput, () => {
  handleSearch();
});

watch(() => props.show, () => {
  getData(1);
});

watch(() => props.selected_items, (newValue) => {
  if (!newValue || newValue.length == 0) {
    selectedClaimRequest.value = [];
  }
});

</script>

<template>
  <div class="text-base">
    <H1Region class="mb-2">{{ $t('claim_block.claims_payments') }}</H1Region>
    <p v-if="props.step_has_documents" class="text-slate-500 text-sm">({{ $t('address_block.only_docs') }})</p>

    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-wrap gap-x-4 gap-y-1 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex items-center gap-2 w-64">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <span class="flex flex-wrap gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-sm flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" />
          {{ status.name }}
        </label>
      </span>

      <span class="ml-auto flex">
        <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="isFilterOpen = !isFilterOpen" title="show">
          <Icon name="fa:filter" class="text-slate-500" />
        </button>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <div class="mb-2 px-2 text-base flex flex-start gap-2 justify-start items-center" v-if="isFilterOpen">

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'step')" :options="filter_steps"
        :filters="selected_steps" :multiple="false" :placeholder="t(`address_block.step`)"
        @update:modelValue="handleStepFiltersChange($event)">
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

    <div class="grid gap-3 text-base border-b items-center" :style="{ gridTemplateColumns: GRID_COLUMNS }">
      <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
        @sort="handleSort" />
      <TableHeader :label="$t('billing_block.step')" sortKey="current_step__name" :currentSortBy="sortBy"
        :sortDesc="sortDesc" @sort="handleSort" />
      <TableHeader :label="$t('common.status')" sortKey="status__name" :currentSortBy="sortBy" :sortDesc="sortDesc"
        @sort="handleSort" />
      <TableHeader :label="$t('contracts')" :sortable="false" />
      <TableHeader :label="$t('billing_block.payments')" :sortable="false" />
      <TableHeader :label="$t('common.amount')" :sortable="false" class="text-right" />
      <TableHeader :label="$t('common.due_date')" sortKey="due_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
        @sort="handleSort" />
    </div>

    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData()" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else class="overflow-y-auto" style="max-height: calc(100vh - 260px);">
      <button v-for="item in items" :key="item.id" type="button" @click="claimRequestClicked(item)"
        class="grid gap-3 w-full text-left text-base border-b items-center hover:bg-slate-100"
        :class="{ 'bg-yellow-50': selectedClaimRequest.includes(item.id) }"
        :style="{ gridTemplateColumns: GRID_COLUMNS }">
        <span class="p-1 text-sky-500 truncate" :title="item.token">{{ item.token }}</span>
        <span class="p-1 truncate" :title="item.current_step?.name">{{ item.current_step?.name || '-' }}</span>
        <span class="p-1">
          <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
        </span>
        <span class="p-1 tabular-nums">{{ item.total_contracts }}</span>
        <span class="p-1 tabular-nums">{{ item.total_payments }}</span>
        <span class="p-1 text-right tabular-nums text-nowrap">{{ formatMoneyWithCurrency(item.amount || 0) }}</span>
        <span class="p-1 text-nowrap">{{ item.due_date ? formatDate(item.due_date) : '-' }}</span>
      </button>

      <div v-if="items.length === 0" class="my-3">
        <p class="text-slate-500">{{ $t('common.no_records') }}</p>
      </div>
    </div>

    <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
  </div>
</template>
