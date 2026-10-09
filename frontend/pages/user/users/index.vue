<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import UserRegion from '~/components/organisms/UserRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import DataTable from '~/components/organisms/DataTable.vue';
import { usePermissions } from '~/middleware/permission';

const toast = useToast();
const { permissions, loading } = usePermissions();

const showRegion = ref(false);
const showRegionClass = computed(() => {
  return showRegion.value ? 'translate-x-0' : 'translate-x-[2000px]';
});
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    detail.value = null
    selectedItemId.value = null
  }
}

const router = useRouter();
const { $UserApiService } = useNuxtApp();
const { t } = useI18n();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getData = async (searchQuery = '', page = 1) => {
  if (!permissions?.value.permissions?.view_user) return
  pending.value = true;
  error.value = null;
  try {
    const data = await $UserApiService.getAll(searchQuery, page);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      const searchInputElement = document.getElementById('searchInput');
      if (searchInputElement) {
        searchInputElement.focus();
      }
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

// XLSX export — columns mirror the visible table columns (in display order).
const exportColumns = computed(() => [
  { header: t('user'), value: (row) => row.username },
  { header: t('common.name'), value: (row) => [row.first_name, row.last_name].filter(Boolean).join(' ') },
  { header: t('common.email_long'), value: (row) => row.email || '' },
  { header: t('group'), value: (row) => row.group_name || (row.is_superuser ? t('common.admin') : '') },
]);

// Hybrid export: single page → client-side; multiple pages → server (all-pages, filter-aware).
const exportUsers = () => $UserApiService.exportData(searchInput.value);

const debouncedGetData = debounce((query) => {
  getData(query, pagination.value.page);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value);
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, newPage);
}

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

onMounted(async () => {
  while (loading.value) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!permissions?.value.permissions?.view_user){
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  } 
  await getData();
});

const detail = ref(null);
const selectedItemId = ref(null);

const showDetail = async (id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ t('users') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="users"
          :total-pages="pagination.totalPages" :server-export-fn="exportUsers" :sheet-name="t('users')" />
        <NuxtLink v-if="permissions?.permissions?.change_user" to="/user/users/add" class="button-primary">{{ $t('user_group.new_user') }}</NuxtLink>
      </div>
    </div>

    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>
    </form>

    <DataTable
      grid-template="1fr,1fr,1fr,1fr"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="t('user')" :sortable="false" />
        <TableHeader :label="t('common.name')" :sortable="false" />
        <TableHeader :label="t('common.email_long')" :sortable="false" />
        <TableHeader :label="t('group')" :sortable="false" />
      </template>

      <template #default="{ gridStyle }">
        <template v-if="permissions?.permissions?.view_user">
          <div v-for="item in items" :key="item.id"
            class="gap-3 text-base border-b items-center bg-white"
            :style="gridStyle"
            :class="{ 'bg-yellow-50': item.id === selectedItemId }">
            <span class="p-0">
              <button class="group flex justify-between w-full items-center p-1 text-sky-500"
                @click="showDetail(item.id);">
                <abbr :title="item.username" class="no-underline">{{ item.username }}</abbr>
                <Icon name="fa6-solid:eye"
                  class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
              </button>
            </span>
            <span v-if="item.first_name || item.last_name " class="p-1">{{ item.first_name }} {{ item.last_name }}</span>
            <span v-else class="p-1">-</span>
            <span class="p-1">{{ item.email? item.email : '-' }}</span>
            <span v-if="item.group_name" class="p-1">{{ item.group_name }}</span>
            <span v-else class="p-1">{{ item.is_superuser ? t('common.admin') : '-' }}</span>
          </div>
        </template>
      </template>
    </DataTable>

    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div>

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <UserRegion v-if="detail" :id="parseInt(detail)" :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
      @close-subregion="toggleRegion(false)"></UserRegion>
    </div>
  </div>
</template>
