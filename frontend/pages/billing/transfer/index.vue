<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import SEPARemittanceDetail from '~/components/molecules/SEPARemittanceDetail.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useSidebarStore } from '~/stores/useNavSideBar';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import { useToast } from 'vue-toastification';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { checkPermission } from '~/middleware/permission';

const sidebarStore = useSidebarStore();
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
    detail.value = null
    selectedItemId.value = null
    detail_data.value = {}
  }
}

const route = useRoute();
const router = useRouter();
const { $SepaRemittanceApiService, $ConfiglistApiService, $ConfigProjectApiService, $DocumentManagerApiService, $PaymentApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const objectPermissions = ref(null);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const filter_type = ref([]);
const selected_types = ref([]);
const types = ref([]);

const sent_token = ref(null);
const processing_status_token = ref(null);

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
    const data = await $SepaRemittanceApiService.getAll(searchQuery, filters, page, sort, desc, true);

    items.value = data.results;
    // muntem la paginacio
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

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/payment-remittance-status');
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value);
}

const handleFiltersChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'status') && !newFilters.some(filter => filter.id === 'status')) {
    selectedFilters.value = [];
    getData();
  }
}

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  pagination.value.page = 1;
  handleSearch();
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
  selected_types.value = [];
  types.value = [];
  isFilterShown.value = [];
  isFilterOpen.value = false
  getData();
};

const detail_data = ref({})

const showDetail = async (item) => {
  await toggleRegion(false);
  detail.value = item.id;
  selectedItemId.value = item.id;
  detail_data.value = { 'token': item.token, 'date': item.created_at }
  handleSubRegionEvent(true);
  toggleRegion(true);
}

const printDocument = async (doc_id) => {
  try {
    const document_file = await $DocumentManagerApiService.getDetail(doc_id)
    let file = await $DocumentManagerApiService.viewDocument(doc_id);
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url;
    link.download = document_file.document_name;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.log(error)
  }
}

const deleteRemittance = async (item) => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    try {
      await $SepaRemittanceApiService.doDelete(item.id);
      toast.success(t('common.deleted_successfully'));
      await getData();
    } catch (error) {
      console.error(error);
      toast.error(t('common.delete_failed'));
    }
  }
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($PaymentApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  sent_token.value = await $ConfigProjectApiService.get('payment_remittance_status_sent_token');
  filtersExtra.value.push(
    { name: t('common.status'), id: "status" }
  );
  processing_status_token.value = await $ConfigProjectApiService.get('payment_remittance_status_processing_token');
  getData();
  getFilterStatus();
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    const item = items.value.find(item => item.id == route.query.id);
    if (item) {
      showDetail(item);
    }
  } else {
    if (route?.query?.id) {
      const item = items.value.find(item => item.id == route.query.id);
      if (item) {
        showDetail(item);
      }
    }
  }
};

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const reload = () => {
  handleSearch()
  toggleRegion(false);
}

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
      <H1 class="mb-2">{{ $t('common.trf_managements') }}</H1>
      <div class="flex gap-2">
        <NuxtLink v-if="objectPermissions?.can_change" to="/billing/transfer/manage" class="button-primary">{{
          $t('billing_block.short_mng_trf') }}</NuxtLink>
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
        <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="isFilterOpen = !isFilterOpen" title="show">
          <Icon name="fa:filter" class="text-slate-500" />
        </button>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <div class="px-2 text-base flex flex-start gap-2 justify-start items-center" v-if="isFilterOpen">

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'status')" :options="filter_status"
        :filters="selectedFilters" :multiple="true" :placeholder="t(`common.statuses`)"
        @update:modelValue="handleStatusChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
        :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>

    <div id="list" class="flex flex-col overflow-hidden" :style="{
      width: 'calc(100vw - ' + sidebarStore.sidebarWidth + 'px)',
      maxWidth: '100%',
      minHeight: 'calc(100vh - 230px)',
      maxHeight: 'calc(100vh - 230px)',
    }">
      <div class="heading flex-shrink-0 bg-white grid gap-3 text-base border-b items-center"
        style="grid-template-columns: 75px 200px 80px 100px 150px 75px 75px 80px 60px 80px;">
        <TableHeader :label="$t('common.creation')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.payments')" :sortable="false" />
        <TableHeader :label="$t('billing_block.total_amount')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('customer_service_block.sent_to')" sortKey="desired_send_at" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('customer_service_block.sent')" sortKey="sent_at" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('customer_service_block.sent_by')" sortKey="sent_by" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('common.doc')" :sortable="false" />
        <TableHeader :label="$t('common.actions')" :sortable="false" />
      </div>
      <div class="flex-1 min-h-0 overflow-y-auto"
        :style="{ width: 'calc(100vw - ' + sidebarStore.sidebarWidth + 'px)', maxWidth: '100%' }">
        <div v-if="pending">
          <AppLoading :text="$t('common.loading')" />
        </div>
        <div v-else-if="error">
          <p>Error: {{ error.message }}</p>
          <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
              }}</button></p>
        </div>
        <div v-else>
          <div v-for="item in items" :key="item.id" class="grid gap-3 text-base border-b items-center"
            :class="{ 'bg-yellow-50': item.id === selectedItemId }"
            style="grid-template-columns: 75px 200px 80px 100px 150px 75px 75px 80px 60px 80px;">
            <span class="p-1 text-nowrap">{{ formatDate(item.created_at) }}</span>
            <span>
              <button
                class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left truncate"
                @click="showDetail(item);">
                <abbr :title="item.token" class="no-underline truncate">{{ item.token }}</abbr>
                <Icon name="fa6-solid:eye"
                  class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
              </button>
            </span>
            <span class="p-1">{{ item.total_payments }}</span>
            <span class="p-1">{{ formatMoneyWithCurrency(item.total_amount) }}</span>
            <span class="p-1">
              <AtomsProcessColorBadge v-if="item.status_token == processing_status_token" :value="item.status_name"
                :color="item.status_color" :taskId="item.task_id" @refresh="getData"></AtomsProcessColorBadge>
              <AtomsColorBadge v-else :value="item.status_name" :color="item.status_color" />
            </span>
            <span class="p-1">{{ item.desired_send_at ? formatDate(item.desired_send_at) : '-' }}</span>
            <span class="p-1">{{ item.sent_at ? formatDate(item.sent_at) : '-' }}</span>
            <span class="p-1">{{ item.sent_by_username ? item.sent_by_username : '-' }}</span>
            <span class="p-1">
              <button @click="printDocument(item.document)"
                class="w-5 h-5 rounded-full border border-orange-500 text-orange-500 bg-orange-50 hover:bg-orange-100 mx-auto">
                <Icon name="fa6-solid:download" class="m-auto w-3 h-3" />
              </button>
            </span>
            <span class="p-1 flex gap-2 justify-center">
              <button @click.stop="deleteRemittance(item)"
                class="w-6 h-6 rounded-full border border-red-500 text-red-500 bg-red-50 hover:bg-red-100 transition-colors duration-200"
                :title="$t('common.delete')">
                <Icon name="fa6-solid:trash" class="m-auto w-3 h-3" />
              </button>
            </span>
          </div><!-- end for items -->

          <div v-if="items.length === 0" class="my-3">
            <p class="text-">{{ $t('common.no_records') }}</p>
          </div>

        </div><!-- else no-error no-pending -->
      </div><!-- scroll area -->
    </div><!-- end list -->
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[50%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div v-if="showRegion" class="px-10">
      <SEPARemittanceDetail v-if="detail" :remittance_id="detail" :info="detail_data" @remittance-updated="getData"
        @close-subregion="reload()" :isReturn="true" />
    </div>
  </div>

</template>