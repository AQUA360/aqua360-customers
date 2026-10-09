<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DailyDocumentTemplateRegion from '~/components/organisms/DailyDocumentTemplateRegion.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';
import DailyDocumentTemplateEdit from '~/components/organisms/DailyDocumentTemplateEdit.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);

const subRegionComponent = ref(null);
const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    detail.value = null
    selectedItemId.value = null
    subRegionComponent.value = null;
  }
}

const route = useRoute();
const router = useRouter();
const { $DailyDocumentTemplateApiService, $ReportsApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
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

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ReportsApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;

  try {
    const data = await $DailyDocumentTemplateApiService.getAll(searchQuery, filters, page, sort, desc);

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
  debouncedGetData(searchInput.value, [], sortBy.value, sortDesc.value);
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
  if (route.query?.id) {
    selectedItemId.value = route.query.id;
    showDetail(route.query.id);
  }
}


const showDetail = async (component, id) => {
  await toggleRegion(false)
  subRegionComponent.value = component;
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
      <H1 class="mb-2">{{ $t('statistics_block.daily_document_templates') }}</H1>

      <div class="flex items-center gap-2">
        <button v-if="permissions?.can_add" class="button-primary flex items-center gap-3 relative"
          @click="showDetail('DailyDocumentTemplateEdit', null)">
          <Icon name="fa6-solid:bars" class="p-1" />
          {{ t('common.new_template') }}
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

    <DataTable grid-template="80px,200px,300px,300px,80px,80px" :pending="pending" :loading="pending" :error="error"
      :is-empty="items.length === 0" @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.description')" :sortable="false" />
        <TableHeader :label="$t('common.report_detail')" :sortable="false" />
        <TableHeader :label="$t('common.expires_in')" sortKey="days_to_complete" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <span></span>
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id" class="gap-3 text-base border-b items-center" :style="gridStyle"
          :class="{
            'bg-yellow-50': item.id === selectedItemId,
            'bg-slate-100': !item.is_active,
          }">

          <span class="p-0">{{ formatDate(item.created_at) }}</span>
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail('DailyDocumentTemplateRegion', item.id);">
              <abbr :title="item.token" class="no-underline">{{ item.name }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-1 truncate">{{ item.description || '-' }}</span>
          <span class="p-1">{{ item.available_report_name || '-' }}</span>
          <span class="p-1">{{item.days_to_complete > 0 ?  `${item.days_to_complete} ${t('common.days')}`  : t('common.doe_not_expire')}}</span>
          <span class="p-1 font-bold text-slate-400">{{ item.is_active ? '' : t('common.inactive') }}</span>
        </div><!-- end for items -->
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 pr-3 text-base bg-white overflow-x-hidden"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <DailyDocumentTemplateRegion v-if="subRegionComponent === 'DailyDocumentTemplateRegion'" :id="selectedItemId"
        :isSubRegion="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @changed="getData"
        @close-subregion="toggleRegion(false)" />
      <DailyDocumentTemplateEdit v-if="subRegionComponent === 'DailyDocumentTemplateEdit'" 
      @show-subregion="handleSubRegionEvent" @changed="getData" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>