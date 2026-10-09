<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDateTime } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import SupplyCutRegion from '~/components/organisms/SupplyCutRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    itemDetail.value = null;
    selectedItemId.value = null;
  }
}

const router = useRouter();
const route = useRoute();
const { $SupplyCutApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const showAddressSearch = ref(false);
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const permissions = ref(null);
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

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $SupplyCutApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, searchByAddressQuery = '') => {
  if (!permissions.value?.can_view) {
    requestSeq++;
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  const seq = ++requestSeq;
  pending.value = true;
  error.value = null;
  try {
    const data = await $SupplyCutApiService.getData(searchQuery, filters, page, sort, desc, null, null, searchByAddressQuery);
    if (seq !== requestSeq) return;
    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0 || String(searchByAddressQuery).trim() !== ''
    });

    nextTick(() => {
      document.getElementById('searchInput').focus();
    });
  } catch (err) {
    if (seq !== requestSeq) return;
    error.value = err;
    if (err?.response?.status === 401) {
      pending.value = false;
    }
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

const debouncedGetData = debounce((query, filters, sort, desc, searchByAddressQuery = '') => {
  getData(query, filters, pagination.value.page, sort, desc, searchByAddressQuery);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, searchByAddress.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, addressString);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value, searchByAddress.value);
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
  selectedFilters.value = [];
  pagination.value.page = 1;
  showAddressSearch.value = false;
  getData();
};

const toggleAddressFilter = () => {
  showAddressSearch.value = !showAddressSearch.value;
};

onMounted(async () => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  await getData();
  getFilterStatus();
  checkRouteQuery();
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    toggleRegion(false);
    showItemDetail(route.query.id)
  }
}

const itemDetail = ref(null);

const requestDeleted = () => {
  toggleRegion(false)
  getData();
}

const showItemDetail = async (id) => {
  await toggleRegion(false);
  itemDetail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const regionAccept = () => {
  getData();
  toggleRegion(false);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const formattedSupplyPointIds = (item) => {
  return Array.isArray(item?.supply_point_ids)
    ? item.supply_point_ids.join("\n")
    : t("service_block.no_affected_sp")
}
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('common.supply_cuts') }}</H1>
      <NuxtLink v-if="permissions?.can_add" to="/service/supply-cut/add" class="button-primary">{{ $t('service_block.new_supply_cut') }}</NuxtLink>
    </div>
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
        <label v-for="status in filter_status" class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
      </span>

      <span class="flex items-center gap-1">
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
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
    <DataTable
      grid-template="80px,70px,300px,170px,150px,150px,150px,150px,170px,15px"
      :pending="pending"
      :error="error"
      :is-empty="permissions?.can_view && items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="id" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.affected_sp')" :sortable="false" />
        <TableHeader :label="$t('address_block.address')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.cut_date_expected_start')" :sortable="false" />
        <TableHeader :label="$t('service_block.cut_date_expected_end')" :sortable="false" />
        <TableHeader :label="$t('service_block.cut_date_real_start')" :sortable="false" />
        <TableHeader :label="$t('service_block.cut_date_real_end')" :sortable="false" />
        <TableHeader :label="$t('order_block.reason')" :sortable="false" />
        <span>&nbsp;</span>
      </template>

      <template #default="{ gridStyle }">
        <template v-if="permissions?.can_view">
          <div v-for="item in items" :key="item.id"
            class="gap-3 text-base border-b items-center bg-white mr-2"
            :style="gridStyle"
            :class="{ 'bg-yellow-50': item.id === selectedItemId }">

            <span>
              <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                @click="showItemDetail(item.id);">
                <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
                <Icon name="fa6-solid:eye"
                  class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
              </button>
            </span>

            <span class="p-1 truncate whitespace-nowrap text-center">
              <abbr :title="formattedSupplyPointIds(item)" class="no-underline">{{ item.affected_supply_points }}</abbr>
            </span>

            <span class="p-1 truncate" :title="item.distinct_streets">{{ item.distinct_streets || "" }}</span>

            <span class="p-1 text-nowrap flex items-center gap-2">
              <AtomsColorBadge :value="item.status_name? item.status_name : ''" :color="item.status_color? item.status_color : ''"></AtomsColorBadge>
              <abbr v-if="item.requires_review" :title="$t('service_block.requires_review')"
                class="flex items-center">
                <Icon name="fa6-solid:exclamation" class="text-amber-500" />
              </abbr>
            </span>

            <span class="p-1">
              {{ item.date_start ? formatDateTime(item.date_start) : "" }}
            </span>

            <span class="p-1">
              {{ item.date_end ? formatDateTime(item.date_end) : "-" }}
            </span>

            <span class="p-1">
              {{ item.exec_start ? formatDateTime(item.exec_start) : "" }}
            </span>

            <span class="p-1">
              {{ item.exec_end ? formatDateTime(item.exec_end) : "-" }}
            </span>

            <span class="p-1 text-nowrap">
              <AtomsColorBadge :value="item.cause_name? item.cause_name : ''" :color="item.cause_color? item.cause_color : ''"></AtomsColorBadge>
            </span>
            <span>&nbsp;</span>
          </div><!-- end for items -->
        </template>
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <SupplyCutRegion v-if="itemDetail" :id="itemDetail" @accept="regionAccept" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @deleted="requestDeleted" @changed="getData" @close-subregion="toggleRegion(false)"></SupplyCutRegion>
    </div>
  </div>

</template>