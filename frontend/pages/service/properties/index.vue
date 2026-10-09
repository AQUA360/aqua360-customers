<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import PropertyRegion from '~/components/organisms/PropertyRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);
const propertyRegion = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const showRegionClass = computed(() => {
  return showRegion.value ? 'translate-x-0' : 'translate-x-[2000px]';
});
const toggleRegion = (force, isReload = false) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    isSubRegionOpen.value = false;
    propertyRegion.value = null
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

const router = useRouter();
const route = useRoute();
const { $PropertyApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const showAddressSearch = ref(false);
const sortBy = ref('token');
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

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $PropertyApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', page = 1, sort = 'token', desc = false, searchByAddressQuery = '') => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    console.log(page)
    const data = await $PropertyApiService.getAll(searchQuery, page, sort, desc, false, searchByAddressQuery);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || String(searchByAddressQuery).trim() !== ''
    });
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

const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.name'), value: (row) => row.name, key: 'name' },
  { header: t('address_block.city'), value: (row) => row.city, key: 'city' },
  { header: t('common.cadastral'), value: (row) => row.cadastral, key: 'cadastral' },
  { header: t('common.short_supply_points'), value: (row) => row.total_supply_points, key: 'total_supply_points' },
  { header: t('route'), value: (row) => row.route?.name },
  { header: t('service_block.route_position'), value: (row) => row.route_position_token, key: 'route_position' },
]);

const exportProperties = (columns) => $PropertyApiService.exportData(searchInput.value, sortBy.value, sortDesc.value, false, searchByAddress.value, columns);

const resetFilters = () => {
  searchInput.value = '';
  searchByAddress.value = '';
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
  checkRouteQuery();
});

const showPropertyRegion = (id) => {
  if (id && selectedItemId.value && String(selectedItemId.value) === String(id) && showRegion.value) {
    toggleRegion(false, true);
    nextTick(() => {
      propertyRegion.value = id;
      selectedItemId.value = id;
      toggleRegion(true);
    });
    return;
  }
  toggleRegion(false);
  propertyRegion.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
  if (route.query.id !== String(id)) {
    router.replace({ path: route.path, query: { ...route.query, id: id } });
  }
}

const checkRouteQuery = () => {
  if (route?.query?.id &&
    !(selectedItemId.value && String(selectedItemId.value) === String(route.query.id) && showRegion.value)) {
    showPropertyRegion(route.query.id);
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('common.properties') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="properties"
          :total-pages="pagination.totalPages" :server-export-fn="exportProperties" />
        <NuxtLink v-if="permissions?.can_add" to="/service/properties/add" class="button-primary">{{ $t('service_block.new_property') }}</NuxtLink>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
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
      grid-template="1fr,2fr,2fr,1fr,1fr,1fr,1fr"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('address_block.city')" sortKey="city_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.cadastral')" sortKey="cadastral" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.short_supply_points')" :sortable="false" />
        <TableHeader :label="$t('route')" :sortable="false" />
        <TableHeader :label="$t('service_block.route_position')" :sortable="false" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showPropertyRegion(item.id);">
              <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-1" :title="item.name">{{ item.name }}</span>
          <span class="p-1" :title="item.city">{{ item.city }}</span>
          <span class="p-1" :title="item.cadastral">{{ item.cadastral }}</span>
          <span class="p-1">{{ item.total_supply_points }}</span>
          <span class="p-1" :title="item.route?.name">{{ item.route?.name }}</span>
          <span class="p-1" :title="item.route_position_token">{{ item.route_position_token }}</span>
        </div><!-- end for items -->
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
      <PropertyRegion v-if="propertyRegion" :id="propertyRegion" @close-subregion="toggleRegion(false)" 
      :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"></PropertyRegion>
    </div>
  </div>

</template>
