<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import debounce from 'lodash.debounce';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { $SupplyCutApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('date_start');
const sortDesc = ref(true);
const selectedSupplyCut = ref([]);

// Status ids are installation specific, so the default selection is resolved
// by name against the status catalogue instead of being hardcoded.
const DEFAULT_STATUS_NAMES = ['Actiu', 'Planificat'];

const emits = defineEmits(['item-clicked']);

const props = defineProps({
  selected_items: {
    type: Array,
    default: () => []
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  multiple: {
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

let requestSeq = 0;

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'date_start', desc = true) => {
  const seq = ++requestSeq;
  pending.value = true;
  error.value = null;
  try {
    const data = await $SupplyCutApiService.getData(searchQuery, filters, page, sort, desc);
    if (seq !== requestSeq) return;
    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0
    });

    nextTick(() => {
      const searchInputElement = document.getElementById('searchInput');
      if (searchInputElement) {
        searchInputElement.focus();
      }
    });
  } catch (err) {
    if (seq !== requestSeq) return;
    error.value = err;
  } finally {
    if (seq === requestSeq) {
      pending.value = false;
    }
  }
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $SupplyCutApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }
}

const applyDefaultStatuses = () => {
  selectedFilters.value = filter_status.value
    .filter((status) => DEFAULT_STATUS_NAMES.includes(status.name))
    .map((status) => status.id);
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

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  pagination.value.page = 1;
  getData();
};

const supplyCutClicked = (supplyCut) => {
  if (props.multiple) {
    const index = selectedSupplyCut.value.indexOf(supplyCut.id);
    if (index > -1) {
      selectedSupplyCut.value.splice(index, 1);
    } else {
      selectedSupplyCut.value.push(supplyCut.id);
    }
  } else {
    selectedSupplyCut.value = [supplyCut.id];
  }

  emits('item-clicked', supplyCut);
}

onMounted(async () => {
  await getFilterStatus();
  applyDefaultStatuses();
  await getData('', selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
  loadSelected();
});

const loadSelected = () => {
  props.selected_items.forEach((item) => {
    if (!selectedSupplyCut.value.includes(item.id)) {
      selectedSupplyCut.value.push(item.id);
    }
  });
};

watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(() => props.selected_items, (newValue) => {
  if (!newValue || newValue.length === 0) {
    selectedSupplyCut.value = [];
  }
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('common.supply_cuts') }}</H1>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" id="searchInput" type="text" name="search"
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

    <div id="list"
      style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);">
      <div
        class="heading grid grid-cols-[100px,90px,150px,120px,120px,120px,120px] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.affected_sp')" :sortable="false" />
        <TableHeader :label="$t('address_block.address')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.cut_date_expected_start')" sortKey="date_start" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('service_block.cut_date_expected_end')" :sortable="false" />
        <TableHeader :label="$t('order_block.reason')" :sortable="false" />
      </div>

      <div v-if="pending">
        <p>{{ $t('common.loading') }}...</p>
      </div>
      <div v-else-if="error">
        <p>Error: {{ error.message }}</p>
        <p>
          <button @click="getData()" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again') }}</button>
        </p>
      </div>
      <div v-else>
        <div v-for="item in items" :key="item.id" @click="supplyCutClicked(item)"
          class="grid grid-cols-[100px,90px,150px,120px,120px,120px,120px] gap-3 text-base border-b items-center bg-white"
          :class="{ 'bg-yellow-50': selectedSupplyCut.includes(item.id) }">
          <span :class="{ 'selected': selectedSupplyCut.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.token || `#${item.id}` }}</span>
          <span :class="{ 'selected': selectedSupplyCut.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200 text-center">
            {{ item.affected_supply_points }}</span>
          <span :class="{ 'selected': selectedSupplyCut.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200 truncate" :title="item.distinct_streets">
            {{ item.distinct_streets }}</span>
          <span :class="{ 'selected': selectedSupplyCut.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item.status_name ? item.status_name : ''"
              :color="item.status_color ? item.status_color : ''"></AtomsColorBadge>
          </span>
          <span :class="{ 'selected': selectedSupplyCut.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ formatDate(item.date_start) }}</span>
          <span :class="{ 'selected': selectedSupplyCut.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ formatDate(item.date_end) }}</span>
          <span :class="{ 'selected': selectedSupplyCut.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item.cause_name ? item.cause_name : ''"
              :color="item.cause_color ? item.cause_color : ''"></AtomsColorBadge>
          </span>
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
