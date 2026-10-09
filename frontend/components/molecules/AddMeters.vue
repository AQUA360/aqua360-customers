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
const { $MeterApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchInputEl = ref(null);
const hasFocusedSearch = ref(false);
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);
const selectedItems = ref([]);

const emits = defineEmits(['item-clicked']);

const props = defineProps({
  selected_items: Array,
  exclude: Number,
  multiple: Boolean,
  show: Boolean,
  allStatuses: {
    type: Boolean,
    default: false
  }
});

const itemClicked = ((item) => {
  if (props.multiple) {
    if (selectedItems.value.includes(item.id)) {
      var index = selectedItems.value.indexOf(item.id);
      if (index > -1) {
        selectedItems.value.splice(index, 1);
      }
    }
    else
    selectedItems.value.push(item.id)
  }
  else {
    selectedItems.value = [item.id]
  }

  emits('item-clicked', item);

})

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'code', desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $MeterApiService.getData(searchQuery, filters, page, sort, desc, false, props.exclude);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0
    });
    
    nextTick(() => {
      // Only focus once on first load. Re-focusing after every search steals the
      // cursor mid-typing on slow servers, and getElementById('searchInput') can
      // hit the parent page's search bar (e.g. supply points) when both are open.
      if (!hasFocusedSearch.value && searchInputEl.value) {
        searchInputEl.value.focus();
        hasFocusedSearch.value = true;
      }
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
    const data = await $MeterApiService.getFilterStatus();
    filter_status.value = data;
    if (props.allStatuses) {
      selectedFilters.value = data.map(s => s.id);
      handleSearch();
    }
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
  loadSelected()
  getData();
  getFilterStatus();
});

const selectedItemId = ref(null);

// Watch for changes in searchInput and reset pagination to 1
watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

const loadSelected = () => {
  
  props.selected_items.forEach(item => {
    if (item) {
      if (!selectedItems.value.includes(item.id)) {
        selectedItems.value.push(item.id)
      }
    }
  });

};

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

</script>
<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-4">
      <H1>{{ $t('common.meters') }}</H1>
    </div>
    <!-- <em class="text-sm text-slate-500 mb-2">
      {{ $t('Comptadors sense punts de subministrament associats') }}
    </em> -->
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input ref="searchInputEl" v-model="searchInput" @input="handleSearch" id="searchInputMeters" type="text" name="search"
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
          @click="resetFilters" title="reset"><Icon name="fa6-solid:rotate-right" class="text-slate-500" /></button>
      </span>
    </form>
    <div id="list"
      style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);">
      <div
        class="heading grid grid-cols-[1fr,1fr,1fr,1fr] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.code')" sortKey="code" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.short_install_date')" sortKey="installation_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.short_uninstall_date')" sortKey="uninstallation_at" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
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
        <div v-for="item in items" :key="item.id" @click="itemClicked(item)"
          class="grid cursor-pointer grid-cols-[1fr,1fr,1fr,1fr] gap-3 text-base border-b items-center bg-white mr-3"
          :class="{ 'bg-yellow-50':selectedItems.includes(item.id) }">
          <span :class="{'selected':selectedItems.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200"> {{ item.code }} </span>
          <span :class="{'selected':selectedItems.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item.status_name" :color="item.status_color"></AtomsColorBadge>
          </span>
          <span :class="{'selected':selectedItems.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.installation_at ? formatDate(item.installation_at) : '-' }}</span>
          <span :class="{'selected':selectedItems.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.uninstallation_at ? formatDate(item.uninstallation_at) : '-' }}</span>
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