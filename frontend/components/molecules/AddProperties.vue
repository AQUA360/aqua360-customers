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
const { $PropertyApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);
const selectedItems = ref([]);
const searchByAddress = ref('');
const showAddressSearch = ref(false);
const searchInputEl = ref(null);

const emits = defineEmits(['item-clicked']);

const props = defineProps({
  selected_items: Array,
  multiple: Boolean,
  show: Boolean,
  only_unassigned: Boolean,
  fitContainer: { type: Boolean, default: false }
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

const focusSearchUnlessOtherFieldActive = () => {
  nextTick(() => {
    const el = searchInputEl.value;
    if (!el) return;
    const active = document.activeElement;
    if (active && active !== el) {
      const tag = active.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || active.isContentEditable)
        return;
    }
    el.focus();
  });
};

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

const getData = async (searchQuery = '', page = 1, sort = 'token', desc = false, searchByAddressQuery = '') => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $PropertyApiService.getAll(searchQuery, page, sort, desc, props.only_unassigned, searchByAddressQuery);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: false
    });

    focusSearchUnlessOtherFieldActive();
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}


const debouncedGetData = debounce((query, sort, desc, searchByAddressQuery = '') => {
  getData(query, pagination.value.page, sort, desc, searchByAddressQuery);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, sortBy.value, sortDesc.value, searchByAddress.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, sortBy.value, sortDesc.value, addressString);
}

const toggleAddressFilter = () => {
  showAddressSearch.value = !showAddressSearch.value;
};

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, newPage, sortBy.value, sortDesc.value, searchByAddress.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, pagination.value.page, sortBy.value, sortDesc.value, searchByAddress.value);
}


onMounted(() => {
  getData();
  loadSelected();
});

const selectedItemId = ref(null);

const resetFilters = () => {
  searchInput.value = '';
  searchByAddress.value = '';
  pagination.value.page = 1;
  showAddressSearch.value = false;
  getData();
};

const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (item) {
      if (!selectedItems.value.includes(item.id)) {
        selectedItems.value.push(item.id)
      }
    }
  });
};
// Watch for changes in searchInput and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(() => props.selected_items, (newValue) => {
  selectedItems.value = (newValue || []).map(item => item?.id).filter(id => id != null);
}, { immediate: true, deep: true });

</script>

<template>
  <div id="wrapper" class="text-base" :class="{ 'h-full flex flex-col': fitContainer }">
    <H1 class="mb-2">{{ $t('common.properties') }}</H1>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input ref="searchInputEl" v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset"><Icon name="fa6-solid:rotate-right" class="text-slate-500" /></button>
        <button id="filterAddress" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showAddressSearch }"
          @click="toggleAddressFilter"
          :title="$t('address_block.address')">
          <Icon name="fa6-solid:house" class="text-slate-500" />
        </button>
      </span>
    </form>
    <div v-if="showAddressSearch" class="mb-2 px-2 flex flex-start gap-2 justify-start items-center">
      <AtomsInputAddressSearch :value="searchByAddress" @change="handleAddressChange" />
    </div>
    <div id="list" :class="{ 'flex-1': fitContainer }"
      :style="fitContainer
        ? 'overflow-y: auto; width: 100%; max-width: 100%;'
        : 'overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);'">
      <div
        class="heading grid grid-cols-[1fr,1fr,1fr,1fr,1fr] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.cadastral')" sortKey="cadastral" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('address_block.city')" sortKey="address_city" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.route_pos')" :sortable="false" />
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
          class="grid grid-cols-[1fr,1fr,1fr,1fr,1fr] cursor-pointer gap-3 text-base border-b items-center bg-white mr-3"
          :class="{ 'bg-yellow-50': selectedItems.includes(item.id) }" @click="itemClicked(item)">
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="transition-all duration-200">
            <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
          </span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.name }}</span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.cadastral }}</span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.city }}</span>
          <span :class="{ 'selected': selectedItems.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.route_position_token || '-' }}</span>
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