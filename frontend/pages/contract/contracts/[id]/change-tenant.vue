<script setup>
// pages/contract/contracts/[id]/change-tenant.vue
//
// Canvi de persones d'un contracte en una sola pantalla (titular, propietari i
// llogater), amb el mateix aspecte que el pas 2 de l'edició de sol·licituds.
// Els canvis es preparen al pas 1 i es desen tots junts al pas 2, on es revisen
// adreces i pagament: així es pot, per exemple, canviar de llogater i alhora
// treure el propietari perquè no surti a la factura.
//
// Titular i propietari es reassignen directament (PUT del contracte amb
// holder_id/owner_id); no és una subrogació, que a més mouria pagament, adreces
// i contactes (això es fa des de /contract/contracts/[id]/surrogate).
// El llogater manté el seu circuit propi (ContractTenantChange) amb documentació.
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';

const route = useRoute()
const { $ContractApiService, $ConfiglistApiService, $GeneralPaymentApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const id = ref(route.params.id)
const saving = ref(false);
const contract = ref(null)

const roles = [
  { key: 'holder', label: 'contract_block.holder', mandatory: true, selectLabel: 'contract_block.select_holder', emptyLabel: 'contract_block.no_holder' },
  { key: 'owner', label: 'contract_block.owner', mandatory: false, selectLabel: 'contract_block.select_owner', emptyLabel: 'contract_block.no_owner' },
  { key: 'tenant', label: 'contract_block.tenant', mandatory: false, selectLabel: 'contract_block.select_tenant', emptyLabel: 'contract_block.no_tenant' },
];

// Persones tal com estan desades al contracte (per calcular què ha canviat).
const originalPersons = ref({ holder: null, owner: null, tenant: null });
// Persones triades a la pantalla, pendents de desar.
const selectedPersons = ref({ holder: null, owner: null, tenant: null });

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPerson = ref(false);
// A quin rol va la persona que se selecciona al panell lateral.
const personFormTarget = ref('tenant');
const currentStep = ref(0);

const selectedBillingAddress = ref(null);
const selectedContactAddress = ref(null);
const selectedPaymentMethod = ref(null);
const selectedBankDebit = ref(null);
const selectedCommType = ref(null);
const selectedDigitalPersonContact = ref(null);
const selectedPhones = ref([]);
const mandateId = ref(null);
const currentPayment = ref(null);

const documentationToUpload = ref([])
const availableDocumentTypes = ref([])
const selectedDocumentTypes = ref([])
const loading_doc_types = ref(true);
const doc_types = ref([]);

const personId = (person) => person?.id ?? null;

const hasRoleChanged = (roleKey) => personId(selectedPersons.value[roleKey]) !== personId(originalPersons.value[roleKey]);

/** Títol del panell lateral, segons el rol que s'està triant. */
const personFormTitle = computed(() => `${t('common.select')} ${t('common.or')} ${t('common.add')} ${t('contract_block.' + personFormTarget.value)}`);

const tenantChanged = computed(() => hasRoleChanged('tenant'));
const hasChanges = computed(() => roles.some(role => hasRoleChanged(role.key)));

/** Persona que deixa el contracte: és la que pot haver-hi deixat dades (IBAN, adreces,
 * contactes) carregades al pas 2 i que cal netejar-ne. */
const leavingPerson = computed(() => {
  if (tenantChanged.value) return originalPersons.value.tenant;
  if (hasRoleChanged('holder')) return originalPersons.value.holder;
  return null;
});

// La documentació d'aquesta pantalla és la del canvi de llogater: si es desfà el canvi,
// deixa de tenir sentit i no s'ha de pujar.
watch(tenantChanged, (changed) => {
  if (!changed) {
    selectedDocumentTypes.value = [];
    documentationToUpload.value = [];
  }
});

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

const getDocumentTypes = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-tenant-change-document-type');
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
    d => d.contract_tenant_change_document_type != docType.id
  );
}

const upsertDocumentationToUpload = (docType, extra = {}) => {
  const i = documentationToUpload.value.findIndex(d => d.contract_tenant_change_document_type == docType.id)
  if (i > -1) {
    Object.assign(documentationToUpload.value[i], extra)
    documentationToUpload.value[i].selected_doc_type = extra.selected_doc_type !== undefined
      ? extra.selected_doc_type
      : (docType.selected_doc_type || documentationToUpload.value[i].selected_doc_type || null)
  } else {
    documentationToUpload.value.push({
      contract_tenant_change_document_type: docType.id,
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
      const i = documentationToUpload.value.findIndex(d => d.contract_tenant_change_document_type == docType.id)
      if (i > -1) {
        documentationToUpload.value[i].file = null;
      }
    }
  } catch (error) {
    console.log(error)
  }
}

const handleDocTypeChange = (docType) => {
  const i = documentationToUpload.value.findIndex(d => d.contract_tenant_change_document_type == docType.id)
  if (i > -1) {
    documentationToUpload.value[i].selected_doc_type = docType.selected_doc_type || null
  } else if (docType.document?.file) {
    upsertDocumentationToUpload(docType, { selected_doc_type: docType.selected_doc_type || null });
  }
}

const isDocTypeRequired = (doc) => {
  return !!doc.document?.file;
}

const getData = async function () {
  const response = await $ContractApiService.getDetail(id.value);
  contract.value = response

  originalPersons.value = {
    holder: contract.value.holder || null,
    owner: contract.value.owner || null,
    tenant: contract.value.tenant || null,
  };
  selectedPersons.value = { ...originalPersons.value };

  await Promise.all([getDocTypes(), getDocumentTypes()]);
}

const hasMissingDocType = () => {
  return documentationToUpload.value.some(doc => doc.file && !doc.selected_doc_type);
}

/** Comprovacions comunes abans de continuar i abans de desar. */
const validateChanges = () => {
  if (!selectedPersons.value.holder) {
    toast.error(t('warning_block.holder_required'));
    return false;
  }
  if (!hasChanges.value) {
    toast.error(t('warning_block.no_person_changes'));
    return false;
  }
  if (hasMissingDocType()) {
    toast.error(t('warning_block.doc_type_required_if_file'));
    return false;
  }
  return true;
}

const goNext = async () => {
  if (!validateChanges()) return;

  // El pas 2 (adreces i pagament) treballa amb les persones del contracte, així que
  // hi apliquem les triades per oferir les seves adreces, comptes i contactes.
  contract.value.holder = selectedPersons.value.holder;
  contract.value.owner = selectedPersons.value.owner;
  contract.value.tenant = selectedPersons.value.tenant;

  currentStep.value++
}

const onChange = (data) => {
  selectedCommType.value = data.communication_type;
  selectedDigitalPersonContact.value = data.person_contact_email;
  selectedPhones.value = data.contacts;
  selectedBillingAddress.value = data.address_billing;
  selectedContactAddress.value = data.address_contact;
  selectedPaymentMethod.value = data.payment_type;
  selectedBankDebit.value = data.IBAN;
  mandateId.value = data.mandate_id;
}

const save = async () => {
  if (!validateChanges()) return;

  saving.value = true
  try {
    // El backend fa copy-on-write: si el GeneralPayment estava compartit amb
    // altres contractes, retorna una fila nova i cal vincular-la al contracte.
    let saved_payment = null;
    if (contract.value.payment) {
      saved_payment = await $GeneralPaymentApiService.save({
        id: contract.value.payment.id,
        iban_id: selectedBankDebit.value,
        type_id: selectedPaymentMethod.value,
        mandate_token: contract.value.token,
      })
    }

    let contract_options = {
      id: contract.value.id,
      address_billing_id: selectedBillingAddress.value,
      address_contact_id: selectedContactAddress.value,
      communication_type: selectedCommType.value,
      person_contact_email_id: selectedDigitalPersonContact.value,
      phone_ids: selectedPhones.value,
      mandate_id: mandateId.value,
      payment_id: saved_payment?.id ?? contract.value.payment?.id ?? null
    }
    // Titular i propietari viatgen amb el mateix PUT; només s'hi envien si canvien,
    // perquè el backend els ignora quan no hi són i així no es generen logs buits.
    if (hasRoleChanged('holder')) {
      contract_options.holder_id = personId(selectedPersons.value.holder);
    }
    if (hasRoleChanged('owner')) {
      contract_options.owner_id = personId(selectedPersons.value.owner);
    }
    await $ContractApiService.save(contract_options)
  } catch (error) {
    // Si això falla, el canvi de titular/propietari no s'ha desat: no continuem amb
    // el canvi de llogater per no deixar el contracte a mitges.
    console.error(error)
    const backendMessage = error.response?._data?.message || error.response?._data?.detail;
    toast.error(backendMessage || t('common.error'));
    saving.value = false;
    return;
  }

  try {
    if (tenantChanged.value) {
      await $ContractApiService.changeTenant({
        token: _.random(1000, 9999),
        contract: contract.value.id,
        new_tenant: personId(selectedPersons.value.tenant),
        previous_tenant: personId(originalPersons.value.tenant),
        requested_at: new Date().toISOString(),
        approved_at: new Date().toISOString()
      })
    }

    await Promise.all(documentationToUpload.value.map((doc) => {
      if (!doc.file) return Promise.resolve();

      return $ContractApiService.saveFile({
        id: contract.value.id,
        file: doc.file,
        is_contract: false,
        contract_type: doc.selected_doc_type,
        text: doc.type_name
          ? `${t('contract_block.tenant_change')} - ${doc.type_name}`
          : t('contract_block.tenant_change'),
      });
    }))

    toast.success(t('contract_block.persons_changed_success'));

    return navigateTo({
      path: '/contract/contracts/',
      query: {
        id: contract.value.id,
      }
    })
  }
  catch (error) {
    console.error(error)
    const backendMessage = error.response?._data?.message || error.response?._data?.detail;
    toast.error(backendMessage || t('common.error'));
  } finally {
    saving.value = false;
  }
}

const closeAllRegions = () => {
  editingPerson.value = false;
  showRegion.value = false;
};

const fetchPerson = async (item) => {
  selectedPersons.value[personFormTarget.value] = item;
  closeAllRegions();
};

const openPersonForm = (roleKey) => {
  personFormTarget.value = roleKey;
  closeAllRegions();
  editingPerson.value = true;
  showRegion.value = true;
};

/** Treu la persona del rol (només rols opcionals). No es desa fins al pas final. */
const removePerson = (roleKey) => {
  selectedPersons.value[roleKey] = null;
};

/** Desfà el canvi d'un rol i hi torna a deixar la persona que hi ha desada. */
const resetPerson = (roleKey) => {
  selectedPersons.value[roleKey] = originalPersons.value[roleKey];
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  await getData()
  currentPayment.value = contract.value.payment;
});

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div v-if="contract == null">
      <div class="flex justify-center items-center">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        <span class="ml-2">{{ $t('common.loading') }}...</span>
      </div>
    </div>
    <div v-else>
      <div class="flex justify-between items-center mb-6">
        <H1>{{ $t(`contract_block.tenant_change`) + ' ' + (contract.supply_point_default ?
          contract.supply_point_default.address_complete : contract.token)
        }}</H1>
      </div>
      <div v-if="currentStep == 0">
        <p class="text-sm text-slate-500 mb-4 max-w-xl">{{ $t('contract_block.persons_change_help') }}</p>

        <div class="border-gray-300 mb-2">
          <!-- Selecció de persones per rols -->
          <div class="mb-4" v-for="role in roles" :key="role.key">
            <label :for="role.key" class="flex items-center text-sm font-medium text-gray-700 mb-3 gap-2">
              <Icon v-show="selectedPersons[role.key]" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
              <Icon v-show="!selectedPersons[role.key] && role.mandatory" name="fa6-solid:asterisk"
                class="text-lg text-pink-600" />
              <Icon v-show="!selectedPersons[role.key] && !role.mandatory" name="fa6-solid:circle"
                class="text-lg text-slate-400" />
              <span>{{ $t(role.label) }}</span>
              <span v-if="hasRoleChanged(role.key)"
                class="px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                {{ $t('common.modified') }}
              </span>
            </label>

            <div v-if="selectedPersons[role.key]" class="bg-green-100 p-4 rounded relative max-w-xl pr-24 group"
              :class="{ 'ring-2 ring-amber-300': hasRoleChanged(role.key) }">
              <p class="font-semibold flex gap-3">
                <AtomsVulnerabilityCheck v-if="selectedPersons[role.key].vulnerability_level > 0"
                  :vulnerability_level="selectedPersons[role.key].vulnerability_level" :small="true" class="mr-1" />
                <span>{{ selectedPersons[role.key].name }} {{ selectedPersons[role.key].surname }}</span>
                <span class="text-sm text-gray-500">{{ selectedPersons[role.key].token }}</span>
              </p>
              <button type="button" @click="openPersonForm(role.key)"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-12 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100"
                :title="`${t('common.modify')} ${t(role.label)}`">
                <Icon name="fa6-solid:pencil" />
              </button>
              <button v-if="!role.mandatory" type="button" @click="removePerson(role.key)"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-red-600 opacity-0 transition-all duration-300 group-hover:opacity-100"
                :title="`${t('common.unlink')} ${t(role.label)}`">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
            <div v-else class="max-w-xl">
              <ButtonSeleccio @click="openPersonForm(role.key)" class="py-2">
                {{ $t(role.selectLabel) }}
              </ButtonSeleccio>
            </div>

            <!-- Què hi havia abans, quan el rol s'ha tocat -->
            <div v-if="hasRoleChanged(role.key)" class="max-w-xl mt-2 flex items-center gap-3 text-sm text-slate-500">
              <span>
                {{ $t('common.previous') }}:
                <template v-if="originalPersons[role.key]">
                  {{ originalPersons[role.key].name }} {{ originalPersons[role.key].surname }}
                  ({{ originalPersons[role.key].token }})
                </template>
                <template v-else>{{ $t(role.emptyLabel) }}</template>
              </span>
              <button type="button" @click="resetPerson(role.key)" class="text-sky-600 hover:underline">
                {{ $t('common.undo') }}
              </button>
            </div>
          </div>
          <!-- /end Selecció de persones per rols -->

          <!-- La documentació és pròpia del canvi de llogater -->
          <div v-if="tenantChanged && availableDocumentTypes.length > 0" class="mb-4 max-w-xl">
            <div class="flex">
              <label for="documents" class="block text-sm font-medium text-gray-700 mb-2">{{ t('common.documentation')
              }}
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
                    @delete="handleDocumentDelete(doc.document, doc)" :name="'contractFile'"
                    :uploaded="doc.document.file" :fullWidth="true" class="w-full" />
                </div>
              </fieldset>
            </div>
          </div>
        </div>
        <hr class="max-w-xl">
        <div class="flex flex-row-reverse mt-4 max-w-xl">
          <button @click="goNext" :disabled="!hasChanges || !selectedPersons.holder" class="button-primary">
            <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.continue') }}
          </button>
        </div>
      </div>
      <div v-else-if="currentStep == 1">
        <MoleculesContractRequestAddressPayment :request="contract" @change="onChange" :usedPayment="currentPayment"
          :sepaValue="'contract'" :previous-tenant="leavingPerson" />

        <div class="flex flex-row-reverse mt-4 max-w-xl">
          <button @click="save" :disabled="!hasChanges || saving" class="button-primary">
            <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
              :class="saving ? 'animate-spin' : ''" />
            &nbsp; {{ saving ? $t('common.saving') : $t('common.save') }}
          </button>
          <button @click="currentStep--" :disabled="saving" class="button-secondary mr-5">
            <Icon name="fa6-solid:angle-left" />&nbsp; {{ $t('common.go_back') }}
          </button>
        </div>
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
        <PersonSearch v-if="editingPerson" @saved="fetchPerson"
          :personLabel="`contract_block.${personFormTarget}`"
          isExistingLabel="contract_block.is_existing_person" :title="personFormTitle" />
      </div>
    </div>
  </div>
</template>
