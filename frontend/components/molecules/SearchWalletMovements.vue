<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '../atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { t } = useI18n();
const router = useRouter();
const { $PaymentApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);

const statuses = ref([])
const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const props = defineProps({
  total_final: Number,
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

const invoiceClicked = ((invoice) => {
  let url = `/billing/wallet-managements/?id=${invoice.id}`
  const newWindow = window.open(url, '_blank');
  if (newWindow) {
    newWindow.focus();
  }
  return;
})

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false,) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $PaymentApiService.getAll(
      searchQuery, filters, page, sort, desc, 
      null, null, null, null, [], null, null, 
      null, [], false, null, null, props.total_final);
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
    console.error('Error obtenint les dades:', err);
  } finally {
    pending.value = false;
  }
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/payment-status');
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
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, statuses.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  statuses.value = []
  pagination.value.page = 1;
  isFilterShown.value = [];
  isFilterOpen.value = false;
  getData();
};

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  statuses.value = []
  selectedFilters.value.forEach(element => {
    statuses.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
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
    statuses.value = [];
    selectedFilters.value = [];
    handleSearch();
  }
}

onMounted(() => {
  getData();
  getFilterStatus();

  filtersExtra.value.push(
    { name: t("common.status"), id: "status" },
  );
});



// Watch for changes in searchInput and reset pagination to 1
watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('payment') }} </H1>

    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <!-- <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
      </span> -->

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

    <div class="mb-2 px-2 text-base flex flex-start gap-2 justify-start items-center" v-if="isFilterOpen">

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'status')" :options="filter_status"
        :filters="selectedFilters" :multiple="true" :placeholder="t(`common.statuses`)"
        @update:modelValue="handleStatusChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect :defaultOpen="false" :options="filtersExtra" :filters="isFilterShown" :multiple="true"
        :selector="true" :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>

    <div id="list"
      style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%; min-height: calc(100vh - 200px); max-height: calc(100vh - 200px);">
      <div
        class="heading grid gap-3 text-base border-b items-center grid-cols-[20px,150px,200px,80px,100px,80px]">
        <span>&nbsp;</span>
        <TableHeader :label="$t('invoice')" sortKey="invoice" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.total')" sortKey="amount" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.payment')" sortKey="payment_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.limit')" sortKey="due_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
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
        <div v-for="item in items" :key="item.id" @click="invoiceClicked(item)"
          class="grid cursor-pointer gap-3 text-base border-b items-center bg-white mr-3 grid-cols-[20px,150px,200px,80px,100px,80px]">
          <span>
            <AtomsRedirectButton :id="item.id" :path="'/billing/wallet-managements/'" />
          </span>
          <span class="p-1 text-nowrap transition-all duration-200 truncate">{{ item.name }}</span>
          <span class="p-1 text-nowrap transition-all duration-200">{{ formatMoneyWithCurrency(item.amount) }}</span>
          <span>{{ item.payment_date ? formatDate(item.payment_date) : '-'  }}</span>
          <span class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item?.status.name" :color="item?.status.color" />
          </span>
          <span class="p-1 text-nowrap transition-all duration-200">
            {{ item.due_date ? formatDate(item.due_date) : '-' }}
          </span>

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