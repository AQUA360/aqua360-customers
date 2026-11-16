<script setup>
// Descàrrega dels documents d'un procés de comunicació: agrupa en un sol lloc les
// opcions que abans eren entrades separades del desplegable (tots, sense factura,
// cartes, correu i factures electròniques).
const { t } = useI18n();

const props = defineProps({
  show: { type: Boolean, default: false },
  data: { type: Object, default: null },
  downloading: { type: Boolean, default: false },
  // Hi ha una descàrrega de factures electròniques en segon pla
  einvoicesRunning: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'download-documents', 'download-einvoices', 'open-advanced']);

const kind = ref('documents');
const channel = ref('all');
const includeInvoices = ref(true);
const markSent = ref(true);

const comFiles = computed(() => props.data?.com_files || []);
const hasDocuments = computed(() => comFiles.value.length > 0);
const documentsDisabled = computed(() => !hasDocuments.value || props.einvoicesRunning);
const einvoicesDisabled = computed(() => !props.data?.has_electronic_invoices || props.einvoicesRunning);

const channelOptions = computed(() => [
  { value: 'all', label: t('customer_service_block.download_docs_all_channels'), disabled: !hasDocuments.value },
  { value: 'postal', label: t('customer_service_block.download_docs_postal'), disabled: !props.data?.has_letters },
  { value: 'email', label: t('customer_service_block.download_docs_email'), disabled: !props.data?.has_email },
]);

// Mateix criteri que fa servir la descàrrega (CommunicationProcessRegion.downloadDocuments)
const documentCount = computed(() => comFiles.value
  .filter(item => channel.value !== 'postal' || item.is_postal)
  .filter(item => channel.value !== 'email' || item.is_email)
  .filter(item => includeInvoices.value || !item.has_invoice)
  .length);

const canDownload = computed(() => {
  if (props.downloading) return false;
  if (kind.value === 'einvoices') return !einvoicesDisabled.value;
  return !documentsDisabled.value && documentCount.value > 0;
});

// En obrir, es parteix d'una opció que tingui documents
watch(() => props.show, (isOpen) => {
  if (!isOpen) return;
  kind.value = documentsDisabled.value && !einvoicesDisabled.value ? 'einvoices' : 'documents';
  channel.value = channelOptions.value.find(option => !option.disabled)?.value || 'all';
  includeInvoices.value = true;
  markSent.value = true;
});

const close = () => {
  if (props.downloading) return;
  emit('close');
};

const download = () => {
  if (!canDownload.value) return;
  if (kind.value === 'einvoices') {
    emit('download-einvoices');
    return;
  }
  emit('download-documents', {
    channel: channel.value,
    includeInvoices: includeInvoices.value,
    markSent: channel.value === 'postal' && markSent.value,
  });
};
</script>

<template>
  <div v-if="show">
    <div class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-40" @click="close"></div>

    <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-xl w-full mx-4 my-auto relative pointer-events-auto">
        <button @click="close" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700" :disabled="downloading">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>

        <h3 class="text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Icon name="fa6-solid:download" class="text-slate-500" />
          {{ t('customer_service_block.download_docs') }}
        </h3>

        <p class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
          {{ t('customer_service_block.download_docs_kind') }}
        </p>
        <div class="space-y-2 mb-5">
          <label class="flex items-center gap-2 text-sm"
            :class="documentsDisabled ? 'text-slate-400 cursor-not-allowed' : 'text-slate-700 cursor-pointer'">
            <input type="radio" value="documents" v-model="kind" :disabled="documentsDisabled" />
            {{ t('customer_service_block.download_docs_documents') }}
          </label>
          <label class="flex items-center gap-2 text-sm"
            :class="einvoicesDisabled ? 'text-slate-400 cursor-not-allowed' : 'text-slate-700 cursor-pointer'">
            <input type="radio" value="einvoices" v-model="kind" :disabled="einvoicesDisabled" />
            {{ t('customer_service_block.download_docs_einvoices') }}
          </label>
        </div>

        <template v-if="kind === 'documents'">
          <p class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
            {{ t('customer_service_block.download_docs_channel') }}
          </p>
          <div class="flex flex-wrap gap-x-5 gap-y-2 mb-5">
            <label v-for="option in channelOptions" :key="option.value" class="flex items-center gap-2 text-sm"
              :class="option.disabled ? 'text-slate-400 cursor-not-allowed' : 'text-slate-700 cursor-pointer'">
              <input type="radio" :value="option.value" v-model="channel" :disabled="option.disabled" />
              {{ option.label }}
            </label>
          </div>

          <div class="space-y-2 mb-5">
            <label class="flex items-center gap-2 text-sm"
              :class="!data?.has_invoices ? 'text-slate-400 cursor-not-allowed' : 'text-slate-700 cursor-pointer'">
              <input type="checkbox" v-model="includeInvoices" :disabled="!data?.has_invoices" />
              {{ t('customer_service_block.download_docs_include_invoices') }}
            </label>
            <label v-if="channel === 'postal'" class="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
              <input type="checkbox" v-model="markSent" />
              {{ t('customer_service_block.download_docs_mark_sent') }}
            </label>
          </div>

          <p class="text-sm text-slate-600 mb-5">
            {{ t('customer_service_block.download_docs_count', { count: documentCount }) }}
          </p>
        </template>

        <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
          <button type="button" class="text-sm text-sky-700 hover:underline" @click="emit('open-advanced')">
            <Icon name="fa6-solid:sliders" class="mr-1" />
            {{ t('customer_service_block.download_docs_advanced') }}
          </button>
          <div class="flex gap-2">
            <button type="button" class="button-secondary" :disabled="downloading" @click="close">
              {{ t('common.cancel') }}
            </button>
            <button type="button" class="button-primary flex items-center gap-2" :disabled="!canDownload" @click="download">
              <Icon v-if="downloading" name="fa6-solid:spinner" class="animate-spin" />
              <Icon v-else name="fa6-solid:download" />
              {{ t('common.download') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
