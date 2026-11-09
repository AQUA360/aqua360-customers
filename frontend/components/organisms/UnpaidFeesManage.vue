<script setup>
// Despeses d'impagat de factures vençudes (finestreta) o amb un retorn SEPA sense
// gestionar. Es filtren les factures, s'hi treuen les que no es volen i el backend
// crea una factura de despeses per a cada una amb les tarifes triades.
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import debounce from 'lodash.debounce';
import Pagination from '~/components/molecules/Pagination.vue';

const { t } = useI18n();
const toast = useToast();
const { $ConfiglistApiService, $InvoiceApiService, $PriceRateApiService, $apiManager } = useNuxtApp();

// Per defecte: finestreta i domiciliació (per als retorns SEPA).
const DEFAULT_PAYMENT_TYPES = ['BANK_PAYMENT', 'DIRECT_DEBIT'];

const pending = ref(true);
const enabled = ref(false);
const error = ref(null);

const unpaidStatuses = ref(['expired', 'returned']);
const paymentTypeOptions = ref([]);
const selectedPaymentTypes = ref([]);
const startDueDate = ref(null);
const endDueDate = ref(null);
const searchInput = ref('');
const billingId = ref('');
const excludeVulnerable = ref(false);
const excludeTerminated = ref(false);
const excludeOpenClaim = ref(false);

const priceRateOptions = ref([]);
const selectedPriceRates = ref([]);
const loadingPriceRates = ref(false);

const invoices = ref([]);
const excludedInvoices = ref([]);
const loadingInvoices = ref(false);
const pagination = ref({ page: 1, perPage: 50, total: 0, totalPages: 0, isFiltered: true });

const taskId = ref(null);
const generating = ref(false);

const unpaidStatusOptions = computed(() => [
  { value: 'expired', label: t('billing_block.unpaid_fee_expired') },
  { value: 'returned', label: t('billing_block.unpaid_fee_returned') },
]);

const priceRateLabel = (priceRate) => priceRate.name || priceRate.token;

// Filtres comuns a la llista i a la generació: així es generen exactament les factures que es veuen.
const filterParams = computed(() => ({
  is_invoice: true,
  search: searchInput.value,
  billing: billingId.value,
  unpaid_status: unpaidStatuses.value,
  payment_type_tokens: selectedPaymentTypes.value.map(type => type.token),
  start_due_date: startDueDate.value && endDueDate.value ? startDueDate.value : null,
  end_due_date: startDueDate.value && endDueDate.value ? endDueDate.value : null,
  without_fee_price_rates: selectedPriceRates.value.map(priceRate => priceRate.id),
  exclude_vulnerable: excludeVulnerable.value || null,
  exclude_terminated: excludeTerminated.value || null,
  exclude_open_claim: excludeOpenClaim.value || null,
}));

const selectedCount = computed(() => Math.max(pagination.value.total - excludedInvoices.value.length, 0));
const canGenerate = computed(() =>
  selectedCount.value > 0 && selectedPriceRates.value.length > 0 && unpaidStatuses.value.length > 0 && !generating.value
);

const loadPaymentTypes = async () => {
  const data = await $ConfiglistApiService.getAll('billing/payment-type');
  paymentTypeOptions.value = (data?.results || []).map(type => ({ label: type.name || type.token, token: type.token, id: type.id }));
  selectedPaymentTypes.value = paymentTypeOptions.value.filter(type => DEFAULT_PAYMENT_TYPES.includes(type.token));
};

const searchPriceRates = debounce(async (search = '') => {
  loadingPriceRates.value = true;
  try {
    const data = await $PriceRateApiService.getAll(search);
    priceRateOptions.value = data?.results || [];
  } catch (err) {
    console.error(err);
  } finally {
    loadingPriceRates.value = false;
  }
}, 300);

const searchInvoices = async (page = 1) => {
  if (!unpaidStatuses.value.length) {
    invoices.value = [];
    pagination.value.total = 0;
    pagination.value.totalPages = 0;
    return;
  }
  loadingInvoices.value = true;
  try {
    const response = await $InvoiceApiService.getUnpaidFeeInvoices(filterParams.value, page);
    invoices.value = response.results;
    pagination.value.page = page;
    pagination.value.total = response.count;
    pagination.value.totalPages = Math.ceil(response.count / pagination.value.perPage);
  } catch (err) {
    console.error(err);
  } finally {
    loadingInvoices.value = false;
  }
};

const debouncedSearch = debounce(() => searchInvoices(1), 400);

const init = async () => {
  pending.value = true;
  error.value = null;
  try {
    const config = await $InvoiceApiService.getUnpaidFeesConfig();
    enabled.value = !!config?.enabled;
    if (!enabled.value) return;
    selectedPriceRates.value = config.default_price_rates || [];
    await loadPaymentTypes();
    searchPriceRates('');
    await searchInvoices(1);
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const isExcluded = (invoiceId) => excludedInvoices.value.includes(invoiceId);

const generate = async () => {
  if (!canGenerate.value) return;
  const feeNames = selectedPriceRates.value.map(priceRateLabel).join(', ');
  if (!confirm(t('billing_block.unpaid_fee_confirm', { count: selectedCount.value, fees: feeNames }))) return;

  generating.value = true;
  try {
    const response = await $InvoiceApiService.generateUnpaidFees(
      filterParams.value,
      selectedPriceRates.value.map(priceRate => priceRate.id),
      excludedInvoices.value,
    );
    taskId.value = response.task_id;
  } catch (err) {
    console.error(err);
    generating.value = false;
  }
};

const onTaskRefresh = async () => {
  try {
    const res = await $apiManager.checkTask(taskId.value);
    const result = res?.result;
    if (res?.state === 'SUCCESS' && result) {
      toast.success(t('billing_block.unpaid_fee_done', { created: result.created, skipped: result.skipped }));
      if (result.errors?.length) {
        const detail = result.errors.slice(0, 5).map(e => `${e.invoice}: ${e.error}`).join('\n');
        toast.error(`${t('billing_block.unpaid_fee_errors', { count: result.errors.length })}\n${detail}`);
      }
    } else {
      toast.error(t('common.error'));
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    taskId.value = null;
    generating.value = false;
    excludedInvoices.value = [];
    searchInvoices(1);
  }
};

watch(
  [unpaidStatuses, selectedPaymentTypes, startDueDate, endDueDate, selectedPriceRates, excludeVulnerable, excludeTerminated, excludeOpenClaim],
  () => {
    excludedInvoices.value = [];
    searchInvoices(1);
  },
  { deep: true },
);

watch([searchInput, billingId], () => {
  excludedInvoices.value = [];
  debouncedSearch();
});

onMounted(init);
</script>

<template>
  <div>
    <div v-if="pending" class="flex items-center justify-center py-16">
      <AtomsAppLoading />
    </div>

    <div v-else-if="error" class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <button @click="init" class="mt-2 font-medium text-sky-600 hover:text-sky-800 hover:underline">
        {{ $t('common.load_again') }}
      </button>
    </div>

    <div v-else-if="!enabled" class="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600">
      {{ $t('billing_block.unpaid_fee_disabled') }}
    </div>

    <div v-else class="grid grid-cols-1 gap-4 lg:grid-cols-[380px_1fr]">
      <div class="flex flex-col gap-4">
        <section class="rounded-lg border border-gray-200 bg-white shadow-sm">
          <header class="flex items-center gap-2 border-b border-gray-100 px-4 py-2.5">
            <Icon name="fa6-solid:filter" class="text-xs text-gray-400" />
            <span class="text-xs font-semibold uppercase tracking-wide text-gray-500">{{ t('common.filters') }}</span>
          </header>

          <div class="space-y-4 p-4">
            <div>
              <label class="mb-1.5 block text-sm font-medium text-gray-600">{{ $t('billing_block.unpaid_fee_reason') }}</label>
              <label v-for="option in unpaidStatusOptions" :key="option.value"
                class="flex items-center gap-2 py-0.5 text-sm text-gray-700">
                <input type="checkbox" v-model="unpaidStatuses" :value="option.value" />
                {{ option.label }}
              </label>
            </div>

            <div>
              <label class="mb-1.5 block text-sm font-medium text-gray-600">{{ $t('payment_types') }}</label>
              <v-select multiple class="block w-full custom-select" v-model="selectedPaymentTypes"
                :options="paymentTypeOptions" />
            </div>

            <div>
              <label class="mb-1.5 block text-sm font-medium text-gray-600">{{ $t('common.due_date') }}</label>
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm text-gray-600">{{ $t('common.from') }}</span>
                <AtomsInputDate v-model="startDueDate" class="w-36" />
                <span class="text-sm text-gray-600">{{ $t('common.to') }}</span>
                <AtomsInputDate v-model="endDueDate" class="w-36" />
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="mb-1.5 block text-sm font-medium text-gray-600">{{ $t('dashboard.search') }}</label>
                <input v-model="searchInput" type="text" class="input w-full" />
              </div>
              <div>
                <label class="mb-1.5 block text-sm font-medium text-gray-600">{{ $t('billing_block.billing_id') }}</label>
                <input v-model="billingId" type="text" class="input w-full" :placeholder="t('billing_block.insert_id')" />
              </div>
            </div>

            <div class="border-t border-gray-100" />

            <div>
              <label class="mb-1.5 block text-sm font-medium text-gray-600">{{ $t('billing_block.unpaid_fee_exclude') }}</label>
              <label class="flex items-center gap-2 py-0.5 text-sm text-gray-700">
                <input type="checkbox" v-model="excludeVulnerable" /> {{ $t('billing_block.unpaid_fee_exclude_vulnerable') }}
              </label>
              <label class="flex items-center gap-2 py-0.5 text-sm text-gray-700">
                <input type="checkbox" v-model="excludeTerminated" /> {{ $t('billing_block.unpaid_fee_exclude_terminated') }}
              </label>
              <label class="flex items-center gap-2 py-0.5 text-sm text-gray-700">
                <input type="checkbox" v-model="excludeOpenClaim" /> {{ $t('billing_block.unpaid_fee_exclude_open_claim') }}
              </label>
            </div>
          </div>
        </section>

        <section class="rounded-lg border border-gray-200 bg-white shadow-sm">
          <header class="flex items-center gap-2 border-b border-gray-100 px-4 py-2.5">
            <Icon name="fa6-solid:coins" class="text-xs text-gray-400" />
            <span class="text-xs font-semibold uppercase tracking-wide text-gray-500">{{ $t('billing_block.unpaid_fee_fees') }}</span>
          </header>
          <div class="space-y-3 p-4">
            <v-select multiple class="block w-full custom-select" v-model="selectedPriceRates"
              :options="priceRateOptions" :get-option-label="priceRateLabel" :filterable="false"
              :loading="loadingPriceRates" @search="searchPriceRates" />
            <p class="text-xs text-gray-500">{{ $t('billing_block.unpaid_fee_fees_help') }}</p>

            <AtomsProcessColorBadge v-if="taskId" class="w-fit flex items-center" @refresh="onTaskRefresh"
              :value="t('common.processing')" color="blue" :taskId="taskId" />
            <button v-else class="button-primary flex w-full items-center justify-center gap-2" :disabled="!canGenerate"
              :class="{ 'cursor-not-allowed opacity-50': !canGenerate }" @click="generate">
              <Icon name="fa6-solid:file-invoice-dollar" />
              {{ $t('billing_block.unpaid_fee_apply') }}
              <span class="rounded-full bg-white/20 px-1.5 py-0.5 text-xs font-semibold">{{ selectedCount }}</span>
            </button>
          </div>
        </section>
      </div>

      <section class="flex min-h-0 flex-col rounded-lg border border-gray-200 bg-white shadow-sm">
        <header class="flex items-center justify-between border-b border-gray-100 px-4 py-2.5">
          <div class="flex items-center gap-2">
            <Icon name="fa6-solid:list-check" class="text-xs text-gray-400" />
            <span class="text-xs font-semibold uppercase tracking-wide text-gray-500">{{ t('common.total_filtered') }}</span>
          </div>
          <span v-if="!loadingInvoices" class="rounded-full bg-sky-50 px-2.5 py-0.5 text-sm font-semibold tabular-nums text-sky-700">
            {{ selectedCount }} / {{ pagination.total }}
          </span>
          <Icon v-else name="fa6-solid:spinner" class="animate-spin text-sm text-sky-500" />
        </header>

        <div class="min-h-[280px] flex-1 overflow-auto" :style="{ maxHeight: 'calc(100vh - 220px)' }">
          <div v-if="loadingInvoices" class="flex items-center justify-center py-16">
            <AtomsAppLoading />
          </div>
          <div v-else-if="invoices.length === 0"
            class="flex min-h-[240px] flex-col items-center justify-center gap-2 px-4 py-12 text-gray-400">
            <Icon name="fa6-solid:inbox" class="text-2xl opacity-40" />
            <p class="text-sm text-gray-500">{{ $t('common.no_data_found') }}</p>
          </div>
          <table v-else class="w-full text-sm">
            <thead class="sticky top-0 bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th class="px-3 py-2">{{ $t('invoice') }}</th>
                <th class="px-3 py-2">{{ $t('contract_block.holder') }}</th>
                <th class="px-3 py-2">{{ $t('payment_types') }}</th>
                <th class="px-3 py-2">{{ $t('common.due_date') }}</th>
                <th class="px-3 py-2 text-right">{{ $t('billing_block.total_to_pay') }}</th>
                <th class="px-3 py-2">{{ $t('common.status') }}</th>
                <th class="px-3 py-2 text-center">{{ $t('billing_block.exclude') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="invoice in invoices" :key="invoice.id"
                :class="isExcluded(invoice.id) ? 'bg-slate-50 opacity-50' : 'hover:bg-gray-50'">
                <td class="px-3 py-2">
                  <NuxtLink :to="`/billing/invoice?id=${invoice.id}`" class="font-medium text-sky-700 hover:underline">
                    {{ invoice.serie_final }}
                  </NuxtLink>
                  <p v-if="invoice.contract_token" class="text-xs text-gray-500">{{ invoice.contract_token }}</p>
                </td>
                <td class="px-3 py-2">{{ invoice.customer_final }}</td>
                <td class="px-3 py-2">{{ invoice.payment_type_final }}</td>
                <td class="px-3 py-2">{{ invoice.due_date ? formatDate(invoice.due_date) : '' }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ formatMoneyWithCurrency(invoice.left_to_pay) }}</td>
                <td class="px-3 py-2"><AtomsColorBadge :value="invoice.status_name" :color="invoice.status_color" /></td>
                <td class="px-3 py-2 text-center">
                  <input type="checkbox" v-model="excludedInvoices" :value="invoice.id"
                    :title="`${$t('billing_block.exclude')} ${$t('invoice')}`" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="border-t border-gray-100 p-2" v-if="pagination.totalPages > 1">
          <Pagination :pagination="pagination" @update:page="searchInvoices" />
        </div>
      </section>
    </div>
  </div>
</template>
