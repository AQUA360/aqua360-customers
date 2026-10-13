<script setup>
import { useRouter } from 'vue-router';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import CommunicationDetail from '../molecules/CommunicationDetail.vue';
import CommunicationProcessRegion from './CommunicationProcessRegion.vue';
import PersonRegion from './PersonRegion.vue';
import CompanyRegion from './CompanyRegion.vue';
import DocumentList from '../molecules/DocumentList.vue';
import CommunicationMessageEdit from '../molecules/CommunicationMessageEdit.vue';
import MessagesVisualization from '../molecules/MessagesVisualization.vue';
import CommunicationEdit from '../molecules/CommunicationEdit.vue';
import InvoiceMiniDetail from '../molecules/InvoiceMiniDetail.vue';
import ContractMiniDetail from '../molecules/ContractMiniDetail.vue';
import ReadingMiniDetail from '../molecules/ReadingMiniDetail.vue';
import ContractRegion from './ContractRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import MeterRegion from './MeterRegion.vue';
import CommunicationDataChange from '../atoms/CommunicationDataChange.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});


const emit = defineEmits(['show-subregion', 'changed', 'close-subregion', 'refresh-list']);
const toast = useToast();
const router = useRouter();
const { $CommunicationApiService, $ConfigProjectApiService, $DocumentManagerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('msg');
const observationNumber = ref(0)
const historyNumber = ref(0)
const dataChangeNumber = ref(0);

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const documents = ref([]);
const loading_documents = ref(false);
const retry_count = ref(0);
const MAX_RETRIES = 2;

const objectPermissions = ref(null);
const updateObservationCount = (count) => {
  observationNumber.value = count;
}

const updateHistoryCount = (count) => {
  historyNumber.value = count;
}

const updateDataChangeCount = (count) => {
  dataChangeNumber.value = count;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $CommunicationApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const validateAndRetryDocuments = async () => {
  if (!documents.value || documents.value.length === 0) return;

  if (!documents.value.every(doc => doc.file)) {
    if (retry_count.value < MAX_RETRIES) {
      retry_count.value++;
      await getData(false);
    } else {
      documents.value = documents.value.filter(doc => doc.file);
    }
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;
  loading_documents.value = true;
  error.value = null;
  try {
    const result = await $CommunicationApiService.getDetail(props.id);
    data.value = result;
    // Els fitxers marcats per no adjuntar-se al correu (p. ex. el document del pas d'una
    // gestió d'impagats quan es desmarca l'opció) no es llisten aquí, per no fer pensar
    // que s'enviaran. `=== false` a posta: només s'amaguen els explícitament exclosos.
    documents.value = (result.files || []).filter(doc => doc.attach_to_email !== false);
    await validateAndRetryDocuments();
  } catch (err) {
    console.error(err)
    error.value = err;
  } finally {
    pending.value = false;
    loading_documents.value = false;
  }
}

const handleDocumentUpdate = async (file) => {
  try {
    let save_data = {
      document: file,
      communication: props.id
    };

    const response = await $CommunicationApiService.generateFiles(save_data);
    if (response) {
      loading_documents.value = true;
      await nextTick();
      await getData()
      emit('change')
    }
  } catch (error) {
    console.error('Error saving document:', error);
  }
};

const handleMessageChange = async (newMessage) => {
  try {
    let save_data = {
      id: newMessage.id,
      subject: newMessage.subject,
      body: newMessage.body,
      type_id: newMessage.type_id,
      communication_id: props.id
    }
    const response = await $CommunicationApiService.saveMessage(save_data);
    for (let i = 0; i < data.value.messages.length; i++) {
      if (data.value.messages[i].id === newMessage.id) {
        data.value.messages[i] = response;
        break;
      }
    }
    await getData(false)
    emit('changed')
  } catch (error) {
    console.error('Error saving message:', error);
  }
}

const generateLetter = async () => {
  try {
    const response = await $CommunicationApiService.generateFiles({
      communication_ids: [props.id]
    });
    if (response) {
      await getData(false)
      emit('changed')
    }
  } catch (error) {
    console.error('Error generating letter:', error);
  }
}

const sendComm = async () => {
  try {
    let save_data = {
      communication_ids: [props.id]
    }
    const response = await $CommunicationApiService.sendCommunications(save_data);
    if (response) {
      toast.success(t('informative_block.info_process_msgs'));
      await getData(false);
      emit('changed');
    }
  } catch (error) {
    console.error('Error sending communication:', error);
  }
}

const cancelComm = async () => {
  if (!confirm(t("confirmation_text_block.confirm_cancel"))) return;
  try {
    const response = await $CommunicationApiService.deleteItem(props.id);
    if (response) {
      toast.success(t('common.deleted_successfully'));
      emit('close-subregion');
      emit('changed');
    }
  } catch (error) {
    console.error('Error canceling communication:', error);
    toast.error(t('common.error'));
  }
}

const returnLetter = async () => {
  if (!confirm(t("confirmation_text_block.confirm_return_letter"))) return;
  try {
    const response = await $CommunicationApiService.returnLetter({
      id: props.id
    });
    if (response) {
      await getData(false);
      emit('refresh-list');
    }
  } catch (error) {
    console.error('Error returning letter:', error);
    toast.error(t('common.error'));
  }
}


const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
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

const refresh = async (close = true) => {
  if (close) closeSubRegion()
  await getData()
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
    await getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

</script>

<template>
  <div class="region__content h-full" @click.stop>
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48%]': SubRegion }">
      <div class="flex justify-between relative mb-3">
        <H1Region class="">{{ $t('communication') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="CommunicationRegionOptions">
          <DropdownOption :name="`${t('common.generate')} ${t('customer_service_block.letter')}`"
            @click="generateLetter()">
            <Icon name="fa6-solid:envelope" class="display-inline mr-2" /> {{ t('common.generate') }} {{
              t('customer_service_block.letter') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.send')} ${t('communication')}`" @click="sendComm()">
            <Icon name="fa6-solid:paper-plane" class="display-inline mr-2" /> {{ t('common.send') }} {{
              t('communication') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.modify')} ${t('communication')}`"
            @click="showDetail('CommunicationEdit', props.id)">
            <Icon name="fa6-solid:pencil" class="display-inline mr-2" /> {{ t('common.modify') }} {{ t('communication')
            }}
          </DropdownOption>
          <DropdownOption v-if="data?.types?.some(type => type.token === 'letter')"
            :name="`${t('common.return')} ${t('customer_service_block.letter')}`"
            @click="returnLetter()" class="text-red-600">
            <Icon name="fa6-solid:rotate-left" class="display-inline mr-2 text-red-600" /> {{ t('common.return') }} {{
              t('customer_service_block.letter') }}
          </DropdownOption>
          <DropdownOption v-if="data?.status?.token === '0'" :name="`${t('common.cancel')} ${t('communication').toLowerCase()}`" @click="cancelComm()">
            <Icon name="fa6-solid:xmark" class="display-inline mr-2" /> {{ t('common.cancel') }} {{ t('communication').toLowerCase() }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <CommunicationDetail :id="props.id" :data="data" @show-detail="showDetail" />
      </div>

      <AtomsTabs>

        <li class="me-2">
          <a href="#tab_msg" @click.prevent="setActiveTab('msg')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'msg', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'msg' }"
            aria-current="page">
            <Icon name="fa6-solid:pen-nib" class="display-inline mr-2" />
            {{ $t("common.message") }}
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_files" @click.prevent="setActiveTab('files')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'files', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'files' }"
            aria-current="page">
            <Icon name="fa6-solid:envelopes-bulk" class="display-inline mr-2" />
            {{ $t("common.docs") }}
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_relations" @click.prevent="setActiveTab('relations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'relations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'relations' }"
            aria-current="page">
            <Icon name="fa6-solid:link" class="display-inline mr-2" />
            {{ $t("common.related") }}
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
          <a href="#tab_modifications" @click.prevent="setActiveTab('modifications')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'modifications', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'modifications' }"
            aria-current="page">
            <Icon name="fa6-solid:pencil" class="display-inline mr-2" />
            {{ $t("common.modifications") }} ({{ dataChangeNumber || 0 }})
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

      <section v-show="activeTab === 'msg'" role="tabpanel" id="tab_msg" class="bg-white antialiased">
        <MessagesVisualization :messages="data.messages" :communication="data" @show-detail="showDetail"
          :modify="objectPermissions?.can_change" @changed="getData(false); emit('changed')" />
      </section>

      <section v-show="activeTab === 'relations'" role="tabpanel" id="tab_relations"
        class="bg-white antialiased py-3 mb-10">
        <div class="mb-5">
          <span class="text-slate-500 font-bold my-2">
            {{ t('contracts') }}
          </span>
          <div class="my-2 border-t border-slate-200">
            <ContractMiniDetail :item="data.contracts" :isSubRegion="isSubRegion" @show-detail="showDetail" />
          </div>
        </div>

        <div class="mb-5">
          <span class="text-slate-500 font-bold my-2">
            {{ t('invoices') }}
          </span>
          <div class="my-2 border-t border-slate-200">
            <InvoiceMiniDetail :item="data.invoices" @show-detail="showDetail" :isSubRegion="isSubRegion" />
          </div>
        </div>

        <div class="mb-5">
          <span class="text-slate-500 font-bold my-2">
            {{ t('readings') }}
          </span>
          <div class="my-2 border-t border-slate-200">
            <ReadingMiniDetail :item="data.readings" :contracts="data.contracts" :isSubRegion="isSubRegion"
              @show-detail="showDetail" />
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'files'" role="tabpanel" id="tab_files" class="bg-white antialiased">
        <div class="my-2">
          <div v-if="documents && documents.length > 0 && documents.every(doc => doc.file)">
            <DocumentList :documents="documents" @change="getData(false)" :loading="loading_documents" />
          </div>
          <div v-else class="mb-10">
            <span class="footering text-slate-500 p-2">
              {{ $t('common.no_records') }}
            </span>
          </div>
          <div v-if="objectPermissions?.can_change" class="w-[50%] my-3">
            <span class="text-slate-500 text-sm flex items-center gap-1">
              {{ t('common.add') }} {{ t('customer_service_block.attached_files') }}
            </span>
            <span class="flex gap-3 pl-1 pt-1">
              <AtomsInputFile @update="handleDocumentUpdate" :name="'communicationDocumentFile'" :uploaded="null"
                :fullWidth="true" class="w-full" />
            </span>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations" class="bg-white antialiased">
        <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
          parent_entity="communication" url_entity="communication" :id="props.id" module="communication">
        </MoleculesObservationList>
      </section>

      <section v-show="activeTab === 'modifications'" role="tabpanel" id="tab_modifications"
        class="bg-white antialiased p-1 h-[50vh] overflow-y-auto">
        <CommunicationDataChange v-if="data" :id="props.id" @update:count="updateDataChangeCount" />
      </section>

      <section v-show="activeTab === 'history'" role="tabpanel" id="tab_history"
        class="bg-white antialiased p-1 h-[50vh] overflow-y-auto">
        <MoleculesLogList v-if="data" entity="communication-status" parent_entity="communication" :id="props.id"
          @update:count="updateHistoryCount" :service="$LoggerApiService">
        </MoleculesLogList>
      </section>

    </div><!-- end if pending -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48%] z-10"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <CommunicationProcessRegion v-if="showRegionDetailComponent === 'CommunicationProcessRegion'"
          :id="regionDetailId" :isSubRegion="true" />
        <PersonRegion v-if="showRegionDetailComponent === 'PersonRegion'" :id="regionDetailId" :isSubRegion="true" />
        <CompanyRegion v-if="showRegionDetailComponent === 'CompanyRegion'" :id="regionDetailId" :isSubRegion="true" />
        <CommunicationMessageEdit v-if="showRegionDetailComponent === 'CommunicationMessageEdit'"
          :message_data="regionDetailId" @change="handleMessageChange" />
        <CommunicationEdit v-if="showRegionDetailComponent === 'CommunicationEdit'" :id="regionDetailId"
          :isSubRegion="true" @changed="refresh(true)" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" />
        <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>