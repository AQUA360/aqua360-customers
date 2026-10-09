<script setup>
import { useI18n } from 'vue-i18n';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import { formatDate } from '~/utils/date';
import BankDetail from '~/components/molecules/BankDetail.vue';
import SendSepaEmailModal from '~/components/molecules/SendSepaEmailModal.vue';
const { $GeneralPaymentApiService, $PersonBankApiService, $DocumentManagerApiService } = useNuxtApp();
const { t } = useI18n();


const props = defineProps({
  item: Object,
  person: Object,
  country: Object,
  sepa: Object,
  request: Object,
  is_checked: Boolean,
  value: String
});

const emit = defineEmits([
  'document-checked',
  'document-update',
  'document-delete',
  'new-item'
]);

const local_checked = ref(false);
const loading_file = ref(false);
const saved_file = ref(null);

const handleDocumentCheck = (event) => {
  //TODO:CHECK THIS
  local_checked.value = event.target.checked;
  emit('document-checked', {
    general_payment: props.item?.id? props.item.id: props.item,
    checked: local_checked.value
  });
};

const handleDocumentUpdate = async (file) => {
  try {
    let save_data = {
      checked: local_checked.value,
      file: file,
      general_payment_id: props.item?.id? props.item.id: props.item,
      contract_date: props.request.registration_date || props.request.created_at
    };

    const response = await $GeneralPaymentApiService.saveSepaDocumentation(save_data);
    if (response) {
      emit('document-update', {
        general_payment: props.item?.id? props.item.id: props.item,
        file: file,
      });

      emit('new-item', response);
    }
  } catch (error) {
    console.error('Error saving document:', error);
  }
};


const handleDocumentDelete = () => {
  emit('document-delete', {
    general_payment: props.item?.id? props.item.id: props.item,
  });

}


const printDocument = async () => {
  try {
    const document_file = await $DocumentManagerApiService.getDetail(props.sepa.file)

    const file = await $DocumentManagerApiService.viewDocument(props.sepa.file);

    //when downloading, allow user to select download folder instead of default download folder
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url
    link.download = document_file.document_name;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.log(error)
  }
}

const showDocument = async () => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(props.sepa.file);
    const document_file = await $DocumentManagerApiService.getDetail(props.sepa.file);

    // First download the file
    const downloadLink = document.createElement('a');
    const pdfBlob = new Blob([file], { type: 'application/pdf' });
    const downloadUrl = URL.createObjectURL(pdfBlob);
    /* downloadLink.href = downloadUrl;
    downloadLink.download = document_file.document_name;
    downloadLink.click(); */

    // Then open in new window
    const newWindow = window.open(downloadUrl, '_blank');

    if (newWindow) {
      setTimeout(() => {
        window.URL.revokeObjectURL(downloadUrl);
      }, 250);
    }

  } catch (error) {
    console.log(error)
  }
}

const buildGenerateRequest = () => {
  const bankId = props.item?.IBAN?.id ? props.item.IBAN.id : (props.item?.IBAN ? props.item.IBAN : null);
  let save_data = {
    id: props.request?.id? props.request.id: props.request,
    person_id: props.item?.IBAN? props.item.IBAN.person?.id ? props.item.IBAN.person.id : props.item.IBAN.person : null,
    bank_id: bankId,
    person_bank_id: bankId,
    value: props.value
  }
  return $GeneralPaymentApiService.generateSepaDocument(props.item?.id? props.item.id: props.item? props.item: null, save_data);
}

const generateDocument = async () => {
  try {
    loading_file.value = true;
    const sepa = await buildGenerateRequest();
    await openAuthenticatedFileUrl(sepa.pdf_url);
  } catch (error) {
    console.error('Error generating document:', error);
  } finally {
    loading_file.value = false;
  }
}


// Enviar per correu: es regenera el document perquè reflecteixi les dades actuals
const sending_file = ref(false);
const showSendModal = ref(false);
const sepaDocumentId = ref(null);
const requestObject = computed(() => (typeof props.request === 'object' ? props.request : { id: props.request }));

const openSendEmail = async () => {
  try {
    sending_file.value = true;
    const sepa = await buildGenerateRequest();
    sepaDocumentId.value = sepa?.sepa_document_id ?? null;
    showSendModal.value = !!sepaDocumentId.value;
  } catch (error) {
    console.error('Error generating document:', error);
  } finally {
    sending_file.value = false;
  }
}


onMounted(() => {
  console.log('props.item', props);
});

</script>
<template>

  <h2 class="text-xl font-semibold mb-4">{{ t("common.doc_sepa") }}</h2>

  <div class="wrapper text-base">
    <div>
      <fieldset v-if="item?.IBAN" class="border border-gray-300 rounded p-4 bg-white mb-2">
        <BankDetail :item="item.IBAN" :person="person" />
      </fieldset>

      <fieldset v-if="props.sepa" class="border border-gray-300 rounded p-4 bg-white mb-2">
        <div class="flex justify-between items-center">
          <AtomsFieldDetail :label="$t('contract_block.holder')" :value="item.name ? item.name : person?.full_name" />
          <AtomsFieldDetail :label="$t('common.updated')" :value="formatDate(item.updated_at)" />
        </div>
        <div class="flex gap-3 mt-2">
          <button name="" class="button-default-xs" @click="showDocument">
            <Icon name="fa6-solid:download" class="text-slate-500 mr-1" />
            {{ $t('common.show') }} {{ $t('common.doc') }}
          </button>
          <button name="" class="button-default-xs" @click="printDocument">
            <Icon name="fa6-solid:download" class="text-slate-500 mr-1" />
            {{ $t('common.download') }} {{ $t('common.doc') }}
          </button>
        </div>
      </fieldset>
    </div>

    <div>
      <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded gap-3">
        <label class="inline-block" :class="'text-slate-400'">
          {{ t('common.add') }} {{ t('common.sepa') }}
          </label>
        <span class="flex gap-3 pl-1 pt-1">
          <label class="text-slate-800 text-base flex items-center gap-1">
            <input @change="handleDocumentCheck" type="checkbox" class="mr-2" :checked="local_checked" />
            {{ t('common.checked') }}
          </label>
          <AtomsInputFile :disabled="!local_checked" @update="handleDocumentUpdate" @delete="handleDocumentDelete"
            :name="'sepaFile'" :uploaded="null" :fullWidth="true" class="w-full" />
        </span>
      </fieldset>
      <div>
        <button class="button-default" @click="generateDocument" :disabled="loading_file">
          <Icon :name="loading_file ? 'fa6-solid:spinner' : 'fa6-solid:file-pdf'" class="mr-2" :class="{ 'animate-spin': loading_file }" />
          {{ loading_file ? $t('common.loading') : $t('common.generate') }} {{ $t('common.doc') }}
        </button>
        <button class="button-default ml-2" @click="openSendEmail" :disabled="loading_file || sending_file">
          <Icon :name="sending_file ? 'fa6-solid:spinner' : 'fa6-solid:envelope'" class="mr-2" :class="{ 'animate-spin': sending_file }" />
          {{ $t('contract_block.sepa_send_email') }}
        </button>
      </div>
    </div>
  </div>

  <SendSepaEmailModal :show="showSendModal" :sepa-document-id="sepaDocumentId" :contract="requestObject"
    :is-request="value !== 'contract'" :person="item?.IBAN?.person || person" @close="showSendModal = false" />
</template>