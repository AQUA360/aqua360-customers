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
const props = defineProps({
  selected_items: {
    type: Array,
    default: () => []
  },
  multiple: {
    type: Boolean,
    default: true
  },
  show: {
    type: Boolean,
    default: false
  },
  contract: {
    type: String,
    default: null
  },
  info: false,
  payment_bank_final: {
    type: String,
    default: null
  },
  total_final: Number,
  // Espai (px) que s'ha de descomptar de l'alçada de la finestra per calcular
  // l'alçada del llistat. Les pantalles amb barra fixa inferior (p.ex. la de
  // remeses SEPA) hi han de sumar l'alçada d'aquesta barra, si no la paginació
  // queda tapada i no es pot canviar de pàgina.
  height_offset: {
    type: Number,
    default: 200
  },
});

const { t } = useI18n();
const router = useRouter();
const { $InvoiceApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const filter_payment_type_tokens = ref([]);
const selectedFilters = ref([]);
const selectedPaymentTypeTokens = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const selectedInvoices = ref([]);
const searchInputTotalFinal = ref(props.total_final || '');

const statuses = ref([])
const payment_type_tokens = ref([]);
const filter_invoice_kinds = ref([]);
const selectedInvoiceKinds = ref([]);
const invoice_kinds = ref([]);
const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const emits = defineEmits(['item-clicked']);


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
  if (props.info) {
    let url = `/billing/invoice/?id=${invoice.id}`
    const newWindow = window.open(url, '_blank');
    if (newWindow) {
      newWindow.focus();
    }
    return;
  }
  if (props.multiple) {
    if (selectedInvoices.value.includes(invoice.id)) {
      var index = selectedInvoices.value.indexOf(invoice.id);
      if (index > -1) {
        selectedInvoices.value.splice(index, 1);
      }
    }
    else
      selectedInvoices.value.push(invoice.id)
  }
  else {
    selectedInvoices.value = [invoice.id]
  }

  emits('item-clicked', invoice);

})

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false,) => {
  pending.value = true;
  error.value = null;
  try {
    let data
    if (props.payment_bank_final) {
      data = await $InvoiceApiService.getInvoiceByCustomerToken(
        searchQuery, filters, page, props.payment_bank_final
      );
    } else {
      data = await $InvoiceApiService.getAll(
        searchQuery, filters, page, sort,
        desc, props.contract, null, null, null,
        null, null, [], searchInputTotalFinal.value, payment_type_tokens.value,
        null, null, null, invoice_kinds.value);
    }
    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0
        || String(searchInputTotalFinal.value).trim() !== ''
        || payment_type_tokens.value.length > 0
        || invoice_kinds.value.length > 0
    });
  } catch (err) {
    console.error('Error obtenint les dades:', err);
  } finally {
    pending.value = false;
  }
}

// El focus s'ha de posar només quan s'obre el panell. Abans es feia a cada
// getData(), així que qualsevol recàrrega (escriure a un altre filtre, canviar
// de pàgina, ordenar) robava el cursor i el tornava a la primera casella.
const focusSearchInput = () => {
  nextTick(() => {
    document.getElementById('searchInput')?.focus();
  });
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/invoice-status');
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterPaymentTypeTokens = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    filter_payment_type_tokens.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleTotalFinalInput = (event) => {
  const value = event.target.value;
  // Only allow numbers, dots, and commas
  const filtered = value.replace(/[^0-9.,]/g, '');
  searchInputTotalFinal.value = filtered;
  handleSearch();
}

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
  // Aquests tres filtres no es netejaven: en reiniciar desapareixien els xips
  // de la interfície però la cerca seguia aplicant-los.
  searchInputTotalFinal.value = '';
  selectedPaymentTypeTokens.value = [];
  payment_type_tokens.value = [];
  selectedInvoiceKinds.value = [];
  invoice_kinds.value = [];
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

const handleInvoiceKindChange = (event) => {
  selectedInvoiceKinds.value = event;
  invoice_kinds.value = event.map(element => element.id);
  pagination.value.page = 1;
  handleSearch();
}

const handlePaymentTypeTokenChange = (event) => {
  selectedPaymentTypeTokens.value = event;
  payment_type_tokens.value = []
  selectedPaymentTypeTokens.value.forEach(element => {
    payment_type_tokens.value.push(element.token);
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
  if (isFilterShown.value.some(filter => filter.id === 'payment_type_token') && !newFilters.some(filter => filter.id === 'payment_type_token')) {
    payment_type_tokens.value = [];
    selectedPaymentTypeTokens.value = [];
    handleSearch();
  }
  if (isFilterShown.value.some(filter => filter.id === 'invoice_kind') && !newFilters.some(filter => filter.id === 'invoice_kind')) {
    invoice_kinds.value = [];
    selectedInvoiceKinds.value = [];
    handleSearch();
  }
}

onMounted(() => {
  getData();
  getFilterStatus();
  getFilterPaymentTypeTokens();
  loadSelected();
  focusSearchInput();

  // Els tipus de factura no són un catàleg de base de dades: `Invoice.type`
  // només distingeix Pressupost/Factura. El backend els deriva de l'origen i,
  // en el cas de les despeses d'impagats, de la PriceRate de la línia.
  filter_invoice_kinds.value = [
    { id: 'consumption', name: t('billing_block.invoice_kind_consumption') },
    { id: 'registration', name: t('billing_block.invoice_kind_registration') },
    { id: 'unpaid_fee', name: t('billing_block.invoice_kind_unpaid_fee') },
    { id: 'connection', name: t('billing_block.invoice_kind_connection') },
    { id: 'supply', name: t('billing_block.invoice_kind_supply') },
    { id: 'other', name: t('billing_block.invoice_kind_other') },
  ];

  filtersExtra.value.push(
    { name: t("common.status"), id: "status" },
    { name: t("common.payment_method"), id: "payment_type_token" },
    { name: t("billing_block.invoice_kind"), id: "invoice_kind" },
  );
});


const loadSelected = () => {
  props.selected_items.forEach(item => {
    if (!selectedInvoices.value.includes(item.id)) {
      selectedInvoices.value.push(item.id)
    }
  });
};

// Watch for changes in searchInput and reset pagination to 1
watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

watch(() => props.show, (newValue, oldValue) => {
  getData();
  if (newValue) focusSearchInput();
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-2">{{ $t('invoices') }} </H1>

    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>
      <div class="h-8 w-px bg-gray-300"></div>

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInputTotalFinal" @input="handleTotalFinalInput" id="searchInputTotalFinal" type="text"
          name="search" :placeholder="$t('search_block.search_total_final')"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
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

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'payment_type_token')" :options="filter_payment_type_tokens"
        :filters="selectedPaymentTypeTokens" :multiple="true" :placeholder="t('common.payment_method')"
        @update:modelValue="handlePaymentTypeTokenChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>
      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'invoice_kind')" :options="filter_invoice_kinds"
        :filters="selectedInvoiceKinds" :multiple="true" :placeholder="t('billing_block.invoice_kind')"
        @update:modelValue="handleInvoiceKindChange($event)">
        <template #icon>
          <Icon name="fa6-solid:file-invoice" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect :defaultOpen="false" :options="filtersExtra" :filters="isFilterShown" :multiple="true"
        :selector="true" :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>

    <div id="list" style="overflow-y: auto; width: 100%; max-width: 100%;" :style="{
      minHeight: `calc(100vh - ${height_offset}px)`,
      maxHeight: `calc(100vh - ${height_offset}px)`
    }">
      <div class="heading grid gap-3 text-base border-b items-center" :class="{
        'grid-cols-[100px,150px,200px,100px,100px,200px,100px,100px,15px]': !info,
        'grid-cols-[20px,100px,150px,200px,100px,100px,200px,100px,100px,15px]': info
      }">
        <span v-if="info">&nbsp;</span>
        <TableHeader :label="$t('common.date')" sortKey="issue_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="serie_final" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('common.title')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.origin')" :sortable="false" />
        <TableHeader :label="$t('contract_block.holder')" :sortable="false" />
        <TableHeader :label="$t('billing_block.total_invoice')" sortKey="total_final" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('billing_block.total_to_pay')" sortKey="left_to_pay" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <span>&nbsp;</span>
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
          class="grid cursor-pointer gap-3 text-base border-b items-center bg-white mr-3" :class="{
            'grid-cols-[100px,150px,200px,100px,100px,200px,100px,100px,15px]': !info,
            'grid-cols-[20px,100px,150px,200px,100px,100px,200px,100px,100px,15px]': info,
            'bg-yellow-50': selectedInvoices.includes(item.id)
          }">
          <span v-if="info">
            <AtomsRedirectButton :id="item.id" :path="'/billing/invoice/'" />
          </span>
          <span :class="{ 'selected': selectedInvoices.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.issue_date }}</span>
          <span :class="{ 'selected': selectedInvoices.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">{{ item.serie_final }}</span>
          <span :class="{ 'selected': selectedInvoices.includes(item.id) }" class="p-1 transition-all duration-200">{{
            item.title_final }}</span>
          <span :class="{ 'selected': selectedInvoices.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            <AtomsColorBadge :value="item?.status_name" :color="item?.status_color" />
          </span>
          <span :class="{ 'selected': selectedInvoices.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">
            {{ item.origin_name }}
          </span>
          <span :class="{ 'selected': selectedInvoices.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200 truncate">{{ item.customer_final }}</span>
          <span :class="{ 'selected': selectedInvoices.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">{{ item.total_final ?
              formatMoneyWithCurrency(item.total_final) : '-' }}</span>
          <span :class="{ 'selected': selectedInvoices.includes(item.id) }"
            class="p-1 text-nowrap transition-all duration-200">{{ item.left_to_pay ?
              formatMoneyWithCurrency(item.left_to_pay) : '-' }}</span>

          <!-- <span>&nbsp;</span> -->
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