<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import InvoiceTemplateRegion from '~/components/organisms/InvoiceTemplateRegion.vue';
import InvoiceTemplateEdit from '~/components/organisms/InvoiceTemplateEdit.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    detail.value = null
    editInvoiceTemplate.value = false
  }
}

const route = useRoute();
const router = useRouter();
const { $InvoiceTemplateApiService, $InvoiceApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const regionComponent = ref(null)

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $InvoiceTemplateApiService.getAll(searchQuery, filters, page, sort, desc);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
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
  sortBy.value = null
  selectedFilters.value = []
  pagination.value.page = 1;
  getData();
};

const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.origin'), value: (row) => row.origin?.name, key: 'origin' },
  { header: t('messages'), value: (row) => Number(row.messages ? row.messages.length : 0) },
]);
const exportInvoiceTemplates = (columns) => $InvoiceTemplateApiService.exportData(
  searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, columns
);

onMounted(async () => {
  objectPermissions.value = await checkPermission($InvoiceApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getData();
  checkRouteQuery()
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
  }
};

const handleChange = () => {
  getData()
  toggleRegion(false)
}


const showDetail = (id) => {
  editInvoiceTemplate.value = false
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const editInvoiceTemplate = ref(false)

const addInvoiceTemplate = () => {
  detail.value = null
  editInvoiceTemplate.value = true
  toggleRegion(true)
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
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

const rowClass = (item) => ({
  'bg-yellow-50': item.id === selectedItemId.value,
  'bg-purple-50': item.is_excluded && !(item.id === selectedItemId.value),
});

const tableColumns = computed(() => [
  { key: 'token', label: t('common.identification'), sortKey: 'token', width: 150, min: 105, priority: 1, removable: false },
  { key: 'origin', label: t('common.origin'), sortKey: 'origin', width: 250, min: 120, grow: 1, priority: 1 },
  { key: 'messages', label: t('messages'), sortKey: 'messages', width: 100, min: 80, priority: 2 },
]);
</script>

<template>
  <div v-if="objectPermissions?.can_view" id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('billing_block.invoice_templates') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="invoice_templates"
          :total-pages="pagination.totalPages" :server-export-fn="exportInvoiceTemplates"
          :sheet-name="$t('billing_block.invoice_templates')" />
        <button v-if="objectPermissions?.can_change" class="button-primary" @click="addInvoiceTemplate()">
          {{ $t('common.new_template') }}
        </button>
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

      <div v-if="filter_status.length" class="h-8 w-px bg-gray-300"></div>

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
    <DataTable
      table-key="invoice-templates"
      :columns="tableColumns"
      :items="items"
      :row-class="rowClass"
      :current-sort-by="sortBy"
      :sort-desc="sortDesc"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @sort="handleSort"
      @retry="getData">
      <template #cell-token="{ item }">
        <button class="group flex justify-between w-full items-center text-sky-500 text-nowrap text-left"
          @click="showDetail(item.id);">
          <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
          <Icon name="fa6-solid:eye"
            class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
        </button>
      </template>
      <template #cell-origin="{ item }">
        <AtomsColorBadge :value="item.origin.name" :color="item.color">
        </AtomsColorBadge>
      </template>
      <template #cell-messages="{ item }">{{ item.messages ? item.messages.length : 0 }}</template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[50%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div v-if="showRegion" class="px-10">
      <InvoiceTemplateRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="getData" @close="toggleRegion(false)"/>
      <InvoiceTemplateEdit v-if="editInvoiceTemplate" :id="null" @show-subregion="handleSubRegionEvent"
        @changed="handleChange" @close="toggleRegion(false)"/>
    </div>
  </div>

</template>
