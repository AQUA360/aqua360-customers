<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import Pagination from '~/components/molecules/Pagination.vue';
import H1Region from '../atoms/H1Region.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import AtomsInputDate from '~/components/atoms/InputDate.vue';
import PaymentRegion from '~/components/organisms/PaymentRegion.vue';
import InvoiceRegion from '../organisms/InvoiceRegion.vue';
import CommitmentDepositRegion from '../organisms/CommitmentDepositRegion.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { useToast } from 'vue-toastification';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { checkPermission } from '~/middleware/permission';
import FilterSelect from '~/components/atoms/FilterSelect.vue';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);

const props = defineProps({
  remittance_id: {
    type: Number,
    required: true
  },
  info: Object,
});

const emit = defineEmits(['remittance-updated', 'close-subregion']);

const route = useRoute();
const router = useRouter();
const { $PaymentApiService, $SepaRemittanceReturnApiService, $DocumentManagerApiService, $ConfiglistApiService } = useNuxtApp();
const remittanceDetails = ref(null);
const searchInput = ref('');
const statuses = ref([])
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const showRegion = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    detail.value = null
    selectedItemId.value = null
    selectedItemComponent.value = null
  }
}

const allPayments = computed(() => remittanceDetails.value?.payments || []);

const hasActiveFilters = computed(() => {
  return String(searchInput.value).trim() !== ''
    || statuses.value.length > 0
});

const filteredPayments = computed(() => {
  let payments = allPayments.value;

  if (statuses.value.length > 0) {
    payments = payments.filter((payment) => statuses.value.includes(payment.status?.id));
  }

  const query = searchInput.value.trim().toLowerCase();
  if (query) {
    payments = payments.filter((payment) => {
      const searchableValues = [
        payment.token,
        payment.invoice?.token,
        payment.contract?.token,
        payment.commitment_deposit?.token,
        payment.status?.name,
      ];

      return searchableValues.some((value) => String(value || '').toLowerCase().includes(query));
    });
  }

  return payments;
});

const sortedPayments = computed(() => {
  const list = [...filteredPayments.value];
  if (!sortBy.value) return list;

  const getValue = (payment) => {
    switch (sortBy.value) {
      case 'token':
        return payment.token || '';
      case 'invoice':
        return payment.invoice?.token || (payment.commitment_deposit ? t('commitment_deposit') : '');
      case 'amount':
        return Number(payment.amount) || 0;
      case 'contract':
        return payment.contract?.token || '';
      case 'payment_date':
        return payment.payment_date ? new Date(payment.payment_date).getTime() : 0;
      case 'status':
        return payment.status?.name || '';
      case 'due_date':
        return payment.due_date ? new Date(payment.due_date).getTime() : 0;
      default:
        return '';
    }
  };

  return list.sort((a, b) => {
    const av = getValue(a);
    const bv = getValue(b);

    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDesc.value ? bv - av : av - bv;
    }

    const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: 'base' });
    return sortDesc.value ? -cmp : cmp;
  });
});

const paginatedPayments = computed(() => {
  const start = (pagination.value.page - 1) * pagination.value.perPage;
  return sortedPayments.value.slice(start, start + pagination.value.perPage);
});

const updatePagination = () => {
  const total = filteredPayments.value.length;
  const totalPages = Math.max(1, Math.ceil(total / pagination.value.perPage));
  const page = Math.min(pagination.value.page, totalPages);

  Object.assign(pagination.value, {
    page,
    total,
    totalPages,
    previous: page > 1 ? page - 1 : null,
    next: page < totalPages ? page + 1 : null,
    isFiltered: hasActiveFilters.value,
  });
};

watch(filteredPayments, updatePagination, { immediate: true });

watch([searchInput, statuses], () => {
  pagination.value.page = 1;
});

const getFilterStatus = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('billing/payment-status');
    filter_status.value = data.results;
  } catch (err) {
    console.error('Error obtenint estats de pagament:', err);
  }
};


// Obtenir detalls de la remesa
const getRemittanceDetails = async () => {
  try {
    const data = await $SepaRemittanceReturnApiService.getDetail(props.remittance_id);
    remittanceDetails.value = data;
  } catch (err) {
    console.error('Error obtenint detalls de la remesa:', err);
  }
};

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  statuses.value = [];
  selectedFilters.value.forEach((element) => {
    statuses.value.push(element.id);
  });
  pagination.value.page = 1;
};

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
};

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
};

const resetFilters = () => {
  searchInput.value = '';
  sortBy.value = null;
  sortDesc.value = false;
  selectedFilters.value = [];
  statuses.value = [];
  pagination.value.page = 1;
};


// Nova funcionalitat: Descarregar document XML
const downloadDocument = async () => {
  if (!remittanceDetails.value?.document) {
    toast.error(t('error_block.no_document_available'));
    return;
  }

  try {
    const document_file = await $DocumentManagerApiService.getDetail(remittanceDetails.value.document)
    let file = await $DocumentManagerApiService.viewDocument(remittanceDetails.value.document);
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


onMounted(async () => {
  objectPermissions.value = await checkPermission($PaymentApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getRemittanceDetails();
  getFilterStatus();
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.component, route.query.id)
    router.replace({
      path: route.path
    });
  }
});

const detail = ref(null);
const selectedItemId = ref(null);
const selectedItemComponent = ref(null);
const showDetail = async (component, id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  selectedItemComponent.value = component;
  toggleRegion(true);
}

</script>

<template>
  <div id="wrapper" class="region__content overflow-x-hidden overflow-y-auto max-h-screen">
    <div class="p-1 transition-all duration-500 ease" :class="{ 'mr-[48%]': showRegion }">
      <div class="flex justify-between relative">
        <H1Region>{{ $t('billing_block.sepa_remittance_detail') }}</H1Region>
      </div>

      <!-- Loading state -->
      <div v-if="!remittanceDetails" class="my-4">
        <p>{{ $t('common.loading') }}...</p>
      </div>

      <!-- Contingut principal quan tenim dades -->
      <template v-else>
        <div class="flex gap-2 items-center mb-2">
          <span class="truncate text-slate-400 text-sm">{{ remittanceDetails.token || info?.token }}</span>
        </div>

        <fieldset class="border border-gray-200 rounded-lg p-4 mb-4">
          <legend>{{ $t('billing_block.return_sepa') }}</legend>
          <div class="grid grid-cols-3 gap-6 items-center">
            <div class="flex flex-col gap-2 mb-4">
              <FieldDetail :label="$t('common.creation_date')"
                :value="remittanceDetails.created_at ? formatDate(remittanceDetails.created_at) : '-'" class="mb-0" />
              <FieldDetail :label="$t('billing_block.total_amount')"
                :value="formatMoneyWithCurrency(remittanceDetails.total_amount)" class="mb-0" />

            </div>
            <FieldDetail :label="$t('common.return_date')"
              :value="remittanceDetails.return_date ? formatDate(remittanceDetails.return_date) : '-'" class="mb-0" />
            <div class="flex gap-2 mt-2 whitespace-nowrap justify-end">
              <button v-if="remittanceDetails.document" @click="downloadDocument" class="button-default"
                :title="$t('billing_block.download_xml_document')">
                <Icon name="fa6-solid:download" class="w-4 h-4" />
                {{ $t('billing_block.download_document') }}
              </button>
            </div>
          </div>
        </fieldset>

        <!-- Secció de pagaments -->
        <div class="flex justify-between items-center mb-3">
          <div>
            <H1Region>{{ $t('billing_block.remittance_payments') }} <span class="text-sm text-slate-500">({{
              remittanceDetails.total_payments || 0 }})</span></H1Region>
          </div>
        </div>


        <form id="form_filter" role="search"
          class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-between"
          @submit.prevent="() => { }">

          <div class="flex flex-start gap-4 justify-start items-center">
            <span class="input-group flex flex-start items-center gap-2 w-80">
              <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
              <input v-model="searchInput" id="searchInputRemittance" type="text" name="search"
                :placeholder="$t('dashboard.search')"
                class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
            </span>

            <span>
              <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
                @click="resetFilters" title="reset">
                <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
              </button>
            </span>

            <FilterSelect :options="filter_status" :filters="selectedFilters" :multiple="true"
              :placeholder="t(`common.statuses`)" @update:modelValue="handleStatusChange($event)">
              <template #icon>
                <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
              </template>
            </FilterSelect>

          </div>
        </form>



        <div id="list" :style="{
          overflowY: 'auto',
          width: '100%',
          maxWidth: '100%',
          minHeight: 'calc(100vh - 400px)', maxHeight: 'calc(100vh - 400px)'
        }" class="scrollbar-hide border-t border-gray-200">
          <div class="heading sticky top-0 bg-white grid gap-3 text-base border-b items-center z-[5]"
            style="grid-template-columns: 120px 150px 100px 100px 80px 100px 80px;">
            <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy"
              :sortDesc="sortDesc" @sort="handleSort" />
            <TableHeader :label="$t('invoice')" sortKey="invoice" :currentSortBy="sortBy" :sortDesc="sortDesc"
              @sort="handleSort" />
            <TableHeader :label="$t('common.total')" sortKey="amount" :currentSortBy="sortBy" :sortDesc="sortDesc"
              @sort="handleSort" />
            <TableHeader :label="$t('contract')" sortKey="contract" :currentSortBy="sortBy" :sortDesc="sortDesc"
              @sort="handleSort" />
            <TableHeader :label="$t('billing_block.payment')" sortKey="payment_date" :currentSortBy="sortBy"
              :sortDesc="sortDesc" @sort="handleSort" />
            <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
              @sort="handleSort" />
            <TableHeader :label="$t('common.limit')" sortKey="due_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
              @sort="handleSort" />
          </div>

          <div class="scrollbar-hide">
            <div v-for="item in paginatedPayments" :key="item.id" class="grid gap-3 text-base border-b items-center"
              style="grid-template-columns: 120px 150px 100px 100px 80px 100px 80px;"
              :class="{ 'bg-yellow-50': item.id === selectedItemId, 'bg-purple-50': item.is_excluded && !(item.id === selectedItemId) }">
              <span>
                <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                  @click="showDetail(item.invoice ? 'InvoiceRegion' : 'CommitmentDepositRegion', item.invoice ? item.invoice.id : item.commitment_deposit.id);">
                  <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
                  <Icon name="fa6-solid:eye"
                    class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
                </button>
              </span>

              <span v-if="item.invoice" class="p-1 truncate">{{ item.invoice.token
                }}</span>
              <span v-else class="p-1 truncate">{{ t('commitment_deposit') }}</span>
              <span class="p-1">{{ formatMoneyWithCurrency(item.amount) }}</span>
              <span class="p-1 truncate">{{ item.contract?.token || '-' }}</span>

              <span class="p-1">{{ item.payment_date ? formatDate(item.payment_date) : '-' }}</span>
              <span class="p-1">
                <AtomsColorBadge :value="item.status?.name" :color="item.status?.color">
                </AtomsColorBadge>
              </span>
              <span class="p-1">{{ item.due_date ? formatDate(item.due_date) : '-' }}</span>

            </div><!-- end for items -->

            <div v-if="filteredPayments.length === 0" class="my-3">
              <p class="text-">{{ $t('common.no_records') }}</p>
            </div>

          </div>
        </div><!-- end list -->
        <div id="list__footer" class="pb-10">
          <Pagination v-if="filteredPayments.length > 0" :pagination="pagination" @update:page="handlePageChange" />
        </div>
      </template>
    </div>
    <div role="region" id="subregion"
      class="fixed top-0 right-0 text-base w-[48%] z-20 h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-hidden shadow-2xl"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
      }">
      <div class="h-full flex flex-col">
        <div id="region_nav" class="mb-3 px-3 flex-none">
          <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="px-10 flex-1 overflow-y-auto pb-10">
          <InvoiceRegion v-if="selectedItemComponent == 'InvoiceRegion'" :id="detail" :isSubRegion="true" />
          <CommitmentDepositRegion v-if="selectedItemComponent == 'CommitmentDepositRegion'" :id="detail"
            :isSubRegion="true" />
        </div>
      </div>
    </div>
  </div><!-- end wrapper -->
</template>