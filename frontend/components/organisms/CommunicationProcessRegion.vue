<script setup>
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import PaymentRegion from './PaymentRegion.vue';
import CommunicationProcessDetail from '../molecules/CommunicationProcessDetail.vue';
import CommunicationMiniDetail from '../molecules/CommunicationMiniDetail.vue';
import CommunicationRegion from './CommunicationRegion.vue';
import CommunicationMessageEdit from '../molecules/CommunicationMessageEdit.vue';
import MessagesVisualization from '../molecules/MessagesVisualization.vue';
import BillingRegion from './BillingRegion.vue';
import ClaimRequestRegion from './ClaimRequestRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);

const router = useRouter();
const { $apiManager, $CommunicationProcessApiService, $CommunicationApiService, $DocumentManagerApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const downloading = ref(false)
const error = ref(null);
const data = ref(null);
const activeTab = ref('communications');
const observationNumber = ref(0)
const historyNumber = ref(0)
const communicationNumber = ref(0)
const generatingFiles = ref(false)
const generationProgress = ref(0)
const objectPermissions = ref(null);
const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const processing_status_token = ref(null)

const updatingMessagesTaskId = ref(null)
const downloadLettersTaskId = ref(null)
const downloadEinvoicesTaskId = ref(null)

const reloadChild = ref(false);
const inZip = ref(false);

const updateCommunicationCount = (count) => {
  communicationNumber.value = count;
}

const updateObservationCount = (count) => {
  observationNumber.value = count;
}

const updateHistoryCount = (count) => {
  historyNumber.value = count;
}

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $CommunicationApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;
  error.value = null;
  updatingMessagesTaskId.value = null;
  try {
    processing_status_token.value = await $ConfigProjectApiService.get('communication_process_status_processing_token');
    const result = await $CommunicationProcessApiService.getDetail(props.id);
    data.value = result;
    updatingMessagesTaskId.value = data.value.updating_messages_task_id;
    downloadLettersTaskId.value = data.value.download_letters_task_id;
    downloadEinvoicesTaskId.value = data.value.download_einvoices_task_id;

    let downloadZip = await $ConfigProjectApiService.get('download_zip')
    //inZip.value = downloadZip.toLowerCase() == "true";
    inZip.value = false;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
    reloadChild.value = !reloadChild.value;
  }
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  showSubRegion();
}

const generateLetters = async () => {
  if (!confirm(t("confirmation_text_block.confirm_generate_letters"))) return;
  try {
    generatingFiles.value = true;
    generationProgress.value = 0;
    let save_data = {
      communication_ids: data.value.communications
    }
    const response = await $CommunicationApiService.generateFiles(save_data);
    if (response && response.task_id) {
      // Start polling for task progress
      const checkProgress = async () => {
        try {
          const progressResponse = await $CommunicationApiService.checkGenerateFilesProgress(response.task_id);
          if (progressResponse.status === 'SUCCESS') {
            generatingFiles.value = false;
            generationProgress.value = 100;
            toast.success(t('common.correct_download'));
            getData(false);
          } else if (progressResponse.status === 'FAILURE') {
            generatingFiles.value = false;
            generationProgress.value = 0;
            toast.error(t('common.error_download'));
          } else {
            if (progressResponse.progress) {
              generationProgress.value = progressResponse.progress;
            }
            setTimeout(checkProgress, 2000);
          }
        } catch (error) {
          console.error('Error checking progress:', error);
          generatingFiles.value = false;
          toast.error(t('common.error'));
        }
      };

      checkProgress();
    }
  } catch (error) {
    console.error(error);
    generatingFiles.value = false;
    toast.error(t('common.error_download'));
  }
}

const downloadLetters = async (postal = false, email = false, no_invoices = false) => {
  try {
    downloading.value = true;
    if (!data.value.com_files || data.value.com_files.length === 0) {
      toast.warning(t('warning_block.warning_no_docs_download'));
      return;
    }

    //GET IDS
    let ids = data.value.com_files.map(item => item.id)
    if (postal) {
      ids = data.value.com_files.filter(item => item.is_postal).map(item => item.id)
    } else if (email) {
      ids = data.value.com_files.filter(item => item.is_email).map(item => item.id)
    }
    if (no_invoices) {
      ids = data.value.com_files.filter(item => !item.has_invoice).map(item => item.id)
    }
    if (ids.length === 0) {
      toast.warning(t('warning_block.warning_no_docs_download'));
      return;
    }

    let save_data = {
      doc_ids: ids
    }

    //MARK AS SENT
    if (postal) {
      if (confirm(t("confirmation_text_block.confirm_sent_postal"))) {
        let save_post_data = {
          process_id: props.id
        }
        await $CommunicationApiService.markAsSent(save_post_data);
      }
    }

    //DOWNLOAD
    const today = new Date();
    const today_date_string = `${today.getDate().toString().padStart(2, '0')}${(today.getMonth() + 1).toString().padStart(2, '0')}${today.getFullYear()}`;
    const fileLabel = email ? t('common.email_long') : t('customer_service_block.letters');
    if (inZip.value) {
      let zippedDocs = await $DocumentManagerApiService.downloadDocuments(save_data);
      const blob = new Blob([zippedDocs], { type: 'application/zip' });

      const url = window.URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = url;
      a.download = `${fileLabel.toLowerCase()}${today_date_string}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      window.URL.revokeObjectURL(url);
    } else {
      const file = await $DocumentManagerApiService.downloadSinglePdfDocument(save_data);
      const pdfBlob = new Blob([file], { type: 'application/pdf' });

      const blob_file_url = URL.createObjectURL(pdfBlob);
      const newWindow = window.open(blob_file_url, '_blank');
      const downloadLink = document.createElement('a');
      downloadLink.href = blob_file_url;
      downloadLink.download = `${fileLabel.toLowerCase()}${today_date_string}.pdf`;
      downloadLink.click();
      if (newWindow) {
        setTimeout(() => {
          window.URL.revokeObjectURL(blob_file_url);
        }, 250);
      }
    }
    await getData(false);
  } catch (error) {
    console.error(error);
  } finally {
    downloading.value = false;
  }
}

const handleMessageChange = async (newMessage) => {
  try {
    let save_data = {
      id: newMessage.id,
      subject: newMessage.subject,
      body: newMessage.body,
      type_id: newMessage.type_id,
      process_id: props.id
    }
    const response = await $CommunicationApiService.saveMessage(save_data);
    //data.value.message = response;
    console.log("response");
    console.log(response);
    console.log(response.updating_messages_task_id);
    if (response && response.updating_messages_task_id) {
      updatingMessagesTaskId.value = response.updating_messages_task_id;
    }
  } catch (error) {
    console.error(error);
  } finally {
    refresh(true);
  }
}

const sendMessages = async (only_returned = false) => {
  let text = t("confirmation_text_block.confirm_send_digital") + "\n" + t("warning_block.warning_can_not_undo")
  if (data.value.email_coms > 0) {
    text += "\n" + t("common.email_long") + ": " + data.value.email_coms
  }
  if (!confirm(text)) return;
  try {
    const response = await $CommunicationProcessApiService.sendMessages(props.id, only_returned);
    if (response) {
      toast.success(t('informative_block.info_process_msgs'));
    } else {
      toast.error(t('common.error_save'));
    }
  } catch (error) {
    console.error(error);
  }
}

const downloadEinvoices = async () => {
  try {
    const response = await $CommunicationProcessApiService.downloadEInvoices(props.id);
    if (response) {
      if (response.task_id) {
        downloadEinvoicesTaskId.value = response.task_id;
      }
    }
  } catch (error) {
    console.error(error);
  }
}

const cancelProcess = async () => {
  if (!confirm(t("confirmation_text_block.confirm_cancel"))) return;
  try {
    const response = await $CommunicationProcessApiService.deleteItem(props.id);
    if (response) {
      toast.success(t('common.deleted_successfully'));
      emit('close-subregion');
      emit('changed');
    }
  } catch (error) {
    console.error('Error canceling process:', error);
    toast.error(t('common.error'));
  }
}

const getFiles = async (taskId) => {
  try {
    const response = await $apiManager.checkTask(taskId)
    console.log("response", response);
    await openAuthenticatedFileUrl(response.result.file_url, !downloadEinvoicesTaskId.value);

    let save_data = {
      id: props.id,
      download_einvoices_task_id: null,
      download_letters_task_id: null,
    }
    await $CommunicationProcessApiService.save(save_data);

    downloadEinvoicesTaskId.value = null;
    downloadLettersTaskId.value = null;

  } catch (error) {
    console.error(error);
  }
}

const refresh = async (close = true) => {
  await getData(false)
  if (close) closeSubRegion()
  emit('changed')
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-5 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative mb-3">
        <div class="flex items-center">
          <H1Region class="">{{ $t('common.comms_process_detail') }}</H1Region>
          <!-- {{ updatingMessagesTaskId }} -->

          <div v-if="generatingFiles || downloading" class="flex items-center ml-5">
            <Icon name="fa6-solid:spinner" class="animate-spin text-sm text-slate-500" />
            <span class="ml-2 text-sm">{{ $t('common.generating') }} {{ t('customer_service_block.letters') }}

              <span v-if="generatingFiles">
                ({{ generationProgress }}%)
              </span>

            </span>
          </div>
          <div v-if="downloadEinvoicesTaskId || downloadLettersTaskId" class="flex items-center ml-5 w-fit">
            <AtomsProcessColorBadge class="w-fit py-2" v-if="downloadEinvoicesTaskId" @refresh="getFiles(downloadEinvoicesTaskId)"
              :value="`${t('common.generating')} ${t('billing_block.einvoices').toLowerCase()}`" :color="'blue'"
              :taskId="downloadEinvoicesTaskId"></AtomsProcessColorBadge>
          </div>
        </div>
        <OptionsDropdown
          v-if="objectPermissions?.can_change && data.status?.token != processing_status_token && !updatingMessagesTaskId"
          id="CommunicationProcessRegionOptions">
          <DropdownOption @click="sendMessages()">
            <Icon name="fa6-solid:paper-plane" class="display-inline mr-2" />
            {{ t('common.send') }} {{ t('contract_block.digital_comms') }}
          </DropdownOption>
          <DropdownOption @click="sendMessages(true)">
            <Icon name="fa6-solid:paper-plane" class="display-inline mr-2" />
            {{ t('customer_service_block.resend_digital_comms') }}
          </DropdownOption>
          <!-- <DropdownOption @click="generateLetters()">
            <Icon name="fa6-solid:envelope" class="display-inline mr-2" /> 
            {{ t('common.generate') }} {{ t('customer_service_block.letters') }}
          </DropdownOption> -->
          <DropdownOption :disabled="!data.com_files || data.com_files.length === 0 || downloadEinvoicesTaskId"
            @click="downloadLetters()">
            <Icon name="fa6-solid:download" class="display-inline mr-2" />
            {{ t('common.download') }} {{ t('common.docs') }} ({{ t('common.all') }})
          </DropdownOption>
          <DropdownOption :disabled="!data.com_files || data.com_files.length === 0 || downloadEinvoicesTaskId || !data.has_invoices"
            @click="downloadLetters(false, false, true)">
            <Icon name="fa6-solid:download" class="display-inline mr-2" />
            {{ t('common.download') }} {{ t('common.docs') }} ({{ t('common.no_invoice') }})
          </DropdownOption>
          <DropdownOption :disabled="!data.has_letters || downloadEinvoicesTaskId || downloading"
            @click="downloadLetters(true)">
            <Icon name="fa6-solid:download" class="display-inline mr-2" />
            {{ t('common.download') }} {{ t('common.docs') }} ({{ t('customer_service_block.letters') }})
          </DropdownOption>
          <DropdownOption :disabled="!data.has_email || downloadEinvoicesTaskId || downloading"
            @click="downloadLetters(false, true)">
            <Icon name="fa6-solid:download" class="display-inline mr-2" />
            {{ t('common.download') }} {{ t('common.docs') }} ({{ t('common.email_long') }})
          </DropdownOption>
          <DropdownOption :disabled="!data.has_electronic_invoices || downloadEinvoicesTaskId || downloading"
            @click="downloadEinvoices()">
            <Icon name="fa6-solid:download" class="display-inline mr-2" />
            {{ t('common.download') }} {{ t('common.docs') }} ({{ t('billing_block.einvoices') }})
          </DropdownOption>
          <DropdownOption v-if="['0', '1'].includes(data?.status?.token)" :name="`${t('common.cancel')} ${t('common.comms_process_detail').toLowerCase()}`" @click="cancelProcess()">
            <Icon name="fa6-solid:xmark" class="display-inline mr-2" /> {{ t('common.cancel') }} {{ t('common.comms_process_detail').toLowerCase() }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <CommunicationProcessDetail :id="props.id" :data="data" @show-detail="showDetail" :isSubRegion="isSubRegion"
          @refresh="getData" :updatingMessagesTaskId="updatingMessagesTaskId" />
      </div>

      <AtomsTabs>

        <li class="me-2">
          <a href="#tab_communications" @click.prevent="setActiveTab('communications')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'communications', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'communications' }"
            aria-current="page">
            <Icon name="fa6-solid:file-invoice" class="display-inline mr-2" />
            {{ $t("common.comms") }}
            ({{ communicationNumber || 0 }})
          </a>
        </li>
        <li v-if="data.messages.length > 0" class="me-2">
          <a href="#tab_messages" @click.prevent="setActiveTab('messages')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'messages', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'messages' }"
            aria-current="page">
            <Icon name="fa6-solid:pen-nib" class="display-inline mr-2" />
            {{ $t("common.general_messages") }}
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_history" @click.prevent="setActiveTab('history')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'history', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'history' }"
            aria-current="page">
            <Icon name="fa6-solid:list" class="display-inline mr-2" />
            {{ $t("common.history") }} ({{ historyNumber || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }"
            aria-current="page">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t('common.observations') }} ({{
              observationNumber }})
          </a>
        </li>

      </AtomsTabs>

      <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations" class="bg-white antialiased">
        <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
          parent_entity="comunication_process" url_entity="communication-process" :id="props.id" module="communication">
        </MoleculesObservationList>
      </section>

      <section v-show="activeTab === 'history'" role="tabpanel" id="tab_history"
        class="bg-white antialiased p-1 h-[50vh] overflow-y-auto">
        <MoleculesLogList v-if="data" entity="communication-process-status" parent_entity="communication-process"
          :id="props.id" @update:count="updateHistoryCount" :service="$LoggerApiService">
        </MoleculesLogList>
      </section>

      <section v-show="activeTab === 'communications'" role="tabpanel" id="tab_communications"
        class="bg-white antialiased p-1">
        <div class="overflow-y-auto" :style="{
          minHeight: 'calc(100vh - 380px)',
          maxHeight: 'calc(100vh - 380px)',
        }">
          <CommunicationMiniDetail :id="props.id" :reload="reloadChild" @update:count="updateCommunicationCount"
            @show-detail="showDetail" :max_height="'calc(100vh - 380px)'"
            :isSubRegion="data.status?.token == processing_status_token" />
        </div>
      </section>

      <section v-show="activeTab === 'messages'" role="tabpanel" id="tab_messages" class="bg-white antialiased p-1">
        <MessagesVisualization :messages="data.messages" @show-detail="showDetail"
          :modify="objectPermissions?.can_change && data.status?.token != processing_status_token" />
      </section>

    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" />
        <PaymentRegion v-if="showRegionDetailComponent === 'PaymentRegion'" :id="regionDetailId" :isSubRegion="true" />
        <CommunicationRegion v-if="showRegionDetailComponent === 'CommunicationRegion'" :id="regionDetailId"
          :isSubRegion="true" @changed="refresh(false)" />
        <CommunicationMessageEdit v-if="showRegionDetailComponent === 'CommunicationMessageEdit'"
          :message_data="regionDetailId" @change="handleMessageChange" :is_process="true" />
        <BillingRegion v-if="showRegionDetailComponent === 'BillingRegion'" :id="regionDetailId" :isSubRegion="true" />
        <ClaimRequestRegion v-if="showRegionDetailComponent === 'ClaimRequestRegion'" :id="regionDetailId"
          :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
