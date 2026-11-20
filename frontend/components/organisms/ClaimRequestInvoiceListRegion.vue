<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import { formatMoney } from '~/utils/money';
import Date from '~/components/atoms/Date.vue';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import ContractRegion from './ContractRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';

// Llista de factures d'una gestió d'impagats. Mateix patró que
// ClaimRequestContractListRegion, però amb una fila per pagament reclamat.
const props = defineProps({
  request: Object
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close', 'show-detail']);
const { $ClaimRequestApiService, $ConfigProjectApiService } = useNuxtApp();

const PER_PAGE = 25;

const loading = ref(false);
const searchQuery = ref('');
const searchInput = ref(null);
const contracts = ref([]);
const hideExcluded = ref(true);
const showVulnerable = ref(false);
const onlyPaid = ref(false);
const page = ref(1);
const paymentStatusPaidToken = ref(null);

const showRegion = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const isClaimPaymentPaid = (claimPayment) =>
  Boolean(
    paymentStatusPaidToken.value
    && claimPayment?.payment?.status?.token === paymentStatusPaidToken.value
  );

// Aplanem contractes -> pagaments reclamats
const invoices = computed(() =>
  contracts.value.flatMap(contract =>
    (contract.claim_payments || [])
      .filter(claimPayment => claimPayment.payment)
      .map(claimPayment => ({
        id: claimPayment.id,
        invoice_id: claimPayment.payment.invoice_id,
        serie_final: claimPayment.payment.invoice_serie_final,
        due_date: claimPayment.payment.due_date,
        amount: parseFloat(claimPayment.payment.amount) || 0,
        status: claimPayment.payment.status,
        is_excluded: claimPayment.is_excluded,
        is_paid: isClaimPaymentPaid(claimPayment),
        contract
      }))
  )
);

// Cada fila és un pagament reclamat i una factura pot tenir-ne més d'un: els comptadors compten
// factures distintes (mateix criteri que affected_invoices_count / excluded_invoices_count del backend)
const countDistinctInvoices = (rows) => new Set(rows.filter(row => row.invoice_id).map(row => row.invoice_id)).size;
const affectedInvoicesCount = computed(() => countDistinctInvoices(invoices.value.filter(invoice => !invoice.is_excluded)));
const excludedInvoicesCount = computed(() => countDistinctInvoices(invoices.value.filter(invoice => invoice.is_excluded)));

const filteredInvoices = computed(() => {
  let result = invoices.value;

  if (hideExcluded.value) {
    result = result.filter(invoice => !invoice.is_excluded);
  }

  if (showVulnerable.value) {
    result = result.filter(invoice => invoice.contract.holder_vulnerability_level >= 0);
  } else {
    result = result.filter(invoice => invoice.contract.holder_vulnerability_level == 0);
  }

  if (onlyPaid.value) {
    result = result.filter(invoice => invoice.is_paid);
  }

  if (!searchQuery.value) return result;

  const query = searchQuery.value.toLowerCase();
  return result.filter(invoice => {
    const contract = invoice.contract;
    const fullName = `${contract.holder_name} ${contract.holder_surname}`.toLowerCase();
    return fullName.includes(query)
      || (invoice.serie_final?.toLowerCase() || '').includes(query)
      || (contract.holder_token?.toLowerCase() || '').includes(query)
      || (contract.token?.toLowerCase() || '').includes(query);
  });
});

const pagination = computed(() => {
  const total = filteredInvoices.value.length;
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE) || 1);
  const isFiltered = Boolean(
    searchQuery.value
    || !hideExcluded.value
    || showVulnerable.value
    || onlyPaid.value
  );

  return {
    page: Math.min(page.value, totalPages),
    perPage: PER_PAGE,
    total,
    totalPages,
    isFiltered
  };
});

const paginatedInvoices = computed(() => {
  const start = (pagination.value.page - 1) * PER_PAGE;
  return filteredInvoices.value.slice(start, start + PER_PAGE);
});

watch(
  [searchQuery, hideExcluded, showVulnerable, onlyPaid],
  () => { page.value = 1; }
);

const handlePageChange = (newPage) => {
  page.value = newPage;
};

const exportColumns = computed(() => [
  { header: t('invoice'), value: row => row.serie_final || '' },
  { header: t('contract'), value: row => row.contract.token || '' },
  { header: t('common.identificator'), value: row => row.contract.holder_token || '' },
  { header: t('common.name'), value: row => `${row.contract.holder_name || ''} ${row.contract.holder_surname || ''}`.trim() },
  { header: t('common.due_date'), value: row => row.due_date || '' },
  { header: t('common.amount'), value: row => row.amount },
  { header: t('common.status'), value: row => row.status?.name || '' },
  { header: t('billing_block.excluded'), value: row => (row.is_excluded ? t('common.yes') : t('common.no')) }
]);

const showDetail = (component, id) => {
  closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-detail', true);
};

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  emit('show-detail', false);
};

const loadInvoices = async () => {
  loading.value = true;
  try {
    const response = await $ClaimRequestApiService.getContracts(props.request.id);
    contracts.value = response?.results || [];
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  paymentStatusPaidToken.value = await $ConfigProjectApiService.get('payment_status_paid_token');
  await loadInvoices();
  searchInput.value?.focus();
});
</script>

<template>
  <div class="region__content pr-1">

    <div class="h-full flex flex-col transition-all duration-500 ease" :class="{ 'mr-[48vw]': showRegion }">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-lg font-semibold">{{ $t('billing_block.invoice_list') }}</h3>
        <AtomsDownloadXlsxButton :columns="exportColumns" :rows="filteredInvoices"
          :disabled="loading || !filteredInvoices.length"
          :file-name="[$t('billing_block.affected_invoices_title'), request?.token].filter(Boolean).join(' - ')" />
      </div>

      <div class="mb-4 space-y-4">
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon name="fa6-solid:magnifying-glass" class="text-gray-400" />
          </div>
          <input ref="searchInput" v-model="searchQuery" type="text"
            :placeholder="`${$t('dashboard.search')} ${$t('invoice')}, ${$t('common.name')}, ${$t('common.identificator')} ${$t('common.or')} ${$t('contract')}`"
            class="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500" />
        </div>

        <div class="flex flex-wrap items-center gap-x-5 gap-y-2">
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="hideExcluded"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.hide') }} {{ $t('billing_block.excluded_invoices')
              }}</span>
          </label>
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showVulnerable"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('contract_block.vulnerables')
              }}</span>
          </label>
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="onlyPaid"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('billing_block.only_paid_invoices') }}</span>
          </label>
        </div>
      </div>

      <div class="flex gap-3 items-center mb-4 text-sm text-gray-700" v-if="!loading">
        <div>
          {{ $t('billing_block.affected_invoices_title') }}: {{ affectedInvoicesCount }}
        </div>
        <div>
          {{ $t('billing_block.excluded_invoices') }}: {{ excludedInvoicesCount }}
        </div>
      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="loading && !contracts.length" class="flex justify-center items-center h-full">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl" />
        </div>
        <div v-else class="flex flex-col h-[70vh]">
          <div class="flex-1 overflow-y-auto divide-y divide-gray-200 border border-gray-200 rounded-md">
            <div
              class="sticky top-0 z-10 px-3 py-2 bg-slate-50 border-b border-gray-200 text-xs font-medium text-gray-500 uppercase tracking-wide">
              <div
                class="grid grid-cols-[minmax(110px,1fr)_minmax(100px,1fr)_minmax(140px,1.6fr)_36px_90px_88px_100px] gap-x-2 items-center">
                <span>{{ $t('invoice') }}</span>
                <span>{{ $t('contract') }}</span>
                <span>{{ $t('common.name') }}</span>
                <span></span>
                <span>{{ $t('common.due_date') }}</span>
                <span>{{ $t('common.amount') }}</span>
                <span>{{ $t('common.status') }}</span>
              </div>
            </div>

            <div v-if="!paginatedInvoices.length" class="px-4 py-10 text-center text-sm text-gray-500">
              {{ $t('common.no_results') }}
            </div>

            <div v-for="(invoice, index) in paginatedInvoices" :key="invoice.id" class="px-3 py-3 hover:bg-gray-50"
              :class="{
                'bg-white': index % 2 !== 0 && !invoice.is_excluded && !invoice.is_paid,
                'bg-sky-50': index % 2 === 0 && !invoice.is_excluded && !invoice.is_paid,
                'bg-emerald-50': invoice.is_paid && !invoice.is_excluded,
                'bg-red-50': invoice.is_excluded
              }">
              <div
                class="grid grid-cols-[minmax(110px,1fr)_minmax(100px,1fr)_minmax(140px,1.6fr)_36px_90px_88px_100px] gap-x-2 items-center">
                <div class="min-w-0 flex items-center gap-1">
                  <button v-if="invoice.invoice_id" @click="showDetail('InvoiceRegion', invoice.invoice_id)"
                    class="text-sky-500 hover:text-sky-700 underline text-left truncate"
                    :title="`${$t('common.show')} ${$t('common.details')}`">
                    {{ invoice.serie_final || '-' }}
                  </button>
                  <span v-else>-</span>
                  <Icon v-if="invoice.is_excluded" name="fa6-solid:ban" class="text-red-600 shrink-0"
                    :title="$t('billing_block.excluded')" />
                </div>

                <div class="min-w-0">
                  <button @click="showDetail('ContractRegion', invoice.contract.id)"
                    class="text-sky-500 hover:text-sky-700 underline text-left truncate block max-w-full"
                    :title="`${$t('common.show')} ${$t('common.details')}`">
                    {{ invoice.contract.token }}
                  </button>
                  <div class="text-xs text-gray-500 mt-0.5 truncate">{{ invoice.contract.holder_token }}</div>
                </div>

                <span class="truncate"
                  :title="`${invoice.contract.holder_name} ${invoice.contract.holder_surname}`">
                  {{ invoice.contract.holder_name }} {{ invoice.contract.holder_surname }}
                </span>

                <div class="flex justify-center">
                  <AtomsVulnerabilityCheck v-if="invoice.contract.holder_vulnerability_level"
                    :vulnerability_level="invoice.contract.holder_vulnerability_level" :small="true" />
                </div>

                <Date :date="invoice.due_date" />

                <span class="tabular-nums whitespace-nowrap">{{ formatMoney(invoice.amount) }} €</span>

                <div class="min-w-0">
                  <ColorBadge :color="invoice.status?.color || 'gray'" :value="invoice.status?.name || '-'" />
                </div>
              </div>
            </div>
          </div>

          <div class="border-t border-gray-100 pt-2 mt-2" v-if="filteredInvoices.length > 0">
            <Pagination :pagination="pagination" @update:page="handlePageChange" />
          </div>
        </div>
      </div>
    </div>
    <div v-if="showRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white flex flex-col overflow-hidden shadow-2xl fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
