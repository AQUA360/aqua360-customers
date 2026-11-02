<script setup>
import { ref, computed, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import InvoiceMiniDetail from '~/components/molecules/InvoiceMiniDetail.vue';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import PaymentRegion from '~/components/organisms/PaymentRegion.vue';
import CommitmentDepositRegion from '~/components/organisms/CommitmentDepositRegion.vue';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  id: Number,
  isSubRegion: {
    type: Boolean,
    default: false,
  },
  isSubRegionOpen: Boolean,
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);
const { $SendBatchApiService, $ConfigProjectApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const data = ref(null);
const pendingStatusToken = ref('0');
const processingStatusToken = ref('1');
const statusTokensLoaded = ref(false);

const activeTab = ref('items');
const observationNumber = ref(0);

const actionPending = ref(false);
const showStatusModal = ref(false);
const statusCheckResult = ref(null);

const SubRegion = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const selectedItemId = ref(null);

const itemsPending = ref(false);
const items = ref([]);
const itemsObjectKind = ref('invoice');
const itemsSearch = ref('');
const itemsPagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false,
});

const errorsPending = ref(false);
const errorRows = ref([]);
const selectedErrorIds = ref([]);
const resending = ref(false);
const previewingPayload = ref(false);
const showPayloadModal = ref(false);
const payloadPreview = ref(null);
const expandedPayloadItems = ref([]);

const statusColors = {
  0: 'yellow',
  1: 'sky',
  2: 'green',
  pending: 'yellow',
  processing: 'sky',
  done: 'green',
  finalized: 'green',
};

const itemsTabLabel = computed(() => {
  const token = data.value?.batch_type?.token;
  if (token === 'payments') return t('send_batch_block.tab_payments');
  if (token === 'commitment_create' || token === 'commitment_cancel') {
    return t('send_batch_block.tab_commitments');
  }
  return t('send_batch_block.tab_invoices');
});

const itemCount = computed(() => {
  if (!data.value) return 0;
  return (data.value.invoices_count || 0)
    + (data.value.payments_count || 0)
    + (data.value.commitment_deposits_count || 0);
});

/** Tots els errors amb aqua_id (també blocked) — per previsualitzar JSON. */
const previewableErrorIds = computed(() =>
  errorRows.value
    .filter((row) => row.aqua_id)
    .map((row) => row.aqua_id),
);

/** Només no blocked — per reenviar. */
const selectableErrorIds = computed(() =>
  errorRows.value
    .filter((row) => row.aqua_id && !row.blocked)
    .map((row) => row.aqua_id),
);

const allPreviewableSelected = computed(() => {
  const ids = previewableErrorIds.value;
  return ids.length > 0 && ids.every((id) => selectedErrorIds.value.includes(id));
});

const selectedResendIds = computed(() =>
  selectedErrorIds.value.filter((id) => selectableErrorIds.value.includes(id)),
);

const payloadJsonText = computed(() => {
  if (!payloadPreview.value) return '';
  const { batch_id: batchId, items } = payloadPreview.value;
  return JSON.stringify({ batch_id: batchId, items: items || [] }, null, 2);
});

const isPendingStatus = computed(() =>
  !!data.value?.status?.token
  && data.value.status.token === pendingStatusToken.value,
);

const isProcessingStatus = computed(() =>
  !!data.value?.status?.token
  && data.value.status.token === processingStatusToken.value,
);

const hasSendError = computed(() => !!data.value?.send_error);

const canRetrySend = computed(() => {
  if (!isPendingStatus.value) return false;
  // Error d'enviament o lot encara no enviat
  return hasSendError.value || !data.value?.sent_at;
});

const canCheckStatus = computed(() => {
  // Després d'un enviament OK el lot passa a processing; llavors es pot consultar l'estat.
  if (!isProcessingStatus.value || hasSendError.value) return false;
  if (!data.value?.sent_at) return false;
  const code = data.value?.instant_status_code;
  return code === 200 || code === 202;
});

const showPendingActions = computed(() => canRetrySend.value || canCheckStatus.value);

const isInvoiceItems = computed(() => itemsObjectKind.value === 'invoice');
const isPaymentItems = computed(() => itemsObjectKind.value === 'payment');
const isCommitmentItems = computed(() => itemsObjectKind.value === 'commitment_deposit');

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const closeSubRegion = () => {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  selectedItemId.value = null;
  emit('show-subregion', false);
};

const showSubRegion = () => {
  SubRegion.value = true;
  emit('show-subregion', true);
};

const showDetail = (component, id) => {
  // Com a subregió no obrim més regions (mateix patró que InvoiceDetail).
  if (props.isSubRegion || !id) return;
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  selectedItemId.value = id;
  showSubRegion();
};

const errorRowTarget = (row) => {
  if (!row) return null;
  if (row.object_kind === 'invoice' && row.invoice_id) {
    return { component: 'InvoiceRegion', id: row.invoice_id };
  }
  if (row.object_kind === 'payment' && row.payment_id) {
    return { component: 'PaymentRegion', id: row.payment_id };
  }
  if (row.object_kind === 'commitment_deposit' && row.object_id) {
    return { component: 'CommitmentDepositRegion', id: row.object_id };
  }
  return null;
};

const canOpenErrorRow = (row) => !props.isSubRegion && !!errorRowTarget(row);

const isErrorRowOpen = (row) => {
  const target = errorRowTarget(row);
  return !!target
    && showRegionDetailComponent.value === target.component
    && regionDetailId.value === target.id;
};

const openErrorRow = (row) => {
  const target = errorRowTarget(row);
  if (!target) return;
  showDetail(target.component, target.id);
};

const loadStatusTokens = async () => {
  if (statusTokensLoaded.value) return;
  try {
    const [pendingToken, processingToken] = await Promise.all([
      $ConfigProjectApiService.get('send_batch_status_pending_token'),
      $ConfigProjectApiService.get('send_batch_status_processing_token'),
    ]);
    if (pendingToken) pendingStatusToken.value = pendingToken;
    if (processingToken) processingStatusToken.value = processingToken;
  } catch (err) {
    console.error(err);
  } finally {
    statusTokensLoaded.value = true;
  }
};

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    await loadStatusTokens();
    data.value = await $SendBatchApiService.getBatchDetail(props.id);
    observationNumber.value = data.value?.observations_count || 0;
    if (activeTab.value === 'items') {
      await loadItems(1);
    }
    if (activeTab.value === 'errors') {
      await loadErrors();
    }
  } catch (err) {
    error.value = err;
    console.error(err);
  } finally {
    pending.value = false;
  }
};

const actionErrorDetail = (err) =>
  err?.response?._data?.detail || err?.data?.detail || t('common.error');

const retrySendBatch = async () => {
  if (!canRetrySend.value) return;
  if (!confirm(t('send_batch_block.retry_send_confirm'))) return;
  actionPending.value = true;
  try {
    data.value = await $SendBatchApiService.retrySend(props.id);
    toast.success(t('send_batch_block.retry_send_success'));
    emit('changed');
    if (activeTab.value === 'items') await loadItems(itemsPagination.value.page || 1);
    if (activeTab.value === 'errors') await loadErrors();
  } catch (err) {
    console.error(err);
    const detail = actionErrorDetail(err);
    toast.error(typeof detail === 'string' ? detail : t('common.error'));
    await getData();
  } finally {
    actionPending.value = false;
  }
};

const checkBatchStatus = async () => {
  if (!canCheckStatus.value) return;
  actionPending.value = true;
  statusCheckResult.value = null;
  try {
    const response = await $SendBatchApiService.checkStatus(props.id);
    statusCheckResult.value = response;
    if (response?.batch) {
      data.value = response.batch;
      observationNumber.value = response.batch.observations_count || observationNumber.value;
    }
    showStatusModal.value = true;
    emit('changed');
  } catch (err) {
    console.error(err);
    const detail = actionErrorDetail(err);
    toast.error(typeof detail === 'string' ? detail : t('common.error'));
  } finally {
    actionPending.value = false;
  }
};

const closeStatusModal = () => {
  showStatusModal.value = false;
};

const loadItems = async (page = 1) => {
  if (!props.id) return;
  itemsPending.value = true;
  try {
    const response = await $SendBatchApiService.getBatchItems(
      props.id,
      itemsSearch.value,
      page,
    );
    items.value = response.results || [];
    itemsObjectKind.value = response.object_kind || data.value?.batch_type?.token || 'invoice';
    if (itemsObjectKind.value === 'payments') itemsObjectKind.value = 'payment';
    if (['commitment_create', 'commitment_cancel'].includes(itemsObjectKind.value)) {
      itemsObjectKind.value = 'commitment_deposit';
    }
    if (itemsObjectKind.value === 'invoices') itemsObjectKind.value = 'invoice';
    const total = response.count || 0;
    const totalPages = Math.ceil(total / itemsPagination.value.perPage) || 0;
    Object.assign(itemsPagination.value, {
      page,
      total,
      totalPages,
      previous: page > 1 ? page - 1 : null,
      next: page < totalPages ? page + 1 : null,
      isFiltered: String(itemsSearch.value).trim() !== '',
    });
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    itemsPending.value = false;
  }
};

const debouncedLoadItems = debounce(() => {
  loadItems(1);
}, 300);

const handleItemsSearch = () => {
  itemsPagination.value.page = 1;
  debouncedLoadItems();
};

const handleItemsPageChange = (page) => {
  loadItems(page);
};

const loadErrors = async () => {
  if (!props.id) return;
  errorsPending.value = true;
  selectedErrorIds.value = [];
  try {
    const response = await $SendBatchApiService.getBatchErrors(props.id);
    errorRows.value = response.results || [];
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    errorsPending.value = false;
  }
};

const toggleErrorSelection = (aquaId) => {
  if (!aquaId) return;
  const idx = selectedErrorIds.value.indexOf(aquaId);
  if (idx === -1) {
    selectedErrorIds.value.push(aquaId);
  } else {
    selectedErrorIds.value.splice(idx, 1);
  }
};

const toggleSelectAllErrors = () => {
  if (allPreviewableSelected.value) {
    selectedErrorIds.value = [];
  } else {
    selectedErrorIds.value = [...previewableErrorIds.value];
  }
};

const resendSelectedErrors = async () => {
  const ids = selectedResendIds.value;
  if (!ids.length) {
    toast.error(t('send_batch_block.resend_none_selected'));
    return;
  }
  if (!confirm(t('send_batch_block.resend_confirm', { count: ids.length }))) {
    return;
  }
  resending.value = true;
  try {
    const response = await $SendBatchApiService.resendErrors(props.id, ids, true);
    const batchCount = response?.batches?.length || (response?.created ? 1 : 0);
    toast.success(t('send_batch_block.resend_success', { count: batchCount || 1 }));
    emit('changed');
    await getData();
    await loadErrors();
  } catch (err) {
    console.error(err);
    const detail = err?.response?._data?.detail || err?.data?.detail || t('common.error');
    toast.error(typeof detail === 'string' ? detail : t('common.error'));
  } finally {
    resending.value = false;
  }
};

const itemPreviewTitle = (item) => {
  if (!item || typeof item !== 'object') return '-';
  return item.name || item.aqua_id || item.move_type || '-';
};

const togglePayloadItem = (index) => {
  const idx = expandedPayloadItems.value.indexOf(index);
  if (idx === -1) {
    expandedPayloadItems.value.push(index);
  } else {
    expandedPayloadItems.value.splice(idx, 1);
  }
};

const closePayloadModal = () => {
  showPayloadModal.value = false;
  payloadPreview.value = null;
  expandedPayloadItems.value = [];
};

const previewSelectedPayload = async () => {
  if (!selectedErrorIds.value.length) {
    toast.error(t('send_batch_block.resend_none_selected'));
    return;
  }
  previewingPayload.value = true;
  payloadPreview.value = null;
  expandedPayloadItems.value = [];
  showPayloadModal.value = true;
  try {
    payloadPreview.value = await $SendBatchApiService.previewPayload(
      props.id,
      selectedErrorIds.value,
    );
    // Obre el primer ítem per defecte
    if ((payloadPreview.value?.items || []).length) {
      expandedPayloadItems.value = [0];
    }
  } catch (err) {
    console.error(err);
    const detail = err?.response?._data?.detail || err?.data?.detail || t('common.error');
    toast.error(typeof detail === 'string' ? detail : t('common.error'));
    closePayloadModal();
  } finally {
    previewingPayload.value = false;
  }
};

const copyPayloadJson = async () => {
  if (!payloadJsonText.value) return;
  try {
    await navigator.clipboard.writeText(payloadJsonText.value);
    toast.success(t('send_batch_block.preview_payload_copied'));
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  }
};

const setActiveTab = async (tab) => {
  activeTab.value = tab;
  if (tab === 'items') {
    await loadItems(itemsPagination.value.page || 1);
  }
  if (tab === 'errors') {
    await loadErrors();
  }
};

const updateObservationCount = (count) => {
  observationNumber.value = count;
};

watch(() => props.id, () => {
  if (props.id) {
    activeTab.value = 'items';
    itemsSearch.value = '';
    closeSubRegion();
    getData();
  }
}, { immediate: true });
</script>

<template>
  <div class="relative">
    <div v-if="pending" class="h-full min-h-[400px]">
      <AtomsAppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error" class="p-4 text-red-600">{{ $t('common.error') }}</div>
    <div v-else-if="data" class="text-base transition-all duration-500 ease" :class="{ 'mr-[48%]': SubRegion }">
      <div class="flex justify-between relative mb-3">
        <H1Region class="">{{ $t('send_batch_block.batch') }}</H1Region>
        <!-- <H1Region class="mb-0">{{ data.token }}</H1Region> -->
        <div v-if="showPendingActions" class="relative">
          <OptionsDropdown id="SendBatchRegionOptions">
            <DropdownOption v-if="canRetrySend" :name="t('send_batch_block.retry_send')" :disabled="actionPending"
              @click="retrySendBatch" />
            <DropdownOption v-if="canCheckStatus" :name="t('send_batch_block.check_status')" :disabled="actionPending"
              @click="checkBatchStatus" />
          </OptionsDropdown>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3 mb-3">
        <FieldDetail :label="$t('common.identification')" :value="data.token || '-'" />
        <FieldDetail :label="$t('common.status')">
          <AtomsColorBadge v-if="data.status"
            :value="data.status.name || t(`send_batch_block.status.${data.status.token}`)"
            :color="data.status.color || statusColors[data.status.token]" />
          <span v-else>-</span>
        </FieldDetail>
        <FieldDetail :label="$t('send_batch_block.provider')"
          :value="data.batch_type?.provider?.name || data.batch_type?.provider?.token || '-'" />
        <FieldDetail :label="$t('send_batch_block.type')" :value="data.batch_type?.name || '-'" />
        <FieldDetail :label="$t('send_batch_block.billing')" :value="data.billing_token || '-'" />
        <hr class="border-gray-200 col-span-2">
        <FieldDetail :label="$t('send_batch_block.sent_at')" :value="data.sent_at ? formatDate(data.sent_at) : '-'" />
        <FieldDetail :label="$t('send_batch_block.finished_at')"
          :value="data.finished_at ? formatDate(data.finished_at) : '-'" />
        <!-- <FieldDetail :label="$t('send_batch_block.instant_status')" :value="data.instant_status_code || '-'" /> -->
        <FieldDetail v-if="data.related_batch" :label="$t('send_batch_block.related_batch')">
          <span v-if="isSubRegion" class="font-mono">{{ data.related_batch_token || data.related_batch }}</span>
          <div v-else class="flex items-center gap-2 min-w-0">
            <button
              type="button"
              class="text-start text-sky-500 underline font-mono truncate"
              @click="showDetail('SendBatchRegion', data.related_batch)">
              {{ data.related_batch_token || data.related_batch }}
            </button>
            <AtomsRedirectButton :id="data.related_batch" :path="'/integrations/batches/'" />
          </div>
        </FieldDetail>
      </div>

      <div v-if="data.send_error" class="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {{ $t('send_batch_block.error_sending', { detail: data.send_error }) }}
      </div>
      <div v-if="data.receive_error"
        class="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {{ $t('send_batch_block.error_receiving', { detail: data.receive_error }) }}
      </div>

      <div v-if="data.summary" class="mb-4 flex flex-wrap gap-3 text-sm text-slate-600">
        <span>{{ $t('send_batch_block.summary_total') }}: {{ data.summary.total ?? 0 }}</span>
        <span class="text-green-700">{{ $t('send_batch_block.summary_ok') }}: {{ data.summary.ok ?? 0 }}</span>
        <span class="text-red-600">{{ $t('send_batch_block.summary_error') }}: {{ data.summary.error ?? 0 }}</span>
        <span>{{ $t('send_batch_block.summary_duplicate') }}: {{ data.summary.duplicate_ignored ?? 0 }}</span>
        <span>{{ $t('send_batch_block.summary_pending') }}: {{ data.summary.pending ?? 0 }}</span>
      </div>

      <AtomsTabs>
        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')" :class="{
            'text-sky-600 border-sky-600': activeTab === 'observations',
            'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations',
          }">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" />
            {{ $t('common.observations') }} ({{ observationNumber }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_items" @click.prevent="setActiveTab('items')" :class="{
            'text-sky-600 border-sky-600': activeTab === 'items',
            'hover:text-gray-600 hover:border-gray-300': activeTab !== 'items',
          }" aria-current="page">
            <Icon name="fa6-solid:file-invoice" class="display-inline mr-2" />
            {{ itemsTabLabel }} ({{ itemCount }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_errors" @click.prevent="setActiveTab('errors')" :class="{
            'text-sky-600 border-sky-600': activeTab === 'errors',
            'hover:text-gray-600 hover:border-gray-300': activeTab !== 'errors',
          }">
            <Icon name="fa6-solid:triangle-exclamation" class="display-inline mr-2" />
            {{ $t('send_batch_block.errors') }} ({{ data.error_count || 0 }})
          </a>
        </li>
      </AtomsTabs>

      <section v-show="activeTab === 'items'" role="tabpanel" id="tab_items" class="bg-white antialiased p-1">
        <form class="mb-3 flex items-center gap-2 border-b border-gray-200 pb-2" @submit.prevent="handleItemsSearch">
          <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
          <input v-model="itemsSearch" type="text" class="w-full p-1 rounded-md focus:outline-none"
            :placeholder="$t('dashboard.search')" @input="handleItemsSearch" />
        </form>

        <div v-if="itemsPending" class="p-3 text-slate-500">{{ $t('common.loading') }}</div>
        <div v-else-if="!items.length" class="p-3 text-slate-500">{{ $t('common.no_records') }}</div>
        <template v-else>
          <div class="max-h-[50vh] overflow-y-auto">
            <InvoiceMiniDetail
              v-if="isInvoiceItems"
              :item="items"
              :isSubRegion="isSubRegion"
              @show-detail="showDetail" />

            <div v-else-if="isPaymentItems" class="min-w-full text-sm text-slate-800 mt-2">
              <div class="grid bg-gray-100 border-b text-left"
                style="grid-template-columns: 110px 1.2fr 1.4fr 1fr 1fr;">
                <span class="p-2 text-slate-900 font-bold">{{ $t('common.date') }}</span>
                <span class="p-2 text-slate-900 font-bold">{{ $t('common.identification') }}</span>
                <span class="p-2 text-slate-900 font-bold">{{ $t('invoice') }}</span>
                <span class="p-2 text-slate-900 font-bold">{{ $t('common.status') }}</span>
                <span class="p-2 text-slate-900 font-bold">{{ $t('common.total') }}</span>
              </div>
              <div v-for="item in items" :key="item.id" class="grid border-b items-center"
                style="grid-template-columns: 110px 1.2fr 1.4fr 1fr 1fr;"
                :class="{ 'bg-yellow-50': item.id === selectedItemId }">
                <div class="p-2 text-slate-500">
                  {{ item.movement_date ? formatDate(item.movement_date) : '-' }}
                </div>
                <div class="p-2 min-w-0">
                  <button
                    v-if="!isSubRegion && item.payment_id"
                    type="button"
                    class="text-start text-sky-500 underline truncate"
                    @click="showDetail('PaymentRegion', item.payment_id)">
                    {{ item.token }}
                  </button>
                  <span v-else class="truncate">{{ item.token }}</span>
                </div>
                <div class="p-2 min-w-0 flex items-center gap-2">
                  <button
                    v-if="!isSubRegion && item.invoice_id"
                    type="button"
                    class="text-start text-sky-500 underline whitespace-nowrap"
                    @click="showDetail('InvoiceRegion', item.invoice_id)">
                    {{ item.invoice_serie_final || '-' }}
                  </button>
                  <span v-else>{{ item.invoice_serie_final || '-' }}</span>
                  <AtomsRedirectButton v-if="item.invoice_id" :id="item.invoice_id" :path="'/billing/invoice/'" />
                </div>
                <div class="p-2">
                  <AtomsColorBadge v-if="item.status_name" :value="item.status_name" :color="item.status_color" />
                  <span v-else>-</span>
                </div>
                <div class="p-2 text-slate-500">
                  {{ item.amount != null ? formatMoneyWithCurrency(item.amount) : '-' }}
                </div>
              </div>
            </div>

            <div v-else-if="isCommitmentItems" class="min-w-full text-sm text-slate-800 mt-2">
              <div class="grid bg-gray-100 border-b text-left" style="grid-template-columns: 1.2fr 1.6fr 1fr 1fr 1fr;">
                <span class="p-2 text-slate-900 font-bold">{{ $t('common.identification') }}</span>
                <span class="p-2 text-slate-900 font-bold">{{ $t('contract_block.holder') }}</span>
                <span class="p-2 text-slate-900 font-bold">{{ $t('common.status') }}</span>
                <span class="p-2 text-slate-900 font-bold">{{ $t('common.total') }}</span>
                <span class="p-2 text-slate-900 font-bold">{{ $t('billing_block.total_to_pay') }}</span>
              </div>
              <div v-for="item in items" :key="item.id" class="grid border-b items-center"
                style="grid-template-columns: 1.2fr 1.6fr 1fr 1fr 1fr;"
                :class="{ 'bg-yellow-50': item.id === selectedItemId }">
                <div class="p-2 min-w-0 flex items-center gap-2">
                  <button
                    v-if="!isSubRegion"
                    type="button"
                    class="text-start text-sky-500 underline truncate"
                    @click="showDetail('CommitmentDepositRegion', item.id)">
                    {{ item.token }}
                  </button>
                  <span v-else class="truncate">{{ item.token }}</span>
                  <AtomsRedirectButton :id="item.id" :path="'/billing/commitment-deposits/'" />
                </div>
                <div class="p-2 text-slate-500">
                  <p>{{ item.customer_final || '-' }}</p>
                  <p class="text-xs">{{ item.customer_token_final }}</p>
                </div>
                <div class="p-2">
                  <AtomsColorBadge v-if="item.status_name" :value="item.status_name" :color="item.status_color" />
                  <span v-else>-</span>
                </div>
                <div class="p-2 text-slate-500">
                  {{ item.total != null ? formatMoneyWithCurrency(item.total) : '-' }}
                </div>
                <div class="p-2 text-slate-500">
                  {{ item.remaining != null ? formatMoneyWithCurrency(item.remaining) : '-' }}
                </div>
              </div>
            </div>
          </div>
          <Pagination v-if="items.length > 0" :pagination="itemsPagination" @update:page="handleItemsPageChange" />
        </template>
      </section>

      <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations" class="bg-white antialiased">
        <MoleculesObservationList v-if="data" parent_entity="send_batch" url_entity="batch" :id="props.id"
          module="send-batch" @update:observation-count="updateObservationCount" />
      </section>

      <section v-show="activeTab === 'errors'" role="tabpanel" id="tab_errors" class="bg-white antialiased p-1">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p class="text-sm text-slate-500">{{ $t('send_batch_block.resend_hint') }}</p>
          <div class="flex flex-wrap items-center gap-2">
            <button type="button" class="button-default"
              :disabled="!previewableErrorIds.length" @click="toggleSelectAllErrors">
              {{ allPreviewableSelected ? $t('common.deselect_all') : $t('common.select_all') }}
            </button>
            <button type="button" class="button-default"
              :disabled="previewingPayload || !selectedErrorIds.length" @click="previewSelectedPayload">
              {{ $t('send_batch_block.preview_payload') }}
              <span v-if="selectedErrorIds.length">({{ selectedErrorIds.length }})</span>
            </button>
            <button type="button" class="button-primary"
              :disabled="resending || !selectedResendIds.length" @click="resendSelectedErrors">
              {{ $t('send_batch_block.resend_selected') }}
              <span v-if="selectedResendIds.length">({{ selectedResendIds.length }})</span>
            </button>
          </div>
        </div>

        <div v-if="errorsPending" class="p-3 text-slate-500">{{ $t('common.loading') }}</div>
        <div v-else-if="!errorRows.length" class="p-3 text-slate-500">{{ $t('send_batch_block.no_errors') }}</div>
        <div v-else class="divide-y border rounded max-h-[50vh] overflow-y-auto">
          <div v-for="row in errorRows" :key="row.aqua_id" class="flex items-start gap-3 px-3 py-2 text-sm hover:bg-slate-100 cursor-pointer" 
          @click="toggleErrorSelection(row.aqua_id)"
          :class="{
            'bg-slate-50 opacity-70': row.blocked,
            'bg-yellow-50': isErrorRowOpen(row),
          }">
            <input type="checkbox" class="mt-1" :disabled="!row.aqua_id"
              :checked="row.aqua_id && selectedErrorIds.includes(row.aqua_id)"
              />
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 min-w-0">
                <button v-if="canOpenErrorRow(row)" type="button"
                  class="font-medium text-sky-500 underline truncate text-left" @click.stop="openErrorRow(row)">
                  {{ row.label || row.aqua_id }}
                </button>
                <span v-else class="font-medium text-slate-700 truncate">
                  {{ row.label || row.aqua_id }}
                </span>
                <AtomsRedirectButton v-if="row.object_kind === 'invoice' && row.invoice_id" :id="row.invoice_id"
                  :path="'/billing/invoice/'" />
                <AtomsRedirectButton v-else-if="row.object_kind === 'commitment_deposit' && row.object_id"
                  :id="row.object_id" :path="'/billing/commitment-deposits/'" />
              </div>
              <div v-if="row.label && row.label !== row.aqua_id" class="font-mono text-xs text-slate-500">
                {{ row.aqua_id }}
              </div>
              <div class="text-red-600">{{ row.message || '-' }}</div>
              <div v-if="row.blocked" class="text-xs text-amber-700 mt-1">
                {{ $t('send_batch_block.resend_blocked') }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <Teleport to="body">
        <div v-if="showStatusModal">
          <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="closeStatusModal" />
          <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
            aria-modal="true" @click="closeStatusModal">
            <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full relative" @click.stop>
              <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
                :aria-label="t('common.cancel')" @click="closeStatusModal">
                <Icon name="fa6-solid:xmark" class="text-xl" />
              </button>
              <h2 class="text-lg font-semibold text-slate-800 mb-4 pr-6">
                {{ $t('send_batch_block.check_status_title') }}
              </h2>
              <div class="space-y-3 text-sm">
                <FieldDetail :label="$t('send_batch_block.check_status_status')"
                  :value="statusCheckResult?.status || data?.status?.name || data?.status?.token || '-'" />
                <FieldDetail :label="$t('send_batch_block.check_status_message')"
                  :value="statusCheckResult?.message || $t('send_batch_block.check_status_empty')" />
                <div v-if="statusCheckResult?.summary" class="flex flex-wrap gap-3 text-slate-600 pt-1">
                  <span>{{ $t('send_batch_block.summary_total') }}: {{ statusCheckResult.summary.total ?? 0 }}</span>
                  <span class="text-green-700">{{ $t('send_batch_block.summary_ok') }}: {{ statusCheckResult.summary.ok
                    ?? 0
                  }}</span>
                  <span class="text-red-600">{{ $t('send_batch_block.summary_error') }}: {{
                    statusCheckResult.summary.error ??
                    0 }}</span>
                  <span>{{ $t('send_batch_block.summary_pending') }}: {{ statusCheckResult.summary.pending ?? 0
                  }}</span>
                </div>
              </div>
              <div class="flex justify-end mt-6">
                <button type="button" class="button-default" @click="closeStatusModal">
                  {{ $t('common.close') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </Teleport>

      <Teleport to="body">
        <div v-if="showPayloadModal">
          <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="closePayloadModal" />
          <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
            aria-modal="true" @click="closePayloadModal">
            <div
              class="bg-white rounded-lg shadow-xl p-8 max-w-5xl w-full relative max-h-[94vh] flex flex-col text-base"
              @click.stop>
              <button type="button" class="absolute top-5 right-5 text-gray-500 hover:text-gray-700"
                :aria-label="t('common.cancel')" @click="closePayloadModal">
                <Icon name="fa6-solid:xmark" class="text-2xl" />
              </button>
              <div class="pr-10 mb-5 shrink-0">
                <h2 class="text-xl font-semibold text-slate-800">
                  {{ $t('send_batch_block.preview_payload_title') }}
                </h2>
                <p class="text-base text-slate-500 mt-1">
                  {{ $t('send_batch_block.preview_payload_subtitle') }}
                </p>
              </div>

              <div v-if="previewingPayload" class="py-12 text-center text-slate-500 text-base">
                {{ $t('send_batch_block.preview_payload_loading') }}
              </div>

              <div v-else-if="payloadPreview" class="min-h-0 flex-1 overflow-y-auto space-y-4">
                <div class="flex flex-wrap items-center gap-3 text-base bg-slate-50 border rounded-md px-4 py-3">
                  <span class="text-slate-500">{{ $t('send_batch_block.preview_payload_batch_id') }}:</span>
                  <code class="font-mono text-slate-800 font-medium text-[0.95rem]">{{ payloadPreview.batch_id }}</code>
                  <span class="text-slate-300">|</span>
                  <span class="text-slate-600">
                    {{ $t('send_batch_block.preview_payload_items') }}:
                    <strong>{{ (payloadPreview.items || []).length }}</strong>
                  </span>
                </div>

                <div v-if="(payloadPreview.mapping_errors || []).length"
                  class="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-base">
                  <div class="font-medium text-amber-800 mb-1">
                    {{ $t('send_batch_block.preview_payload_mapping_errors') }}
                  </div>
                  <ul class="space-y-1 text-amber-900">
                    <li v-for="err in payloadPreview.mapping_errors" :key="err.aqua_id" class="font-mono text-sm">
                      <span class="font-semibold">{{ err.aqua_id }}</span>: {{ err.detail }}
                    </li>
                  </ul>
                </div>

                <div v-if="!(payloadPreview.items || []).length" class="text-base text-slate-500 py-6 text-center">
                  {{ $t('send_batch_block.preview_payload_empty') }}
                </div>

                <div v-else class="space-y-3">
                  <div v-for="(item, index) in payloadPreview.items" :key="item.aqua_id || index"
                    class="border rounded-md overflow-hidden">
                    <button type="button"
                      class="w-full flex items-center justify-between gap-2 px-4 py-3 text-left bg-slate-50 hover:bg-slate-100"
                      @click="togglePayloadItem(index)">
                      <div class="min-w-0">
                        <div class="font-medium text-slate-800 text-base truncate">{{ itemPreviewTitle(item) }}</div>
                        <div class="font-mono text-sm text-slate-500 truncate">
                          {{ item.aqua_id }}
                          <span v-if="item.move_type" class="text-slate-400"> · {{ item.move_type }}</span>
                          <span v-if="item.invoice_date" class="text-slate-400"> · {{ item.invoice_date }}</span>
                        </div>
                      </div>
                      <Icon
                        :name="expandedPayloadItems.includes(index) ? 'fa6-solid:chevron-up' : 'fa6-solid:chevron-down'"
                        class="text-slate-400 shrink-0 text-lg" />
                    </button>
                    <pre v-if="expandedPayloadItems.includes(index)"
                      class="m-0 px-4 py-3 text-sm font-mono text-slate-700 bg-white overflow-x-auto max-h-80 border-t whitespace-pre-wrap break-all leading-relaxed">
                {{ JSON.stringify(item, null, 2) }}</pre>
                  </div>
                </div>

                <details class="border rounded-md">
                  <summary class="cursor-pointer px-4 py-3 text-base text-slate-600 bg-slate-50 hover:bg-slate-100">
                    {{ $t('send_batch_block.preview_payload_title') }} (raw)
                  </summary>
                  <pre
                    class="m-0 px-4 py-3 text-sm font-mono text-slate-700 overflow-x-auto max-h-96 whitespace-pre-wrap break-all border-t leading-relaxed">
              {{ payloadJsonText }}</pre>
                </details>
              </div>

              <div class="flex justify-end gap-2 mt-6 shrink-0">
                <button type="button"
                  class="px-4 py-2 text-base rounded border border-slate-300 hover:bg-slate-100 disabled:opacity-50"
                  :disabled="!payloadJsonText" @click="copyPayloadJson">
                  {{ $t('send_batch_block.preview_payload_copy') }}
                </button>
                <button type="button" class="button-default text-base" @click="closePayloadModal">
                  {{ $t('common.close') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </Teleport>
    </div>

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48%] z-10"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button type="button" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300"
          @click="closeSubRegion()">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <SendBatchRegion
          v-if="showRegionDetailComponent === 'SendBatchRegion'"
          :id="regionDetailId"
          :isSubRegion="true" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" />
        <PaymentRegion v-if="showRegionDetailComponent === 'PaymentRegion'" :id="regionDetailId" :isSubRegion="true" />
        <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId"
          :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
