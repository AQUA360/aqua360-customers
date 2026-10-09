<script setup>
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import _ from 'lodash';
import AddAddress from '~/components/molecules/AddAddress.vue';
import AddContact from '~/components/molecules/AddContact.vue';
import AddBank from '~/components/molecules/AddBank.vue';
import AddCnae from '~/components/molecules/AddCnae.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { isValidDNI } from '~/utils/dni';

const props = defineProps({
  id: Number
});

const { t } = useI18n();
const { $PersonApiService, $ConfiglistApiService } = useNuxtApp();
const toast = useToast();
const objectPermissions = ref(null);
const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const person = ref(null);

const cnaes = ref([])
const banks = ref([])
const bank = ref(null)
const contacts = ref([])
const contact = ref(null)
const addresses = ref([])
const address = ref(null)
const attention_to = ref('')
const identificatorTypes = ref([]);

const token = ref(null);
const name = ref(null);
const surname = ref(null);
const currentYear = ref(null);
const currentRecord = ref(null);
const selectedHistoricalRecord = ref(null);
const eRecords = ref([]);

const historicalRecords = computed(() =>
  (eRecords.value || [])
    .filter(r => r.year != currentYear.value)
    .sort((a, b) => b.year - a.year)
);
const isJuridic = ref(false);
const socialServices = ref(false);
const selectedIdentificatorType = ref(null);

const isDniType = computed(() =>
  selectedIdentificatorType.value?.token === 'dni'
);

const dniIsValid = computed(() => {
  if (!isDniType.value || !token.value) return true; // no avisem si no és DNI o si és buit
  return isValidDNI(token.value);
});

const editingBank = ref(false);
const editingContact = ref(false);
const editingAddress = ref(false);
const editingCnae = ref(false);
const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const getData = async () => {
  if (props.id != null) {

    try {
      currentYear.value = new Date().getFullYear();
      const result = await $PersonApiService.getFullDetail(props.id);
      person.value = result;
      currentRecord.value = result.records.find(r => r.year == currentYear.value).e_record || null;
      if (Array.isArray(person.value?.records) && person.value.records.some(r => r.year != currentYear.value)) {
        // Get all records except the one for the current year
        const historical = person.value.records.filter(r => r.year != currentYear.value).sort((a, b) => b.year - a.year);
        selectedHistoricalRecord.value = historical[0];
      }
 
    } catch (err) {
      console.error(err);
    } finally {
      loading.value = false;
    }

    setValues();
  }
  else {
    loading.value = false;
  }
}

const getIdentificatorTypes = async () => {
  try {
    const result = await $ConfiglistApiService.getAll('coredata/identification-type');
    identificatorTypes.value = result.results;
    console.log("identificatorTypes.value");
    console.log(identificatorTypes.value);
  }
  catch (err) {
    console.error(err);
  }
}

const onNewAddress = (new_address) => {
  let i = addresses.value.findIndex(pa =>
    (pa.address?.id && pa.address?.id === new_address.id) ||
    (pa.address?.temp_id && pa.address?.temp_id === new_address.temp_id)
  );

  if (i > -1) {
    let person_address = {
      ...addresses.value[i],
      attention_to: attention_to.value,
      address: new_address,
    }

    addresses.value.splice(i, 1, person_address);
  }
  else {
    let billing_idx = addresses.value.findIndex(pa => pa.is_billing === true);

    const address_with_temp = {
      ...new_address,
      temp_id: _.random(100000, 999999)
    };

    let person_address = {
      address: address_with_temp,
      attention_to: attention_to.value,
      is_billing: billing_idx == -1,
      is_active: true
    }
    addresses.value.push(person_address);
  }
  closeAllRegions();
}

const onNewContact = (new_contact) => {
  let i = contacts.value.findIndex(c => (c.id === new_contact.id && new_contact.id != null));

  if (i == -1) {
    i = contacts.value.findIndex(c => c.temp_id === new_contact.temp_id && new_contact.temp_id != null)
  }


  if (i != -1) {
    let c = {
      ...contacts.value[i],
      ...new_contact
    }

    contacts.value.splice(i, 1, c);
  }
  else {
    let i = contacts.value.findIndex(c => c.is_default === true);

    let c = {
      ...new_contact,
      is_default: i == -1,
      is_active: true,
      temp_id: _.random(100000, 999999)
    }
    contacts.value.push(c);
  }
  closeAllRegions();
}

const onNewBank = (new_bank) => {
  let i = banks.value.findIndex(b => (b.id === new_bank.id && b.id != null));
  if (i != -1) {
    let b = {
      ...banks.value[i],
      ...new_bank
    }

    banks.value.splice(i, 1, b);
  }
  else {
    let i = banks.value.findIndex(b => b.is_default === true);

    let b = {
      ...new_bank,
      is_default: i == -1,
      is_active: true,
      temp_id: _.random(100000, 999999)
    }
    banks.value.push(b);
  }
  closeAllRegions();
}

const onNewCnae = (new_cnae) => {
  let i = banks.value.findIndex(b => b.temp_id === new_bank.temp_id || (b.id === new_bank.id && b.id != null));

  if (i != -1) {
    let b = {
      ...banks.value[i],
      ...new_bank
    }

    banks.value.splice(i, 1, b);
  }
  else {
    let i = banks.value.findIndex(b => b.is_default === true);

    let b = {
      ...new_bank,
      is_default: i == -1,
      is_active: true,
      temp_id: _.random(100000, 999999)
    }
    banks.value.push(b);
  }
  closeAllRegions();
}

const save = async () => {
  attemptedSave.value = true;
  if (isValid()) {
    saving.value = true;

    if (!props.id) {
      try {
        let init_data = {
          id: person.value ? person.value.id : null,
          token: token.value,
          name: name.value,
          surname: surname.value,
          e_records: isJuridic.value ? eRecords.value : null,
          is_juridic: isJuridic.value,
          vulnerability_level: socialServices.value ? 1 : 0,
        }
        person.value = await $PersonApiService.save(init_data, true);
      } catch (err) {
        if (err.response?._data?.token === 'TOKEN_ALREADY_EXISTS') {
          toast.error(t('warning_block.TOKEN_ALREADY_EXISTS'))
        }
        saving.value = false;
        return;
      }
    }

    let mapped_addresses = addresses.value.map(address => {
      return {
        address: address.address, // Now this is the full object emitted by AddAddress
        attention_to: address.attention_to,
        is_billing: address.is_billing,
        is_active: address.is_active,
        id: address.id || null,
        person: person.value.id
      }
    })
    let mapped_contacts = contacts.value.map(contact => {
      return {
        phone: contact.phone,
        email: contact.email,
        role: contact.role,
        is_default: contact.is_default,
        is_active: contact.is_active,
        person: person.value.id,
        id: contact.id || null
      }
    });
    let mapped_banks = banks.value.map(pb => {
      return {
        iban: pb.iban,
        iban_save: pb.iban,
        is_default: pb.is_default,
        is_active: pb.is_active,
        name: pb.name,
        dni: pb.dni ? pb.dni : token.value,
        role: pb.role,
        country: pb.country,
        person: person.value.id,
        id: pb.id || null,
        id_save: pb.id || null,
        swift: pb.swift
      }
    });

    let mapped_cnaes = [];

    if (props.id) {
      let current_cnaes = person.value.cnaes || [];


      mapped_cnaes = cnaes.value.map(cnae => {
        return {
          cnae: cnae.id,
          token: current_cnaes.find(pc => pc.cnae.id == cnae.id)?.token || _.random(100000, 999999),
          is_active: cnae.is_active,
          person: null,
          id: current_cnaes.find(pc => pc.cnae.id == cnae.id)?.id || null
        }
      });
    }
    else {
      mapped_cnaes = cnaes.value.map(cnae => {
        return {
          cnae: cnae.id,
          token: _.random(100000, 999999),
          is_active: cnae.is_active,
          person: null
        }
      });
    }


    try {

      let data = {
        id: person.value.id || null,
        name: name.value,
        surname: surname.value,
        token: token.value,
        is_juridic: isJuridic.value,
        vulnerability_level: socialServices.value ? 1 : 0,
        addresses: mapped_addresses,
        contacts: mapped_contacts,
        e_records: isJuridic.value ? eRecords.value : null,
        banks: mapped_banks,
        cnaes: mapped_cnaes,
        identification_type_id: selectedIdentificatorType.value?.id || null
      };
      const result = await $PersonApiService.save(data);

      return navigateTo('/contract/persons/')
    }
    catch (err) {
      console.error(err);
      saving.value = false;
    }

  }
  else {
    saving.value = false;
  }
}
const deletePerson = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    await $PersonApiService.deletePerson(props.id);
    return navigateTo('/contract/persons/')
  }
}

const createCnae = () => {
  bank.value = null;
  openRegion('cnae');
}

const editCnae = (b) => {
  bank.value = b;
  openRegion('cnae');
}
const deleteCnae = (bank) => {
  if (!confirm(t('confirmation_text_block.confirm_delete'))) return;
  const i = cnaes.value.findIndex(b => (b.temp_id != null && b.temp_id == bank.temp_id) || (b.id != null && b.id == bank.id));

  const wasDefault = bank.is_default;

  if (i > -1) {
    cnaes.value.splice(i, 1);

    if (cnaes.value.length > 0 && wasDefault) {
      cnaes.value[0].is_default = true;
    }
  }
}
const createBank = () => {
  bank.value = null;
  openRegion('bank');
}

const editBank = (b) => {
  bank.value = b;
  openRegion('bank');
}
const deleteBank = (bank) => {
  if (!confirm(t('confirmation_text_block.confirm_delete'))) return;
  const i = banks.value.findIndex(b => (b.temp_id != null && b.temp_id == bank.temp_id) || (b.id != null && b.id == bank.id));

  const wasDefault = bank.is_default;

  if (i > -1) {
    banks.value.splice(i, 1);

    if (banks.value.length > 0 && wasDefault) {
      banks.value[0].is_default = true;
    }
  }
}
const createContact = () => {
  contact.value = null;
  openRegion('contact');
}

const editContact = (c) => {
  contact.value = c;
  openRegion('contact');
}
const deleteContact = (con) => {
  if (!confirm(t('confirmation_text_block.confirm_delete'))) return;
  const i = contacts.value.findIndex(c => c.email == con.email && c.phone == con.phone && c.role == con.role);

  const wasDefault = con.is_default;

  if (i > -1) {
    contacts.value.splice(i, 1);

    if (contacts.value.length > 0 && wasDefault) {
      contacts.value[0].is_default = true;
    }
  }
}

const handleIdentificatorTypeChange = (type) => {
  selectedIdentificatorType.value = type;
}

const createAddress = () => {
  address.value = null;
  attention_to.value = '';
  openRegion('address');
}

const editAddress = (ad) => {
  console.log("address");
  console.log(ad);
  address.value = ad.address;
  attention_to.value = ad.attention_to;
  openRegion('address');
}
const deleteAddress = (ad) => {
  if (!confirm(t('confirmation_text_block.confirm_delete'))) return;
  const i = addresses.value.findIndex(a =>
    (a.id && a.id === ad.id) ||
    (a.address?.id && a.address?.id === ad.address?.id) ||
    (a.address?.temp_id && a.address?.temp_id === ad.address?.temp_id)
  );

  const wasBilling = ad.is_billing;

  if (i > -1) {
    addresses.value.splice(i, 1);

    if (addresses.value.length > 0 && wasBilling) {
      addresses.value[0].is_billing = true;
    }
  }
}

const isBillingChange = (item) => {
  addresses.value.forEach(ap => {
    ap.is_billing = false;
  });
  item.is_billing = true;
}
const defaultContactChange = (item) => {
  contacts.value.forEach(c => {
    c.is_default = false;
  });
  item.is_default = true;
}

const defaultBankChange = (item) => {
  banks.value.forEach(c => {
    c.is_default = false;
  });
  item.is_default = true;
}

const setValues = () => {
  token.value = person.value.token;
  name.value = person.value.name;
  surname.value = person.value.surname;
  isJuridic.value = person.value.is_juridic;
  socialServices.value = person.value.vulnerability_level == 1;
  addresses.value = person.value.addresses;
  contacts.value = person.value.contacts;
  banks.value = person.value.banks;
  eRecords.value = person.value.records;
  cnaes.value = person.value.cnaes?.map(pc => pc.cnae)
  selectedIdentificatorType.value = person.value.identification_type;
  console.log("selectedIdentificatorType.value");
  console.log(selectedIdentificatorType.value);
}
const isValid = () => {
  if (token.value == '' || token.value == null) return false;
  if (name.value == '' || name.value == null) return false;
  if (!isJuridic.value && (surname.value == '' || surname.value == null)) return false;

  return true;
}

const openRegion = (region) => {
  closeAllRegions();

  if (region == 'address') {
    editingAddress.value = true;
  }
  else if (region == 'contact') {
    editingContact.value = true;
  }
  else if (region == 'bank') {
    editingBank.value = true;
  }
  else if (region == 'cnae') {
    editingCnae.value = true;
  }

  showRegion.value = true;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const updateCurrentRecord = (e) => {
  console.log("updateCurrentRecord");
  console.log(e);
  currentRecord.value = e.target.value;
  if (eRecords.value.find(r => r.year == currentYear.value)) {
    eRecords.value.find(r => r.year == currentYear.value).e_record = currentRecord.value;
  } else {
    eRecords.value.push({
      year: currentYear.value,
      e_record: currentRecord.value
    })
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const closeAllRegions = () => {
  // tanquem tots els components
  editingAddress.value = false;
  editingContact.value = false;
  editingBank.value = false;
  editingCnae.value = false;
  // tanquem region
  showRegion.value = false;
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($PersonApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getIdentificatorTypes();
  getData()
});

watch(isJuridic, () => {
  if (isJuridic.value) {
    surname.value = '';
  }
});


</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded p-4 bg-white">
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <div class="flex items-center gap-x-2">
            <label class="block text-sm font-medium text-slate-500">{{ t('common.identificator') }}
              <!-- ({{ t('common.person_id') }}) -->
            </label>
            <div v-for="type in identificatorTypes" :key="type.id" class="flex items-center justify-center h-[45px]">
              <button
                class="px-2 text-sm font-medium  border border-transparent rounded-3xl  transition duration-200 ease-in-out"
                @click="handleIdentificatorTypeChange(type)"
                :class="selectedIdentificatorType?.id === type.id ? 'border border-sky-500 bg-sky-50 hover:bg-sky-400 hover:text-white text-sky-600 rounded-3xl font-semibold ring-1 ring-sky-400' : 'text-slate-400 hover:bg-slate-200 hover:border hover:border-slate-200 '">
                {{ type.name }}
              </button>
            </div>
          </div>
          <input type="text" v-model="token" class="input"
            :class="{ 'invalid': attemptedSave && (token == '' || attemptedSave && token == null) }" />
          <p v-if="isDniType && token && !dniIsValid" class="text-amber-600 text-xs mt-1">
            <Icon name="fa6-solid:triangle-exclamation" /> {{ t('warning_block.invalid_dni') }}
          </p>
        </div>
        <div class="mb-2 grid grid-cols-2 gap-3">
          <div class="flex items-center mt-9 ml-2 text-slate-500">
            <input v-model="isJuridic" type="checkbox" id="is_juridic" name="is_juridic" class="checkbox" />
            <label for="is_juridic" class="ml-2"> {{ t('contract_block.is_juridic') }}</label>
          </div>
          <div v-if="!isJuridic" class="flex items-center mt-9 ml-2 text-slate-500">
            <input v-model="socialServices" type="checkbox" id="socialServices" name="socialServices"
              class="checkbox" />
            <label for="socialServices" class="ml-2"> {{ t('contract_block.short_in_social_risk') }}</label>
          </div>
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="name" class="input"
            :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.surname') }}</label>
          <input :disabled="isJuridic" type="text" v-model="surname" class="input"
            :class="{ 'invalid': attemptedSave && !isJuridic && (surname == '' || surname == null) }" />
        </div>
        <div v-if="isJuridic" class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.current_record') }} {{
            currentYear }} ({{ t('common.electronic_invoice') }})</label>
          <input type="text" :value="currentRecord" class="input" @change="updateCurrentRecord" @input="updateCurrentRecord" />
        </div>
        <div v-if="isJuridic" class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.historical_records') }} ({{
            t('common.electronic_invoice') }})</label>
          <div class="flex items-center gap-x-2">
            <input type="text" disabled :value="historicalRecords.length === 0 ? t('common.no_records') : selectedHistoricalRecord?.e_record || ''" class="input flex-1" />
            <v-select class="block w-full custom-select flex-1" :model-value="selectedHistoricalRecord"
              @update:modelValue="selectedHistoricalRecord = $event" :options="historicalRecords" label="year"
              :disabled="historicalRecords.length === 0" />
          </div>
        </div>
        <div class="mb-2 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.addresses') }}</label>

          <div :class="{ 'mt-1': addresses.length == 0 }" class="text-gray-900 rounded shadow">
            <div v-if="addresses.length > 0"
              class="group grid grid-cols-[100px,2fr,1fr] divide-x text-sm border-b leading-4 ">
              <span class="p-1 pl-2 text-slate-400"> {{ t('contract_block.billing_address_default') }} </span>
              <span class="p-1 pl-2 text-slate-400 flex items-center"> {{ t('address_block.address') }} </span>
              <span class="p-1 pl-2 text-slate-400 flex items-center"> {{ t('contract_block.attention_to') }} </span>
            </div>
            <div v-for="item in addresses"
              class="group grid grid-cols-[100px,2fr,1fr] divide-x text-sm leading-4 border-b transition-all duration-100">
              <div class="p-2 text-slate-800">
                <input type="radio" name="billing" class="ml-2" :value="item.address?.id || item.address?.temp_id"
                  :checked="item.is_billing" @change="isBillingChange(item)" />
              </div>
              <div class="text-slate-500 p-2 w-full">
                {{ item.address?.address_complete }} - {{ item.address?.postal_code }}, {{ item.address?.city_name }}
              </div>
              <div class="relative footering text-slate-500 p-2 w-full">
                {{ item.attention_to }}
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-8 top-1 rounded-md text-slate-600 hover:text-blue-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="editAddress(item)">
                  <Icon name="fa6-solid:pencil" />
                </button>
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="deleteAddress(item)">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering">
              <button @click="createAddress"
                class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
              </button>
            </div>
          </div>
        </div>

        <div class="mb-2 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.contact') }}</label>

          <div :class="{ 'mt-1': contacts.length == 0 }" class="text-gray-900 rounded shadow">
            <div v-if="contacts.length > 0"
              class="group grid grid-cols-[100px,1fr,1fr,1fr] divide-x text-sm border-b leading-4 ">
              <span class="p-1 pl-2 text-slate-400"> {{ t('default') }} </span>
              <span class="p-1 pl-2 text-slate-400 flex items-center"> {{ t('common.tlf') }} </span>
              <span class="p-1 pl-2 text-slate-400 flex items-center"> {{ t('common.email') }} </span>
              <span class="p-1 pl-2 text-slate-400 flex items-center"> {{ t('common.role') }} </span>
            </div>
            <div v-for="item in contacts"
              class="group grid grid-cols-[100px,1fr,1fr,1fr] divide-x text-sm leading-4 border-b transition-all duration-100">
              <div class="p-2 text-slate-800">
                <input type="radio" name="default" class="ml-2" :value="item.id" :checked="item.is_default"
                  @change="defaultContactChange(item)" />
              </div>
              <div class="footering text-slate-500 p-2">
                {{ item.phone }}
              </div>
              <div class="footering text-slate-500 p-2">
                {{ item.email }}
              </div>
              <div class="footering text-slate-500 p-2 relative w-full">
                {{ item.role }}
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-8 top-1 rounded-md text-slate-600 hover:text-blue-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="editContact(item)">
                  <Icon name="fa6-solid:pencil" />
                </button>
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="deleteContact(item)">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering">
              <button @click="createContact"
                class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
              </button>
            </div>
          </div>
        </div>
        <div class="mb-2 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.bank_data') }}</label>

          <div :class="{ 'mt-1': banks.length == 0 }" class="text-gray-900 rounded shadow">
            <div v-if="banks.length > 0"
              class="group grid grid-cols-[100px,3fr,2fr,1fr,1fr,1fr] divide-x text-sm border-b leading-4 ">
              <span class="p-1 pl-2 flex items-center text-slate-400"> {{ t('default') }} </span>
              <span class="p-1 pl-2 flex items-center text-slate-400">{{ t('common.iban') }}</span>
              <span class="p-1 pl-2 flex items-center text-slate-400">{{ t('contract_block.holder') }}</span>
              <span class="p-1 pl-2 flex items-center text-slate-400">{{ t('common.person_id') }}</span>
              <span class="p-1 pl-2 flex items-center text-slate-400">{{ t('common.role') }}</span>
              <span class="p-1 pl-2 flex items-center text-slate-400">{{ t('common.deactivated') }}</span>
            </div>
            <div v-for="item in banks"
              class="group grid grid-cols-[100px,3fr,2fr,1fr,1fr,1fr] divide-x text-sm leading-4 border-b transition-all duration-100">
              <div class="p-2 text-slate-800" :class="{ 'opacity-50': !item.is_active }">
                <input :disabled="!item.is_active" type="radio" name="default_bank" class="ml-2" :value="item.id"
                  :checked="item.is_default" @change="defaultBankChange(item)" />
              </div>
              <div class="footering text-slate-500 p-2" :class="{ 'opacity-50': !item.is_active }">
                <!-- {{ item.iban?.match(/.{1,4}/g).join(' ').toUpperCase() }} -->
                <AtomsIBAN :value="item.iban" />
              </div>
              <div class="footering text-slate-500 p-2" :class="{ 'opacity-50': !item.is_active }">
                {{ item.name }}
              </div>
              <div class="footering text-slate-500 p-2" :class="{ 'opacity-50': !item.is_active }">
                {{ item.dni }}
              </div>
              <div class="footering text-slate-500 p-2" :class="{ 'opacity-50': !item.is_active }">
                {{ item.role }}
              </div>
              <div class="footering text-slate-500 p-2 relative w-full">
                {{ item.deactivated_at ? formatDateTime(item.deactivated_at) : '-' }}
                <button v-if="item.is_active"
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-8 top-1 rounded-md text-slate-600 hover:text-blue-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="editBank(item)">
                  <Icon name="fa6-solid:pencil" />
                </button>
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="deleteBank(item)">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering">
              <button @click="createBank"
                class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
              </button>
            </div>
          </div>
        </div>
        <div class="mb-2 col-span-2" v-if="isJuridic">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('contract_block.cnae_codes') }}</label>

          <div :class="{ 'mt-1': cnaes.length == 0 }" class="text-gray-900 rounded shadow">
            <div v-if="cnaes.length > 0" class="group grid grid-cols-[1fr,3fr] divide-x text-sm border-b leading-4 ">
              <span class="p-1 pl-2 flex items-center text-slate-400"> {{ t('common.code') }} </span>
              <span class="p-1 pl-2 flex items-center text-slate-400"> {{ t('common.description') }} </span>
            </div>
            <div v-for="item in cnaes"
              class="group grid grid-cols-[1fr,3fr] divide-x text-sm leading-4 border-b transition-all duration-100">
              <div class="footering text-slate-500 p-2">
                {{ item.token }}
              </div>
              <div class="footering text-slate-500 p-2 relative w-full">
                {{ item.description }}
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="deleteCnae(item)">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering">
              <button @click="createCnae"
                class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
              </button>
            </div>
          </div>
        </div>
      </div>
      <div class="flex flex-row-reverse mt-4">
        <button v-if="person != null" @click="deletePerson" :disabled="saving" class="button-default mx-5">
          &nbsp; {{ $t('common.delete') }}</button>
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}
        </button>
      </div>
    </div>
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddAddress :selectedAddress="address" :isSubRegion="true" :isSubRegionOpen="isSubRegionOpen"
          @new-address="onNewAddress" @show-subregion="handleSubRegionEvent" v-if="editingAddress">
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t("contract_block.attention_to") }}</label>
            <input maxlength="50" type="text" v-model="attention_to" class="input" />
          </div>
        </AddAddress>
        <AddContact :selectedContact="contact" @new-contact="onNewContact" v-if="editingContact" />
        <AddBank :selectedBank="bank" :defaultPerson="person" @new-bank="onNewBank" v-if="editingBank" />
        <AddCnae v-model="cnaes" @new-cnae="onNewCnae" v-if="editingCnae" />
      </div>
    </div>
  </div>
</template>