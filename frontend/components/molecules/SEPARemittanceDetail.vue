<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import { formatIban } from '~/utils/iban';
import Pagination from '~/components/molecules/Pagination.vue';
import H1Region from '../atoms/H1Region.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import AtomsInputDate from '~/components/atoms/InputDate.vue';
import ContractRegion from '../organisms/ContractRegion.vue';
import PersonRegion from '../organisms/PersonRegion.vue';
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
  isReturn: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['remittance-updated', 'close-subregion']);

const route = useRoute();
const router = useRouter();
const { $apiManager, $PaymentApiService, $ConfiglistApiService, $SepaRemittanceApiService, $DocumentManagerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const remittanceDetails = ref(null);
const searchInput = ref('');
const statuses = ref([])
const filter_status = ref([]);
const selectedFilters = ref([]);
const selected_payment_types = ref([])
const payment_types = ref([])
const filter_payment_type = ref([])
const sortBy = ref(null);
const sortDesc = ref(false);
const exportingCSV = ref(false);
const sending = ref(false);
const regeneratingDocument = ref(false);
const sent_at = ref(new Date(Date.now()).toISOString().split('T')[0]);
const desired_send_at = ref(null);

const taskId = ref(null);
const regenerated = ref(false);

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

/*
const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $PaymentApiService.getAll(
      searchQuery, filters, page, sort, desc,
      null, null, null, null,
      [], null, null, null,
      [], false, null, props.remittance_id
    );

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      const searchElement = document.getElementById('searchInputRemittance');
      if (searchElement) {
        searchElement.focus();
      }
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}
  */

const deleteRemittance = async () => {
  if (!confirm(t('confirmation_text_block.confirm_delete'))) return;
  try {
    await $SepaRemittanceApiService.doDelete(props.remittance_id);
    toast.success(t('common.deleted_successfully'));
    emit('close-subregion');
  } catch (error) {
    console.error(error);
    toast.error(t('error_block.error_delete'));
  }
}

const getPayments = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, payment_types = []) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $SepaRemittanceApiService.getPayments(
      props.remittance_id,
      searchQuery,
      filters,
      page,
      sort,
      desc,
      payment_types
    );

    items.value = data.results;

    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      const searchElement = document.getElementById('searchInputRemittance');
      if (searchElement) {
        searchElement.focus();
      }
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
    const data = await $ConfiglistApiService.getAll('billing/payment-status')
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterPaymentType = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    filter_payment_type.value = [
      {
        id: null,
        token: '',
        name: t('None'),
      },
      ...(data.results || []),
    ];
  } catch (err) {
    error.value = err;
  }
}

// Obtenir detalls de la remesa
const getRemittanceDetails = async () => {
  try {
    const data = await $SepaRemittanceApiService.getDetail(props.remittance_id);
    remittanceDetails.value = data;
    regenerated.value = !(data.has_paid_payments || data.has_non_direct_debit_payments || data.pending_changes) || data.sent_at
    if (data.send_at) {
      const formattedDate = data.send_at.split('T')[0];
      desired_send_at.value = formattedDate;
      sent_at.value = formattedDate;
    }
  } catch (err) {
    console.error('Error obtenint detalls de la remesa:', err);
  }
}

const debouncedGetPayments = debounce((query, filters, sort, desc, payment_types) => {
  getPayments(query, filters, pagination.value.page, sort, desc, payment_types);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetPayments(searchInput.value, statuses.value, sortBy.value, sortDesc.value, payment_types.value);
}

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  statuses.value = []
  selectedFilters.value.forEach(element => {
    statuses.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handlePayTypeChange = (event) => {
  selected_payment_types.value = event;
  payment_types.value = []
  selected_payment_types.value.forEach(element => {
    payment_types.value.push(element.id);
  })
  
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getPayments(searchInput.value, statuses.value, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getPayments(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  sortBy.value = null
  selectedFilters.value = []
  statuses.value = []
  selected_payment_types.value = []
  // payment_types.value = []
  pagination.value.page = 1;
  getPayments();
};

// Nova funcionalitat: Eliminar relació pagament-remesa
const removePaymentFromRemittance = async (payment) => {
  if (confirm(t('confirmation_text_block.confirm_remove_payment_from_remittance'))) {
    try {
      await $SepaRemittanceApiService.deletePaymentRelation(props.remittance_id, payment.id);
      toast.success(t('success_block.payment_removed_from_remittance'));
      await getPayments(); // Refresh la llista
      await getRemittanceDetails();
      emit('remittance-updated'); // Notificar al component pare
    } catch (error) {
      console.error(error);
      toast.error(t('error_block.remove_payment_failed'));
    }
  }
}

// Nova funcionalitat: Regenerar document SEPA
const regenerateSepaDocument = async () => {
  if (confirm(t('confirmation_text_block.confirm_regenerate_sepa_document'))) {
    regeneratingDocument.value = true;
    try {
      // Preparar les dades opcionals (send_date)
      const data = desired_send_at.value
        ? { send_date: desired_send_at.value }
        : {};

      const res = await $SepaRemittanceApiService.regenerateSepaDocument(props.remittance_id, data);
      if (res && res.task_id) {
        taskId.value = res.task_id;
      }
      // toast.success(t('success_block.sepa_document_regenerated'));

      // Actualitzar detalls de la remesa per obtenir el nou document
      // await getRemittanceDetails();
      // regenerated.value = true;
      // emit('remittance-updated'); // Notificar al component pare
    } catch (error) {
      console.error(error);
      toast.error(t('error_block.regenerate_sepa_document_failed'));
      regeneratingDocument.value = false;
      taskId.value = null;
    }
  }
}

const getDocument = async () => {
  try {
    toast.success(t('success_block.sepa_document_regenerated'));

    // Actualitzar detalls de la remesa per obtenir el nou document
    await getRemittanceDetails();
    regenerated.value = true;
    emit('remittance-updated');
  } catch (error) {
    console.error(error);
  } finally {
    regeneratingDocument.value = false;
    taskId.value = null;
  }
}

// Nova funcionalitat: Descarregar document XML
const downloadXMLDocument = async () => {
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
// FIX DOCUMENT URL LATER
/* const downloadXMLDocument = async () => {
  if (!remittanceDetails.value?.document_url) {
    toast.error(t('error_block.no_document_available'));
    return;
  }

  try {
    // Crea un link temporal per descarregar el fitxer
    const link = document.createElement('a');
    link.href = remittanceDetails.value.document_url;
    link.download = remittanceDetails.value.document_name;
    link.target = '_blank';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    toast.success(t('success_block.document_downloaded'));
  } catch (error) {
    console.error('Error descarregant el document:', error);
    toast.error(t('error_block.download_failed'));
  }
} */

// Nova funcionalitat: Marcar data d'enviament de la remesa
const sendRemittance = async () => {
  if (!confirm(t('confirmation_text_block.confirm_send_remittance'))) return;
  if (!sent_at.value || sent_at.value === '') {
    toast.error(t('error_block.sent_date_required'));
    return;
  }
  sending.value = true;
  try {
    let save_data = {
      ids: [props.remittance_id],
      sent_at: sent_at.value
    };
    await $SepaRemittanceApiService.sendRemittance(save_data);
    toast.success(t('success_block.remittance_sent'));
    await getRemittanceDetails();
    await getPayments();
    emit('remittance-updated');
  } catch (error) {
    console.error(error);
    toast.error(t('error_block.send_remittance_failed'));
  } finally {
    sending.value = false;
  }
}

// Nova funcionalitat: Exportar pagaments a CSV
const exportPaymentsToCSV = async () => {
  exportingCSV.value = true;
  try {
    const response = await $SepaRemittanceApiService.exportPaymentsCSV(
      props.remittance_id,
      searchInput.value,
      statuses.value,
      sortBy.value,
      sortDesc.value
    );

    // Afegir BOM UTF-8 per assegurar compatibilitat amb Excel
    const utf8BOM = "\uFEFF";
    const csvData = utf8BOM + response;

    // Crear un blob amb les dades CSV
    const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;

    const date = new Date();
    const today = date.getFullYear().toString() +
      String(date.getMonth() + 1).padStart(2, '0') +
      String(date.getDate()).padStart(2, '0');
    link.download = `payments_remittance_${props.remittance_id}_${today}.csv`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);

    toast.success(t('success_block.csv_exported'));
  } catch (error) {
    console.error('Error exportant CSV:', error);
    toast.error(t('error_block.csv_export_failed'));
  } finally {
    exportingCSV.value = false;
  }
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($PaymentApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getPayments();
  getRemittanceDetails();
  getFilterStatus();
  getFilterPaymentType();
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

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

</script>

<template>
  <div id="wrapper" class="region__content overflow-x-hidden overflow-y-auto max-h-screen">
    <div class="p-1 transition-all duration-500 ease" :class="{ 'mr-[48%]': showRegion }">
      <div class="flex justify-between relative">
        <H1Region>{{ isReturn ? $t('billing_block.trf_remittance_detail') : $t('billing_block.sepa_remittance_detail') }}</H1Region>
        <div v-if="objectPermissions?.can_change" class="relative">
          <OptionsDropdown id="SupplyPointRegionOptions">

            <DropdownOption :name="t('common.delete')" @click="deleteRemittance">
            </DropdownOption>
          </OptionsDropdown>
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="!remittanceDetails" class="my-4">
        <p>{{ $t('common.loading') }}...</p>
      </div>

      <!-- Contingut principal quan tenim dades -->
      <template v-else>
        <div class="flex gap-2 items-center mb-2">
          <span class="truncate text-slate-400 text-sm">{{ remittanceDetails.token || info?.token }}</span>
          <AtomsColorBadge :value="remittanceDetails.status_name" :color="remittanceDetails.status_color" />
        </div>

        <fieldset class="border border-gray-200 rounded-lg p-4 mb-4">
          <legend>{{ isReturn ? $t('billing_block.trf_doc') : $t('billing_block.sepa_doc') }}</legend>
          <div class="grid grid-cols-3 gap-6 items-center">
            <div class="flex flex-col gap-2 mb-4">
              <FieldDetail :label="$t('common.creation_date')"
                :value="remittanceDetails.created_at ? formatDate(remittanceDetails.created_at) : '-'" class="mb-0" />
                <div class="mb-2 grid grid-cols-[0.7fr,120px]">
                  <label class="inline-block" :class="'text-slate-400'">{{ $t('common.send_date_expected') }}:</label>
                  <slot><span class="text-black-900">{{ remittanceDetails.desired_send_at ?
                  formatDate(remittanceDetails.desired_send_at) : '-' }}</span></slot>
              </div>
              <FieldDetail :label="$t('billing_block.total_amount')"
                :value="formatMoneyWithCurrency(remittanceDetails.total_amount)" class="mb-0" />
              <FieldDetail :label="$t('common.iban')"
                :value="remittanceDetails.company_bank_iban ? formatIban(remittanceDetails.company_bank_iban) : '-'" class="mb-0" />
              
            </div>
            <AtomsInputDate v-model="desired_send_at"
              :label="$t('common.select') + ' ' + $t('common.send_date_expected').toLowerCase()" />
            <div v-if="objectPermissions?.can_change" class="flex gap-2 mt-2 whitespace-nowrap justify-end">
              <button v-if="remittanceDetails.document_url" :disabled="!regenerated" @click="downloadXMLDocument"
                class="button-default" :title="$t('billing_block.download_xml_document')">
                <Icon name="fa6-solid:download" class="w-4 h-4" />
                {{ $t('billing_block.download_document') }}
              </button>
              <button v-if="!regeneratingDocument" @click="regenerateSepaDocument"
                class="button-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="regeneratingDocument || remittanceDetails.has_paid_payments || remittanceDetails.has_non_direct_debit_payments"
                :title="$t('billing_block.regenerate_sepa_document')">
                <Icon name="fa6-solid:rotate-right" class="w-4 h-4" />
                <span>{{ $t('billing_block.regenerate_document') }}</span>
              </button>
              <AtomsProcessColorBadge v-else class="h-full items-center justify-center py-2.5" 
              :value="$t('common.processing')" color="blue" :taskId="taskId" 
              @refresh="getDocument"></AtomsProcessColorBadge>
            </div>
          </div>
        </fieldset>

        <fieldset class="border border-gray-200 rounded-lg p-4 mb-4 pb-0">
          <legend>{{ $t('billing_block.send_sepa') }}</legend>
          <template v-if="remittanceDetails.sent_at">
            <div class="flex gap-2 items-center">
              <FieldDetail :label="$t('billing_block.sent_date')"
                :value="remittanceDetails.sent_at ? formatDate(remittanceDetails.sent_at) : '-'" />
            </div>
          </template>
          <template v-else>
            <p class="mb-2">{{ isReturn ? $t('billing_block.trf_not_sent_yet') : $t('billing_block.sepa_not_sent_yet') }}</p>
            <p class="mb-2">{{ $t('informative_block.info_sepa_process') }}</p>
            <p class="mb-2">{{ $t('informative_block.info_sepa_send_pay') }}</p>
            <p v-if="!isReturn" class="mb-2">{{ $t('informative_block.info_sepa_return') }}</p>
            <hr class="mb-2" />
            <div class="grid grid-cols-[1fr,2fr] gap-2">
              <form @submit.prevent="sendRemittance" class="flex items-end gap-2">
                <AtomsInputDate v-model="sent_at" :label="$t('billing_block.sent_date')" />
                <button v-if="objectPermissions?.can_change" type="submit" class="button-primary mb-4" :disabled="sending || !sent_at || sent_at === '' ||
                  remittanceDetails.has_paid_payments ||
                  remittanceDetails.has_non_direct_debit_payments ||
                  remittanceDetails.pending_changes">
                  {{ sending ? $t('billing_block.marking_as_sent') + '...' : $t('billing_block.mark_as_sent') }}
                </button>
              </form>
              <div class="my-auto">
                <div v-if="remittanceDetails.has_paid_payments || remittanceDetails.has_non_direct_debit_payments"
                  class="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="alert">
                  <div class="flex items-start gap-2">
                    <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5 text-amber-700" />
                    <div class="min-w-0">
                      <ul class="list-disc pl-4 space-y-1">
                        <li v-if="remittanceDetails.has_paid_payments">
                          {{ $t('warning_block.warning_has_paid_payments') }}
                        </li>
                        <li v-if="remittanceDetails.has_non_direct_debit_payments">
                          {{ $t('warning_block.warning_has_non_direct_debit_payments') }}
                        </li>
                      </ul>
                      <p class="mt-2 font-semibold text-slate-900">
                        {{ $t('informative_block.info_exclude_payments') }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
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
          @submit.prevent="() => {}">

          <div class="flex flex-start gap-4 justify-start items-center">
            <span class="input-group flex flex-start items-center gap-2 w-80">
              <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
              <input v-model="searchInput" @input="handleSearch" id="searchInputRemittance" type="text" name="search"
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
  
            <FilterSelect :options="filter_payment_type" :filters="selected_payment_types" :multiple="false"
              :placeholder="t(`common.type`)" @update:modelValue="handlePayTypeChange($event)">
              <template #icon>
                <Icon name="fa6-solid:cube" class="text-slate-500 " />
              </template>
            </FilterSelect>
          </div>
          <span>
            <button id="exportCSV" name="form_filter" type="button"
              class="px-3 py-1 bg-green-500 hover:bg-green-600 text-white rounded flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed mb-1"
              @click="exportPaymentsToCSV" :disabled="exportingCSV" :title="$t('export_csv')">
              <Icon v-if="!exportingCSV" name="fa6-solid:file-csv" class="text-white" />
              <span v-if="exportingCSV">{{ $t('common.loading') }}...</span>
              <span v-else>{{ $t('export_csv') }}</span>
            </button>
          </span>
        </form>



        <div id="list" :style="{
          overflowY: 'auto',
          width: '100%',
          maxWidth: '100%',
          height: '600px',
        }" class="scrollbar-hide border-t border-gray-200">
          <div class="heading sticky top-0 bg-white grid gap-3 text-base border-b items-center z-[5]"
            style="grid-template-columns: 120px 150px 100px 150px 80px 100px 80px 80px;">
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
            <span>{{ $t('common.actions') }}</span>
          </div>

          <div v-if="pending">
            <p>{{ $t('common.loading') }}...</p>
          </div>
          <div v-else-if="error">
            <p>Error: {{ error.message }}</p>
            <p><button @click="getPayments" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
            }}</button></p>
          </div>
          <div v-else class="scrollbar-hide">
            <div v-for="item in items" :key="item.id" class="grid gap-3 text-base border-b items-center"
              style="grid-template-columns: 120px 150px 100px 150px 80px 100px 80px 80px;"
              :class="{ 'bg-yellow-50': item.id === selectedItemId, 'bg-purple-50': item.is_excluded && !(item.id === selectedItemId) }">
              <span>
                <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                  @click="showDetail(isReturn ? item.contract ? 'ContractRegion' : 'PersonRegion' :
                  item.invoice ? 'InvoiceRegion' : 'CommitmentDepositRegion', 
                  isReturn ? item.contract ? item.contract.id : item.person ? item.person.id : null : item.invoice ? item.invoice.id : item.commitment_deposit.id);">
                  <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
                  <Icon name="fa6-solid:eye"
                    class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
                </button>
              </span>
              <span v-if="isReturn" class="p-1 truncate">{{ t('contract_block.balance_to_move') }}</span>
              <span v-else-if="item.invoice" class="p-1 truncate">{{ item.invoice.token
                }}</span>
              <span v-else class="p-1 truncate">{{ t('commitment_deposit') }}</span>
              <span class="p-1">{{ formatMoneyWithCurrency(item.amount) }}</span>
              <span class="p-1 truncate">{{ item.contract ? item.contract.token : item.person ? `${item.person.token} ${item.person.name}` : '-' }}</span>

              <span class="p-1">{{ item.payment_date ? formatDate(item.payment_date) : '-' }}</span>
              <span class="p-1">
                <AtomsColorBadge :value="item.status?.name" :color="item.status?.color">
                </AtomsColorBadge>
              </span>
              <span class="p-1">{{ item.due_date ? formatDate(item.due_date) : '-' }}</span>
              <span class="p-1 ">
                <button v-if="objectPermissions?.can_change" @click.stop="removePaymentFromRemittance(item)"
                  class="w-6 h-6 rounded-full border border-orange-500 text-orange-500 bg-orange-50 hover:bg-orange-100 transition-colors duration-200"
                  :title="$t('billing_block.remove_from_remittance')">
                  <Icon name="fa6-solid:link-slash" class="m-auto w-3 h-3" />
                </button>
              </span>
            </div><!-- end for items -->

            <div v-if="items.length === 0" class="my-3">
              <p class="text-">{{ $t('common.no_records') }}</p>
            </div>

          </div><!-- else no-error no-pending -->
        </div><!-- end list -->
        <div id="list__footer" class="pb-10">
          <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
        </div>
      </template>
    </div>
    <div role="region" id="subregion"
      class="fixed top-0 text-base w-[48%] z-20 h-full border-l border-gray-100 transition-[right] duration-500 ease py-2 text-base bg-white overflow-hidden shadow-2xl"
      :class="showRegion ? 'right-0' : 'right-[-48%]'">
      <div class="h-full flex flex-col">
        <div id="region_nav" class="mb-3 px-3 flex-none">
          <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="px-10 flex-1 overflow-y-auto pb-10">
          <InvoiceRegion v-if="selectedItemComponent == 'InvoiceRegion'" :id="detail" :isSubRegion="true" />
          <PersonRegion v-if="selectedItemComponent == 'PersonRegion'" :id="detail" :isSubRegion="true" />
          <ContractRegion v-if="selectedItemComponent == 'ContractRegion'" :id="detail" :isSubRegion="true" />
          <CommitmentDepositRegion v-if="selectedItemComponent == 'CommitmentDepositRegion'" :id="detail"
            :isSubRegion="true" />
        </div>
      </div>
    </div>
  </div><!-- end wrapper -->
</template>