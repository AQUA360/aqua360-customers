<script setup>
// components/organisms/ClusterDetail.vue
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import PersonBankSelect from '~/components/molecules/PersonBankSelect.vue';
import InputSepa from '~/components/atoms/InputSepa.vue';
import InputDate from '~/components/atoms/InputDate.vue';

import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import {
  resolveId,
  toSortedPhoneIds,
} from '~/utils/contractDataChangeDisplay';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const route = useRoute()
const router = useRouter()
const { $ContractApiService, $ConfiglistApiService, $GeneralPaymentApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);

const emit = defineEmits(['change', 'show-subregion']);

const id = ref(route.params.id)
const contract = ref(null)
const selectedPerson = ref(null)
const newHolder = ref(null)

const showRegionComponent = ref('');
const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPerson = ref(false);

const payment = ref({});

const selectedBillingAddress = ref(null);
const selectedContactAddress = ref(null);
const selectedPaymentMethod = ref(null);
const selectedBankDebit = ref(null);
const selectedCommType = ref(null);
const selectedDigitalPersonContact = ref(null);
const selectedPhones = ref([]);
const selectedSMSPhones = ref([]);
const previousSelectedPaymentType = ref(null)
const electronicInvoiceData = ref(null)
const remittance_date = ref(null)
const paymentToUpdate = ref(null);
const mandateId = ref(null);
const mandateIdOverwrite = ref(false);
const sepaDocuments = ref(null);
const usedPayment = ref(null);
const previousPaymentIBAN = ref(null);
const previousPaymentIBANValue = ref(null);
const previousTotalPersons = ref(null);
const paymentSnapshotAtLoad = ref(null);

// Representatives
const selectedRepresentatives = ref([]); // Array de { person: Object, type: Object|null }
const representativeTypes = ref([]);
const editingRepresentative = ref(false);
const addressPaymentRef = ref(null);
const isSaving = ref(false);
const initialRepresentativesSnapshot = ref(null);
const allowContractDateEdit = ref(false);
const registrationDate = ref('');
const previousRegistrationDate = ref('');
const config = useRuntimeConfig();
const language = ref(config.public.defaultLocale);
const previousLanguage = ref(language.value);

const toInputDate = (value) => {
  if (!value) return '';
  if (typeof value === 'string') return value.slice(0, 10);
  return value;
};

const isConfigFlagEnabled = (value) => value === true || value === 'True' || value === 'true';

const snapshotRepresentatives = (reps) =>
  JSON.stringify(
    (reps || []).map((rep) => ({
      person: rep.person?.id ?? rep.person,
      type: rep.type?.id ?? rep.type ?? null,
    })),
  );

const representativesChanged = () => {
  if (!initialRepresentativesSnapshot.value) return true;
  return snapshotRepresentatives(selectedRepresentatives.value)
    !== initialRepresentativesSnapshot.value;
};

/** Telèfons seleccionats al formulari fill (evita desincronització pare/fill). */
const getPhoneStateForSave = () => {
  const fromChild = addressPaymentRef.value?.getContactsState?.();
  if (fromChild) return fromChild;
  return {
    phoneIds: toSortedPhoneIds(selectedPhones.value),
    phones: [...(selectedPhones.value || [])],
    smsPhoneIds: toSortedPhoneIds(selectedSMSPhones.value),
    smsPhones: [...(selectedSMSPhones.value || [])],
  };
};

const syncPhonesSnapshotFromContract = () => {
  const contacts = contract.value?.contacts || [];
  selectedPhones.value = contacts.map((c) => c.id);
  selectedSMSPhones.value = (contract.value?.person_contact_sms || []).map((c) => c.id ?? c);
};

const emitChange = () => {
  if (!payment.value) payment.value = {};
  payment.value['person_bank'] = selectedBankDebit.value?.id || null;
  payment.value['type'] = selectedPaymentMethod.value || null;
  let data = {
    address_billing: selectedBillingAddress.value,
    payment: payment.value,
    sepa_document: sepaDocuments.value,
    bank_debit: selectedBankDebit.value?.id || null,
  };

  emit('change', data);
};

const snapshotPaymentState = () => ({
  type_id: selectedPaymentMethod.value ?? null,
  iban_id: resolveId(selectedBankDebit.value),
  accounting_office: electronicInvoiceData.value?.accounting_office ?? null,
  managing_body: electronicInvoiceData.value?.managing_body ?? null,
  processing_unit: electronicInvoiceData.value?.processing_unit ?? null,
});

const applyPaymentState = (paymentData) => {
  payment.value = paymentData || {};
  usedPayment.value = paymentData;
  sepaDocuments.value = paymentData?.sepa_document || null;
  previousPaymentIBAN.value = paymentData?.IBAN?.id ?? resolveId(paymentData?.IBAN);
  previousPaymentIBANValue.value = paymentData?.IBAN?.iban || null;
  previousSelectedPaymentType.value = paymentData?.type?.id ?? null;
  selectedPaymentMethod.value = paymentData?.type?.id ?? null;
  selectedBankDebit.value = paymentData?.IBAN ?? null;
  electronicInvoiceData.value = paymentData;
  paymentSnapshotAtLoad.value = snapshotPaymentState();
};

const contractPaymentIsComplete = (paymentData) =>
  paymentData?.id != null && paymentData?.type?.id != null;

const getData = async function () {
  const response = await $ContractApiService.getDataChangeDetail(id.value);
  contract.value = response;
  previousTotalPersons.value = contract.value.total_persons ?? null;
  syncPhonesSnapshotFromContract();
  selectedPerson.value = contract.value.holder;

  if (contract.value.representatives && Array.isArray(contract.value.representatives)) {
    selectedRepresentatives.value = contract.value.representatives.map((rep) => {
      const matchedType = representativeTypes.value.find(t => t.id === rep.type?.id) || rep.type || null;
      return {
        person: rep.person,
        type: matchedType,
      };
    });
  }
  initialRepresentativesSnapshot.value = snapshotRepresentatives(selectedRepresentatives.value);
  paymentToUpdate.value = null;

  if (contractPaymentIsComplete(contract.value.payment)) {
    applyPaymentState(contract.value.payment);
  } else if (contract.value?.payment?.id) {
    // Hi ha GeneralPayment però sense type (o incomplet): carregar detall
    await getContractPayment();
  } else {
    // Sense mètode de pagament: snapshot buit per detectar la primera assignació
    applyPaymentState(null);
  }

  registrationDate.value = toInputDate(contract.value.registration_date || contract.value.created_at);
  previousRegistrationDate.value = registrationDate.value;

  language.value = contract.value.language || config.public.defaultLocale;
  previousLanguage.value = language.value;

};

const getContractPayment = async () => {
  try {
    if (!contract.value?.payment?.id) {
      applyPaymentState(null);
      return;
    }
    const response = await $GeneralPaymentApiService.getDetail(contract.value.payment.id);
    applyPaymentState(response);
  } catch (error) {
    console.error(error);
    applyPaymentState(contract.value.payment || null);
  }
};

const paymentNeedsSave = () => {
  if (paymentToUpdate.value) return true;
  if (!paymentSnapshotAtLoad.value) return true;
  return JSON.stringify(snapshotPaymentState()) !== JSON.stringify(paymentSnapshotAtLoad.value);
};


const onPersonBankSelected = (bank) => {
  selectedBankDebit.value = bank;
  sepaDocuments.value = usedPayment.value?.sepa_document || null;
  emitChange();
  closeAllRegions();
};


const onSepaSaved = (item) => {
  sepaDocuments.value = item
  usedPayment.value.sepa_document = sepaDocuments.value;

  emitChange();
  closeAllRegions();
}

const goBackAfterSave = () => {
  if (import.meta.client && window.history.length > 1) {
    router.back();
    return;
  }
  return navigateTo({
    path: '/contract/contracts/',
    query: { id: contract.value.id },
  });
};

/** Contacte digital usable: té id i email no buit. */
const digitalContactHasEmail = (contact) => {
  if (!resolveId(contact)) return false;
  if (typeof contact !== 'object' || contact == null) return true;
  const email = contact.email ?? '';
  return String(email).trim() !== '';
};

/** Persones a l'habitatge: mínim 1 (0 o negatiu peta la facturació). */
const isTotalPersonsValid = computed(() => {
  const value = Number(contract.value?.total_persons);
  return Number.isInteger(value) && value >= 1;
});

const save = async () => {
  if (isSaving.value) return;
  // Persones a l'habitatge: 0 o negatiu trenca la facturació (divisió per zero)
  const totalPersonsValue = Number(contract.value?.total_persons);
  if (!Number.isInteger(totalPersonsValue) || totalPersonsValue < 1) {
    toast.error(t('contract_block.total_persons_min'));
    return;
  }
  isSaving.value = true;
  try {
    const phoneStateAtSave = getPhoneStateForSave();
    // Valors al carregar el formulari: applyPaymentState() no ha de sobreescriure'ls abans del log
    const paymentTypeIdAtLoad = previousSelectedPaymentType.value;
    const paymentIbanIdAtLoad = previousPaymentIBAN.value;

    // Digital/BOTH sense email → paper (no es pot comunicar digitalment sense mail)
    if (
      (selectedCommType.value === 'DIGITAL' || selectedCommType.value === 'BOTH')
      && !digitalContactHasEmail(selectedDigitalPersonContact.value)
    ) {
      selectedCommType.value = 'PAPER';
      selectedDigitalPersonContact.value = null;
    }

    const payment_options = {
      id: contract.value.payment?.id ?? null,
      iban_id: selectedBankDebit.value?.id ?? null,
      type_id: selectedPaymentMethod.value,
      accounting_office: electronicInvoiceData.value?.accounting_office,
      managing_body: electronicInvoiceData.value?.managing_body,
      processing_unit: electronicInvoiceData.value?.processing_unit,
      mandate_token: contract.value.token,
    };

    const selectedEmailId = resolveId(selectedDigitalPersonContact.value);
    const previousEmailId = resolveId(contract.value?.person_contact_email);
    const phoneIds = phoneStateAtSave.phoneIds;
    const smsPhoneIds = phoneStateAtSave.smsPhoneIds;
    const initialPhoneIds = toSortedPhoneIds((contract.value?.contacts || []).map((c) => c.id));
    const initialSmsPhoneIds = toSortedPhoneIds(
      (contract.value?.person_contact_sms || []).map((c) => c.id ?? c),
    );

    const hadNoPayment = contract.value?.payment?.id == null;
    const paymentTypeChanged = paymentTypeIdAtLoad != payment_options?.type_id;
    const paymentIbanChanged = paymentIbanIdAtLoad != resolveId(selectedBankDebit.value);
    const billingAddressChanged = selectedBillingAddress.value != contract.value?.address_billing?.id;
    const contactAddressChanged = selectedContactAddress.value != contract.value?.address_contact?.id;
    const communicationTypeChanged = selectedCommType.value != contract.value?.communication_type;
    const emailChanged = selectedEmailId != previousEmailId;
    const totalPersonsChanged = contract.value.total_persons != previousTotalPersons.value;
    const languageChanged = language.value != previousLanguage.value;
    const phonesChanged = JSON.stringify(phoneIds) !== JSON.stringify(initialPhoneIds);
    const smsPhonesChanged = JSON.stringify(smsPhoneIds) !== JSON.stringify(initialSmsPhoneIds);
    const remittanceChanged = remittance_date.value != contract.value?.remittance_date;
    const mandateChanged = mandateId.value != contract.value?.mandate_id;
    const registrationChanged = allowContractDateEdit.value
      && registrationDate.value !== previousRegistrationDate.value;
    const repsChanged = representativesChanged();
    const needsPaymentSave = !!paymentToUpdate.value || paymentNeedsSave();
    // Cal vincular el GeneralPayment al contracte si abans no n'hi havia o ha canviat tipus/IBAN.
    // També sempre que es desi el payment: el backend fa copy-on-write si la fila
    // està compartida amb altres contractes i retorna una fila nova a vincular.
    const needsPaymentLink = hadNoPayment || paymentTypeChanged || paymentIbanChanged
      || needsPaymentSave;

    const hasDataChange = paymentTypeChanged || paymentIbanChanged || billingAddressChanged
      || contactAddressChanged || communicationTypeChanged || emailChanged || totalPersonsChanged
      || languageChanged;

    const needsContractSave = billingAddressChanged || contactAddressChanged
      || communicationTypeChanged || emailChanged || totalPersonsChanged
      || phonesChanged || smsPhonesChanged || remittanceChanged || mandateChanged
      || registrationChanged || repsChanged || needsPaymentLink;

    // Sense cap canvi real: no tocar BD
    if (!hasDataChange && !needsPaymentSave && !needsContractSave) {
      return goBackAfterSave();
    }

    let response_payment = contract.value.payment;

    // Un sol save de payment: si ve de paymentToUpdate (fill), usar-lo; si no, payment_options
    if (needsPaymentSave) {
      let paymentPayload;
      if (paymentToUpdate.value) {
        paymentToUpdate.value.mandate_token = contract.value.token;
        paymentToUpdate.value.mandate_id = mandateId.value;
        if (mandateIdOverwrite.value) paymentToUpdate.value.mandate_overwrite = mandateId.value;
        // Assegurar type_id / iban_id perquè el backend els resolgui bé en create/update
        paymentToUpdate.value.type_id = selectedPaymentMethod.value ?? paymentToUpdate.value.type_id ?? null;
        paymentToUpdate.value.iban_id = selectedBankDebit.value?.id
          ?? paymentToUpdate.value.iban_id
          ?? null;
        if (!paymentToUpdate.value.id && contract.value.payment?.id) {
          paymentToUpdate.value.id = contract.value.payment.id;
        }
        paymentPayload = paymentToUpdate.value;
        paymentToUpdate.value = null;
      } else {
        payment_options.mandate_token = contract.value.token;
        if (mandateIdOverwrite.value) payment_options.mandate_overwrite = mandateId.value;
        paymentPayload = payment_options;
      }

      const savedPayment = await $GeneralPaymentApiService.save(paymentPayload);
      if (contractPaymentIsComplete(savedPayment)) {
        response_payment = savedPayment;
        usedPayment.value = savedPayment;
        sepaDocuments.value = savedPayment?.sepa_document ?? null;
      } else if (savedPayment?.id) {
        const detail = await $GeneralPaymentApiService.getDetail(savedPayment.id);
        response_payment = detail;
        usedPayment.value = detail;
        sepaDocuments.value = detail?.sepa_document ?? null;
      } else {
        response_payment = savedPayment;
      }
      if (response_payment) {
        contract.value.payment = response_payment;
      }
    }

    if (hasDataChange) {
      const changeData = {
        token: _.random(1000, 9999),
        contract: contract.value.id,
        requested_at: new Date().toISOString(),
        approved_at: new Date().toISOString(),
      };
      if (paymentTypeChanged) {
        changeData.new_payment_type = selectedPaymentMethod.value || null;
        changeData.previous_payment_type = paymentTypeIdAtLoad ?? null;
      }
      if (paymentIbanChanged) {
        changeData.previous_payment = paymentIbanIdAtLoad ?? null;
        changeData.new_payment = resolveId(selectedBankDebit.value);
      }
      if (billingAddressChanged) {
        changeData.new_address_billing = selectedBillingAddress.value;
        changeData.previous_address_billing = contract.value?.address_billing?.id || null;
      }
      if (contactAddressChanged) {
        changeData.new_address_contact = selectedContactAddress.value;
        changeData.previous_address_contact = contract.value?.address_contact?.id || null;
      }
      if (communicationTypeChanged) {
        changeData.new_communication_type = selectedCommType.value;
        changeData.previous_communication_type = contract.value?.communication_type || null;
      }
      if (emailChanged) {
        changeData.new_person_contact_email = selectedEmailId;
        changeData.previous_person_contact_email = previousEmailId;
      }
      if (totalPersonsChanged) {
        changeData.new_total_persons = contract.value.total_persons;
        changeData.previous_total_persons = previousTotalPersons.value;
      }
      if (languageChanged) {
        changeData.new_language = language.value || null;
        changeData.previous_language = previousLanguage.value || null;
      }
      await $ContractApiService.changeData(changeData);
    }

    if (needsContractSave) {
      const address_options = {
        id: contract.value.id,
      };
      // Només enviar camps que han canviat (evita side-effects al backend)
      if (phonesChanged) {
        address_options.phone_ids = phoneIds;
      }
      if (smsPhonesChanged) {
        address_options.sms_phone_ids = smsPhoneIds;
      }
      // Comunicació: només si ha canviat (o correcció digital sense mail → paper)
      if (communicationTypeChanged) {
        address_options.communication_type = selectedCommType.value;
      }
      // Mail només si DIGITAL/BOTH (sempre, perquè el backend no el buidi i passi a PAPER).
      // Si és PAPER, no s'envia: tenir mail no ha de convertir la comunicació a digital.
      if (selectedCommType.value === 'DIGITAL' || selectedCommType.value === 'BOTH') {
        address_options.person_contact_email_id = selectedEmailId;
      }
      if (billingAddressChanged) {
        address_options.address_billing_id = selectedBillingAddress.value;
      }
      if (contactAddressChanged) {
        address_options.address_contact_id = selectedContactAddress.value;
      }
      if (totalPersonsChanged) {
        address_options.total_persons = contract.value.total_persons;
      }
      if (remittanceChanged) {
        address_options.remittance_date = remittance_date.value;
      }
      if (mandateChanged) {
        address_options.mandate_id = mandateId.value;
        address_options.mandate_id_overwrite = mandateIdOverwrite.value;
      }
      if (registrationChanged) {
        address_options.registration_date = registrationDate.value || null;
      }
      if (repsChanged) {
        address_options.representatives_save = selectedRepresentatives.value.map((rep) => ({
          person: rep.person.id,
          type: rep.type ? rep.type.id : null,
        }));
      }

      if (needsPaymentLink) {
        address_options.payment_id = response_payment?.id
          ?? usedPayment.value?.id
          ?? contract.value.payment?.id
          ?? null;
      }

      await $ContractApiService.save(address_options, { dataChangeEdit: true });
    }

    return goBackAfterSave();
  }
  catch (error) {
    console.log(error)
  } finally {
    isSaving.value = false;
  }
}


const onChange = async (data) => {
  // Només SEPA inline (person_bank sol és per selecció d'IBAN, no cal save intermedi)
  /* if (data.sepa_document != null || data.payment?.sepa_document != null) {
  } */
  
  paymentToUpdate.value = data.payment;
  //previousPaymentType.value = selectedBankDebit.value
  selectedCommType.value = data.communication_type;
  selectedDigitalPersonContact.value = data.person_contact_email;
  selectedPhones.value = Array.isArray(data.contacts)
    ? data.contacts.map((c) => resolveId(c)).filter((id) => id != null)
    : [];
  selectedSMSPhones.value = Array.isArray(data.sms_phones)
    ? data.sms_phones.map((c) => resolveId(c)).filter((id) => id != null)
    : [];
  selectedBillingAddress.value = data.address_billing;
  selectedContactAddress.value = data.address_contact;
  selectedPaymentMethod.value = data.payment_type ?? null;
  electronicInvoiceData.value = data.payment;
  selectedBankDebit.value = data.payment.IBAN ?? null;
  remittance_date.value = data.remittance_date;
  mandateId.value = data.mandate_id ?? null;
  mandateIdOverwrite.value = data.mandate_id != paymentToUpdate.value?.mandate_id;
}

const closeAllRegions = () => {
  // tanquem tots els components
  editingPerson.value = false;
  editingRepresentative.value = false;
  showRegionComponent.value = '';
  // tanquem region
  showRegion.value = false;
};

// Funció per obrir el formulari de representant
const openRepresentativeForm = async () => {
  if (!representativeTypes.value.length) {
    await fetchRepresentativeType();
  }
  closeAllRegions();
  editingRepresentative.value = true;
  showRegion.value = true;
};

// Funció per obtenir els tipus de representant
const fetchRepresentativeType = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-representative-type');
    representativeTypes.value = data.results;
  } catch (error) {
    console.error('Error fetching representative types:', error);
  }
};

// Funció per gestionar la salvaguarda d'un representant
const onRepresentativeSaved = async (item) => {
  const defaultType = representativeTypes.value.find(type => type.is_default) || null;
  selectedRepresentatives.value.push({
    person: item,
    type: defaultType
  });
  closeAllRegions();
};

// Funció per eliminar un representant
const removeRepresentative = (index) => {
  selectedRepresentatives.value.splice(index, 1);
};

const fetchPerson = async (item) => {
  newHolder.value = item;
  closeAllRegions();
};


onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  await fetchRepresentativeType();
  const allowEdit = await $ConfigProjectApiService.get('allow_contract_date_edit');
  console.log(allowEdit);
  allowContractDateEdit.value = isConfigFlagEnabled(allowEdit);
  await getData();
});

</script>

<template>
  <div
    v-if="objectPermissions == null || (objectPermissions?.can_change && contract == null)" class="text-base p-4 max-w-full flex justify-center">
    <AppLoading :text="$t('common.loading')" />
  </div>
  <div v-else-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
      <div class="flex justify-between items-center mb-6">
        <H1>{{ $t(`common.modify`) }} {{ $t(`contract_block.contract_data`) }} {{ contract.token }}</H1>
      </div>
      <div class="border-gray-300 mb-2">
        <div class="grid grid-cols-2 gap-2">
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
          
          <div v-if="contract.tenant" class="mb-4">
            <label for="person" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
              <Icon name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
              <span>{{ $t('contract_block.current_tenant') }}:</span>
            </label>
  
            <div class="bg-green-100 p-4 rounded relative max-w-xl group">
              <p class="font-semibold">{{ contract.tenant.name }} {{ contract.tenant.surname }}<br />
                <span class="text-sm text-gray-500">{{ contract.tenant.token }}</span>
              </p>
            </div>
          </div>
        </div>

        <div class="max-w-xl mb-5">
          <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon name="fa6-solid:circle-check" class="text-xl"
              :class="isTotalPersonsValid ? 'text-emerald-600' : 'text-red-600'" />
            <span :class="{ 'text-red-600': !isTotalPersonsValid }">{{ $t('contract_block.total_persons') }}:</span>
          </label>
          <input type="number" min="1" step="1" v-model="contract.total_persons" class="input"
            :class="{ 'invalid': !isTotalPersonsValid, 'ring-1': !isTotalPersonsValid, 'ring-red-600': !isTotalPersonsValid }" />
          <div v-if="!isTotalPersonsValid"
            class="mt-2 flex items-start gap-2 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5 shrink-0 text-base" />
            <span>{{ $t('contract_block.total_persons_min') }}</span>
          </div>
        </div>

        <div v-if="allowContractDateEdit" class="max-w-xl mb-5">
          <InputDate v-model="registrationDate" :label="t('common.registration_date')" />
        </div>

        <div class="max-w-xl mb-5 w-[200px]">
          <label class="block text-sm font-medium text-gray-700 mb-3">{{ t('common.language') }}</label>
          <select v-model="language" class="input">
            <option v-for="lang in AVAILABLE_LANGUAGES" :key="lang.code" :value="lang.code">
              {{ t(lang.name) }}
            </option>
          </select>
        </div>
        
        <MoleculesContractRequestAddressPayment
          ref="addressPaymentRef"
          :request="contract"
          :usedPayment="usedPayment"
          :auto-assign-supply-address="false"
          @change="onChange"
          @refresh="getData"
          :sepaValue="'contract'"
        />

        <span class="flex gap-3 mb-4">
          <label class="text-slate-800 text-base flex items-center gap-1">
            <input type="checkbox" v-model="contract.simplified_invoice" :value="contract.simplified_invoice"/> {{ t('billing_block.simplified_invoice') }}
          </label>
        </span>

        <!-- Representatives Section -->
        <div class="mb-4 max-w-xl">
          <div class="text-sm font-medium text-gray-700 mb-3">
            <label class="block mb-1">{{ $t('contract_block.representatives') }}:</label>
            <button @click="openRepresentativeForm"
              class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600" :title="`${t('common.add')} ${t('contract_block.representative')}`">
              + {{ $t('common.add') }} {{ $t('contract_block.representative') }}
            </button>
          </div>

          <!-- Llista de representants -->
          <div v-if="selectedRepresentatives.length > 0" class="space-y-4">
            <div v-for="(rep, index) in selectedRepresentatives" :key="index"
              class="bg-yellow-100 p-4 rounded relative max-w-xl group">
              <p class="font-semibold flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
                <span>{{ rep.person.name }} {{ rep.person.surname }}</span>
                <span class="text-sm text-gray-500 mr-10">{{ rep.person.token }}</span>
              </p>
              <div class="mt-2">
                <label class="text-sm font-medium text-gray-700">{{ $t('contract_block.representative_type') }}:</label>
                <select v-model="rep.type"
                  class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-sky-500 focus:border-sky-500 sm:text-sm rounded-md">
                  <option value="" disabled :selected="!rep.type">-- {{ $t('common.select') }} {{ $t('common.type') }} --</option>
                  <option v-for="type in representativeTypes" :key="type.id" :value="type" :selected="type.is_default">
                    {{ type.name }}
                  </option>
                </select>
              </div>
              <button @click="removeRepresentative(index)"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-red-600 opacity-0 transition-all duration-300 group-hover:opacity-100"
                aria-label="Eliminar Persona">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
          </div>
          <!-- /end Llista de representants -->
        </div>
        <!-- /end Representatives Section -->
      </div>
      <hr class="max-w-xl">
      <div class="flex flex-row-reverse mt-4 max-w-xl">
        <button @click="save" :disabled="selectedPerson == null || isSaving || !isTotalPersonsValid"
          class="button-primary">
          <Icon v-if="isSaving" name="fa6-solid:spinner" class="animate-spin" />
          <Icon v-else name="fa6-solid:floppy-disk" />
          &nbsp; {{ isSaving ? $t('common.saving') : $t('common.save') }}
        </button>
        
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
          :request="contract.id" @new-item="onSepaSaved" :value="'contract'" />
        <PersonSearch v-if="editingPerson" @saved="fetchPerson" />
        <PersonSearch v-if="editingRepresentative" @saved="onRepresentativeSaved" 
          :title="`${t('common.select')} ${t('common.or')} ${t('common.add')} ${t('contract_block.representative')}`" />
        <PersonBankSelect v-if="showRegionComponent === 'PersonBankSelect'" :title="`${$t('common.select')} ${$t('common.iban')}`"
          :persons="[selectedPerson]" @selected-item="onPersonBankSelected" />
      </div>
    </div>
  </div>
</template>