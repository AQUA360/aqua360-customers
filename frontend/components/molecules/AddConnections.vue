<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import ExploitationRegion from '~/components/organisms/ExploitationRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';


const router = useRouter();
const { $ConnectionApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);
const selectedItems = ref([]);

const emits = defineEmits(['item-clicked']);

const props = defineProps({
  selected_items: Array,
  multiple: Boolean,
  show: Boolean,
  exploitation_id: Number
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

const itemClicked = (async (item) => {
  if (props.multiple) {
    if (selectedItems.value.includes(item.id)) {
      var index = selectedItems.value.indexOf(item.id);
      if (index > -1) {
        selectedItems.value.splice(index, 1);
      }
    }
    else {
      selectedItems.value.push(item.id)
    }
    emits('item-clicked', item);
  }
  else {
    selectedItems.value = [item.id]
    let selectedConnection = await $ConnectionApiService.getDetail(item.id);
    emits('item-clicked', selectedConnection);
  }


})

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'token', desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $ConnectionApiService.getData(searchQuery, filters, page, sort, desc, props.exploitation_id || null);
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
    const data = await $ConnectionApiService.getFilterStatus();
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

onMounted(() => {
  getData();
  getFilterStatus();
  loadSelected();
});

const connectionRegion = ref(null);
const selectedItemId = ref(null);

const showConnectionRegion = (id) => {
  connectionRegion.value = id;
  selectedItemId.value = id;
}

const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (item) {
      if (!selectedItems.value.includes(item.id)) {
        selectedItems.value.push(item.id)
      }
    }
  });
};
// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(() => props.exploitation_id, () => {
  pagination.value.page = 1;
  handleSearch();
})

</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('common.connections') }}</H1>
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
      <div class="heading top-0 sticky bg-white grid grid-cols-[1fr,2fr,1fr,1fr,1fr,1fr,1fr,1fr] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.address')" sortKey="street" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.diameter')" sortKey="diameter_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.usage')" sortKey="use_type_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.short_install_date')" sortKey="installation_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.dma')" sortKey="dma_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('exploitation')" sortKey="exploitation_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
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
        <div v-for="item in items" :key="item.id"
          class="grid grid-cols-[1fr,2fr,1fr,1fr,1fr,1fr,1fr,1fr] cursor-pointer gap-3 text-base border-b items-center"
          :class="{ 'bg-yellow-50': selectedItems.includes(item.id) }" @click="itemClicked(item)">
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="transition-all duration-200">
            <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
          </span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{ item.street }}
            {{ item.street_number && item.street_number != 'None' ? ', ' + item.street_number : '' }}</span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item.status_name" :color="item.status_color"></AtomsColorBadge>
          </span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.diameter?.name }}</span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.use_type?.name }}</span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.installation_at ? formatDate(item.installation_at) : '-' }}</span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200 truncate">{{
            item.dma_name || item.dma_token }}</span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.exploitation_name || item.exploitation_token }}</span>
        </div><!-- end for items -->

        <div v-if="items.length === 0" class="my-3">
          <p class="text-">{{ $t('common.no_records') }}</p>
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