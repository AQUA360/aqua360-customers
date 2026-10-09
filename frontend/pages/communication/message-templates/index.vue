<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DataTable from '~/components/organisms/DataTable.vue';
import MessageTemplateRegion from '~/components/organisms/MessageTemplateRegion.vue';
import MessageTemplateEdit from '~/components/organisms/MessageTemplateEdit.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
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
    selectedItemId.value = null
    openAddTemplate.value = false
  }
}

const route = useRoute();
const router = useRouter();
const { $MessageTemplateApiService, $CommunicationApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref(null);
const sortDesc = ref(false);

const openAddTemplate = ref(false)

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, load = true) => {
  pending.value = load;
  error.value = null;

  try {
    const data = await $MessageTemplateApiService.getAll(searchQuery, filters, page, sort, desc);

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

const debouncedGetData = debounce((query, filters, sort, desc, load) => {
  getData(query, filters, pagination.value.page, sort, desc, load);
}, 300);

const handleSearch = (load = true) => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, [], sortBy.value, sortDesc.value, load);
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, [], newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, [], pagination.value.page, sortBy.value, sortDesc.value);
}

const exportColumns = computed(() => [
  { header: t('common.date'), value: (row) => formatDate(row.created_at) },
  { header: t('common.identification'), value: (row) => row.token },
  { header: t('common.name'), value: (row) => row.name },
  { header: t('common.origin'), value: (row) => row.origin_name },
  { header: t('common.templates'), value: (row) => row.total_templates },
]);

const exportMessageTemplates = () => $MessageTemplateApiService.exportData(searchInput.value, [], sortBy.value, sortDesc.value);

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($CommunicationApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getData();
  checkRouteQuery()
});

const checkRouteQuery = () => {
  if (route.query?.id) {
    selectedItemId.value = route.query.id;
    showDetail(route.query.id);
  }
}

const refresh = async (load = true, close = true) => {
  if (load) toggleRegion(!close)
  await handleSearch(load)
}


const showDetail = async (id) => {
  await toggleRegion(false)
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const addTemplate = async () => {
  await toggleRegion(false)
  openAddTemplate.value = true;
  toggleRegion(true);
}
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div v-if="objectPermissions?.can_view" id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('customer_service_block.comms_templates') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="message_templates"
          :total-pages="pagination.totalPages" :server-export-fn="exportMessageTemplates" />
        <button v-if="objectPermissions?.can_change" class="button-primary" @click="addTemplate">
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
      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <DataTable
      grid-template="80px,200px,300px,200px,150px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')"  sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
        @sort="handleSort" />
        <TableHeader :label="$t('common.origin')" sortKey="origin" :currentSortBy="sortBy" :sortDesc="sortDesc"
        @sort="handleSort" />
        <TableHeader :label="$t('common.templates')" sortKey="templates" :currentSortBy="sortBy" :sortDesc="sortDesc"
        @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">

          <span class="p-0">{{ formatDate(item.created_at) }}</span>
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-1 truncate">{{ item.name }}</span>
          <span class="p-1">{{ item.origin_name }}</span>
          <span class="p-1">{{ item.total_templates }}</span>
        </div><!-- end for items -->
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <MessageTemplateRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
        @changed="refresh" @close="toggleRegion(false)"></MessageTemplateRegion>
      <MessageTemplateEdit v-if="openAddTemplate" :item="null" :isSubRegionOpen="isSubRegionOpen" @saved="refresh" @close="toggleRegion(false)"></MessageTemplateEdit>
    </div>
  </div>

</template>
