<script setup>
// components/molecules/ContractRequestAddressPayment.vue
import { ref, onMounted, watch, computed, nextTick } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import AddAddress from '~/components/molecules/AddAddress.vue';
import PersonBankSelect from '~/components/molecules/PersonBankSelect.vue';
import PersonContactSelect from '~/components/molecules/PersonContactSelect.vue';
import PersonAddressSelect from '~/components/molecules/PersonAddressSelect.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';

import BankDetail from '~/components/molecules/BankDetail.vue';
import SepaQuickActions from '~/components/molecules/SepaQuickActions.vue';
import SendSepaEmailModal from '~/components/molecules/SendSepaEmailModal.vue';
import InputSepa from '~/components/atoms/InputSepa.vue';
import PersonContactDetail from '~/components/molecules/PersonContactDetail.vue';
import { resolveId, toSortedPhoneIds } from '~/utils/contractDataChangeDisplay';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';


const { $SupplyPointApiService, $PersonApiService, $PersonAddressApiService, $PersonBankApiService, $ContractApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  request: {
    type: Object,
    required: false
  },
  usedPayment: {  //Fet servir des del refactor de sepa a un nivell mes baix. Guardar payment directament a request per cridat watch aqui genera problemes i això és més una solució més simple de moment.
    type: Object,
    required: false
  },
  sepaValue: {
    type: String,
    default: 'request'
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  /** Si false, no crea adreça des del punt de subministrament (p. ex. edició de contracte). */
  autoAssignSupplyAddress: {
    type: Boolean,
    default: true,
  },
  /**
   * Persona (objecte o id) que era llogater/titular abans del canvi actual.
   * Quan s'informa, en carregar les dades es netegen del formulari (IBAN, mandat,
   * adreces, contacte digital, telèfons) tots els valors que pertanyin EXCLUSIVAMENT
   * a aquesta persona, ja que deixen de ser vàlids un cop hi ha un nou llogater/titular.
   * Les dades d'altres persones vinculades al contracte (titular, nou llogater,
   * representants) no es toquen.
   */
  previousTenant: {
    type: Object,
    default: null
  },
});

const emit = defineEmits(['change', 'show-subregion', 'refresh']);

const showRegionComponent = ref('');
const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const initializing = ref(true);

// Objecte per gestionar l'estat de cada rol de persona
const addressOptions = ref({});
const addressOptionsById = ref([]);
const addressOptionsAreEmpty = ref(true);
const paymentTypeOptionsById = ref([]);
const bankDebitOptions = ref([]);
const payment = ref({});
const supplyAddress = ref(null)

const is_electronic_invoice = ref(false);
const dir3 = ref(null)
const accounting_office = ref(null)
const managing_body = ref(null)
const processing_unit = ref(null)
const command = ref(null)
const record = ref(null)

const sepaDocuments = ref(null);
const generatingSepaDocument = ref(false);
const savingDefaultBank = ref(false);

const selectedBillingAddress = ref(null);
const selectedContactAddress = ref(null);

const selectedPaymentMethod = ref(null);
const selectedBankDebit = ref(null);
const selectedRemittanceDate = ref(null);
const mandateId = ref(null);

const holder = ref(null);
const owner = ref(null);
const tenant = ref(null);

const representatives = ref([]);

// Persona que ha deixat de ser llogater/titular (ve del pare via prop `previousTenant`).
// Només s'usa per detectar i netejar dades que li pertanyien exclusivament.
const previousTenant = ref(null);

const localPayment = ref(null);

const controlledAddressNull = ref(false);

const selectedBankDebitPerson = computed(() => {
  if (!selectedBankDebit.value) return holder.value;
  const bankId = selectedBankDebit.value.id || selectedBankDebit.value;
  const persons = [holder.value, owner.value, tenant.value, ...representatives.value];
  const found = persons.find(p => p && p.banks && p.banks.some(b => b.id === bankId));
  return found || holder.value;
});

// Variables per la comunicació
const selectedCommType = ref(null);
const selectedDigitalPersonContact = ref(null);

// Variables per la selecció de telèfons
const selectedPhones = ref([]); // Llista de telèfons seleccionats
const selectedSMSPhones = ref([]); // Llista de telèfons SMS seleccionats

const personContactSelectRef = ref(null);

// Funció per tancar totes les regions
const closeAllRegions = () => {
  // Tanquem tots els formularis
  showRegionComponent.value = '';
  // Tanquem region
  showRegion.value = false;
  personContactSelectRef.value?.close();
};

// Funció per emetre els canvis
const emitChange = () => {
  if (!payment.value) payment.value = {};
  payment.value['person_bank'] = selectedBankDebit.value?.id || null;
  payment.value['IBAN'] = selectedBankDebit?.value || null;
  payment.value['type'] = selectedPaymentMethod.value || null;
  payment.value['dir3'] = dir3.value || null;
  payment.value['accounting_office'] = accounting_office.value || null;
  payment.value['managing_body'] = managing_body.value || null;
  payment.value['processing_unit'] = processing_unit.value || null;
  payment.value['command'] = command.value || null;
  payment.value['record'] = record.value || null;

  let communicationType = selectedCommType.value;
  const personContactEmailId = selectedDigitalPersonContact.value?.id || selectedDigitalPersonContact.value || null;

  if (communicationType === 'DIGITAL' && !personContactEmailId) {
    communicationType = 'PAPER';
  }

  console.log("payment.value");
  console.log(payment.value);
  console.log(mandateId.value);

  let data = {
    address_billing: selectedBillingAddress.value,
    address_contact: selectedContactAddress.value,
    payment: payment.value,
    sepa_document: sepaDocuments.value,
    bank_debit: selectedBankDebit.value?.id || null,
    communication_type: communicationType,
    person_contact_email: personContactEmailId,
    sms_phones: selectedSMSPhones.value.map((phone) => resolveId(phone)).filter((id) => id != null),
    contacts: selectedPhones.value.map((phone) => resolveId(phone)).filter((id) => id != null),
    IBAN: selectedBankDebit.value?.id || null,
    payment_type: selectedPaymentMethod.value || null,
    remittance_date: selectedRemittanceDate.value || null,
    mandate_id: mandateId.value || null,
  };
  emit('change', data);

};

// Funcions per obrir els formularis de cada rol
const openAddBillingAddressForm = (roleKey) => {
  closeAllRegions();
  showRegionComponent.value = 'addBillingAddress';
  showRegion.value = true;
};

const openAddContactAddressForm = (roleKey) => {
  closeAllRegions();
  showRegionComponent.value = 'addContactAddress';
  showRegion.value = true;
};

const openInputSepa = () => {
  closeAllRegions();
  showRegionComponent.value = 'addSepa';
  showRegion.value = true;
};

// Document SEPA (no domiciliat) per enviar per correu
const sendingSepaDocument = ref(false);
const showSendSepaModal = ref(false);
const noSepaDocumentId = ref(null);

const generateDocumentNoSepa = async ({ sendByEmail = false } = {}) => {
  const contractId = props.request?.id ?? props.request?.contract?.id;
  if (!contractId) return;

  const personId = holder.value?.id
    ?? props.request?.holder?.id
    ?? props.request?.holder
    ?? null;

  const bankId = selectedBankDebit.value?.id || selectedBankDebit.value || null;

  // Actualitzem el compte de pagament abans de generar el document, perquè quedi
  // persistit a la sol·licitud amb el mateix compte que s'envia al backend.
  emitChange();

  const loading = sendByEmail ? sendingSepaDocument : generatingSepaDocument;
  try {
    loading.value = true;
    const sepa = await $ContractApiService.generateSepaDocumentNoDirect(
      contractId,
      {
        person_id: personId,
        bank_id: bankId,
        person_bank_id: bankId,
      },
      { is_request: props.sepaValue !== 'contract' },
    );
    if (sendByEmail) {
      noSepaDocumentId.value = sepa?.sepa_document_id ?? null;
      showSendSepaModal.value = !!noSepaDocumentId.value;
      return;
    }
    const fileUrl = sepa?.pdf_url ?? sepa?.url;
    if (fileUrl) {
      await openAuthenticatedFileUrl(fileUrl);
    }
  } catch (error) {
    console.error('Error generating document:', error);
  } finally {
    loading.value = false;
  }
};

// Funcions per afegir adreces


const openPersonBillingAddressSelect = () => {
  closeAllRegions();
  showRegionComponent.value = 'BillingAddressSelect';
  showRegion.value = true;
};

const openPersonContactAddressSelect = () => {
  closeAllRegions();
  showRegionComponent.value = 'ContactAddressSelect';
  showRegion.value = true;
};


const onPersonBillingAddressSelected = async (personAddress) => {
  selectedBillingAddress.value = personAddress.id;

  // opcional però recomanat: refrescar opcions (com ja fas en altres punts)
  await fillAddressOptions();
  emitChange();
  closeAllRegions();
};

const onPersonContactAddressSelected = async (personAddress) => {
  selectedContactAddress.value = personAddress.id;

  await fillAddressOptions();
  emitChange();
  closeAllRegions();
};


const onAddBillingAddressSaved = async (address) => {
  var person_address = {
    person: props.request.holder?.id ? props.request.holder.id : props.request.holder,
    address: address.id,
    is_billing: true,
  }

  var person_address = await $PersonAddressApiService.save(person_address);
  holder.value = await hydratePerson(props.request.holder?.id ? props.request.holder.id : props.request.holder);
  fillAddressOptions(); // actualitzem valors del select
  selectedBillingAddress.value = person_address.id;

  emitChange();
  emit('refresh')
  closeAllRegions();
};

const onAddContactAddressSaved = async (address) => {
  var person_address = {
    person: props.request.holder?.id ? props.request.holder.id : props.request.holder,
    address: address.id,
    is_billing: false, // S'ha de fixar a false per adreça de contacte
  }

  var person_address = await $PersonAddressApiService.save(person_address);
  holder.value = await hydratePerson(props.request.holder?.id ? props.request.holder.id : props.request.holder);
  fillAddressOptions(); // actualitzem valors del select
  selectedContactAddress.value = person_address.id;

  emitChange();
  emit('refresh')
  closeAllRegions();
}

const onSepaSaved = (item) => {

  //selectedBankDebit.value.sepa_document = sepaDocuments.value;
  localPayment.value.sepa_document = item;
  sepaDocuments.value = item;
  let options = {
    sepa_document: sepaDocuments.value.id,
    id: selectedBankDebit.value.id
  }
  //$PersonBankApiService.save(options)
  emitChange();
  closeAllRegions();
}

// Pagament real (GeneralPayment desat) sobre el qual es genera/puja el SEPA des de les accions ràpides.
// Si el compte seleccionat encara no s'ha desat al pagament, no s'ofereixen les accions.
const sepaPayment = computed(() => {
  const candidate = props.usedPayment?.id ? props.usedPayment : (payment.value?.id ? payment.value : null);
  if (!candidate) return null;
  const selectedBankId = selectedBankDebit.value?.id ?? selectedBankDebit.value ?? null;
  const paymentBankId = candidate.IBAN?.id ?? candidate.IBAN ?? null;
  if (selectedBankId && paymentBankId && Number(selectedBankId) !== Number(paymentBankId)) return null;
  return candidate;
});

const onSepaQuickSaved = (item) => {
  sepaDocuments.value = item;
  if (localPayment.value) {
    localPayment.value.sepa_document = item;
  }
  emitChange();
};

// Funció per omplir les adreces des de la persona
const fillAddressFromPerson = (person, roleLabel) => {
  const addresses = [];

  const personName = getPersonDisplayName(person, roleLabel);
  if (!person || !personName) return addresses;

  // Inicialitza array de persona sempre
  if (!addressOptions.value[personName]) {
    addressOptions.value[personName] = [];
  }

  // Si la persona té adreces
  if (Array.isArray(person.addresses) && person.addresses.length > 0) {
    const seen = new Set();

    person.addresses.forEach((pa) => {
      const id = Number(pa.id);
      if (!seen.has(id)) {
        seen.add(id);
        addressOptions.value[personName].push({
          value: id,
          label: pa.address_complete
        });
        addresses.push(id);
      }
    });
  }

  return addresses;
};

// Funció per omplir les opcions d'adreces
const fillAddressOptions = async () => {
  addressOptions.value = {};

  // primer omplim adreces del titular
  var added = fillAddressFromPerson(holder.value, roleLabelFor('holder'));

  // afegim altres adreces de propietari i inquilí que ja haurien de ser hidratats
  if (owner.value) {
    added = added.concat(fillAddressFromPerson(owner.value, roleLabelFor('owner')));
  }
  if (tenant.value) {
    added = added.concat(fillAddressFromPerson(tenant.value, roleLabelFor('tenant')));
  }

  // afegim adreces de representants
  if (representatives.value.length > 0) {
    representatives.value.forEach((rep) => {
      added = added.concat(fillAddressFromPerson(rep, representativeRoleLabel(rep)));
    });
  }

  if (added.length > 0) {
    addressOptionsAreEmpty.value = false;

    // Remove duplicates within each person's address list
    Object.keys(addressOptions.value).forEach(personName => {
      const seen = new Set();
      addressOptions.value[personName] = addressOptions.value[personName].filter(address => {
        // Keep empty value addresses (no address option) and unique addresses
        if (address.value === "" || !seen.has(address.value)) {
          if (address.value !== "") {
            seen.add(address.value);
          }
          return true;
        }
        return false;
      });
    });

    addressOptionsById.value = {};
    Object.values(addressOptions.value).forEach(addressList => {
      addressList.forEach(address => {
        const id = Number(address.value);
        if (!addressOptionsById.value[id]) {
          addressOptionsById.value[id] = address.label;
        }
      });
    });


  }
  else {
    addressOptionsAreEmpty.value = true;
  }

  controlledAddressNull.value = ensureSelectedIsValid();
}


const ensureSelectedIsValid = () => {
  let controlled = false;
  if (selectedBillingAddress.value != null) {
    const exists = !!addressOptionsById.value[selectedBillingAddress.value];
    if (!exists) {
      selectedBillingAddress.value = null;
      controlled = true;
    }
  }

  if (selectedContactAddress.value != null) {
    const exists = !!addressOptionsById.value[selectedContactAddress.value];
    if (!exists) {
      selectedContactAddress.value = null;
      controlled = true;
    }
  }

  return controlled;
};

// --- Neteja de dades de l'antic llogater/titular (previousTenant) ---
//
// Quan hi ha canvi de llogater, els valors ja carregats al formulari (IBAN, mandat,
// adreces, contacte digital, telèfons) poden pertànyer a la persona que ha deixat
// de ser llogater. Aquests valors s'han de buidar i requerir selecció manual.
// Les dades d'altres persones vinculades al contracte (titular, nou llogater,
// representants) NO es toquen -- ni tan sols quan aquesta "altra persona" resulta
// ser la MATEIXA persona que l'antic llogater amb un altre rol (p. ex. algú que
// era llogater i alhora és el titular del contracte, i que continua sent-ho).
// Per això no n'hi ha prou de comprovar la pertinença a previousTenant: cal
// excloure les dades que TAMBÉ pertanyen a qualsevol persona encara vinculada.

/** Retorna el conjunt d'IDs dels elements d'un camp (banks/contacts/addresses) d'una persona. */
const idsOf = (person, field) =>
  new Set((person?.[field] || []).map((item) => Number(resolveId(item))));

/** Unió d'IDs d'un camp entre diverses persones. */
const idsOfAny = (persons, field) => {
  const result = new Set();
  persons.forEach((person) => {
    idsOf(person, field).forEach((id) => result.add(id));
  });
  return result;
};

/** Persones actualment vinculades al contracte (excloent l'antic llogater). */
const currentlyLinkedPersons = computed(() => (
  [holder.value, owner.value, tenant.value, ...representatives.value].filter(Boolean)
));

/**
 * IDs "exclusius" de l'antic llogater per a un camp donat: pertanyen a previousTenant
 * però a NINGÚ de les persones actualment vinculades. Només aquests es netegen.
 */
const exclusiveStaleIds = (field) => {
  const prevIds = idsOf(previousTenant.value, field);
  const currentIds = idsOfAny(currentlyLinkedPersons.value, field);
  return new Set([...prevIds].filter((id) => !currentIds.has(id)));
};

const staleBankIds = computed(() => exclusiveStaleIds('banks'));
const staleContactIds = computed(() => exclusiveStaleIds('contacts'));
const staleAddressIds = computed(() => exclusiveStaleIds('addresses'));

const sanitizeStaleTenantSelections = () => {
  if (!previousTenant.value) return; // només actua quan venim del flux de canvi de llogater/titular

  // IBAN + mandat (el mandat és una dada dependent del compte bancari)
  if (selectedBankDebit.value) {
    const bankId = Number(selectedBankDebit.value?.id ?? selectedBankDebit.value);
    if (staleBankIds.value.has(bankId)) {
      selectedBankDebit.value = null;
      sepaDocuments.value = null;
      localPayment.value = null;
      mandateId.value = null;
    }
  }

  // Adreça fiscal i de contacte
  if (selectedBillingAddress.value != null && staleAddressIds.value.has(Number(selectedBillingAddress.value))) {
    selectedBillingAddress.value = null;
  }
  if (selectedContactAddress.value != null && staleAddressIds.value.has(Number(selectedContactAddress.value))) {
    selectedContactAddress.value = null;
  }

  // Contacte digital (email) de comunicació
  if (selectedDigitalPersonContact.value) {
    const contactId = Number(resolveId(selectedDigitalPersonContact.value));
    if (staleContactIds.value.has(contactId)) {
      selectedDigitalPersonContact.value = null;
    }
  }

  // Telèfons de contacte i SMS
  selectedPhones.value = selectedPhones.value.filter(
    (phone) => !staleContactIds.value.has(Number(resolveId(phone)))
  );
  selectedSMSPhones.value = selectedSMSPhones.value.filter(
    (phone) => !staleContactIds.value.has(Number(resolveId(phone)))
  );
};


const onPaymentTypesLoaded = ({ byId }) => {
  paymentTypeOptionsById.value = byId;
};

const isDirectDebitSelected = computed(() => (
  paymentTypeOptionsById.value[selectedPaymentMethod.value]?.token === 'DIRECT_DEBIT'
));

// Funció per omplir les opcions de debit bancari
const fillBankDebitOptions = async () => {
  const request = props.request;
  if (request.holder && holder.value && holder.value.banks) { // Correcció aquí
    bankDebitOptions.value = holder.value.banks.map(bank => ({
      value: bank.id,
      label: bank.iban
    }));
  }
}

// Funció per obrir la selecció de banc
const openPersonBankSelect = () => {
  closeAllRegions();
  showRegionComponent.value = 'PersonBankSelect';
  showRegion.value = true;
};

// Funció per marcar el compte seleccionat com a forma de pagament per defecte de la persona titular del compte
const saveBankAsDefault = async () => {
  const bankId = selectedBankDebit.value?.id || selectedBankDebit.value;
  if (!bankId || savingDefaultBank.value) return;

  try {
    savingDefaultBank.value = true;
    await $PersonBankApiService.save({ id: bankId, is_default: true });
    selectedBankDebit.value = { ...selectedBankDebit.value, is_default: true };

    // Reflectim el canvi també a la persona titular carregada localment
    const person = selectedBankDebitPerson.value;
    if (person?.banks) {
      person.banks.forEach((b) => {
        b.is_default = b.id === bankId;
      });
    }
  } catch (error) {
    console.error('Error saving default bank:', error);
  } finally {
    savingDefaultBank.value = false;
  }
};

// Funció per manejar la selecció d'un banc
const onPersonBankSelected = (bank) => {
  selectedBankDebit.value = bank;
  if (bank.id == props.usedPayment?.id) {
    sepaDocuments.value = props.usedPayment.sepa_document;
  } else {
    sepaDocuments.value = null;
  }
  // Actualitzem localPayment perquè InputSepa (Generar SEPA) faci servir sempre
  // el nou compte bancari i el seu titular, no el compte anterior.
  localPayment.value = {
    ...(localPayment.value || {}),
    id: selectedBankDebit.value.id,
    IBAN: bank,
    sepa_document: sepaDocuments.value,
  };
  emitChange();
  closeAllRegions();
};

// Funció per gestionar la selecció del mètode de pagament
/* const onSelectPaymentMethod = (event) => {
  emitChange();
}
 */
// Funcions per gestionar la selecció de contactes digitals
const openDigitalPersonContact = () => {
  closeAllRegions();
  showRegionComponent.value = 'DigitalPersonContactSelect';
  showRegion.value = true;
};

const onDigitalPersonContact = (contact) => {
  selectedDigitalPersonContact.value = contact;
  emitChange();
  closeAllRegions();
};

// Funcions per gestionar la selecció de telèfons
const openAddPhoneSelect = () => {
  closeAllRegions();
  showRegionComponent.value = 'PhonePersonContactSelect';
  showRegion.value = true;
};

const openAddSMSPhoneSelect = () => {
  closeAllRegions();
  showRegionComponent.value = 'SMSPhonePersonContactSelect';
  showRegion.value = true;
};

const onPhoneSelected = (phoneContact) => {
  if (!selectedPhones.value.find(phone => phone.id === phoneContact.id)) {
    selectedPhones.value.push(phoneContact);
  }
  // En afegir un telèfon de contacte, s'habilita l'SMS automàticament sense pas manual.
  if (!selectedSMSPhones.value.find(phone => phone.id === phoneContact.id)) {
    selectedSMSPhones.value.push(phoneContact);
  }
  emitChange();
  closeAllRegions();
};

const onSMSPhoneSelected = (phoneContact) => {
  if (!selectedSMSPhones.value.find(phone => phone.id === phoneContact.id)) {
    selectedSMSPhones.value.push(phoneContact);
  }
  emitChange();
  closeAllRegions();
};

const setSupplyAddresses = async () => {
  if (props.request?.address_billing?.id) {
    return;
  }
  if (supplyAddress.value == null && props.request?.supply_point_default) {
    let supply = await $SupplyPointApiService.getDetail(props.request?.supply_point_default.id)
    supplyAddress.value = supply.address
    if (supplyAddress.value) {
      const supplyAddressId = supplyAddress.value.id;
      const existingPersonAddress = holder.value?.addresses?.find(
        pa => (pa.address?.id ?? pa.address) === supplyAddressId
      );

      let personAddressId;
      if (existingPersonAddress) {
        personAddressId = existingPersonAddress.id;
      } else {
        var person_address_data = {
          person: props.request.holder?.id ? props.request.holder.id : props.request.holder,
          address: supplyAddressId,
          is_billing: true,
        };
        var person_address = await $PersonAddressApiService.save(person_address_data);
        holder.value = await hydratePerson(props.request.holder?.id ? props.request.holder.id : props.request.holder);
        fillAddressOptions();
        personAddressId = person_address.id;
      }

      if (!controlledAddressNull.value) {
        selectedBillingAddress.value = personAddressId;
        selectedContactAddress.value = personAddressId;
      }
    }
  }
};

const selectSMSPhone = (phoneId) => {
  const phone = selectedPhones.value.find(phone => phone.id === phoneId);
  if (phone) {
    if (!selectedSMSPhones.value.find(phone => phone.id === phoneId)) {
      selectedSMSPhones.value.push(phone);
    } else {
      selectedSMSPhones.value = selectedSMSPhones.value.filter(phone => phone.id !== phoneId);
    }
  }
  emitChange();
};

// Funció per eliminar un telèfon seleccionat
const removePhone = (phoneId) => {
  selectedPhones.value = selectedPhones.value.filter(phone => phone.id !== phoneId);
  emitChange();
};

const getPersonDisplayName = (person, roleLabel) => {
  if (!person || typeof person !== 'object') return '';
  const baseName = person.full_name
    || [person.name, person.surname].filter(Boolean).join(' ').trim()
    || person.token
    || String(person.id ?? '');
  if (!baseName) return '';
  return roleLabel ? `${baseName} (${roleLabel})` : baseName;
};

// --- Etiquetes de rol per identificar fàcilment cada persona als selectors ---
//
// Ex: "LUIS MISEROL CONESA (Titular)". S'usa tant al desplegable d'adreces com
// als selectors d'IBAN i de contacte (email/telèfon), perquè quan una mateixa
// persona té diversos rols al contracte (p. ex. és titular i alhora representant)
// quedi clar de seguida a quin títol correspon cada opció.

const ROLE_LABELS = {
  holder: () => t('common.roles.HOLDER'),
  owner: () => t('common.roles.OWNER'),
  tenant: () => t('common.roles.TENANT'),
  representative: () => t('contract_block.role_representative'),
};

const roleLabelFor = (roleKey) => ROLE_LABELS[roleKey]?.() || '';

/** Nom del tipus de representant (p. ex. "Representant legal"), indexat per id de persona. */
const representativeTypeById = ref({});

const representativeRoleLabel = (person) =>
  representativeTypeById.value[person?.id] || roleLabelFor('representative');

/** Retorna una còpia superficial de la persona amb el nom ja decorat amb el rol. */
const decoratePersonWithRole = (person, roleLabel) => {
  if (!person) return null;
  return {
    ...person,
    full_name: getPersonDisplayName(person, roleLabel),
  };
};

/** Persones a oferir als selectors d'IBAN i d'adreça (inclou representants). */
const rolePersons = computed(() => {
  const list = [];
  if (holder.value) list.push(decoratePersonWithRole(holder.value, roleLabelFor('holder')));
  if (owner.value) list.push(decoratePersonWithRole(owner.value, roleLabelFor('owner')));
  if (tenant.value) list.push(decoratePersonWithRole(tenant.value, roleLabelFor('tenant')));
  representatives.value.forEach((rep) => {
    list.push(decoratePersonWithRole(rep, representativeRoleLabel(rep)));
  });
  return list.filter(Boolean);
});

/** Persones a oferir als selectors de contacte digital/telèfon (sense representants, com fins ara). */
const rolePersonsNoReps = computed(() => {
  const list = [];
  if (holder.value) list.push(decoratePersonWithRole(holder.value, roleLabelFor('holder')));
  if (owner.value) list.push(decoratePersonWithRole(owner.value, roleLabelFor('owner')));
  if (tenant.value) list.push(decoratePersonWithRole(tenant.value, roleLabelFor('tenant')));
  return list.filter(Boolean);
});

/**
 * Evitem getFullDetail només si l'objecte JA porta TOTES les relacions que fem
 * servir arreu del component (adreces, bancs i contactes). Comprovar només
 * 'addresses' no és suficient: el contracte pot embeny les adreces d'una persona
 * però no els seus bancs/contactes, deixant selectedBankDebitPerson, PersonBankSelect
 * i PersonContactSelect sense dades per a aquesta persona.
 */
const personHasEmbeddedRelations = (person) =>
  person
  && typeof person === 'object'
  && Array.isArray(person.addresses)
  && Array.isArray(person.banks)
  && Array.isArray(person.contacts);

const resolvePerson = async (personRef) => {
  if (!personRef) return null;
  const person = typeof personRef === 'object' ? personRef : { id: personRef };
  if (personHasEmbeddedRelations(person)) return person;
  return hydratePerson(person.id ?? personRef);
};

const hydratePerson = async (person) => {
  if (!person) return null;
  const personId = person.id || person;
  return await $PersonApiService.getFullDetail(personId);
};

// Funció per carregar les dades de la sol·licitud existent
const loadData = async () => {
  initializing.value = true;
  await Promise.all([
    resolvePerson(props.request.holder).then((p) => {
      holder.value = p;
    }),
    props.previousTenant
      // Forcem sempre getFullDetail (i no resolvePerson) perquè l'objecte tenant que
      // arriba embegut dins el contracte pot portar un array 'addresses' (encara que
      // sigui buit), cosa que faria que resolvePerson() se saltés la crida real i nosaltres
      // ens quedéssim sense 'banks' i 'contacts' per detectar les dades a netejar.
      ? hydratePerson(props.previousTenant).then((p) => {
          previousTenant.value = p;
        })
      : Promise.resolve().then(() => { previousTenant.value = null; }),
    loadPersons(),
  ]);

  payment.value = props.request.payment || {};

  selectedBillingAddress.value = props.request?.address_billing?.id
    ? props.request.address_billing.id : null;
  selectedContactAddress.value = props.request?.address_contact?.id
    ? props.request.address_contact.id : null;

  fillAddressOptions();
  fillBankDebitOptions();

  if (props.request?.contract) {
    const addressIds = Object.keys(addressOptionsById.value || {});
    if (addressIds.length === 1) {
      const onlyId = Number(addressIds[0]);
      if (selectedBillingAddress.value === null) {
        selectedBillingAddress.value = onlyId;
      }
      if (selectedContactAddress.value === null) {
        selectedContactAddress.value = onlyId;
      }
    }
  }

  selectedPaymentMethod.value = payment.value?.type?.id || null;
  selectedBankDebit.value = payment.value?.IBAN || null;
  mandateId.value = payment.value?.mandate_id ||props.request.mandate_id || null;
  dir3.value = payment.value?.dir3 || null;
  accounting_office.value = payment.value?.accounting_office || null;
  managing_body.value = payment.value?.managing_body || null;
  processing_unit.value = payment.value?.processing_unit || null;

  if (accounting_office.value || managing_body.value || processing_unit.value) {
    is_electronic_invoice.value = true;
  }

  command.value = payment.value?.command || null;
  record.value = payment.value?.record || null;

  //  sepaDocuments.value = selectedBankDebit?.value?.sepa_document || [];
  selectedRemittanceDate.value = props.request?.remittance_date || null;

  // Inicialitzar les preferències de comunicació
  selectedCommType.value = props.request.communication_type || null;
  selectedDigitalPersonContact.value = props.request.person_contact_email || null;
  // Còpia per no mutar contract.contacts en afegir/eliminar telèfons (trencaria la detecció de canvis al guardar)
  selectedPhones.value = [...(props.request.contacts || [])];
  selectedSMSPhones.value = [...(props.request.person_contact_sms || [])];

  // Si venim d'un canvi de llogater/titular, netegem qualsevol dada carregada
  // que pertanyi exclusivament a la persona que ha deixat el contracte.
  sanitizeStaleTenantSelections();

  const shouldAssignFromSupply = props.autoAssignSupplyAddress
    && !controlledAddressNull.value
    && selectedBillingAddress.value == null
    && selectedContactAddress.value == null;

  if (shouldAssignFromSupply) {
    await setSupplyAddresses();
  }

  initializing.value = false;
  await nextTick();
  emitChange();
};

const onChangeElectronicInvoice = () => {
  emitChange();
}

const loadPersons = async () => {
  const tasks = [];

  if (props.request.owner) {
    tasks.push(
      resolvePerson(props.request.owner).then((p) => {
        owner.value = p;
      }),
    );
  } else {
    owner.value = null;
  }

  if (props.request.tenant) {
    tasks.push(
      resolvePerson(props.request.tenant).then((p) => {
        tenant.value = p;
      }),
    );
  } else {
    tenant.value = null;
  }

  if (props.request.representatives?.length > 0) {
    tasks.push(
      Promise.all(
        props.request.representatives.map(async (item) => {
          const personData = item.person || item;
          const person = personData ? await resolvePerson(personData) : null;
          if (person) {
            representativeTypeById.value[person.id] = item.type?.name || item.type?.list_name || null;
          }
          return person;
        }),
      ).then((reps) => {
        representatives.value = reps.filter(Boolean);
      }),
    );
  } else {
    representatives.value = [];
    representativeTypeById.value = {};
  }

  await Promise.all(tasks);
};

// onMounted
onMounted(async () => {
  await loadData();
});

/** Estat actual de telèfons (font de veritat al guardar des del pare). */
const getContactsState = () => ({
  phoneIds: toSortedPhoneIds(selectedPhones.value),
  phones: selectedPhones.value.map((p) => (typeof p === 'object' ? { ...p } : p)),
  smsPhoneIds: toSortedPhoneIds(selectedSMSPhones.value),
  smsPhones: selectedSMSPhones.value.map((p) => (typeof p === 'object' ? { ...p } : p)),
});

defineExpose({ getContactsState });

// Recarregar només si canvia el contracte (no en cada mutació del mateix objecte)
watch(() => props.request?.id, async (newId, oldId) => {
  if (!newId || newId === oldId) return;
  await loadData();
});

const syncingMandateId = ref(false);

watch(() => props.usedPayment, (newVal) => {
  if (newVal?.mandate_id != null && newVal.mandate_id !== mandateId.value) {
    // Evita que el sync des del backend torni a disparar un save
    syncingMandateId.value = true;
    mandateId.value = newVal.mandate_id;
    nextTick(() => { syncingMandateId.value = false; });
  }
  if (newVal?.id == localPayment.value?.id) return;
  localPayment.value = newVal;
  sepaDocuments.value = newVal?.sepa_document || null;
}, { deep: true, immediate: true });

// Observa canvis en els seleccionats per emetre l'esdeveniment (immediat)
watch(
  [
    selectedBillingAddress,
    selectedContactAddress,
    selectedPaymentMethod,
    selectedBankDebit,
    selectedCommType,
    selectedDigitalPersonContact,
    selectedPhones,
    selectedSMSPhones,
    selectedRemittanceDate,
  ],
  () => {
    console.log('selectedBankDebit', selectedBankDebit.value);
    if (initializing.value) return;
    emitChange();
  },
  { deep: true }
);

// Mandate id: debounce perquè l'usuari pugui acabar d'escriure abans de guardar
const debouncedEmitMandateChange = useDebounceFn(() => {
  if (initializing.value) return;
  emitChange();
}, 1500);

watch(mandateId, () => {
  if (initializing.value || syncingMandateId.value) return;
  debouncedEmitMandateChange();
});

// Quan se selecciona "Sense comunicació" es desvincula l'email de contacte i l'adreça de contacte.
watch(selectedCommType, (newVal) => {
  if (newVal === 'NONE') {
    selectedDigitalPersonContact.value = null;
    selectedContactAddress.value = null;
  }
});

watch(is_electronic_invoice, (newVal) => {
  if (!newVal) {
    accounting_office.value = null;
    managing_body.value = null;
    processing_unit.value = null;
    command.value = null;
    record.value = null;
    emitChange();
  }
}, { deep: true });

const handleSubRegionEvent = (show) => {
  isSubRegionOpen.value = show;
}
</script>

<template>
  <div class="region__content pr-2 relative pb-24" :class="{ 'h-full overflow-y-auto': !isSubRegion }">
    <div id="wrapper" class="text-base">
      <!-- Títol -->


      <!-- Selecció d'adreça fiscal -->
      <div class="mb-4">
        <label for="billing_address" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedBillingAddress !== null" name="fa6-solid:circle-check"
            class="text-xl text-emerald-600" />
          <Icon v-show="selectedBillingAddress === null" name="fa6-solid:asterisk" class="text-lg text-pink-600" />
          <span>{{ $t('common.fiscal_address') }}:</span>
        </label>

        <div v-if="addressOptionsAreEmpty">
          <div class="bg-yellow-100 p-3 italic">{{ t('contract_block.holder_no_addresses') }}</div>
          <ButtonSeleccio @click="openAddBillingAddressForm" class="py-3">
            <Icon name="fa-solid:plus" class="text-slate-500" />
            {{ $t('common.add') }} {{ $t('common.fiscal_address') }}
          </ButtonSeleccio>
        </div>
        <div v-else class="grid grid-cols-[1fr,80px,1fr] gap-3 items-center">
          <select v-model="selectedBillingAddress" class="w-full text-base border border-gray-300 rounded p-2"
            id="billing_address">
            <option :value="null" selected="selected">--{{ $t('address_block.select_address') }}</option>
            <template v-for="(addresses, person) in addressOptions" :key="person">
              <optgroup :label="person">
                <option v-for="address in addresses" :value="address.value" :key="address.value">
                  {{ address.label }}
                </option>
              </optgroup>
            </template>
          </select>

          <span class="text-center"> — {{ t('common.or') }} —</span>
          <div class="flex flex-col gap-2">

            <ButtonSeleccio @click="openPersonBillingAddressSelect" class="py-3">
              <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
              {{ $t('common.select') }} {{ $t('common.address') }}
            </ButtonSeleccio>
          </div>
        </div>
      </div>
      <!-- /end Selecció d'adreça fiscal -->


      <!-- Selecció d'adreça enviament -->
      <div class="mb-4">
        <label for="contact_address" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedContactAddress !== null" name="fa6-solid:circle-check"
            class="text-xl text-emerald-600" />
          <Icon v-show="selectedContactAddress === null" name="fa6-solid:asterisk" class="text-lg text-pink-600" />
          <span>{{ $t('contract_block.contact_address') }}:</span>
        </label>

        <div v-if="addressOptionsAreEmpty">
          <div class="bg-yellow-100 p-3 italic">{{ t('contract_block.holder_no_addresses') }}</div>
          <ButtonSeleccio @click="openAddContactAddressForm" class="py-3">
            <Icon name="fa-solid:plus" class="text-slate-500" />
            {{ $t('common.add') }} {{ $t('contract_block.contact_address') }}
          </ButtonSeleccio>
        </div>
        <div v-else class="grid grid-cols-[1fr,80px,1fr] gap-3 items-center">
          <select v-model="selectedContactAddress" class="w-full text-base border border-gray-300 rounded p-2"
            id="contact_address">
            <option :value="null" selected="selected">--{{ $t('address_block.select_address') }}</option>
            <template v-for="(addresses, person) in addressOptions" :key="person">
              <optgroup :label="person">
                <option v-for="address in addresses" :value="address.value" :key="address.value">
                  {{ address.label }}
                </option>
              </optgroup>
            </template>
          </select>

          <span class="text-center"> — {{ t('common.or') }} —</span>
          <div class="flex flex-col gap-2">

            <ButtonSeleccio @click="openPersonContactAddressSelect" class="py-3">
              <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
              {{ $t('common.select') }} {{ $t('common.address') }}
            </ButtonSeleccio>
          </div>
        </div>
      </div>
      <!-- /end Selecció d'adreça enviament -->

      <hr class="my-2" />

      <!-- Selecció Payment -->
      <div class="grid grid-cols-2 gap-x-3">
        <div class="mb-4">
          <SelectPaymentType v-model="selectedPaymentMethod" show-label-icons select-wrapper-class="max-w-xl"
            :model-as-number="true" @loaded="onPaymentTypesLoaded" />
          <div class="select_bank mt-3 max-w-xl" v-if="isDirectDebitSelected">
            <div v-if="selectedBankDebit" class="bg-green-100 p-4 rounded relative group">
              <div>
                <BankDetail :item="selectedBankDebit" :person="selectedBankDebitPerson" :sepa="sepaDocuments || null"
                  :show_sepa="true">
                  <template #sepa-actions>
                    <SepaQuickActions :payment="sepaPayment" :sepa="sepaDocuments" :owner="request" :value="sepaValue"
                      @saved="onSepaQuickSaved" />
                  </template>
                </BankDetail>
              </div>
              <button @click="openPersonBankSelect"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                <Icon name="fa6-solid:pencil" />
              </button>
              <button v-if="!selectedBankDebit.is_default" @click="saveBankAsDefault" :disabled="savingDefaultBank"
                class="mt-2 button-default-xs" type="button">
                <Icon :name="savingDefaultBank ? 'fa6-solid:spinner' : 'fa6-solid:star'"
                  :class="{ 'animate-spin': savingDefaultBank }" class="text-slate-500 mr-1" />
                {{ t('common.save_as_default_payment') }}
              </button>
              <div v-else class="mt-2 text-sm text-emerald-700 flex items-center gap-1">
                <Icon name="fa6-solid:star" />
                {{ t('common.default_payment') }}
              </div>
            </div>

            <ButtonSeleccio v-else @click="openPersonBankSelect()" class="py-3">
              <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
              {{ $t('common.select') }} {{ $t('common.iban') }}
            </ButtonSeleccio>

            <div v-if="selectedBankDebit">
              <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded">
                <!-- <label class="inline-block" :class=" 'text-slate-400 m-1'">{{
                 t('Documents de pagament SEPA') }}</label> -->
                <div v-if="sepaDocuments && sepaDocuments?.file != null && sepaDocuments?.checked">
                  <button
                    class="item__bank border bg-gray-100 hover:bg-yellow-100 border-gray-200 w-full p-2 block text-left mb-2"
                    @click="openInputSepa">
                    <label class="inline-block" :class="'text-black-400 m-1'">{{
                      t('contract_block.document_sepa') }}</label>
                  </button>
                </div>
                <div v-else class="flex flex-col items-start gap-1">
                  <div class="flex items-center text-sm text-slate-600 gap-1">
                    <Icon name="fa6-solid:file-signature" class="text-slate-500" />
                    <span>{{ t('contract_block.sepa_quick_actions_hint') }}</span>
                    <span class="ml-1 text-xs italic text-slate-400">({{ t('common.optional') }})</span>
                  </div>
                  <div class="text-xs text-slate-500 flex items-start gap-1">
                    <Icon name="fa6-solid:circle-info" class="mt-0.5" />
                    <span>{{ t('common.sepa_optional_info') }}</span>
                  </div>
                  <div v-if="!selectedBankDebit.is_default" class="text-xs text-amber-600 flex items-center gap-1">
                    <Icon name="fa6-solid:triangle-exclamation" />
                    {{ t('common.default_payment_needed_for_sepa') }}
                  </div>
                </div>

              </fieldset>
            </div>
          </div>

          <div v-if="isDirectDebitSelected" class="field mb-3 max-w-xl">
            <label for="mandate_id" class="block text-sm font-medium text-gray-700 mb-2">
              {{ $t('common.mandate_id') }}
            </label>
            <input id="mandate_id" v-model="mandateId" type="text"
              class="w-full text-base border border-gray-300 rounded p-2" />
          </div>


          <div v-if="isDirectDebitSelected" class="field mb-3">
            <div>
              <label class="flex text-sm font-medium text-gray-700 my-3 gap-2">
                <Icon v-show="selectedRemittanceDate" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
                <Icon v-show="!selectedRemittanceDate" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
                <span>{{ $t('contract_block.best_remittance') }}
                </span>
                <abbr :title="t('informative_block.info_remittance_day')" class="inline-block no-underline">
                  <Icon name="fa6-solid:info" class="text-slate-500 text-[12px]"></Icon>
                </abbr>
              </label>
              <input v-numeric-only maxlength="2" :placeholder="''" v-model="selectedRemittanceDate"
                class="text-base border border-gray-300 rounded p-2 w-[100px]" type="numeric" />
            </div>
          </div>

          <div v-if="!isDirectDebitSelected">
            

            <button @click="generateDocumentNoSepa()" :disabled="generatingSepaDocument || sendingSepaDocument" name="" class="button-default-xs mt-4">
              <Icon v-if="generatingSepaDocument" name="fa6-solid:spinner" class="animate-spin text-slate-500 mr-1" />
              <Icon v-else name="fa-solid:plus" class="text-slate-500 mr-1" />
              {{ t('contract_block.generate_no_sepa_document')}}
            </button>
            <button @click="generateDocumentNoSepa({ sendByEmail: true })" :disabled="generatingSepaDocument || sendingSepaDocument"
              type="button" class="button-default-xs mt-4 ml-2">
              <Icon :name="sendingSepaDocument ? 'fa6-solid:spinner' : 'fa6-solid:envelope'"
                :class="{ 'animate-spin': sendingSepaDocument }" class="text-slate-500 mr-1" />
              {{ t('contract_block.sepa_send_email') }}
            </button>
            <SendSepaEmailModal :show="showSendSepaModal" :sepa-document-id="noSepaDocumentId" :contract="request"
              :is-request="sepaValue !== 'contract'" :person="holder" @close="showSendSepaModal = false" />
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
                    @change="onChangeElectronicInvoice" placeholder="Codi oficina" />
                </div>
                <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.managing_body') }}
                  </label>
                  <input type="text" v-model="managing_body"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi òrgan" />
                </div>
                <div class="space-y-1">
                  <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                    {{ $t('billing_block.processing_unit') }}
                  </label>
                  <input type="text" v-model="processing_unit"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                    @change="onChangeElectronicInvoice" placeholder="Codi unitat" />
                </div>
                <!-- <div class="space-y-1">
                <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                  {{ $t('billing_block.command') }}
                </label>
                <input type="text" v-model="command" class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                  @change="onChangeElectronicInvoice" placeholder="Codi comanda" />
              </div>
              <div class="space-y-1 col-span-2">
                <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                  {{ $t('billing_block.record') }}
                </label>
                <input type="text" v-model="record" class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                  @change="onChangeElectronicInvoice" placeholder="Codi expedient" />
              </div> -->
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- /end Selecció Payment -->


      <hr class="my-2" />


      <!-- Selecció Comunicació -->
      <div class="mb-4">
        <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedCommType" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="!selectedCommType" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('communication') }}:</span>
        </label>

        <div class="communication_type max-w-xxl">
          <div class="flex gap-4 py-2">
            <label class="flex items-center">
              <input type="radio" value="PAPER" v-model="selectedCommType" class="mr-2">
              {{ $t('contract_block.paper_comm') }}
            </label>
            <label class="flex items-center">
              <input type="radio" value="DIGITAL" v-model="selectedCommType" class="mr-2">
              {{ $t('contract_block.digital_comm') }}
            </label>
            <label class="flex items-center">
              <input type="radio" value="BOTH" v-model="selectedCommType" class="mr-2">
              {{ $t('contract_block.both_comm') }}
            </label>
            <label class="flex items-center">
              <input type="radio" value="NONE" v-model="selectedCommType" class="mr-2">
              {{ $t('contract_block.no_comm') }}
            </label>
          </div>

          <div v-if="selectedCommType == 'PAPER' || selectedCommType == 'BOTH'" class="mb-4">
            <div class="text-xs font-semibold text-slate-500 uppercase mb-2">
              {{ $t('contract_block.paper_comm') }}
            </div>
            <div class="max-w-xl">
              <div v-if="selectedContactAddress" class="bg-green-100 p-4 rounded relative group">
                <div>{{ addressOptionsById[selectedContactAddress] }}</div>
                <button @click="openPersonContactAddressSelect()"
                  class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                  <Icon name="fa6-solid:pencil" />
                </button>
              </div>
              <ButtonSeleccio v-else @click="openPersonContactAddressSelect()" class="py-3">
                <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
                {{ $t('common.select') }} {{ $t('common.address') }}
              </ButtonSeleccio>
            </div>
          </div>

          <div v-if="selectedCommType == 'DIGITAL' || selectedCommType == 'BOTH'">
            <div class="text-xs font-semibold text-slate-500 uppercase mb-2">
              {{ $t('contract_block.digital_comm') }}
            </div>
            <div class="max-w-xl">
              <div v-if="selectedDigitalPersonContact" class="bg-green-100 p-4 rounded relative group">
                <div>
                  <PersonContactDetail :item="selectedDigitalPersonContact" :onlyEmail="true" />
                </div>
                <button @click="selectedDigitalPersonContact = null"
                  class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-12 top-3 rounded-md text-red-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                  <Icon name="fa6-solid:trash" />
                </button>
                <button @click="openDigitalPersonContact()"
                  class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                  <Icon name="fa6-solid:pencil" />
                </button>
              </div>
              <ButtonSeleccio v-else @click="openDigitalPersonContact()" class="py-3">
                <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
                {{ $t('common.select') }} {{ $t('common.email_long') }}
              </ButtonSeleccio>
            </div>
          </div>
        </div>
      </div>
      <!-- /end Comunicació -->


      <hr class="my-2" />


      <!-- Selecció Telèfons -->
      <div class="mb-4 max-w-xl">
        <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedPhones.length > 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="selectedPhones.length <= 0" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('contract_block.contact_tlfs') }}:</span>
        </label>

        <div v-if="selectedPhones.length === 0">
          <ButtonSeleccio @click="openAddPhoneSelect" class="py-3">
            <Icon name="fa-solid:plus" class="text-slate-500" />
            {{ $t('common.add') }} {{ $t('common.tlf') }}
          </ButtonSeleccio>
        </div>
        <div v-else class="space-y-2">
          <div v-for="phone in selectedPhones.filter(c => c.phone)" :key="phone.id"
            class="flex items-center grid grid-cols-[1fr,50px]">
            <div class="flex items-center justify-between bg-gray-100 p-3 gap-x-2 rounded">
              <span><span class="inline-block mr-3">{{ phone.phone }}</span>
                <em v-if="phone.role">
                  ({{ phone.role }})</em></span>
              <button @click="removePhone(phone.id)"
                class="opacity-50 text-red-500 hover:text-red-700 hover:opacity-100">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
            <abbr :title="t('customer_service_block.tlf_sms')" class="flex items-center ml-2 rounded-md justify-center"
              :class="{
                'bg-green-100 text-green-500 hover:text-green-700': selectedSMSPhones.find(smsPhone => smsPhone.id === phone.id),
                'bg-slate-100 text-slate-500 hover:text-slate-700': !selectedSMSPhones.find(smsPhone => smsPhone.id === phone.id),
              }">
              <button @click="selectSMSPhone(phone.id)" class="flex items-center justify-center w-full h-full py-3">
                <Icon name="fa6-solid:comment-sms" class="w-4 h-4 m-auto" />
              </button>
            </abbr>
          </div>
          <ButtonSeleccio @click="openAddPhoneSelect" class="py-3">
            <Icon name="fa-solid:plus" class="text-slate-500" />
            {{ $t('common.add') }} {{ $t('common.tlf') }}
          </ButtonSeleccio>
        </div>
      </div>
      <!-- /end Selecció Telèfons -->



      <!-- Regió lateral de ContractRequestAddressPayment -->
      <div role="region" id="right_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10 overflow-y-auto"
        :class="{
          'translate-x-0': showRegion,
          'translate-x-full': !showRegion,
          'w-[95%]': isSubRegionOpen,
          'w-1/2': !isSubRegionOpen
        }">
        <div id="region_nav" class="mb-3 px-3 flex justify-start">
          <button @click="showRegion = false"
            class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded" aria-label="Tancar formulari">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="px-10">
          <InputSepa v-if="showRegionComponent === 'addSepa'" :item="localPayment" :person="selectedBankDebitPerson"
            :sepa="sepaDocuments?.file ? sepaDocuments : null" :request="request" @new-item="onSepaSaved"
            :value="sepaValue" />
          <AddAddress v-if="showRegionComponent === 'addBillingAddress'" :isSubRegion="true"
            :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
            @new-address="onAddBillingAddressSaved" />
          <AddAddress v-if="showRegionComponent === 'addContactAddress'" :isSubRegion="true"
            :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
            @new-address="onAddContactAddressSaved" />
          <PersonBankSelect v-if="showRegionComponent === 'PersonBankSelect'"
            :title="`${$t('common.select')} ${$t('common.iban')}`"
            :persons="rolePersons" @selected-item="onPersonBankSelected" />
          <PersonContactSelect ref="personContactSelectRef" v-if="showRegionComponent === 'DigitalPersonContactSelect'"
            :title="`${$t('common.select')} ${$t('common.email_long')}`" :persons="rolePersonsNoReps"
            :onlyEmail="true" @selected-item="onDigitalPersonContact" />
          <PersonContactSelect v-if="showRegionComponent === 'PhonePersonContactSelect'"
            :title="`${$t('common.select')} ${$t('common.tlf')}`" :persons="rolePersonsNoReps" :onlyPhone="true"
            @selected-item="onPhoneSelected" />
          <PersonContactSelect v-if="showRegionComponent === 'SMSPhonePersonContactSelect'"
            :title="`${$t('common.select')} ${$t('customer_service_block.tlf_sms')}`" :persons="rolePersonsNoReps"
            :onlyPhone="true" @selected-item="onSMSPhoneSelected" />
          <PersonAddressSelect v-if="showRegionComponent === 'BillingAddressSelect'"
            :title="`${$t('common.select')} ${$t('common.fiscal_address')}`"
            :persons="rolePersons" :isBilling="true"
            @selected-item="onPersonBillingAddressSelected" />

          <PersonAddressSelect v-if="showRegionComponent === 'ContactAddressSelect'"
            :title="`${$t('common.select')} ${$t('contract_block.contact_address')}`"
            :persons="rolePersons" :isBilling="false"
            @selected-item="onPersonContactAddressSelected" />
        </div>
      </div><!-- /end Regió lateral per formularis -->



    </div><!-- /end #wrapper -->
  </div>
</template>