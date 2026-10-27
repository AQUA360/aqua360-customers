<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import debounce from 'lodash.debounce';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { useExportJobsStore } from '~/stores/useExportJobs';
import { useSidebarStore } from '~/stores/useNavSideBar';

const { t } = useI18n();
const toast = useToast();
const route = useRoute();
const sidebarStore = useSidebarStore();
const {
  $BillingApiService,
  $CommunicationProcessApiService,
  $CommunicationApiService,
  $ConfiglistApiService,
} = useNuxtApp();

const pending = ref(true);
const source = ref('billings');
const billingOptions = ref([]);
const processOptions = ref([]);
const selectedBillings = ref([]);
const selectedProcess = ref(null);
const loadingBillings = ref(false);
const loadingProcesses = ref(false);
const paymentTypes = ref([]);
const loadingPaymentTypes = ref(false);
const selectedPaymentTypes = ref([]);
const delivery = ref('all');
const ordering = ref('contact_address');
const descending = ref(false);
const previewCount = ref(null);
const previewing = ref(false);
const submitting = ref(false);
const linkedBillingId = ref(null);

let previewToken = 0;
let previewTimer = null;

const billingOption = (billing) => ({
  value: billing.id,
  label: [billing.token, billing.name].filter(Boolean).join(' · '),
  token: billing.token,
});

const processOption = (process) => ({
  value: process.id,
  label: [process.token, process.description].filter(Boolean).join(' · '),
  token: process.token,
});

const hasSelection = computed(() => (
  source.value === 'process' ? !!selectedProcess.value : selectedBillings.value.length > 0
));

const payload = () => ({
  billing_ids: source.value === 'billings' ? selectedBillings.value.map(item => item.value) : [],
  communication_process_id: source.value === 'process' ? selectedProcess.value?.value : null,
  payment_type_tokens: selectedPaymentTypes.value.map(item => item.token),
  delivery: source.value === 'process' ? delivery.value : 'all',
  ordering: ordering.value,
  descending: descending.value,
});

const footerTitle = computed(() => {
  if (!hasSelection.value) return t('billing_block.download_select_source');
  if (previewCount.value === 0) {
    return source.value === 'process'
      ? t('billing_block.download_no_documents')
      : t('billing_block.download_no_invoices');
  }
  return '';
});

const mergeOptions = (selected, fetched) => {
  const selectedItems = Array.isArray(selected) ? selected : (selected ? [selected] : []);
  const selectedIds = new Set(selectedItems.map(item => item.value));
  return [...selectedItems, ...fetched.filter(item => !selectedIds.has(item.value))];
};

const loadBillingOptions = async (search = '') => {
  loadingBillings.value = true;
  try {
    const data = await $BillingApiService.getAll(search, [], 1, 'created_at', true);
    const fetched = (data.results || []).map(billingOption);
    billingOptions.value = mergeOptions(selectedBillings.value, fetched);
  } catch (err) {
    console.error(err);
  } finally {
    loadingBillings.value = false;
  }
};

const loadProcessOptions = async (search = '') => {
  loadingProcesses.value = true;
  try {
    const data = await $CommunicationProcessApiService.getAll(search, [], 1, 'created_at', true);
    const fetched = (data.results || []).map(processOption);
    processOptions.value = mergeOptions(selectedProcess.value, fetched);
  } catch (err) {
    console.error(err);
  } finally {
    loadingProcesses.value = false;
  }
};

const onSearchBillings = debounce((search, loading) => {
  loading(true);
  loadBillingOptions(search).finally(() => loading(false));
}, 300);

const onSearchProcesses = debounce((search, loading) => {
  loading(true);
  loadProcessOptions(search).finally(() => loading(false));
}, 300);

const refreshPreview = async () => {
  if (!hasSelection.value) {
    previewCount.value = null;
    previewing.value = false;
    return;
  }
  const token = ++previewToken;
  previewing.value = true;
  try {
    const result = await $BillingApiService.previewDocumentDownload(payload());
    if (token !== previewToken) return;
    previewCount.value = result.count;
  } catch (err) {
    console.error(err);
    if (token !== previewToken) return;
    previewCount.value = null;
  } finally {
    if (token === previewToken) previewing.value = false;
  }
};

const schedulePreview = () => {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(refreshPreview, 300);
};

const loadPaymentTypes = async () => {
  loadingPaymentTypes.value = true;
  try {
    const fetchData = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    paymentTypes.value = (fetchData.results || [])
      .filter(item => item.token !== 'BALANCE')
      .map(item => ({ label: item.name, token: item.token }));
  } catch (err) {
    console.error(err);
  } finally {
    loadingPaymentTypes.value = false;
  }
};

const requestDownload = async () => {
  if (submitting.value || !hasSelection.value || previewCount.value === 0) return;
  submitting.value = true;
  try {
    if (source.value === 'process' && delivery.value === 'postal') {
      if (confirm(t('confirmation_text_block.confirm_sent_postal'))) {
        await $CommunicationApiService.markAsSent({ process_id: selectedProcess.value.value });
      }
    }
    const response = await $BillingApiService.requestDocumentDownload(payload());
    if (response?.export_job_id) {
      useExportJobsStore().track(response.export_job_id, t('billing_block.download_new'));
    }
    return navigateTo('/billing/document-downloads/');
  } catch (err) {
    console.error(err);
  } finally {
    submitting.value = false;
  }
};

watch(source, (value) => {
  if (value === 'billings') delivery.value = 'all';
});

watch(
  [source, selectedBillings, selectedProcess, selectedPaymentTypes, delivery, ordering, descending],
  schedulePreview,
  { deep: true },
);

onMounted(async () => {
  let canView = false;
  try {
    const billingPermissions = await $BillingApiService.getPermissions();
    canView = !!billingPermissions?.can_view;
    if (!canView) {
      const processPermissions = await $CommunicationProcessApiService.getPermissions();
      canView = !!processPermissions?.can_view;
    }
  } catch (err) {
    console.error(err);
  }
  if (!canView) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  try {
    if (route.query.billing) {
      linkedBillingId.value = route.query.billing;
      const billing = await $BillingApiService.getDetail(route.query.billing);
      selectedBillings.value = [billingOption(billing)];
    } else if (route.query.process) {
      source.value = 'process';
      const process = await $CommunicationProcessApiService.getDetail(route.query.process);
      selectedProcess.value = processOption(process);
    }
    await Promise.all([
      loadPaymentTypes(),
      loadBillingOptions(),
      loadProcessOptions(),
    ]);
    await refreshPreview();
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    pending.value = false;
  }
});

onBeforeUnmount(() => {
  clearTimeout(previewTimer);
  onSearchBillings.cancel();
  onSearchProcesses.cancel();
});
</script>

<template>
  <div id="wrapper" class="text-base max-w-full mb-40">
    <div v-if="pending">
      <AppLoading :text="t('common.loading')" />
    </div>
    <div v-else>
      <NuxtLink v-if="linkedBillingId" :to="`/billing/billing/edit/${linkedBillingId}`" class="text-sky-500 hover:underline text-sm">
        {{ t('billing_block.download_back_to_billing') }}
      </NuxtLink>
      <div class="mt-2">
        <H1>{{ t('billing_block.download_new') }}</H1>
      </div>
      <p class="mt-3 text-sm text-slate-600 max-w-3xl">{{ t('billing_block.download_panel_intro') }}</p>

      <form class="mt-6 border border-slate-200 rounded-md bg-white p-4 space-y-5" @submit.prevent="requestDownload">
        <fieldset>
          <legend class="text-sm font-medium text-slate-700 mb-2">{{ t('billing_block.download_source') }}</legend>
          <div class="flex flex-wrap gap-4">
            <label class="inline-flex items-center gap-2">
              <input type="radio" value="billings" v-model="source" />
              {{ t('billing_block.download_source_billings') }}
            </label>
            <label class="inline-flex items-center gap-2">
              <input type="radio" value="process" v-model="source" />
              {{ t('billing_block.download_source_process') }}
            </label>
          </div>
        </fieldset>

        <div v-if="source === 'billings'">
          <label class="block text-sm font-medium text-slate-700 mb-1">{{ t('billing_block.download_billings') }}</label>
          <p class="text-xs text-slate-500 mb-2">{{ t('billing_block.download_billings_help') }}</p>
          <v-select multiple class="block w-full custom-select" v-model="selectedBillings" :options="billingOptions"
            :filterable="false" :loading="loadingBillings" @search="onSearchBillings" />
          <div class="mt-3 rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950">
            {{ t('billing_block.download_billing_channel_note') }}
          </div>
        </div>
        <div v-else>
          <label class="block text-sm font-medium text-slate-700 mb-1">{{ t('billing_block.download_process') }}</label>
          <p class="text-xs text-slate-500 mb-2">{{ t('billing_block.download_process_help') }}</p>
          <v-select class="block w-full custom-select" v-model="selectedProcess" :options="processOptions"
            :filterable="false" :clearable="true" :loading="loadingProcesses" @search="onSearchProcesses" />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">{{ t('billing_block.download_payment_types') }}</label>
          <p class="text-xs text-slate-500 mb-2">{{ t('billing_block.download_payment_types_help') }}</p>
          <v-select multiple class="block w-full custom-select" v-model="selectedPaymentTypes"
            :options="paymentTypes" :loading="loadingPaymentTypes" />
        </div>

        <fieldset v-if="source === 'process'">
          <legend class="text-sm font-medium text-slate-700 mb-2">{{ t('billing_block.download_delivery') }}</legend>
          <div class="flex flex-wrap gap-4">
            <label class="inline-flex items-center gap-2">
              <input type="radio" value="all" v-model="delivery" />
              {{ t('billing_block.download_delivery_all') }}
            </label>
            <label class="inline-flex items-center gap-2">
              <input type="radio" value="postal" v-model="delivery" />
              {{ t('billing_block.download_delivery_postal') }}
            </label>
            <label class="inline-flex items-center gap-2">
              <input type="radio" value="email" v-model="delivery" />
              {{ t('billing_block.download_delivery_email') }}
            </label>
          </div>
          <p class="mt-2 text-xs text-slate-500">
            <span v-if="delivery === 'postal'">{{ t('billing_block.download_delivery_postal_help') }} </span>
            <span v-else-if="delivery === 'email'">{{ t('billing_block.download_delivery_email_help') }} </span>
            <span v-else>{{ t('billing_block.download_delivery_scope_help') }}</span>
          </p>
          <div v-if="delivery === 'postal'" class="mt-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
            {{ t('billing_block.download_postal_mark_sent') }}
          </div>
        </fieldset>

        <fieldset>
          <legend class="text-sm font-medium text-slate-700 mb-2">{{ t('billing_block.download_ordering') }}</legend>
          <div class="space-y-2">
            <label class="flex items-center gap-2">
              <input type="radio" value="contact_address" v-model="ordering" />
              {{ t('billing_block.download_order_contact_address') }}
            </label>
            <label class="flex items-center gap-2">
              <input type="radio" value="contract_token" v-model="ordering" />
              {{ t('billing_block.download_order_contract_token') }}
            </label>
            <label class="flex items-center gap-2">
              <input type="radio" value="invoice_code" v-model="ordering" />
              {{ t('billing_block.download_order_invoice_code') }}
            </label>
          </div>
          <div class="mt-3 flex flex-wrap gap-4">
            <label class="inline-flex items-center gap-2">
              <input type="radio" :value="false" v-model="descending" />
              {{ t('billing_block.download_order_asc') }}
            </label>
            <label class="inline-flex items-center gap-2">
              <input type="radio" :value="true" v-model="descending" />
              {{ t('billing_block.download_order_desc') }}
            </label>
          </div>
        </fieldset>
      </form>

      <div class="fixed right-0 bottom-0 z-[10] border-t border-gray-200 py-4 px-4 shadow-lg bg-[#FAE2DA] transition-[left] duration-200 ease-in-out"
        :style="{ left: sidebarStore.sidebarWidth + 'px' }">
        <div class="mx-auto flex justify-between items-center gap-6 px-4">
          <div class="flex items-center gap-2 min-w-0" :title="footerTitle">
            <Icon name="fa6-solid:file-lines" class="text-slate-500" />
            <span class="text-lg font-bold text-slate-900">
              <Icon v-if="previewing" name="fa6-solid:spinner" class="animate-spin" />
              <template v-else>{{ previewCount ?? 0 }}</template>
            </span>
            <span class="text-sm font-semibold text-slate-700 whitespace-nowrap">
              {{ source === 'process' ? t('billing_block.download_document_count') : t('billing_block.download_invoice_count') }}
            </span>
          </div>
          <button type="button" class="button-default flex items-center gap-2 shrink-0"
            :disabled="submitting || previewing || !hasSelection || previewCount === 0"
            @click="requestDownload">
            <Icon :name="submitting ? 'fa6-solid:spinner' : 'fa6-solid:download'" :class="{ 'animate-spin': submitting }" />
            {{ t('billing_block.download_request') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
