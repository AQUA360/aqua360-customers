<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import BankDetail from '~/components/molecules/BankDetail.vue';
import InputSepa from '~/components/atoms/InputSepa.vue';
import PersonBankSelect from '~/components/molecules/PersonBankSelect.vue';
import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';

const route = useRoute()
const router = useRouter()
const { $ContractApiService, $ConfiglistApiService, $ContractSurrogationApiService, $PersonApiService, $GeneralPaymentApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  request: {
    type: Object,
    required: false
  }
});
const emit = defineEmits(['change', 'show-subregion']);

const id = ref(route.params.id)
const contract = ref(null)
const selectedPerson = ref(null)
const newHolder = ref(null)
const newHolderBankSelect = ref(null)

// Llogater: la subrogació només mou el titular (ContractSurrogationSerializer.create()
// canvia holder, pagament, adreces i contactes), així que el llogater de l'antic
// titular es quedaria enganxat al contracte si no es pot decidir des d'aquí.
const currentTenant = ref(null)
const savingTenant = ref(false)
// A quin camp va la persona que se selecciona al panell de cerca: 'holder' o 'tenant'.
const personFormTarget = ref('holder')

const showRegionComponent = ref('');
const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPerson = ref(false);

const surrogationMotives = ref([])
const surrogationMotive = ref(null)

const paymentTypeOptionsById = ref([]);

const onPaymentTypesLoaded = ({ byId }) => {
  paymentTypeOptionsById.value = byId;
};
const bankDebitOptions = ref([]);
const payment = ref({});

const sepaDocuments = ref(null);
const usedPayment = ref({});

const selectedPaymentMethod = ref(null);
const selectedBankDebit = ref(null);

const is_electronic_invoice = ref(false);
const dir3 = ref(null)
const accounting_office = ref(null)
const managing_body = ref(null)
const processing_unit = ref(null)
const command = ref(null)
const record = ref(null)

const documentationToUpload = ref([])
const availableDocumentTypes = ref([])
const selectedDocumentTypes = ref([])

const loading_doc_types = ref(true);
const doc_types = ref([]);

const emitChange = () => {
  if (!payment.value) payment.value = {};
  payment.value['person_bank'] = selectedBankDebit.value?.id || null;
  payment.value['type'] = selectedPaymentMethod.value || null;
  let data = {
    payment: payment.value,
    sepa_document: sepaDocuments.value,
    bank_debit: selectedBankDebit.value?.id || null,
  };

  emit('change', data);
};

const getDocTypes = async () => {
  loading_doc_types.value = true;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-documentation-type');
    doc_types.value = data.results;
  } catch (error) {
    console.error('Error getting doc types:', error);
  } finally {
    loading_doc_types.value = false;
  }
}

const getData = async function () {
  const response = await $ContractApiService.getDetail(id.value);
  contract.value = response
  //usedPayment.value = contract.value.payment;
  //sepaDocuments.value = contract.value.payment.sepa_document || null;

  surrogationMotives.value = []
  let data = [];
  data = await $ConfiglistApiService.getAll('contract/contract-surrogation-type');
  data.results?.forEach(type => {
    surrogationMotives.value.push({
      code: type.id,
      label: type.name || type.token
    })
  });

  selectedPerson.value = contract.value.holder;
  currentTenant.value = contract.value.tenant;

  fillBankDebitOptions();
  getDocTypes();

  selectedPaymentMethod.value = payment.value?.type?.id || null;
  selectedBankDebit.value = payment.value?.IBAN || null;
  selectedPaymentMethod.value = payment.value?.type?.id || null;
  selectedBankDebit.value = payment.value?.IBAN || null;
  dir3.value = payment.value?.dir3 || null;
  accounting_office.value = payment.value?.accounting_office || null;
  managing_body.value = payment.value?.managing_body || null;
  processing_unit.value = payment.value?.processing_unit || null;

  if (accounting_office.value || managing_body.value || processing_unit.value) {
    is_electronic_invoice.value = true;
  }

  command.value = payment.value?.command || null;
  record.value = payment.value?.record || null;

  await getDocumentTypes();
}


const fillBankDebitOptions = async () => {
  //const request = props.request;
  if (selectedPerson.value && selectedPerson.value.banks) { // Correcció aquí
    bankDebitOptions.value = selectedPerson.value.banks.map(bank => ({
      value: bank.id,
      label: bank.iban
    }));
  }
}

const openPersonBankSelect = async () => {
  closeAllRegions();
  let result = await $PersonApiService.getDetail(newHolder.value.id)
  newHolderBankSelect.value = result
  showRegionComponent.value = 'PersonBankSelect';
  showRegion.value = true;
};

const openInputSepa = () => {
  closeAllRegions();
  showRegionComponent.value = 'addSepa';
  showRegion.value = true;
};

const onSepaSaved = (item) => {
  sepaDocuments.value = item
  usedPayment.value.sepa_document = sepaDocuments.value;
  emitChange();
  closeAllRegions();
}

const onPersonBankSelected = async (bank) => {
  selectedBankDebit.value = bank;
  sepaDocuments.value = usedPayment.value?.sepa_document || null;
  try {
    let save_data = {
      ...usedPayment.value,
      person_bank: bank.id,
      type: selectedPaymentMethod.value,
      mandate_token: contract.value.token,
    }
    let saved_payment = await $GeneralPaymentApiService.save(save_data);
    usedPayment.value = saved_payment;
  } catch (error) {
    console.log(error)
  }
  emitChange();
  closeAllRegions();
};

const onChangeElectronicInvoice = async () => {
  try {
    let save_data = {
      ...usedPayment.value,
      type: selectedPaymentMethod.value,
      dir3: dir3.value,
      accounting_office: accounting_office.value,
      managing_body: managing_body.value,
      processing_unit: processing_unit.value,
      command: command.value,
      record: record.value,
      mandate_token: contract.value.token,
    }
    let saved_payment = await $GeneralPaymentApiService.save(save_data);
    usedPayment.value = saved_payment;

  } catch (error) {
    console.log(error)
  }
}

const getDocumentTypes = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-surrogation-document-type');
    availableDocumentTypes.value = data.results || [];
  } catch (error) {
    console.error('Error fetching document types:', error);
  }
}

const isDocumentTypeSelected = (type) => {
  return selectedDocumentTypes.value.some(s => s.id === type.id);
}

const toggleDocumentType = (type) => {
  const existing = selectedDocumentTypes.value.find(s => s.id === type.id);
  if (existing) {
    removeDocumentType(existing);
    return;
  }

  const docType = {
    ...type,
    document: { checked: true },
    selected_doc_type: null,
  };
  selectedDocumentTypes.value.push(docType);
  upsertDocumentationToUpload(docType, { checked: true, type_name: type.name || type.list_name });
}

const removeDocumentType = (docType) => {
  selectedDocumentTypes.value = selectedDocumentTypes.value.filter(d => d.id !== docType.id);
  documentationToUpload.value = documentationToUpload.value.filter(
    d => d.contract_surrogation_document_type != docType.id
  );
}

const upsertDocumentationToUpload = (docType, extra = {}) => {
  const i = documentationToUpload.value.findIndex(d => d.contract_surrogation_document_type == docType.id)
  if (i > -1) {
    Object.assign(documentationToUpload.value[i], extra)
    documentationToUpload.value[i].selected_doc_type = extra.selected_doc_type !== undefined
      ? extra.selected_doc_type
      : (docType.selected_doc_type || documentationToUpload.value[i].selected_doc_type || null)
  } else {
    documentationToUpload.value.push({
      contract_surrogation_document_type: docType.id,
      type_name: docType.name || docType.list_name,
      selected_doc_type: extra.selected_doc_type !== undefined
        ? extra.selected_doc_type
        : (docType.selected_doc_type || null),
      ...extra
    });
  }
}

const handleDocumentUpdate = async (doc, docType) => {
  try {
    docType.document.file = doc;
    upsertDocumentationToUpload(docType, { file: doc, type_name: docType.name || docType.list_name });
  } catch (error) {
    console.log(error)
  }
}

const handleDocumentDelete = async (doc, docType) => {
  try {
    if (docType) {
      docType.document.file = null;
      const i = documentationToUpload.value.findIndex(d => d.contract_surrogation_document_type == docType.id)
      if (i > -1) {
        documentationToUpload.value[i].file = null;
      }
    }
  } catch (error) {
    console.log(error)
  }
}

const handleDocTypeChange = (docType) => {
  const i = documentationToUpload.value.findIndex(d => d.contract_surrogation_document_type == docType.id)
  if (i > -1) {
    documentationToUpload.value[i].selected_doc_type = docType.selected_doc_type || null
  } else if (docType.document?.file) {
    upsertDocumentationToUpload(docType, { selected_doc_type: docType.selected_doc_type || null });
  }
}

const isDocTypeRequired = (doc) => {
  return !!doc.document?.file;
}

const onSelectPaymentMethod = async () => {
  usedPayment.value.type = selectedPaymentMethod.value;
  emitChange();
}

const save = async () => {
  try {
    const missingDocType = documentationToUpload.value.some(doc => doc.file && !doc.selected_doc_type);
    if (missingDocType) {
      toast.error(t('warning_block.doc_type_required_if_file'));
      return;
    }

    let response = await $ContractSurrogationApiService.save({
      token: _.random(1000, 9999),
      contract: contract.value.id,
      new_holder: newHolder.value.id,
      previous_holder: selectedPerson.value.id,
      type: surrogationMotive.value.code,
      requested_at: new Date().toISOString(),
      approved_at: new Date().toISOString(),
      ...(payment.value != null && {
        payment_id: usedPayment?.value?.id ? usedPayment?.value?.id : null,
        new_payment: payment.value,
        previous_payment: contract.value?.payment?.id || null
      })
    })

    documentationToUpload.value.forEach((doc) => {
      if (!doc.file) return;

      doc.contract_request = response.id
      let save_data = {
        id: contract.value.id,
        file: doc.file,
        is_contract: false,
        contract_type: doc.selected_doc_type,
        text: doc.type_name
          ? `${t('contract_block.surrogation')} - ${doc.type_name}`
          : t('contract_block.surrogation'),
      };

      $ContractApiService.saveFile(save_data);

      // $ContractSurrogationApiService.saveDocument(doc)
    })


    return navigateTo({
      path: '/contract/contracts/',
      query: {
        id: contract.value.id,
      }
    })
  }
  catch (error) {
    console.log(error)
  }
}

const closeAllRegions = () => {
  // tanquem tots els components
  editingPerson.value = false;
  showRegionComponent.value = '';
  // tanquem region
  showRegion.value = false;
};

const updateMotive = (e) => {
  surrogationMotive.value = e
}

const fetchPerson = async (item) => {
  if (personFormTarget.value === 'tenant') {
    closeAllRegions();
    await assignTenant(item);
    return;
  }
  newHolder.value = item;
  closeAllRegions();
};

const openPersonForm = (target = 'holder') => {
  closeAllRegions();
  personFormTarget.value = target;
  editingPerson.value = true;
  showRegion.value = true;
};

/**
 * Aplica un canvi de llogater a l'instant, pel mateix camí que la pantalla de
 * "Canvi de llogater": crea un ContractTenantChange perquè el backend deixi
 * l'observació i el ContractLog corresponents, en lloc de tocar `tenant` a pèl.
 * S'aplica immediatament i no espera a desar la subrogació, igual que la
 * desvinculació de `change-tenant.vue`.
 */
const applyTenantChange = async (newTenant) => {
  if (savingTenant.value) return false;

  savingTenant.value = true;
  try {
    await $ContractApiService.changeTenant({
      token: _.random(1000, 9999),
      contract: contract.value.id,
      new_tenant: newTenant?.id ?? null,
      previous_tenant: currentTenant.value?.id ?? null,
      requested_at: new Date().toISOString(),
      approved_at: new Date().toISOString(),
    });

    currentTenant.value = newTenant ?? null;
    contract.value.tenant = currentTenant.value;
    return true;
  } catch (error) {
    console.error(error);
    const backendMessage = error.response?._data?.message || error.response?._data?.detail;
    toast.error(backendMessage || t('common.error'));
    return false;
  } finally {
    savingTenant.value = false;
  }
};

/** Desvincula el llogater del contracte (tenant_id = null) sense eliminar la persona. */
const removeTenant = async () => {
  if (!currentTenant.value || savingTenant.value) return;
  if (!confirm(t('confirmation_text_block.confirm_unlink_tenant'))) return;

  if (await applyTenantChange(null)) {
    toast.success(t('contract_block.tenant_unlinked_success'));
  }
};

/** Assigna un llogater nou al contracte, o el substitueix si ja n'hi havia un. */
const assignTenant = async (person) => {
  if (!person || person.id === currentTenant.value?.id) return;

  if (await applyTenantChange(person)) {
    toast.success(t('contract_block.tenant_changed_success'));
  }
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getData()
});

watch(
  [
    selectedPaymentMethod,
    selectedBankDebit
  ],
  () => {
    emitChange();
  },
  { deep: true }
);


watch(is_electronic_invoice, (newVal) => {
  if (!newVal) {
    accounting_office.value = null;
    managing_body.value = null;
    processing_unit.value = null;
    command.value = null;
    record.value = null;
  }
}, { deep: true });

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-xl">
    <div v-if="contract == null">
      <div class="flex justify-center items-center">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        <span class="ml-2">{{ $t('common.loading') }}...</span>
      </div>
    </div>
    <div v-else>
      <div class="flex justify-between items-center mb-6">
        <H1>{{ $t(`contract_block.contract_surrogation`) }}
          {{ contract.supply_point_default?.address_complete || contract.token }}</H1>
      </div>
      <div class="border-gray-300 mb-2">
        <div class="mb-4">
          <label for="person" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="selectedPerson" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <Icon v-show="!selectedPerson" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
            <span>{{ $t('contract_block.current_holder') }}:</span>
          </label>

          <div v-if="selectedPerson" class="bg-green-100 p-4 rounded relative max-w-xl group">
            <p class="font-semibold">{{ selectedPerson.name }} {{ selectedPerson.surname }}<br />
              <span class="text-sm text-gray-500">{{ selectedPerson.token }}</span>
            </p>
          </div>
        </div>

        <div class="max-w-xl mb-2">
          <div class="flex">
            <label for="source" class="block text-sm font-medium text-slate-500 mb-2">
              {{ $t('contract_block.surrogation_reason') }}</label>
          </div>
          <v-select class="block w-full mr-2 required" :disabled="surrogationMotives.length == 0"
            :model-value="surrogationMotive" @update:modelValue="updateMotive" :options="surrogationMotives" />
        </div>


        <div class="mb-4">
          <label for="person" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="newHolder" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <Icon v-show="!newHolder" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
            <span>{{ $t('contract_block.new_holder') }}:</span>
          </label>

          <div v-if="newHolder" class="bg-green-100 p-4 rounded relative max-w-xl group">
            <p class="font-semibold">{{ newHolder.name }} {{ newHolder.surname }}<br />
              <span class="text-sm text-gray-500">{{ newHolder.token }}</span>
            </p>
            <button @click="openPersonForm('holder')"
              class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
              <Icon name="fa6-solid:pencil" />
            </button>
          </div>
          <div v-else class="max-w-xl">
            <ButtonSeleccio :disabled="surrogationMotive == null" @click="openPersonForm('holder')">
              {{ $t('common.select') }} {{ $t('common.or') }} {{ $t('common.add') }} {{ $t('contract_block.holder') }}
            </ButtonSeleccio>
          </div>
        </div>

        <!-- La subrogació no toca el llogater: si no es decideix res aquí, el llogater
             de l'antic titular es queda enganxat al contracte. -->
        <div class="mb-4">
          <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="currentTenant" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <span>{{ $t('contract_block.current_tenant') }}:</span>
          </label>

          <div v-if="currentTenant" class="bg-green-100 p-4 rounded relative max-w-xl pr-24">
            <p class="font-semibold">{{ currentTenant.name }} {{ currentTenant.surname }}<br />
              <span class="text-sm text-gray-500">{{ currentTenant.token }}</span>
            </p>
            <button type="button" @click="openPersonForm('tenant')" :disabled="savingTenant"
              class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-12 top-3 rounded-md text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              :title="`${t('common.change')} ${t('contract_block.tenant')}`">
              <Icon name="fa6-solid:pencil" />
            </button>
            <button type="button" @click="removeTenant" :disabled="savingTenant"
              class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-red-600 hover:bg-red-50 disabled:opacity-50"
              :title="`${t('common.unlink')} ${t('contract_block.tenant')}`">
              <Icon :name="savingTenant ? 'fa6-solid:spinner' : 'fa6-solid:trash'" :class="{ 'animate-spin': savingTenant }" />
            </button>
          </div>
          <div v-else class="max-w-xl">
            <p class="text-sm text-slate-500 mb-2">{{ $t('contract_block.no_tenant') }}</p>
            <ButtonSeleccio :disabled="savingTenant" @click="openPersonForm('tenant')">
              {{ $t('contract_block.select_tenant') }}
            </ButtonSeleccio>
          </div>
        </div>

        <div class="mb-4">

          <SelectPaymentType v-model="selectedPaymentMethod" :disabled="surrogationMotive == null"
            :model-as-number="true" select-wrapper-class="max-w-xl"
            select-class="w-full text-base border border-gray-300 rounded p-2" @change="onSelectPaymentMethod"
            @loaded="onPaymentTypesLoaded">
            <template #label>
              <label for="person" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
                <Icon v-show="newHolder && selectedPaymentMethod" name="fa6-solid:circle-check"
                  class="text-xl text-emerald-600" />
                <Icon v-show="!newHolder || !selectedPaymentMethod" name="fa6-solid:asterisk"
                  class="text-lg text-slate-400" />
                <span>{{ $t('common.payment_method') }}:</span>
              </label>
            </template>
          </SelectPaymentType>

          <div class="select_bank mt-3 max-w-xl"
            v-if="paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'DIRECT_DEBIT'">
            <div v-if="selectedBankDebit" class="bg-green-100 p-4 rounded relative group">
              <div>
                <BankDetail :item="selectedBankDebit" :sepa="sepaDocuments || null" :show_sepa="true" />
              </div>
              <button @click="openPersonBankSelect"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                <Icon name="fa6-solid:pencil" />
              </button>
            </div>
            <ButtonSeleccio v-else @click="openPersonBankSelect()" class="py-3">
              <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
              {{ $t('common.select') }} {{ $t('common.iban') }}
            </ButtonSeleccio>

            <div v-if="selectedBankDebit">
              <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded">
                <!-- <label class="inline-block" :class=" 'text-slate-400 m-1'">{{
              t('Documents de pagament SEPA') }}</label> -->
                <div v-if="!sepaDocuments" class="flex items-center">
                  <!-- <Icon name="fa6-solid:circle-xmark" class="text-xl text-600" /> -->
                  <button @click="openInputSepa()" name="" class="button-default-xs">
                    <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
                    {{ t('common.add') }} {{ t('common.sepa') }}
                  </button>
                </div>
                <div v-else>
                  <button
                    class="item__bank border bg-gray-100 hover:bg-yellow-100 border-gray-200 w-full p-2 block text-left mb-2"
                    @click="openInputSepa">
                    <label class="inline-block" :class="'text-black-400 m-1'">{{
                      t('contract_block.document_sepa') }}</label>
                  </button>
                </div>

              </fieldset>

            </div>

          </div>

          <div>
            <div class="flex items-center mt-9 ml-2 text-slate-500">
              <input v-model="is_electronic_invoice" type="checkbox" id="is_electronic_invoice"
                name="is_electronic_invoice" class="checkbox" />
              <label for="is_electronic_invoice" class="ml-2"> {{ t('common.electronic_invoice') }}</label>
            </div>

            <div class="select_bank mt-3 max-w-xl" v-if="is_electronic_invoice">
              <div class="bg-green-50 border border-slate-200 rounded-lg p-4 relative group mb-2">
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-1">
                    <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                      {{ $t('billing_block.accounting_office') }}
                    </label>
                    <input type="text" v-model="accounting_office"
                      class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                      @change="onChangeElectronicInvoice" :placeholder="$t('billing_block.accounting_office')" />
                  </div>
                  <div class="space-y-1">
                    <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                      {{ $t('billing_block.managing_body') }}
                    </label>
                    <input type="text" v-model="managing_body"
                      class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                      @change="onChangeElectronicInvoice" :placeholder="$t('billing_block.managing_body')" />
                  </div>
                  <div class="space-y-1">
                    <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                      {{ $t('billing_block.processing_unit') }}
                    </label>
                    <input type="text" v-model="processing_unit"
                      class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                      @change="onChangeElectronicInvoice" :placeholder="$t('billing_block.processing_unit')" />
                  </div>
                  <!-- <div class="space-y-1">
                    <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                      {{ $t('billing_block.command') }}
                    </label>
                    <input type="text" v-model="command"
                      class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                      @change="onChangeElectronicInvoice" :placeholder="$t('billing_block.command')" />
                  </div>
                  <div class="space-y-1 col-span-2">
                    <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                      {{ $t('billing_block.record') }}
                    </label>
                    <input type="text" v-model="record"
                      class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                      @change="onChangeElectronicInvoice" :placeholder="$t('billing_block.record')" />
                  </div> -->
                </div>
              </div>
            </div>
          </div>

        </div>


        <div v-if="availableDocumentTypes.length > 0" class="mb-4 max-w-xl mt-2 border-t pt-2">
          <div class="flex">
            <label for="documents" class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.documentation') }}
            </label>
          </div>

          <div class="flex flex-wrap gap-2 mb-3">
            <button v-for="docType in availableDocumentTypes" :key="docType.id" type="button"
              @click="toggleDocumentType(docType)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border transition-all" :class="isDocumentTypeSelected(docType)
                ? 'bg-sky-100 border-sky-400 text-sky-800 font-medium'
                : 'bg-white border-slate-300 text-slate-600 hover:bg-slate-50'">
              <Icon :name="isDocumentTypeSelected(docType) ? 'fa6-solid:circle-check' : 'fa6-solid:file-circle-plus'"
                :class="isDocumentTypeSelected(docType) ? 'text-emerald-600' : 'text-slate-400'" />
              {{ docType.list_name || docType.name }}
            </button>
          </div>

          <div v-for="doc in selectedDocumentTypes" :key="doc.id" class="flex gap-2 items-start">
            <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded">
              <div class="flex flex-col items-center gap-y-1">
                <div class="w-full flex items-start gap-x-2">
                  <div class="pt-1">
                    <legend class="px-3 font-semibold bg-white shadow">{{ doc.list_name || doc.name }}</legend>
                  </div>
                  <div class="flex-1">
                    <label :for="'doc_type_' + doc.id" class="block text-xs font-medium text-slate-600 mb-1.5">
                      {{ $t('common.doc_type') }}
                      <span v-if="isDocTypeRequired(doc)" class="text-red-500">*</span>
                    </label>
                    <select v-model="doc.selected_doc_type" :id="'doc_type_' + doc.id"
                      @change="handleDocTypeChange(doc)"
                      class="w-full px-3 py-2.5 text-sm border rounded-lg bg-white shadow-sm transition-all"
                      :class="isDocTypeRequired(doc) && !doc.selected_doc_type ? 'border-red-400' : 'border-slate-300'">
                      <option value="">{{ $t('common.select') }}...</option>
                      <option v-for="innerDocType in doc_types" :value="innerDocType.id" :key="innerDocType.id">
                        {{ innerDocType.list_name || innerDocType.name }}
                      </option>
                    </select>
                    <p v-if="isDocTypeRequired(doc) && !doc.selected_doc_type" class="mt-1 text-xs text-red-600">
                      {{ $t('warning_block.doc_type_required_if_file') }}
                    </p>
                  </div>
                </div>
                <AtomsInputFile @update="handleDocumentUpdate($event, doc)"
                  @delete="handleDocumentDelete(doc.document, doc)" :name="'contractFile'" :uploaded="doc.document.file"
                  :fullWidth="true" class="w-full" />
              </div>
            </fieldset>
          </div>
        </div>

      </div>
      <hr class="max-w-xl">
      <div class="flex flex-row-reverse mt-4 max-w-xl">
        <button @click="save" :disabled="newHolder == null" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}
        </button>
        <!-- <button v-if="person != null" @click="deletePerson" :disabled="saving" class="button-delete mr-5">
          <font-awesome icon="trash" />&nbsp; {{ $t('Eliminar') }}</button> -->
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <InputSepa v-if="showRegionComponent === 'addSepa'" :item="usedPayment" :sepa="sepaDocuments || null"
          :request="contract" @new-item="onSepaSaved" :value="'contract'" />
        <PersonSearch v-if="editingPerson" @saved="fetchPerson"
          :personLabel="personFormTarget === 'tenant' ? 'contract_block.tenant' : 'common.requester'"
          :isExistingLabel="personFormTarget === 'tenant' ? 'contract_block.is_existing_tenant' : 'contract_block.is_existing_applicant'" />
        <PersonBankSelect v-if="showRegionComponent === 'PersonBankSelect'"
          :title="`${$t('common.select')} ${$t('common.iban')}`" :persons="[newHolderBankSelect]"
          @selected-item="onPersonBankSelected" />
      </div>
    </div>
  </div>
</template>