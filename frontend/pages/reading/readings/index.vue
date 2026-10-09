<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DataTable from '~/components/organisms/DataTable.vue';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();

const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  const nextShow = force !== undefined ? force : !showRegion.value;
  const closing = showRegion.value && !nextShow;
  showRegion.value = nextShow;
  if (!showRegion.value) {
    isSubRegionOpen.value = false;
    detail.value = null;
    selectedItemId.value = null;
    if (closing) {
      getData(searchInput.value, [], pagination.value.page, sortBy.value, sortDesc.value);
    }
  }
};

const route = useRoute();
const router = useRouter();
const { $ReadingDocumentApiService, $ReadingApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref('id');
const sortDesc = ref(true);
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
    const data = await $ReadingApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'id', desc = true) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $ReadingDocumentApiService.getAll(searchQuery, filters, page, sort, desc);

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

const downloadFile = async (file) => {
  try {
    await openAuthenticatedFileUrl(file, false);
  } catch (error) {
    console.error(error);
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, [], sortBy.value, sortDesc.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
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

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    getData();
    checkRouteQuery();
  } else {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});
const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
  }else if (route.query?.action == 'filterPage') {
    searchInput.value = route.query.search;
    handleSearch();
  }
}


const showDetail = async (id) => {
  await toggleRegion(false);
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
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('common.enter_readings') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsLecturappHelpLink class="mr-2" />
        <button v-if="permissions?.can_add" @click="router.push('/reading/readings/estimation')" class="button-default flex items-center gap-2">
          <Icon name="fa6-solid:bolt" />
          {{ $t('reading_block.contract_estimation_title') }}
        </button>
        <button
          v-if="permissions?.can_add"
          type="button"
          class="button-primary"
          @click="router.push('/reading/readings/add')"
        >
          {{ $t('common.upload_doc') }}
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
          @click="resetFilters" title="reset"><Icon name="fa6-solid:rotate-right" class="text-slate-500" /></button>
      </span>
    </form>
    <DataTable
      grid-template="150px,150px,1fr,150px"
      :pending="pending"
      :error="error"
      :is-empty="permissions?.can_view && items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.creation_date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.file')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('readings')" sortKey="num_readings" :currentSortBy="sortBy" :sortDesc="sortDesc"
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
                @click="showDetail(item.id);">
                <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
                <Icon name="fa6-solid:eye"
                  class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
              </button>
            </span>
            <span class="p-1">{{ formatDate(item.created_at) }}</span>
            <button class="text-sky-500 hover:text-sky-700" @click="downloadFile(item.file)"><span class="p-1">{{ item.file?.split('/').pop() }}</span></button>
            <span class="p-1">{{ item.num_readings }}</span>
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
      <button @click="toggleRegion(false)"
        class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300"><Icon name="fa6-solid:angles-right"
          class="text-slate-500" /></button>
    </div>
    <div class="pl-10 h-full">
      <MoleculesReadingDocumentRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)"></MoleculesReadingDocumentRegion>
    </div>
  </div>

</template>
