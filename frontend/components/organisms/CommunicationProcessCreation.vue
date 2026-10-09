<script setup>
import { shallowRef, toRaw } from 'vue';
import _ from 'lodash';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';
import { useToast } from 'vue-toastification';
import CheckCommunicationsProcess from '~/components/molecules/CheckCommunicationsProcess.vue';
import CommunicationProcessCreationSetup from '~/components/molecules/CommunicationProcessCreationSetup.vue';
import CommunicationProcessCreationManage from '~/components/molecules/CommunicationProcessCreationManage.vue';
import CommunicationProcessPersonList from '~/components/organisms/CommunicationProcessPersonList.vue';
import CommunicationProcessCreationMessage from '~/components/molecules/CommunicationProcessCreationMessage.vue';
import CommunicationProcessCreationFinalMessage from '~/components/molecules/CommunicationProcessCreationFinalMessage.vue';
import CommunicationProcessPersonMessageList from '~/components/organisms/CommunicationProcessPersonMessageList.vue';
import CommunicationProcessCreationData from '~/components/molecules/CommunicationProcessCreationData.vue';
import CommunicationSelectManageOptions from '~/components/molecules/CommunicationSelectManageOptions.vue';
import { checkPermission } from '~/middleware/permission';
import { storeToRefs } from 'pinia';
import { useConfigStore } from '~/stores/useConfigStore';
const route = useRoute();
const router = useRouter();

const props = defineProps({
  request: Object,
});

const toast = useToast()
const { t } = useI18n();
const { $CommunicationProcessApiService, $CommunicationApiService, $apiManager, $ConfigProjectApiService, $ExploitationApiService } = useNuxtApp();
const configStore = useConfigStore();
const { attachClaimDocumentsEnabled } = storeToRefs(configStore);
configStore.fetchAttachClaimDocumentsEnabled();
const objectPermissions = ref(null);
// Estats generals
const loadingRequestData = ref(false);
const currentStep = ref(0);
const loading = ref(true);
const loadingSetupData = ref(false);
const maxStep = ref(0);
const saving = ref(false);

const request = ref({})
const filteringTaskId = ref(null)

const wizardSteps = computed(() => [
    {
        index: 0,
        label: `${t('billing_block.step')} 1`,
        title: t('customer_service_block.recipients'),
        description: '',
        icon: 'fa6-solid:address-card',
    },
    {
        index: 1,
        label: `${t('billing_block.step')} 2`,
        title: t('customer_service_block.process_info'),
        description: '',
        icon: 'fa6-solid:circle-info',
    },
    {
        index: 2,
        label: `${t('billing_block.step')} 3`,
        title:  `${t('common.settings')}`,
        description: '',
        icon: 'fa6-solid:gear',
    },
    {
        index: 3,
        label: `${t('billing_block.step')} 4`,
        title:  `${t('common.select')} ${t('common.template')}`,
        description: '',
        icon: 'fa6-solid:envelope-open-text',
    },
    {
        index: 4,
        label: `${t('billing_block.step')} 5`,
        title:  t('customer_service_block.msg_confirmation'),
        description: '',
        icon: 'fa6-solid:message',
    },
    {
        index: 5,
        label: `${t('billing_block.step')} 6`,
        title:  t('common.summary'),
        description: '',
        icon: 'fa6-solid:paper-plane',
    },
]);

const persons = shallowRef([]) // Use shallowRef for large arrays
const setupType = ref(null)
const attachInvoices = ref(false)
const attachReadings = ref(false)
// Només aplica a la gestió d'impagats: el document del pas (carta de suspensió /
// recordatori) es genera i queda arxivat sempre; això només decideix si s'adjunta al correu.
// El valor per defecte ve marcat pel configProject ATTACH_CLAIM_DOCUMENTS_ENABLED.
const attachClaimDocuments = ref(true)

watch(attachClaimDocumentsEnabled, (value) => {
  if (value !== null) {
    attachClaimDocuments.value = value
  }
}, { immediate: true })
const excludedPersons = ref([])
const messageData = ref({})
const finalData = ref({})
const company = ref(null)

// Empresa del pas 1 (només si el projecte fa servir múltiples empreses): filtra els contractes
// de la cerca i preselecciona la configuració d'empresa del pas 3.
const useMultipleCompanies = ref(false)
const filterCompanies = ref([])
const filterCompany = ref(null)

const loadUseMultipleCompanies = async () => {
  try {
    const multi = await $ConfigProjectApiService.get('use_multiple_companies');
    useMultipleCompanies.value = multi === true || multi === 'True' || multi === 'true';
  } catch {
    useMultipleCompanies.value = false;
  }
}

const loadFilterCompanies = async () => {
  try {
    const collected = [];
    let page = 1;
    let hasNext = true;
    while (hasNext && page < 200) {
      const data = await $ExploitationApiService.getCompanies('', page, null, false, { is_provider: true });
      collected.push(...(data.results || []));
      hasNext = !!data.next;
      page += 1;
    }
    filterCompanies.value = collected.map(c => ({ id: c.id, label: c.name }));
  } catch (error) {
    console.error('Error loading companies:', error);
  }
}

// En canviar d'empresa, el resultat de la cerca ja no és vàlid i el pas 3 ha de tornar a
// preseleccionar la configuració de la nova empresa.
watch(filterCompany, () => {
  persons.value = []
  company.value = null
  if (finalData.value?.company || finalData.value?.company_config_email) {
    finalData.value = { ...finalData.value, company: null, company_config_email: null }
  }
})

const steps = ref([])
const stepsValue = ref([]) // per v-select

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(false)
const regionDetailId = ref(false)
const sendSearch = ref(false)

const objectSearchData = ref({})
const isObjectFixed = ref(false)
// Talls amb els que es crea el procés. Poden venir de l'objecte fixat (deep link
// des del detall del tall) o del filtre multi-tall del pas 1.
const supplyCutIds = ref([])

const isClaimRequest = computed(() => objectSearchData.value?.entity === 'claimrequest')

// Context de la comunicació segons el que s'ha triat al pas 1 (facturació fixada,
// gestió d'impagats o cerca per facturació). Els passos 3 i 4 el fan servir per
// preseleccionar el tipus d'ús i l'origen/plantilla pel token corresponent.
const contextToken = computed(() => {
  if (objectSearchData.value?.entity === 'billing') return 'billing'
  if (objectSearchData.value?.entity === 'claimrequest') return 'claim'
  if (setupType.value === 'BILLING') return 'billing'
  return null
})

// Si canvia el context al pas 1 (p. ex. es tria una facturació després d'haver passat pel pas 3),
// s'oblida el tipus d'ús desat perquè el pas 3 torni a preseleccionar el del nou context.
watch(contextToken, () => {
  if (finalData.value?.use_type) {
    finalData.value = { ...finalData.value, use_type: null }
  }
})

// Resum del resultat de la cerca. Es compta sobre les persones que realment
// s'enviaran, aplicant les dues exclusions que hi ha al wizard: el flag
// `exclude` que ja arriba de la cerca i les persones tretes manualment al pas 2
// (`excludedPersons`), que és el mateix criteri que fa servir save(); si només
// es mirés `exclude`, el resum no quadraria amb el que es desa.
const isPersonExcluded = (person) =>
  !!person?.exclude || excludedPersons.value.includes(person?.id)

const selectedPersons = computed(() =>
  (persons.value ?? []).filter(p => !isPersonExcluded(p))
)

const excludedPersonsCount = computed(() =>
  (persons.value ?? []).length - selectedPersons.value.length
)

// Els registres relacionats venen dins de cada persona (contracts / invoices /
// readings), tal com s'envien al payload de save().
const countRelated = (key) =>
  selectedPersons.value.reduce((total, p) => total + (p?.[key]?.length ?? 0), 0)

const invoices = computed(() => countRelated('invoices'))
const contracts = computed(() => countRelated('contracts'))
const readings = computed(() => countRelated('readings'))

// Els comptadors sense registres no s'ensenyen, perquè cada tipus de cerca
// (facturació, impagats, remeses...) retorna només algunes d'aquestes dades.
const searchSummary = computed(() => [
  {
    key: 'persons',
    label: t('contract_block.selected_persons'),
    value: selectedPersons.value.length,
    icon: 'fa6-solid:address-card',
    always: true,
  },
  {
    key: 'excluded',
    label: t('customer_service_block.excluded_persons'),
    value: excludedPersonsCount.value,
    icon: 'fa6-solid:eye-slash',
  },
  {
    key: 'contracts',
    label: t('contracts'),
    value: contracts.value,
    icon: 'fa6-solid:file-contract',
  },
  {
    key: 'invoices',
    label: t('invoices'),
    value: invoices.value,
    icon: 'fa6-solid:file-invoice',
  },
  {
    key: 'readings',
    label: t('readings'),
    value: readings.value,
    icon: 'fa6-solid:gauge-simple',
  },
].filter(item => item.always || item.value > 0))

// El resum viu al footer, com a SEPAManagementEdit: quan els comptadors canvien
// (una cerca nova, o una persona exclosa al pas 2) es fa el flaix per avisar-ne,
// perquè el footer és fix i queda fora de la vista on l'usuari està treballant.
const highlightFooter = ref(false)

const triggerFooterHighlight = () => {
  highlightFooter.value = false
  nextTick(() => {
    highlightFooter.value = true
    setTimeout(() => (highlightFooter.value = false), 1800)
  })
}

watch([persons, excludedPersons], () => {
  triggerFooterHighlight()
})

const handleSearch = (entity, id, is_fixed = false) => {
  objectSearchData.value.entity = entity
  objectSearchData.value.id = id
  isObjectFixed.value = is_fixed
  toggleRegion(false)
}

const removeFix = () => {
  objectSearchData.value = {}
  isObjectFixed.value = false
  // Create new empty array reference for shallowRef reactivity
  persons.value = []
}

const triggerSearch = () => {
  sendSearch.value = !sendSearch.value;
}

const refreshData = async () => {
    try {
        const response = await $apiManager.checkTask(filteringTaskId.value)
        persons.value = response.result.persons
        filteringTaskId.value = null;
    } catch (error) {
        console.error(error)
    } finally {
        loading.value = false
        loadingRequestData.value = false;
    }
}

const loadData = async () => {
  loading.value = true;
  try {
    if (props.request) {
      loadingRequestData.value = true;
      const payload = {
        type: 'DRAFT',
        filters: {
          id: props.request.id,
        }
      }
      const response = await $CommunicationProcessApiService.getCommunicationProcessData(payload);
      console.log("Response load data: ", response);
      if (response) {
        // persons.value = response.persons;
        filteringTaskId.value = response.task_id;
      }

      currentStep.value = 1;
    } else {
      loading.value = false;
      loadingRequestData.value = false;
    }

  } catch (error) {
    console.error('Error loading data:', error);
  // } finally {
  //   loading.value = false;
  //   loadingRequestData.value = false;
  }
}

const nextStep = () => {

  if (currentStep.value == 0 && persons.value.length > 0 && setupType.value == 'COMMUNICATION') {
    showDetail('CheckCommunicationsProcess', null)
    handleSubRegionEvent(true)
    return;
  }


  if (currentStep.value < 5) {
    currentStep.value++;
    maxStep.value = currentStep.value;
  }

}

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
    maxStep.value = currentStep.value;
  }
}

const isValid = () => {

  return true
}

// Ids d'un sol procés: el fixat des del deep link i el del pas 1 no es dupliquen.
const collectSupplyCutIds = () => {
  const fixedId = objectSearchData.value?.entity === 'supplycut' ? objectSearchData.value.id : null;
  return [...new Set([fixedId, ...supplyCutIds.value].filter(Boolean))].map(Number);
}

const onSupplyCutsChange = (ids) => {
  supplyCutIds.value = ids || [];
}

const save = async () => {
  saving.value = true;
  try {
    if (!isValid()) return

    if (!confirm(t('confirmation_text_block.confirm_create_process'))) return
    
    const saving_persons = persons.value
      .filter(p => !excludedPersons.value.includes(p.id))
      .map(p => {
        const rawPerson = toRaw(p);
        const person = { id: rawPerson.id };
        if (rawPerson.contracts && rawPerson.contracts.length > 0) {
          person.contracts = JSON.parse(JSON.stringify(toRaw(rawPerson.contracts.map(c => c.id))));
        }
        if (rawPerson.invoices && rawPerson.invoices.length > 0) {
          person.invoices = JSON.parse(JSON.stringify(toRaw(rawPerson.invoices.map(i => i.id))));
        }
        if (rawPerson.readings && rawPerson.readings.length > 0) {
          person.readings = JSON.parse(JSON.stringify(toRaw(rawPerson.readings.map(r => r.id))));
        }
        return person;
      });
    const chunkSize = 500;

    const personChunks = []
    for (let i = 0; i < saving_persons.length; i += chunkSize) {
      personChunks.push(saving_persons.slice(i, i + chunkSize));
    }

    let allSuccessful = true;

    // One token for the whole save: the server uses it to tell "this user is
    // launching another batch of the same run" apart from "this is a genuinely
    // concurrent process", so batch 2 is not blocked by batch 1.
    const runToken = [Date.now().toString(36), Math.random().toString(36).slice(2, 10)].join('-');
    const supplyCutIds = collectSupplyCutIds();

    for (let i = 0; i < personChunks.length; i++) {
      const rawFinalData = toRaw(finalData.value);
      const rawMessageData = toRaw(messageData.value);
      const rawObjectSearchData = toRaw(objectSearchData.value);
      const rawCompany = toRaw(company.value);

      const save_data = {
        og_id: props.request?.id,
        persons: JSON.parse(JSON.stringify(personChunks[i])),
        description: personChunks.length > 1 ? `${rawFinalData.description} - ${t('common.batch')} ${i + 1}/${personChunks.length}` : rawFinalData.description,
        due_date: rawFinalData.due_date,
        messages_data: rawFinalData.messages_data ? JSON.parse(JSON.stringify(toRaw(rawFinalData.messages_data))) : null,
        attach_letter: rawFinalData.attach_letter,
        attach_reading_invoices: rawFinalData.attach_invoices,
        attach_claim_documents: attachClaimDocuments.value,
        company_id: rawCompany?.id,
        company_config_email_id: rawFinalData.company_config_email?.id,
        message_template_id: rawMessageData.message_template,
        message_types_ids: rawMessageData.message_types ? rawMessageData.message_types.map(mt => mt.id) : [],
        message_type_names: rawMessageData.message_type_names,
        fixed_data: rawObjectSearchData?.entity ? rawObjectSearchData.entity : null,
        fixed_data_id: rawObjectSearchData?.id ? rawObjectSearchData.id : null,
        batch_number: i + 1,
        attach_invoices: attachInvoices.value,
        attach_readings: attachReadings.value,
        total_batches: personChunks.length,
        use_type_id: rawFinalData.use_type?.value || null,
        run_token: runToken,
      }

      if (supplyCutIds.length) {
        save_data.supply_cuts = supplyCutIds;
      }
      
      const response = await $CommunicationProcessApiService.save(save_data);
      
      if (!response) {
        allSuccessful = false;
        toast.error(t('common.error_save') + ` - Batch ${i + 1}/${personChunks.length}`);
        break;
      }
    }
      
    if (allSuccessful) {
      toast.success(t('common.correct_save'));
      return navigateTo('/communication/process-communications/')
      // if (route?.query?.claim_request_id){
      //   return navigateTo('/billing/claim-managements/edit/' + route.query.claim_request_id)
      // } else if (route?.query?.billing_id){
      //   return navigateTo('/billing/billing/edit/' + route.query.billing_id)
      // } else {
      //   return navigateTo('/communication/process-communications/')
      // }
    }
  } catch (err) {
    console.error(err)
    // The server rejects a save when another process is already running for the
    // same supply cut. That is a distinct outcome from a generic failure, and
    // retrying will not help.
    const body = err?.response?._data || err?.response?.data;
    if (body?.tier === 'block') {
      toast.error(body.message || t('communication_process_actions.already_running', { count: 1 }));
      return;
    }
    toast.error(t('common.error_save'))
  } finally {
    saving.value = false;
  }
}

const onExcludedPersonsChange = (value) => {
  excludedPersons.value = value
}

const onPersonsChange = (value, type = null, attach_invoices = false, attach_readings = false) => {
  persons.value = [...value]
  request.value.persons = value
  setupType.value = type
  attachInvoices.value = attach_invoices || false
  attachReadings.value = attach_readings || false
}

const onProcessInfoChange = (values) => {
  company.value = values.company
  finalData.value = values
}

const onMessageChange = (value) => {
  messageData.value = value
}

const onFinalDataChange = (value) => {
  finalData.value = value
}

const showDetail = (component, id) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  toggleRegion(true)
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    showRegionDetailComponent.value = null
    regionDetailId.value = null
    isSubRegionOpen.value = false;
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($CommunicationApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  loadData()
  loadUseMultipleCompanies().then(() => {
    if (useMultipleCompanies.value) loadFilterCompanies()
  })
  if (route?.query?.claim_request_id){
    objectSearchData.value = {
      entity: 'claimrequest',
      id: parseInt(route.query.claim_request_id),
    }
    isObjectFixed.value = true
  }
  if (route?.query?.billing_id){
    objectSearchData.value = {
      entity: 'billing',
      id: parseInt(route.query.billing_id),
    }
    isObjectFixed.value = true
  }
  // Notificació de tall: l'objecte queda fixat i el pas 1 (destinataris) es resol
  // automàticament, de manera que s'obre directament al pas 2 amb la cerca feta.
  // El tall s'envia també com a supply_cuts: fixed_data és el que fixa els
  // destinataris, però el vincle amb el procés s'ha de poder llegir després.
  if (route?.query?.supply_cut_id){
    objectSearchData.value = {
      entity: 'supplycut',
      id: parseInt(route.query.supply_cut_id),
    }
    supplyCutIds.value = [parseInt(route.query.supply_cut_id)];
    isObjectFixed.value = true
    currentStep.value = 1
    maxStep.value = 1
    // Aquest salt no passa pel getData() del pare, que és qui normalment deixa
    // el wizard enlliure. Sense això es queda heretat l'estat de càrrega inicial.
    loading.value = false;
    loadingRequestData.value = false;
    loadingSetupData.value = false;
  }
});

</script>

<template>
  <div v-if="objectPermissions?.can_change" class="wrapper text-base max-w-full mb-40">
    <!-- Navegació de passos -->
    <div class="mb-6">
      <!-- <StatusesNav :statuses="[
        { id: 0, name: `${$t('common.select')} ${$t('customer_service_block.recipients')}`, color: 'blue' },
        { id: 1, name: $t('customer_service_block.recipients'), color: 'blue' },
        { id: 2, name: $t('customer_service_block.process_info'), color: 'blue' },
        { id: 3, name: `${$t('common.select')} ${$t('common.template')}`, color: 'blue' },
        { id: 4, name: $t('customer_service_block.msg_confirmation'), color: 'blue' },
        { id: 5, name: $t('common.summary'), color: 'blue' }
      ]" :active="{ id: currentStep }" /> -->
      <WizardStatusNav :steps="wizardSteps" :current-step="currentStep" :max-step="maxStep" disabled
                :show-description="false" />
    </div>

    <div class="border border-gray-300 rounded py-4 px-4 bg-white">
      <AtomsProcessColorBadge class="w-fit flex items-center gap-x-2" v-show="false"
            @refresh="refreshData" :value="t('common.loading')" :color="'blue'" :taskId="filteringTaskId" />
      <div v-if="loadingRequestData">
        <AtomsAppLoading/>

      </div>
      <div v-else class="">
        <!-- Pas 1: Configuració -->
        <div v-show="currentStep === 0" class="space-y-4">
          <div v-if="useMultipleCompanies" class="max-w-md">
            <div class="text-sm font-medium text-gray-500 mb-2">
              {{ $t('customer_service_block.select_contracts_company') }}
            </div>
            <v-select v-model="filterCompany" :options="filterCompanies" class="block w-full"
              :placeholder="$t('service_block.companies')" />
          </div>

          <CommunicationProcessCreationManage v-if="objectSearchData?.entity && objectSearchData?.id"
            :data="objectSearchData" @load="loadingSetupData = $event" @remove-fix="removeFix" @change="onPersonsChange"
            :search="sendSearch" @show-detail="showDetail" :isFixed="isObjectFixed" :company-id="filterCompany?.id" />

          <CommunicationProcessCreationSetup v-else
            :request="request" @load="loadingSetupData = $event" @change="onPersonsChange" :search="sendSearch"
            @show-detail="showDetail" :company-id="filterCompany?.id" @change-supply-cuts="onSupplyCutsChange" />
        </div>

        <!-- Pas 2: Selecció de pagaments -->
        <div v-if="currentStep === 1" class="space-y-4">
          <CommunicationProcessPersonList :excludedPersons="excludedPersons" :persons="persons" @change-excluded="onExcludedPersonsChange" :fixed_data="objectSearchData" />
        </div>

        <!-- Pas 3: Informació del procés -->
        <div v-if="currentStep === 2" class="space-y-4">
          <CommunicationProcessCreationData :data="finalData" :has-readings="props.request?.readings?.length > 0"
            :default-use-type-token="contextToken" :default-company-id="filterCompany?.id" @change="onProcessInfoChange" />
        </div>

        <!-- Pas 4: Selecció de missatge -->
        <div v-if="currentStep === 3" class="space-y-4">
          <CommunicationProcessCreationMessage :message="messageData" :persons="persons"
            :default-origin-token="contextToken" @change="onMessageChange"/>
        </div>

        <!-- Pas 5: Confirmació de missatge -->
        <div v-if="currentStep === 4" class="space-y-4">
          <CommunicationProcessCreationFinalMessage :message="messageData" :final_data="finalData" :persons="persons"
            @change="onFinalDataChange" :fixed_data="objectSearchData" />
        </div>

        <!-- Pas 6: Resum i finalització -->
        <div v-if="currentStep === 5" class="space-y-4">
          <div v-if="isClaimRequest" class="p-3 border border-slate-200 rounded bg-white">
            <div class="flex items-center gap-2">
              <abbr class="flex items-center" :title="$t('informative_block.info_attach_claim_documents')">
                <Icon name="fa6-solid:circle-info" class="text-slate-500" />
              </abbr>
              <span>{{ $t('common.attach_claim_documents_to_email') }}</span>
              <input type="checkbox" v-model="attachClaimDocuments" />
            </div>
          </div>
          <CommunicationProcessPersonMessageList :excludedPersons="excludedPersons" :persons="persons" :final_data="finalData"
          @change="onPersonsChange" @change-excluded="onExcludedPersonsChange" :fixed_data="objectSearchData" />
        </div>
      </div>
    </div>

    <!-- Barra de navegació fixada al footer -->
    <div class="fixed right-0 bottom-0 z-[10] border-t border-gray-200 py-4 px-4 shadow-lg bg-[#FAE2DA]"
      :class="{ 'jquery-highlight': highlightFooter }"
      style="width: calc(100% - 250px)">

      <div class="mx-auto flex justify-between items-center gap-6 px-4">
        <button v-if="currentStep > 0" @click="prevStep" class="button-secondary flex items-center gap-2 shrink-0"
          :title="$t('billing_block.go_prev_step')">
          <Icon name="fa6-solid:chevron-left" /> {{ $t('common.previous') }}
        </button>

        <!-- Resum del resultat de la cerca -->
        <div class="grid auto-cols-max grid-flow-col items-center gap-x-8"
          :title="$t('customer_service_block.search_summary')">
          <div v-for="item in searchSummary" :key="`footer-summary-${item.key}`" class="flex items-center gap-2">
            <Icon :name="item.icon" :class="item.key === 'excluded' ? 'text-red-500' : 'text-slate-500'" />
            <span class="text-lg font-bold" :class="item.key === 'excluded' ? 'text-red-700' : 'text-slate-900'">
              {{ item.value }}
            </span>
            <span class="text-sm font-semibold whitespace-nowrap"
              :class="item.key === 'excluded' ? 'text-red-600' : 'text-slate-700'">
              {{ item.label }}
            </span>
          </div>
        </div>

        <div v-if="loadingSetupData" class="flex justify-center items-center h-full">
          <div class="flex items-center gap-3">
            <div class="animate-spin rounded-full h-6 w-6 border-4 border-fuchsia-200 border-t-fuchsia-500"></div>
            <span class="text-fuchsia-700 font-medium text-sm">{{ $t('common.loading') }}...</span>
          </div>
        </div>
        <div class="flex space-x-4 ml-auto">
          <button v-if="currentStep === 0" @click="triggerSearch" class="button-default flex items-center gap-2"
            :title="$t('dashboard.search')" :disabled="loadingSetupData">
            <Icon name="fa6-solid:magnifying-glass" />
            {{ $t('dashboard.search') }}
          </button>
          <button v-if="currentStep < 5 && persons?.length > 0" @click="nextStep" class="button-primary flex items-center gap-2"
            :title="$t('billing_block.go_next_step')" :disabled="loadingSetupData ||
              (currentStep == 0 && persons?.length == 0) ||
              (currentStep == 2 && (!company || !finalData?.description == null || finalData?.description == '' || !finalData?.due_date == null || finalData?.company_config_email == null)) ||
              (currentStep == 3 && (messageData == null || messageData?.message_types == null || messageData?.message_types?.length == 0)) ||
              (currentStep == 4 && (finalData == null || ((finalData?.subject == '' || finalData?.body == '') && (objectSearchData?.entity == null))))">
            {{ $t('common.next') }}
            <Icon name="fa6-solid:chevron-right" />
          </button>
          <button v-if="currentStep === 5" @click="save" :disabled="saving"
            class="button-primary flex items-center gap-2" :title="$t('common.save')">
            <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': saving }" />
            {{ $t('common.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Regió lateral -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-[50]"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[55%]': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <CommunicationSelectManageOptions v-if="showRegionDetailComponent === 'openManageOptions'"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @search="handleSearch" />
        <CheckCommunicationsProcess v-if="showRegionDetailComponent === 'CheckCommunicationsProcess'" :communication-ids="persons"/>
      </div>
    </div>
  </div>
</template>

<style scoped>

:deep(.custom-select .vs__selected-options) {
  max-height: 50px;
  overflow-y: auto;
}

:deep(.custom-select .vs__dropdown-menu) {
  max-height: 130px !important;
  overflow-y: auto;
}

</style>
