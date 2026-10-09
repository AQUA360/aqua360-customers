  <script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useI18n } from 'vue-i18n';
import ContractRequestTypeRegion from '~/components/organisms/ContractRequestTypeRegion.vue';
import ContractRequestTypeEditRegion from '~/components/organisms/ContractRequestTypeEditRegion.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const showRegion = ref(false);
const toast = useToast();
const objectPermissions = ref(null);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}
const { t } = useI18n();
const { $ContractRequestTypeApiService, $ContractRequestApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref('token');
const sortDesc = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'token', desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $ContractRequestTypeApiService.getAll(searchQuery, filters, page, sort, desc);

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

const onChangeRegion = (event) => {
  getData(searchInput.value, [], pagination.value.page, sortBy.value, sortDesc.value);
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractRequestApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getData();
});

const regionShowing = ref(false);
const detail = ref(null);
const selectedItemId = ref(null);

const showAddRegion = () => {
  regionShowing.value = 'ContractRequestTypeEditRegion';
  toggleRegion(true);
}

const showDetail = (id) => {
  detail.value = id;
  selectedItemId.value = id;
  regionShowing.value = 'ContractRequestTypeRegion';
  toggleRegion(true);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const handleSavedAdd = (item) => {
  regionShowing.value = false;
  toggleRegion(false);
  showDetail(item.id);
  getData();
}

</script>

<template>
  <div v-if="objectPermissions?.can_view" id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('contract_block.request_type') }}</H1>
      <button v-if="objectPermissions?.can_change" @click="showAddRegion" class="button-primary">{{ $t('contract_block.new_request_type') }}</button>
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
      grid-template="150px,1fr,1fr,1fr,1fr,1fr,1fr,1fr"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.type')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.docs')" :sortable="false" />
        <TableHeader :label="$t('variables')" :sortable="false" />
        <TableHeader :label="$t('common.orders')" :sortable="false" />
        <!-- <TableHeader :label="$t('Fiances')" :sortable="false" /> -->
        <TableHeader :label="$t('contract_block.clauses')" :sortable="false" />
        <TableHeader :label="$t('contract_block.contract_price_rate')" :sortable="false" />
        <TableHeader :label="$t('contract_block.registration_price_rate')" :sortable="false" />
      </template>

      <template #default="{ gridStyle }">
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
          <span class="p-0">{{ item.name }}</span>
          <span class="p-0">{{ item.documentation_types?.length }}</span>
          <span class="p-0">{{ item.variable_types?.length }}</span>
          <span class="p-0">{{ item.order_types?.length }}</span>
          <!-- <span class="p-0">{{ item.bail_types?.length }}</span> -->
          <span class="p-0">{{ item.clause_templates?.length }}</span>
          <span class="p-0">{{ item.price_rates?.length }}</span>
          <span class="p-0">{{ item.registration_price_rates?.length }}</span>
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
      <button @click="toggleRegion(false)"
        class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300"><Icon name="fa6-solid:angles-right"
          class="text-slate-500" /></button>
    </div>
    <div class="pl-10 h-full">
      <ContractRequestTypeRegion v-if="regionShowing == 'ContractRequestTypeRegion'" :id="detail" @close="toggleRegion(false)"
        :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @changed="onChangeRegion" />
      <ContractRequestTypeEditRegion v-if="regionShowing == 'ContractRequestTypeEditRegion'" :item="{ 'id': null }"
        :isSubRegionOpen="isSubRegionOpen" @saved="handleSavedAdd" @close="toggleRegion(false)" />
    </div>
  </div>

</template>
