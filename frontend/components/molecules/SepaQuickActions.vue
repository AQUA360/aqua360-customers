<script setup>
// components/molecules/SepaQuickActions.vue
// Accions ràpides del mandat SEPA al costat de l'indicador (X / check):
//  - Descarregar el document SEPA per signar (o veure el ja signat).
//  - Pujar el document signat i marcar-lo com a revisat en un sol pas.
//  - Enviar el document SEPA per correu al client.
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import SendSepaEmailModal from '~/components/molecules/SendSepaEmailModal.vue';

const { $GeneralPaymentApiService, $DocumentManagerApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  /** GeneralPayment (ha de tenir `id` i `IBAN`). */
  payment: {
    type: Object,
    default: null,
  },
  /** Document SEPA actual (GeneralPaymentSepaDocument). */
  sepa: {
    type: Object,
    default: null,
  },
  /** Sol·licitud o contracte al qual pertany el pagament. */
  owner: {
    type: [Object, Number],
    default: null,
  },
  /** 'request' o 'contract', segons d'on es genera el document. */
  value: {
    type: String,
    default: 'request',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['saved']);

const fileInput = ref(null);
const downloading = ref(false);
const uploading = ref(false);

const paymentId = computed(() => props.payment?.id ?? null);
const isSigned = computed(() => !!(props.sepa?.file != null && props.sepa?.checked));
const sending = ref(false);
const isBusy = computed(() => downloading.value || uploading.value || sending.value);

const showSendModal = ref(false);
const sepaDocumentId = ref(null);
const ownerObject = computed(() => (typeof props.owner === 'object' ? props.owner : { id: props.owner }));

const generateSepa = () => {
  const iban = props.payment?.IBAN;
  const bankId = iban?.id ?? iban ?? null;
  const personId = iban?.person?.id ?? iban?.person ?? null;
  return $GeneralPaymentApiService.generateSepaDocument(paymentId.value, {
    id: props.owner?.id ?? props.owner,
    person_id: personId,
    bank_id: bankId,
    person_bank_id: bankId,
    value: props.value,
  });
};

const downloadToSign = async () => {
  if (!paymentId.value || isBusy.value) return;
  try {
    downloading.value = true;
    const sepa = await generateSepa();
    await openAuthenticatedFileUrl(sepa.pdf_url);
  } catch (error) {
    console.error('Error generating SEPA document:', error);
    toast.error(t('contract_block.sepa_download_error'));
  } finally {
    downloading.value = false;
  }
};

// Es regenera el document abans d'enviar-lo perquè reflecteixi les dades actuals
const openSendEmail = async () => {
  if (!paymentId.value || isBusy.value) return;
  try {
    sending.value = true;
    const sepa = await generateSepa();
    sepaDocumentId.value = sepa?.sepa_document_id ?? null;
    showSendModal.value = !!sepaDocumentId.value;
  } catch (error) {
    console.error('Error generating SEPA document:', error);
    toast.error(t('contract_block.sepa_download_error'));
  } finally {
    sending.value = false;
  }
};

const viewSigned = async () => {
  if (!props.sepa?.file || isBusy.value) return;
  try {
    downloading.value = true;
    const file = await $DocumentManagerApiService.viewDocument(props.sepa.file);
    const blob = file instanceof Blob && file.type === 'application/pdf'
      ? file
      : new Blob([file], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    console.error('Error opening SEPA document:', error);
  } finally {
    downloading.value = false;
  }
};

const pickFile = () => {
  if (!paymentId.value || isBusy.value) return;
  fileInput.value?.click();
};

const onFileSelected = async (event) => {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file || !paymentId.value) return;

  try {
    uploading.value = true;
    const response = await $GeneralPaymentApiService.saveSepaDocumentation({
      checked: true,
      file,
      general_payment_id: paymentId.value,
    });
    toast.success(t('contract_block.sepa_signed_uploaded'));
    emit('saved', response);
  } catch (error) {
    console.error('Error uploading signed SEPA:', error);
    toast.error(t('contract_block.sepa_upload_error'));
  } finally {
    uploading.value = false;
  }
};
</script>

<template>
  <div class="inline-flex items-center gap-1">
    <button v-if="isSigned" type="button" @click.stop="viewSigned" :disabled="disabled || isBusy"
      :title="t('contract_block.sepa_view_signed')"
      class="w-7 h-7 inline-flex items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:text-sky-600 hover:border-sky-500 disabled:opacity-50">
      <Icon :name="downloading ? 'fa6-solid:spinner' : 'fa6-solid:eye'" :class="{ 'animate-spin': downloading }"
        class="w-3.5 h-3.5" />
    </button>
    <button v-else type="button" @click.stop="downloadToSign" :disabled="disabled || isBusy || !paymentId"
      :title="t('contract_block.sepa_download_to_sign')"
      class="w-7 h-7 inline-flex items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:text-sky-600 hover:border-sky-500 disabled:opacity-50">
      <Icon :name="downloading ? 'fa6-solid:spinner' : 'fa6-solid:download'" :class="{ 'animate-spin': downloading }"
        class="w-3.5 h-3.5" />
    </button>

    <button type="button" @click.stop="pickFile" :disabled="disabled || isBusy || !paymentId"
      :title="isSigned ? t('contract_block.sepa_replace_signed') : t('contract_block.sepa_upload_signed')"
      class="w-7 h-7 inline-flex items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:text-emerald-600 hover:border-emerald-500 disabled:opacity-50">
      <Icon :name="uploading ? 'fa6-solid:spinner' : 'fa6-solid:upload'" :class="{ 'animate-spin': uploading }"
        class="w-3.5 h-3.5" />
    </button>
    <button type="button" @click.stop="openSendEmail" :disabled="disabled || isBusy || !paymentId"
      :title="t('contract_block.sepa_send_email')"
      class="w-7 h-7 inline-flex items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:text-sky-600 hover:border-sky-500 disabled:opacity-50">
      <Icon :name="sending ? 'fa6-solid:spinner' : 'fa6-solid:envelope'" :class="{ 'animate-spin': sending }"
        class="w-3.5 h-3.5" />
    </button>
    <input ref="fileInput" type="file" accept="application/pdf,image/*" class="hidden" @change="onFileSelected" />
    <SendSepaEmailModal :show="showSendModal" :sepa-document-id="sepaDocumentId" :contract="ownerObject"
      :is-request="value === 'request'" :person="payment?.IBAN?.person" @close="showSendModal = false" />
  </div>
</template>
