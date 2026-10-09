<script setup>
// components/organisms/MeterRegion.vue
import { ref, watch, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import SelectorType from '../atoms/SelectorType.vue';
import Pagination from '~/components/molecules/Pagination.vue';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  person_id: Number,
  contract_id: Number,
});

const emit = defineEmits(['show-subregion', 'changed']);

const router = useRouter();
const { $ConfiglistApiService, $InvoiceApiService, $PersonApiService, $apiManager } = useNuxtApp();
const pending = ref(true);
const loadingInvoices = ref(false);
const error = ref(null);

const person = ref(null);

const selectedInvoiceStatuses = ref([]);
const invoiceStatuses = ref([])
const loadingInvoiceStatuses = ref(false)
const startIssueDate = ref(null)
const endIssueDate = ref(null)
const startTotalFinalAmount = ref(null)
const endTotalFinalAmount = ref(null)

const inZip = ref(true)
const zipInvoicesSelectOptions = computed(() => [
  { value: true, label: t('common.separated_in_zip') },
  { value: false, label: t('common.all_in_one_document') },
]);
// Invoices of the currently visible page only; the actual bulk download is resolved
// entirely server-side (see downloadInvoices()), not from this list.
const selectedInvoices = ref([])
const excludedInvoices = ref([])
const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  isFiltered: true,
})

const downloadTaskId = ref(null)
const downloading = ref(false)

const showTotalAmountFilter = ref(false)

const getData = async (load = true) => {
  pending.value = load;
  error.value = null;
  try {
    if (load) await getInitData()
    searchData()
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const fetchConfigData = async (service, entity, targetArray, loading) => {
  try {
    loading.value = true;
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];

    if (data.results) {
      data.results.forEach(data => {
        targetArray.value.push({
          label: data.name || data.token,
          code: data.id,
          token: data.token
        })
      });
    }
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  } finally {
    loading.value = false;
  }
}

const searchData = async (page = 1) => {
  loadingInvoices.value = true
  try {
    const response = await $InvoiceApiService.getAll(
      "", selectedInvoiceStatuses.value.map(status => status.code) || [], page,
      null, false, props.contract_id,
      true, null, null,
      startIssueDate.value && endIssueDate.value ? { start_date: startIssueDate.value, end_date: endIssueDate.value } : null,
      startTotalFinalAmount.value && endTotalFinalAmount.value ? { start_date: startTotalFinalAmount.value, end_date: endTotalFinalAmount.value } : null, [],
      null, [], null,
      startTotalFinalAmount.value || endTotalFinalAmount.value ? { start_date: startTotalFinalAmount.value || null, end_date: endTotalFinalAmount.value || null } : null,
      props.person_id || null
    );

    selectedInvoices.value = response.results;
    pagination.value.page = page;
    pagination.value.total = response.count;
    pagination.value.totalPages = Math.ceil(response.count / pagination.value.perPage);
  } catch (err) {
    console.error(err);
  } finally {
    loadingInvoices.value = false;
  }
}

const onPageChange = (newPage) => {
  searchData(newPage);
}

const getInitData = async () => {
  try {
    fetchConfigData('billing', 'invoice-status', invoiceStatuses, loadingInvoiceStatuses);
    if (props.person_id) {
      person.value = await $PersonApiService.getDetail(props.person_id);
    }
  } catch (err) {
    error.value = err;
  }
}

const selectZipInvoices = (value) => {
  inZip.value = value;
}

// The backend gathers every invoice matching the current filters (not just the visible page),
// excludes `excludedInvoices` and generates the zip/pdf as a Celery task; we just poll it below
// via `AtomsProcessColorBadge`/`task-progress` (same pattern as the e-invoices bulk download).
const downloadInvoices = async () => {
  downloading.value = true;
  try {
    const response = await $InvoiceApiService.massiveDownload(
      excludedInvoices.value, inZip.value,
      "", selectedInvoiceStatuses.value.map(status => status.code) || [], props.contract_id,
      true, null, null,
      startIssueDate.value && endIssueDate.value ? { start_date: startIssueDate.value, end_date: endIssueDate.value } : null,
      startTotalFinalAmount.value && endTotalFinalAmount.value ? { start_date: startTotalFinalAmount.value, end_date: endTotalFinalAmount.value } : null, [],
      null, [], null,
      startTotalFinalAmount.value || endTotalFinalAmount.value ? { start_date: startTotalFinalAmount.value || null, end_date: endTotalFinalAmount.value || null } : null,
      props.person_id || null
    );
    downloadTaskId.value = response.task_id;
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
    downloading.value = false;
  }
}

const onDownloadTaskRefresh = async () => {
  const taskId = downloadTaskId.value;
  try {
    const res = await $apiManager.checkTask(taskId);
    if (res?.state === 'SUCCESS' && res.result?.file_url) {
      await openAuthenticatedFileUrl(res.result.file_url, !inZip.value);
    } else {
      toast.error(t('common.error'));
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    downloadTaskId.value = null;
    downloading.value = false;
  }
}

const isInvoiceExcluded = (invoiceId) => excludedInvoices.value.includes(invoiceId)

watch([startIssueDate, endIssueDate, startTotalFinalAmount, endTotalFinalAmount, selectedInvoiceStatuses], () => {
  searchData(1);
});

onMounted(() => {
  getData();
});

</script>

<template>
  <div class="region__content">
    <div v-if="pending" class="flex items-center justify-center py-16">
      <AtomsAppLoading />
    </div>

    <div v-else-if="error" class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p v-if="error.message !== t('common.no_permissions')" class="mt-2">
        <button @click="getData" class="font-medium text-sky-600 hover:text-sky-800 hover:underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>

    <div v-else class="flex flex-col gap-4">
      <div class="flex items-center gap-3">
        <H1Region>{{ $t('common.massive_invoice_download') }}</H1Region>
      </div>

      <div id="item_data" class="grid grid-cols-1 gap-4">
        <section class="rounded-lg border border-gray-200 bg-white shadow-sm">
          <header class="flex items-center gap-2 border-b border-gray-100 px-4 py-2.5">
            <Icon name="fa6-solid:filter" class="text-xs text-gray-400" />
            <span class="text-xs font-semibold uppercase tracking-wide text-gray-500">{{ t('common.filters') }}</span>
          </header>

          <div class="space-y-4 p-4">
            <div>
              <label class="mb-1.5 block text-sm font-medium text-gray-600">
                {{ $t('common.status') }} · {{ $t('invoice') }}
              </label>
              <v-select multiple class="block w-full custom-select" v-model="selectedInvoiceStatuses"
                :options="invoiceStatuses" :loading="loadingInvoiceStatuses" />
            </div>

            <div class="border-t border-gray-100" />

            <div>
              <h3 class="mb-2 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                {{ $t('billing_block.issue_date') }}
              </h3>
              <div class="flex flex-wrap items-center gap-3">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-gray-600">{{ $t('common.from') }}</span>
                  <AtomsInputDate v-model="startIssueDate" class="w-36" />
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-gray-600">{{ $t('common.to') }}</span>
                  <AtomsInputDate v-model="endIssueDate" class="w-36" />
                </div>
              </div>

              <div class="mt-3 flex flex-wrap items-center gap-3">
                <SelectorType :options="zipInvoicesSelectOptions" :model-value="inZip" @select="selectZipInvoices" />
                <AtomsProcessColorBadge v-if="downloadTaskId" class="w-fit flex items-center"
                  @refresh="onDownloadTaskRefresh" :value="t('common.processing')" :color="'blue'"
                  :taskId="downloadTaskId" />
                <button v-else class="button-secondary flex items-center justify-center gap-2"
                  :disabled="!pagination.total || downloading"
                  :class="{ 'cursor-not-allowed opacity-50': !pagination.total || downloading }" @click="downloadInvoices">
                  <Icon name="fa6-solid:download" class="text-white" />
                  {{ $t('common.download') }}
                  <span v-if="pagination.total"
                    class="rounded-full bg-white/20 px-1.5 py-0.5 text-xs font-semibold">
                    {{ pagination.total - excludedInvoices.length }}
                  </span>
                </button>
              </div>
            </div>

            <div class="border-t border-gray-100" />

            <div>
              <button type="button" class="mb-2 flex w-full items-center justify-between text-left"
                @click="showTotalAmountFilter = !showTotalAmountFilter">
                <h3 class="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                  {{ $t('billing_block.total_amount') }}
                </h3>
                <Icon name="fa6-solid:chevron-down" class="text-[10px] text-gray-400 transition-transform"
                  :class="{ '-rotate-180': showTotalAmountFilter }" />
              </button>
              <div v-if="showTotalAmountFilter" class="grid grid-cols-[72px_1fr] items-center gap-x-3 gap-y-2">
                <span class="text-sm font-medium text-gray-600">{{ $t('common.from') }}</span>
                <input type="number" v-model="startTotalFinalAmount" class="input w-full" />
                <span class="text-sm font-medium text-gray-600">{{ $t('common.until') }}</span>
                <input type="number" v-model="endTotalFinalAmount" class="input w-full" />
              </div>
            </div>
          </div>
        </section>

        <section class="flex min-h-0 flex-col rounded-lg border border-gray-200 bg-white shadow-sm">
          <header class="flex items-center justify-between border-b border-gray-100 px-4 py-2.5">
            <div class="flex items-center gap-2">
              <Icon name="fa6-solid:list-check" class="text-xs text-gray-400" />
              <span class="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {{ t('common.total_filtered') }}
              </span>
            </div>
            <span v-if="!loadingInvoices"
              class="rounded-full bg-sky-50 px-2.5 py-0.5 text-sm font-semibold tabular-nums text-sky-700">
              {{ pagination.total - excludedInvoices.length }}
            </span>
            <Icon v-else name="fa6-solid:spinner" class="animate-spin text-sm text-sky-500" />
          </header>

          <div class="min-h-[280px] flex-1 overflow-y-auto" :style="{ maxHeight: 'calc(100vh - 250px)' }">
            <div v-if="loadingInvoices" class="flex items-center justify-center py-16">
              <AtomsAppLoading />
            </div>

            <div v-else-if="selectedInvoices.length === 0"
              class="flex h-full min-h-[240px] flex-col items-center justify-center gap-2 px-4 py-12 text-gray-400">
              <Icon name="fa6-solid:inbox" class="text-2xl opacity-40" />
              <p class="text-sm text-gray-500">{{ $t('common.no_data_found') }}</p>
            </div>

            <ul v-else class="divide-y divide-gray-100">
              <li v-for="invoice in selectedInvoices" :key="invoice.id"
                class="flex items-center justify-between gap-3 px-4 py-2.5 transition-colors"
                :class="isInvoiceExcluded(invoice.id) ? 'bg-slate-50' : 'hover:bg-gray-50'">
                <div class="min-w-0 transition-opacity" :class="{ 'opacity-50': isInvoiceExcluded(invoice.id) }">
                  <p class="truncate text-sm font-medium text-gray-800">{{ invoice.serie_final }}</p>
                  <p v-if="invoice.issue_date || invoice.total_final"
                    class="mt-0.5 flex items-center gap-2 text-xs text-gray-500">
                    <span v-if="invoice.issue_date">{{ formatDate(invoice.issue_date) }}</span>
                    <span v-if="invoice.issue_date && invoice.total_final" class="text-gray-300">·</span>
                    <span v-if="invoice.total_final">{{ formatMoneyWithCurrency(invoice.total_final) }}</span>
                  </p>
                </div>
                <div class="flex shrink-0 items-center gap-x-2">
                  <AtomsColorBadge :value="invoice.status_name" :color="invoice.status_color"
                    :class="{ 'opacity-50': isInvoiceExcluded(invoice.id) }" />
                  <label
                    class="inline-flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors"
                    :title="isInvoiceExcluded(invoice.id)
                      ? `${$t('common.includes')} ${$t('invoice')}`
                      : `${$t('billing_block.exclude')} ${$t('invoice')}`">
                    <input type="checkbox" v-model="excludedInvoices" :value="invoice.id" class="peer sr-only" />
                    <span
                      class="flex h-4 w-4 shrink-0 items-center justify-center rounded border border-gray-300 bg-white text-lg font-bold leading-none text-transparent transition-colors peer-checked:border-red-400 peer-checked:bg-red-50 peer-checked:text-red-600 peer-focus-visible:ring-2 peer-focus-visible:ring-sky-500 peer-focus-visible:ring-offset-1">
                      ×
                    </span>
                    <!-- <span>
                      {{ isInvoiceExcluded(invoice.id) ? $t('billing_block.excluded') : $t('billing_block.exclude') }}
                    </span> -->
                  </label>
                </div>
              </li>
            </ul>
          </div>

          <div class="border-t border-gray-100 p-2" v-if="pagination.totalPages > 1">
            <Pagination :pagination="pagination" @update:page="onPageChange" />
          </div>
        </section>
      </div>
    </div>
  </div>
</template>