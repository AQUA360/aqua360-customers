<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { formatDateTime } from '~/utils/date';

const { t } = useI18n();
const toast = useToast();
const route = useRoute();
const {
  $BillingApiService,
  $CommunicationProcessApiService,
  $ConfiglistApiService,
  $DocumentManagerApiService,
} = useNuxtApp();

const pending = ref(true);
const history = ref([]);
const paymentTypes = ref([]);
const downloadingId = ref(null);

let pollTimer = null;

const hasActiveDownload = computed(() =>
  history.value.some(item => item.status === 'pending' || item.status === 'running')
);

const orderLabel = (value) => ({
  contact_address: t('billing_block.download_order_contact_address'),
  contract_token: t('billing_block.download_order_contract_token'),
  invoice_code: t('billing_block.download_order_invoice_code'),
}[value] || value);

const deliveryLabel = (value) => ({
  all: t('billing_block.download_delivery_all'),
  postal: t('billing_block.download_delivery_postal'),
  email: t('billing_block.download_delivery_email'),
}[value] || value);

const paymentLabel = (tokens) => {
  if (!tokens?.length) return t('billing_block.download_delivery_all');
  return tokens.map(token => paymentTypes.value.find(item => item.token === token)?.label || token).join(', ');
};

const originLabel = (item) => {
  if (item.source === 'process') return item.communication_process_token || '—';
  return (item.billing_tokens || []).filter(Boolean).join(', ') || '—';
};

const statusClass = {
  pending: 'bg-slate-100 text-slate-600',
  running: 'bg-sky-100 text-sky-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

const loadHistory = async () => {
  history.value = await $BillingApiService.getDocumentDownloads() || [];
};

const schedulePoll = () => {
  clearTimeout(pollTimer);
  if (!hasActiveDownload.value) return;
  pollTimer = setTimeout(async () => {
    try {
      await loadHistory();
    } catch (err) {
      console.error(err);
    }
    schedulePoll();
  }, 4000);
};

const loadPaymentTypes = async () => {
  try {
    const fetchData = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    paymentTypes.value = (fetchData.results || [])
      .filter(item => item.token !== 'BALANCE')
      .map(item => ({ label: item.name, token: item.token }));
  } catch (err) {
    console.error(err);
  }
};

const downloadFile = async (item) => {
  if (!item.document_id) return;
  downloadingId.value = item.id;
  try {
    const file = await $DocumentManagerApiService.viewDocument(item.document_id);
    const link = document.createElement('a');
    const fileUrl = URL.createObjectURL(file);
    link.href = fileUrl;
    link.download = item.document_name || 'documents.pdf';
    link.click();
    setTimeout(() => URL.revokeObjectURL(fileUrl), 250);
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_download'));
  } finally {
    downloadingId.value = null;
  }
};

onMounted(async () => {
  if (route.query.billing || route.query.process) {
    return navigateTo({ path: '/billing/document-downloads/add', query: route.query });
  }
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
    await Promise.all([loadPaymentTypes(), loadHistory()]);
    schedulePoll();
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    pending.value = false;
  }
});

onBeforeUnmount(() => {
  clearTimeout(pollTimer);
});
</script>

<template>
  <div id="wrapper" class="text-base max-w-full">
    <div v-if="pending">
      <AppLoading :text="t('common.loading')" />
    </div>
    <div v-else>
      <div class="flex justify-between items-center mb-4">
        <H1>{{ t('billing_block.download_history') }}</H1>
        <button type="button" class="button-primary" @click="navigateTo('/billing/document-downloads/add')">
          {{ t('billing_block.download_new') }}
        </button>
      </div>

      <p v-if="history.length === 0" class="text-sm text-slate-500">{{ t('billing_block.download_history_empty') }}</p>
      <div v-else class="overflow-x-auto border border-slate-200 rounded-md bg-white">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-left text-slate-600">
            <tr>
              <th class="p-3 font-medium">{{ t('common.date') }}</th>
              <th class="p-3 font-medium">{{ t('billing_block.download_origin') }}</th>
              <th class="p-3 font-medium">{{ t('billing_block.download_requested_by') }}</th>
              <th class="p-3 font-medium">{{ t('billing_block.download_payment_types') }}</th>
              <th class="p-3 font-medium">{{ t('billing_block.download_delivery') }}</th>
              <th class="p-3 font-medium">{{ t('billing_block.download_ordering') }}</th>
              <th class="p-3 font-medium">{{ t('billing_block.download_document_count') }}</th>
              <th class="p-3 font-medium">{{ t('common.status') }}</th>
              <th class="p-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in history" :key="item.id" class="border-t border-slate-100 align-top">
              <td class="p-3 whitespace-nowrap">{{ formatDateTime(item.created_at) }}</td>
              <td class="p-3">{{ originLabel(item) }}</td>
              <td class="p-3">{{ item.requested_by_name || '—' }}</td>
              <td class="p-3">{{ paymentLabel(item.payment_type_tokens) }}</td>
              <td class="p-3">{{ item.source === 'process' ? deliveryLabel(item.delivery) : '—' }}</td>
              <td class="p-3">
                {{ orderLabel(item.ordering) }}
                <span class="text-slate-400">({{ item.descending ? t('billing_block.download_order_desc') : t('billing_block.download_order_asc') }})</span>
              </td>
              <td class="p-3">{{ item.invoice_count }}</td>
              <td class="p-3">
                <span class="rounded px-1.5 py-0.5 text-xs" :class="statusClass[item.status]">
                  {{ t(`export_jobs.status_${item.status}`) }}
                </span>
                <p v-if="item.status === 'failed' && item.error_message" class="mt-1 text-xs text-red-600">
                  {{ item.error_message }}
                </p>
              </td>
              <td class="p-3">
                <button v-if="item.status === 'completed' && item.document_id" type="button"
                  class="button-secondary !py-1 !px-2" :disabled="downloadingId === item.id"
                  @click="downloadFile(item)">
                  <Icon :name="downloadingId === item.id ? 'fa6-solid:spinner' : 'fa6-solid:download'"
                    :class="{ 'animate-spin': downloadingId === item.id }" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
