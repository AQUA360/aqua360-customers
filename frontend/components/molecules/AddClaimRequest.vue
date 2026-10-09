<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { $ClaimRequestApiService, $ConfigProjectApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);
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

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'token', desc = false,) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $ClaimRequestApiService.getAll(searchQuery, filters, page, sort, desc, steps.value, null, null, props.is_comm);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0
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

const handleStepFiltersChange = (event) => {
  steps.value = event[0].id;
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
  if (isFilterShown.value.some(filter => filter.id === 'step') && !newFilters.some(filter => filter.id === 'step')) {
    filter_steps.value = [];
    selected_steps.value = [];
    getData();
  }
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
  pagination.value.page = 1;
  selected_steps.value = []
  steps.value = []
  isFilterShown.value = [];
  isFilterOpen.value = false
  getData();
};

onMounted(async () => {
  filtersExtra.value.push(
    { name: t("billing_block.step"), id: "step" },
  );
  await getFilterStatus();
  await getClaimSteps();
  await getData('', selectedFilters.value);
  loadSelected();
});

const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (!selectedClaimRequest.value.includes(item.id)) {
      selectedClaimRequest.value.push(item.id)
    }
  });
};

// Watch for changes in searchInput and reset pagination to 1
watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(() => props.show, (newValue, oldValue) => {
  getData();
});

watch(() => props.selected_items, (newValue, oldValue) => {
  if (!newValue || newValue.length == 0) {
    selectedClaimRequest.value = [];
  }
});

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('claim_block.claims_payments') }} </H1>
    <span class="text-slate-500 text-sm">
      {{ props.step_has_documents ? '(' + $t('address_block.only_docs') + ')' : '' }}
    </span>
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
    <div id="list"
      style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);">
      <div
        class="heading grid grid-cols-[100px,150px,100px,150px,80px,80px,100px,15px] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.step')" sortKey="step" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('contracts')" :sortable="false" />
        <TableHeader :label="$t('billing_block.payments')" :sortable="false" />
        <TableHeader :label="$t('common.amount')" :sortable="false" />
        <TableHeader :label="$t('common.due_date')" sortKey="due_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <span></span>
      </div>

      <div v-if="pending">
        <p>{{ $t('common.loading') }}...</p>
      </div>
      <div v-else-if="error">
        <p>Error: {{ error.message }}</p>
        <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button></p>
      </div>
      <div v-else>
        <div v-for="item in items" :key="item.id" @click="claimRequestClicked(item)"
          class="grid grid-cols-[100px,150px,100px,150px,80px,80px,100px,15px] gap-3 text-base border-b items-center bg-white"
          :class="{ 'bg-yellow-50': selectedClaimRequest.includes(item.id) }">
          <span :class="{ 'selected': selectedClaimRequest.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.token }}</span>
          <span :class="{ 'selected': selectedClaimRequest.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200 truncate">
            {{ item.current_step ? item.current_step.name : '-' }}</span>
          <span :class="{ 'selected': selectedClaimRequest.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item.status_name" :color="item.status_color"></AtomsColorBadge>
          </span>
          <span :class="{ 'selected': selectedClaimRequest.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.total_contracts }}</span>
          <span :class="{ 'selected': selectedClaimRequest.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.total_payments }}</span>
          <span :class="{ 'selected': selectedClaimRequest.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.amount ? formatMoneyWithCurrency(item.amount) : formatMoneyWithCurrency(0) }}</span>
          <span :class="{ 'selected': selectedClaimRequest.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.due_date ? formatDate(item.due_date) : '-' }}</span>
          <span>&nbsp;</span>
        </div><!-- end for items -->

        <div v-if="items.length === 0" class="my-3">
          <p class="text-slate-500">{{ $t('common.no_records') }}</p>
        </div>

      </div><!-- else no-error no-pending -->
    </div><!-- end list -->
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->
</template>

<style scoped>
.selected {
  margin-left: 15px
}
</style>