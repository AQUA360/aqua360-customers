<script setup>
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import VerifactuBatchRegion from '~/components/organisms/VerifactuBatchRegion.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    regionComponent.value = null
    detail.value = null;
    selectedItemId.value = null;
  }
}

// Verifactu statuses:
const statusesColors = {
  'Correcto': 'green',
  'Incorrecto': 'red',
  'ParcialmenteCorrecto': 'yellow',
  'Error': 'red'
}

const route = useRoute();
const router = useRouter();
const { $VerifactuApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref(null);
const sortDesc = ref(false);
const regionComponent = ref(null)
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
    const data = await $VerifactuApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', page = 1, sort = null, desc = false) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $VerifactuApiService.getAllBatches(searchQuery, page, sort, desc);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      const activeInput = document.getElementById('searchInput');
      if (activeInput) {
        activeInput.focus();
      }
    });
  } catch (err) {
    error.value = err;
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

const refresh = () => {
  debouncedGetData(searchInput.value, sortBy.value, sortDesc.value);
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, newPage, sortBy.value, sortDesc.value);
}

// XLSX export — columns mirror the visible table columns (in display order).
const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token },
  { header: t('common.date'), value: (row) => row.sent_at ? formatDate(row.sent_at) : '' },
  { header: t('billing_block.notifications_count'), value: (row) => row.verifactu_notifications_count },
  { header: t('common.status'), value: (row) => row.response_status ? t(`common.verifactu_batch_status.${row.response_status}`) : '' },
]);

// Hybrid export: single page → client-side; multiple pages → server (all-pages, filter-aware).
const exportBatches = () => $VerifactuApiService.exportData(
  searchInput.value, sortBy.value, sortDesc.value,
);

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

const showDetail = async (id, component) => {
  await toggleRegion(false)
  regionComponent.value = component
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    await getData();
    checkRouteQuery()
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id, 'VerifactuBatchRegion')
  }
  if (route?.query?.id) {
      showDetail(route.query.id, 'VerifactuBatchRegion');
    }
}


// Watch for changes in searchInput and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('billing_block.verifactu_comms') }}</H1>
      <span>
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="verifactu_batches"
          :total-pages="pagination.totalPages" :server-export-fn="exportBatches" :sheet-name="$t('billing_block.verifactu_comms')" />
      </span>
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

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <DataTable
      grid-template="150px,1fr,1fr,1fr"
      :pending="pending"
      :error="error"
      :is-empty="permissions?.can_view && items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.date')" sortKey="issue_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.notifications_count')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <template v-if="permissions?.can_view">
          <div v-for="item in items" :key="item.id"
            class="gap-3 text-base border-b items-center bg-white"
            :style="gridStyle"
            :class="{ 'bg-yellow-50': item.id === selectedItemId }">
            <span>
              <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                @click="showDetail(item.id, 'VerifactuBatchRegion');">
                <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
                <Icon name="fa6-solid:eye"
                  class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
              </button>
            </span>
            <span class="p-1">{{ formatDate(item.sent_at) }}</span>
            <span class="p-1">{{ item.verifactu_notifications_count }}</span>
            <span>
              <AtomsColorBadge :value="t(`common.verifactu_batch_status.${item?.response_status}`)" :color="statusesColors[item?.response_status]" />
            </span>
          </div><!-- end for items -->
        </template>
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div v-if="regionComponent" class="px-10">
      <VerifactuBatchRegion v-if="regionComponent === 'VerifactuBatchRegion'" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="refresh" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>

