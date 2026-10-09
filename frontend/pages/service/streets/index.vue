<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import StreetRegion from '~/components/organisms/StreetRegion.vue';
import DataTable from '~/components/organisms/DataTable.vue';

import FilterSelect from '~/components/atoms/FilterSelect.vue';

const toast = useToast();
const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const { $StreetApiService } = useNuxtApp();

const showRegion = ref(false);
const showRegionClass = computed(() => {
  return showRegion.value ? 'translate-x-0' : 'translate-x-[2000px]';
});

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    selectedStreetId.value = null;
  }
}

const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref('name');
const sortDesc = ref(false);
const objectPermissions = ref(null);

const cities = ref([]);
const selectedCity = ref(null);
const loadingCities = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getCitiesList = async () => {
  loadingCities.value = true;
  try {
    const activeExploitationId = localStorage.getItem('exploitation') || 1;
    let exploitationCities = [];
    try {
      const activeExploitation = await $StreetApiService.getDetail ? await useNuxtApp().$ExploitationApiService.getDetail(activeExploitationId) : null;
      if (activeExploitation && activeExploitation.cities) {
        exploitationCities = activeExploitation.cities.map(c => c.id);
      }
    } catch (e) {
      console.error("Error fetching exploitation detail:", e);
    }

    const { $AddressApiService } = useNuxtApp();
    // Retrieve only cities with streets
    const result = await $AddressApiService.getCities('', 1, null, false, true);
    
    // Sort cities: active exploitation's cities first, then others alphabetically
    const sorted = [...result.results].sort((a, b) => {
      const aIsExp = exploitationCities.includes(a.id);
      const bIsExp = exploitationCities.includes(b.id);
      if (aIsExp && !bIsExp) return -1;
      if (!aIsExp && bIsExp) return 1;
      return a.name.localeCompare(b.name);
    });

    cities.value = sorted.map(c => ({
      code: c.id,
      label: c.name
    }));

    if (cities.value.length > 0) {
      selectedCity.value = cities.value[0];
    }
  } catch (err) {
    console.error("Error loading cities:", err);
  } finally {
    loadingCities.value = false;
  }
};

const getData = async (searchQuery = '', page = 1, sort = 'name', desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const cityId = selectedCity.value ? selectedCity.value.code : null;
    const data = await $StreetApiService.getAll(searchQuery, [], page, sort, desc, cityId);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || cityId !== null
    });

    nextTick(() => {
      const el = document.getElementById('searchInput');
      if (el) el.focus();
    });
  } catch (err) {
    error.value = err;
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const debouncedGetData = debounce((query, sort, desc) => {
  getData(query, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, sortBy.value, sortDesc.value);
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const exportColumns = computed(() => [
  { header: t('common.identificator'), value: (row) => row.id, key: 'id' },
  { header: t('common.type'), value: (row) => row.type_abbreviation || row.type?.abbreviation },
  { header: t('common.name'), value: (row) => row.name, key: 'name' },
  { header: t('address_block.city'), value: (row) => typeof row.city === 'object' ? row.city?.name : (row.city_name || row.city) },
]);

const exportStreets = (columns) => $StreetApiService.exportData(searchInput.value, [], sortBy.value, sortDesc.value, selectedCity.value ? selectedCity.value.code : null, columns);

const resetFilters = () => {
  searchInput.value = '';
  if (cities.value.length > 0) {
    selectedCity.value = cities.value[0];
  } else {
    selectedCity.value = null;
  }
  pagination.value.page = 1;
  getData();
};

const selectedStreetId = ref(null);

const showStreetDetail = (id) => {
  selectedStreetId.value = id;
  toggleRegion(true);
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($StreetApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  await getCitiesList();
  getData();
});

watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(selectedCity, () => {
  pagination.value.page = 1;
  getData(searchInput.value, 1, sortBy.value, sortDesc.value);
});
</script>

<template>
  <div v-if="objectPermissions?.can_view" id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('address_block.streets') }}</H1>
      <span>
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="streets"
          :total-pages="pagination.totalPages" :server-export-fn="exportStreets" />
      </span>
    </div>
    
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center pb-2"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <span class="w-80 flex items-center gap-2">
        <label for="city-filter" class="text-slate-500 text-sm whitespace-nowrap">{{ $t('address_block.city') }}:</label>
        <v-select
          id="city-filter"
          class="w-full custom-select"
          v-model="selectedCity"
          :options="cities"
          :placeholder="$t('address_block.select_city')"
        />
      </span>

      <span>
        <button id="filterReset" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <DataTable
      grid-template="100px,100px,1fr,250px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identificator')" sortKey="id" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.type')" sortKey="type__abbreviation" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('address_block.city')" sortKey="city__name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white hover:bg-slate-50 transition-colors"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedStreetId }">
          <span>
            <button class="group flex justify-between w-full items-center p-2 text-sky-500 text-nowrap text-left"
              @click="showStreetDetail(item.id);">
              <abbr :title="item.id" class="no-underline font-mono">{{ item.id }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-2 font-mono text-slate-500">{{ item.type_abbreviation || item.type?.abbreviation }}</span>
          <span class="p-2 font-medium">{{ item.name }}</span>
          <span class="p-2 text-slate-500">{{ typeof item.city === 'object' ? item.city?.name : (item.city_name || item.city) }}</span>
        </div><!-- end for items -->
      </template>
    </DataTable>

    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div>

  <!-- Right Region -->
  <div role="region" id="right_page"
    :class="['fixed', 'w-1/2', 'h-full', 'border-l', 'border-gray-100', 'top-0', 'right-0', 'transition-transform', 'duration-270', 'ease', 'py-2', 'text-base', 'bg-white', showRegionClass, 'shadow-2xl']">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="h-full">
      <StreetRegion v-if="selectedStreetId" :id="selectedStreetId" @close="toggleRegion(false)" @changed="getData(searchInput, pagination.page, sortBy, sortDesc)"></StreetRegion>
    </div>
  </div>
</template>
