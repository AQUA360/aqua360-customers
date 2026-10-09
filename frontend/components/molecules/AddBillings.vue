<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { $BillingApiService, $ConfigProjectApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('send_at');
const sortDesc = ref(true);
const selectedBillings = ref([]);

const { t } = useI18n();
const emits = defineEmits(['item-clicked']);

const props = defineProps({
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

const billingClicked = ((billing) => {
  if (props.multiple) {
    if (selectedBillings.value.includes(billing.id)) {
      var index = selectedBillings.value.indexOf(billing.id);
      if (index > -1) {
        selectedBillings.value.splice(index, 1);
      }
    }
    else
      selectedBillings.value.push(billing.id)
  }
  else {
    selectedBillings.value = [billing.id]
  }

  emits('item-clicked', billing);

})

const getData = async (searchQuery = searchInput.value, filters = selectedFilters.value, page = pagination.value.page, sort = sortBy.value, desc = sortDesc.value) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $BillingApiService.getAll(searchQuery, filters, page, sort, desc);

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
    const data = await $ConfiglistApiService.getAll('billing/billing-status');
    filter_status.value = data;
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

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = true;
  }
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  pagination.value.page = 1;
  sortBy.value = 'send_at';
  sortDesc.value = true;
  getData();
};

onMounted(async () => {
  await getFilterStatus();
  await getData();
  loadSelected();
});

const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (!selectedBillings.value.includes(item.id)) {
      selectedBillings.value.push(item.id)
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
    selectedBillings.value = [];
  }
});

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('common.billings') }} </H1>
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
    <div id="list"
      style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);">
      <div
        class="heading sticky top-0 bg-white grid grid-cols-[170px,1fr,70px,80px,100px,80px,15px] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.creation_date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.issue_date')" sortKey="send_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('invoices')" :sortable="false" />
        <span>&nbsp;</span>
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
        <div v-for="item in items" :key="item.id" @click="billingClicked(item)"
          class="grid grid-cols-[170px,1fr,70px,80px,100px,80px,15px] gap-3 text-base border-b items-center bg-white"
          :class="{ 'bg-yellow-50': selectedBillings.includes(item.id) }">
          <span :class="{ 'selected': selectedBillings.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200 truncate">
            {{ item.token }}</span>
          <span :class="{ 'selected': selectedBillings.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200 truncate">
            {{ item.name }}</span>
          <span :class="{ 'selected': selectedBillings.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ formatDate(item.created_at) }}</span>
          <span :class="{ 'selected': selectedBillings.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.send_at ? formatDate(item.send_at) : '-' }}</span>
          <span :class="{ 'selected': selectedBillings.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item.status?.name" :color="item.status?.color"></AtomsColorBadge>
          </span>
          <span :class="{ 'selected': selectedBillings.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.total_invoices }}</span>
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