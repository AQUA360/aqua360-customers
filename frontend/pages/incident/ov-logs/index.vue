<script setup>
import { ref, onMounted, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import AtomsColorBadge from '~/components/atoms/ColorBadge.vue';
import DatePicker from '~/components/atoms/DatePicker.vue';
import OvLogsRegion from '~/components/organisms/OvLogsRegion.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();

const { $OvLogsApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');

const sortBy = ref(null);
const sortDesc = ref(false);

const showRegion = ref(false);
const selectedItemId = ref(null);
const sideComponent = shallowRef(OvLogsRegion);

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const startDate = ref(null);
const endDate = ref(null);
const dateInputValue = ref('');
const showDatePickerDropdown = ref(false);

const toggleRegion = (id, component = OvLogsRegion) => {
  if (id) {
    selectedItemId.value = id;
    sideComponent.value = component;
    showRegion.value = true;
  } else {
    showRegion.value = false;
    selectedItemId.value = null;
    isSubRegionOpen.value = false;
  }
}

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
    const data = await $OvLogsApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
    permissions.value = { can_view: true };
  }
}

const getData = async (searchQuery = '', page = 1, sort = null, desc = false, start = null, end = null) => {
  pending.value = true;
  error.value = null;

  try {
    const data = await $OvLogsApiService.getAll(
      searchQuery, [], page, sort, desc, 50, start, end
    );

    items.value = data.results || [];
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || start !== null || end !== null
    });
  } catch (err) {
    error.value = err;
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const handleDateRangeSelected = (event) => {
  startDate.value = event.start;
  endDate.value = event.end;
  
  if (event.start && event.end) {
     dateInputValue.value = `${formatDate(event.start)} - ${formatDate(event.end)}`;
  } else if (event.start) {
     dateInputValue.value = `${formatDate(event.start)} - ...`;
  } else {
     dateInputValue.value = '';
  }
  
  showDatePickerDropdown.value = false;
  
  pagination.value.page = 1;
  getData(searchInput.value, pagination.value.page, sortBy.value, sortDesc.value, startDate.value, endDate.value);
};

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, pagination.value.page, sortBy.value, sortDesc.value, startDate.value, endDate.value);
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, newPage, sortBy.value, sortDesc.value, startDate.value, endDate.value);
}

const handleSearch = debounce(() => {
  pagination.value.page = 1;
  getData(searchInput.value, 1, sortBy.value, sortDesc.value, startDate.value, endDate.value);
}, 500);

const resetFilters = () => {
  searchInput.value = '';
  startDate.value = null;
  endDate.value = null;
  dateInputValue.value = '';
  pagination.value.page = 1;
  getData();
};

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    getData();
  } else {
    pending.value = false;
  }
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('common.ov_logs') }}</H1>
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
      <div v-if="showDatePickerDropdown" @click="showDatePickerDropdown = false" class="fixed inset-0 z-40 bg-transparent"></div>

      <span class="input-group flex flex-start items-center gap-2 w-80 relative z-50">
        <Icon name="fa6-regular:calendar" class="text-slate-500" />
        <input type="text" :value="dateInputValue" @click="showDatePickerDropdown = !showDatePickerDropdown"
            :placeholder="$t('search_block.search_date')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 cursor-pointer bg-transparent" readonly />
        
        <div v-if="showDatePickerDropdown" class="absolute top-10 left-0 bg-white border border-gray-200 shadow-xl rounded-md w-[320px] p-2">
           <DatePicker @date-range-selected="handleDateRangeSelected" />
        </div>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <DataTable
      grid-template="180px,200px,150px,150px,1fr"
      :pending="pending"
      :error="error"
      :is-empty="permissions?.can_view && items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.date')" sortKey="timestamp" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.type')" sortKey="type" :currentSortBy="sortBy" :sortDesc="sortDesc"
        @sort="handleSort" />
        <TableHeader :label="$t('contract')" />
        <TableHeader :label="$t('common.app')" />
        <TableHeader :label="$t('common.details')" />
      </template>

      <template #default="{ gridStyle }">
        <template v-if="permissions?.can_view">
          <div v-for="item in items" :key="item.id"
            class="gap-3 text-base border-b items-center bg-white min-h-[40px] hover:bg-sky-50 cursor-pointer"
            :style="gridStyle"
            @click="toggleRegion(item.id)" :class="{ 'bg-sky-50': selectedItemId === item.id }">
            <span class="p-0 text-sm whitespace-nowrap">{{ formatDate(item.timestamp) }}</span>
            <span class="p-1 truncate" :title="item.type">
              {{ $t('ov_logs_block.types.' + item.type) !== 'ov_logs_block.types.' + item.type ? $t('ov_logs_block.types.' + item.type) : item.type }}
            </span>
            <span class="p-1 truncate">
               <button v-if="item.detail?.contract_id" @click.stop="toggleRegion(item.detail.contract_id, ContractRegion)" class="text-sky-600 underline hover:text-sky-400">
                  {{ item.detail.contract }}
               </button>
               <span v-else>-</span>
            </span>

            <span class="p-1">
              <AtomsColorBadge
                :color="item.app === 'billing' ? 'green' : (item.app === 'contract' ? 'blue' : 'gray')"
                :value="$t('ov_logs_block.apps.' + item.app) !== 'ov_logs_block.apps.' + item.app ? $t('ov_logs_block.apps.' + item.app) : item.app"
              />
            </span>

            <span class="p-1 text-sm truncate" :title="item.detail?.field_name ? `${item.detail.field_name}: ${item.detail.old_value} -> ${item.detail.new_value}` : ''">
              <template v-if="item.detail?.field_name">
                  <span class="font-semibold mr-1">{{ item.detail.field_name }}:</span>
                  <span class="text-gray-400">{{ item.detail.old_value || 'None' }}</span>
                  <Icon name="fa6-solid:arrow-right" class="mx-1 text-xs text-gray-300" />
                  <span>{{ item.detail.new_value || 'None' }}</span>
              </template>
              <template v-else-if="item.detail?.reading_value">
                  <span class="font-semibold">{{ $t('reading') }}:</span> {{ item.detail.reading_value }}
              </template>
              <template v-else>-</template>
            </span>
          </div>
        </template>
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>

  </div><!-- end wrapper -->

  <!-- Lateral Region -->
  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-[90]"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3 shrink-0">
      <button @click="toggleRegion(null)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="px-10 h-full">
       <component v-if="selectedItemId" :is="sideComponent" :id="selectedItemId" @close-subregion="toggleRegion(null)" :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
    </div>
  </div>

</template>
