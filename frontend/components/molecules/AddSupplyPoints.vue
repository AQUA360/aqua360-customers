<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { $SupplyPointApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);
const selectedSupplyPoints = ref([]);

const { t } = useI18n();
const emits = defineEmits(['item-clicked']);

const props = defineProps({
  noMeter: {
    type: Boolean,
    default: false
  },
  noProperty: {
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

const supplyPointClicked = (async (supplyPoint) => {
  if (props.multiple) {
    if (selectedSupplyPoints.value.includes(supplyPoint.id)) {
      var index = selectedSupplyPoints.value.indexOf(supplyPoint.id);
      if (index > -1) {
        selectedSupplyPoints.value.splice(index, 1);
      }
    }
    else
      selectedSupplyPoints.value.push(supplyPoint.id)
      emits('item-clicked', supplyPoint);
  }
  else {
    selectedSupplyPoints.value = [supplyPoint.id]
    let selectedDetail = await $SupplyPointApiService.getDetail(supplyPoint.id);
    emits('item-clicked', selectedDetail);
  }
})

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'token', desc = false,) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $SupplyPointApiService.getList(searchQuery, filters, page, sort, desc, props.noMeter, props.noProperty);

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
    const data = await $SupplyPointApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }

  try {
    /* const data = await $ConfigProjectApiService.get('supply_point_status_activate_token')
    if (data) {
      selectedFilters.value.push(filter_status.value.filter(f => f.token == data)[0].id)
    } */
  } catch (err) {
    console.error(err)
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

onMounted(async () => {
  await getFilterStatus();
  await getData('', selectedFilters.value);
  loadSelected();
});

const supplyPointRegion = ref(null);
const selectedItemId = ref(null);

const showSupplyPointRegion = (id) => {
  supplyPointRegion.value = id;
  selectedItemId.value = id;
}

const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (!selectedSupplyPoints.value.includes(item?.id)) {
      selectedSupplyPoints.value.push(item.id)
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

watch(() => props.noMeter, (newValue, oldValue) => {
  getData();
});

watch(() => props.selected_items, (newValue) => {
  selectedSupplyPoints.value = (newValue || []).map(item => item?.id).filter(id => id != null);
}, { immediate: true, deep: true });

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('common.supply_points') }} </H1>
    <span class="text-slate-500 text-sm">
      {{ props.noMeter ? '(' + $t('service_block.no_meters') + ')' : '' }}
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
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset"><Icon name="fa6-solid:rotate-right" class="text-slate-500" /></button>
      </span>
    </form>
    <div id="list"
      style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);">
      <div
        class="heading grid grid-cols-[80px,35px,150px,250px,150px,150px,150px,150px,150px,150px,150px,150px,150px,15px] gap-3 text-base border-b items-center">
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <span></span>
        <TableHeader :label="$t('common.contracts')" :sortable="false" />
        <TableHeader :label="$t('address_block.address')" sortKey="address_complete" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('address_block.locality')" sortKey="address_city" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.type')" sortKey="type_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('route')" sortKey="property_route_position_token" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('meter')" sortKey="meter_code" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('cluster')" sortKey="cluster_nozzle_token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('connection')" sortKey="connection_token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('contract')" :sortable="false" />
        <TableHeader :label="$t('exploitation')" sortKey="connection_exploitation_name" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
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
        <div v-for="item in items" :key="item.id" @click="supplyPointClicked(item)"
          class="grid grid-cols-[80px,35px,150px,250px,150px,150px,150px,150px,150px,150px,150px,150px,150px,15px] cursor-pointer gap-3 text-base border-b items-center bg-white mr-3"
          :class="{ 'bg-yellow-50':selectedSupplyPoints.includes(item.id) }">
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.token }}</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">
            <abbr v-if="item.current_fraud" :title="t('service_block.supply_with_fraud')" class="">
              <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-orange-500 m-auto" />
            </abbr>
          </span>
          <abbr :title="item.contracts?.map(c => c.token).join(', ')" :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 transition-all duration-200 truncate">
            <span class="truncate">
              {{ item.contracts?.map(c => c.token).join(', ') }}
            </span></abbr>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 transition-all duration-200">{{ item.address_complete }}</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.address_city }}</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.type_name || item.type_token }}</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item.status_name || item.status_token" :color="item.status_color">
            </AtomsColorBadge>
          </span>

          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.property_route_position_token }}</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.meter_code }}</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.cluster_nozzle_token }}</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.connection_name || item.connection_token }}</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">-</span>
          <span :class="{'selected':selectedSupplyPoints.includes(item.id)}" class="p-1 text-nowrap transition-all duration-200">{{ item.connection_exploitation_name || item.connection_exploitation_token
            }}</span>
          <span>&nbsp;</span>
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