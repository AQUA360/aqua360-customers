<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import AddCompanyConfig from './AddCompanyConfig.vue';
import CompanyBankRouting from './CompanyBankRouting.vue';
import H1 from '~/components/atoms/H1.vue';
import AddCompanyBanks from './AddCompanyBanks.vue';
import TranslatableNameField from './TranslatableNameField.vue';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const { $ExploitationApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();
const toast = useToast();

const props = defineProps({
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean,
  company_id: Number
});

const emit = defineEmits(['show-subregion', 'new-company', 'close']);

const loadingCompanyTypes = ref(false);

const name = ref('')
const alias = ref('')
const vat = ref('')
const address_id = ref(null)
const address = ref(null)
const logo = ref(null)
const logoUrl = ref('')
const phone = ref('')
const phone2 = ref('')
const email = ref('')
const website = ref('')
const contact_name = ref('')
const contact_phone = ref('')
const contact_email = ref('')
const barcode_ident = ref('')
const supply_code = ref('')
const configInvoiceMainColor = ref('#000000');
const configInvoiceSecondaryColor = ref('#ffffff');
const invoice_main_color = ref('#000000');
const invoice_secondary_color = ref('#ffffff');
const invoice_footer_text = ref('')
const data_protection_law_text = ref('')
const invoice_footer_text_translations = ref([])
const data_protection_law_text_translations = ref([])
const selectedBank = ref(null)
const selectedCompanyType = ref(null)
const banks = ref([])
const companyTypes = ref([])
const is_provider = ref(false)

const config_data = ref(null);

const attemptedSave = ref(false);
const addingAddress = ref(false);
const addingBank = ref(false);
const openConfigRegion = ref(false);
const openRoutingRegion = ref(false);
// L'encaminament només té sentit amb més d'un compte: amb un de sol no hi ha
// res a repartir i la pantalla només afegiria soroll.
const activeBanksCount = computed(() => banks.value.filter(bank => bank.is_active !== false).length);
const openSubRegion = ref(props.isSubRegionOpen);
const saving = ref(false);
const deleteCurrentLogo = ref(false);
const objectPermissions = ref(null);

const getPermissions = async () => {
  try {
    objectPermissions.value = await $ExploitationApiService.getCompanyPermissions();
  } catch (error) {
    console.log(error);
  }
}

const loadConfigInvoiceDefaults = async () => {
  try {
    const main = await $ConfigProjectApiService.get('invoice_main_color');
    const secondary = await $ConfigProjectApiService.get('invoice_secondary_color');
    if (main != null && main !== '') configInvoiceMainColor.value = main;
    if (secondary != null && secondary !== '') configInvoiceSecondaryColor.value = secondary;
  } catch (e) {
    // keep fallback defaults
  }
}


const save = async () => {
  if (isValid()) {
    saving.value = true;
    const selectedOptions = {
      name: name.value,
      alias: alias.value,
      vat: vat.value,
      address: address_id.value,
      phone: phone.value,
      phone2: phone2.value,
      email: email.value,
      website: website.value,
      contact_name: contact_name.value,
      contact_phone: contact_phone.value,
      contact_email: contact_email.value,
      barcode_ident: barcode_ident.value,
      supply_code: supply_code.value || null,
      invoice_main_color: invoice_main_color.value || null,
      invoice_secondary_color: invoice_secondary_color.value || null,
      invoice_footer_text: invoice_footer_text.value || null,
      data_protection_law_text: data_protection_law_text.value || null,
      invoice_footer_text_translations: Object.fromEntries(invoice_footer_text_translations.value.filter((row) => row.name).map((row) => [row.language, row.name])),
      data_protection_law_text_translations: Object.fromEntries(data_protection_law_text_translations.value.filter((row) => row.name).map((row) => [row.language, row.name])),
      type_id: selectedCompanyType.value ? selectedCompanyType.value.value : null,
      company_banks_ids: banks.value.map(b => parseInt(b.id)),
      is_provider: is_provider.value || false
    };

    if (logo.value) {
      selectedOptions.logo = logo.value;
    }

    if (deleteCurrentLogo.value == true) {
      selectedOptions.logo_delete = true;
    }

    let config = null;
    if (config_data.value) {
      try {
        config = await $ExploitationApiService.saveCompanyConfig(config_data.value);
        selectedOptions.config_id = config.id;
      } catch (error) {
        console.error(error);
        config = null;
      }
    }

    let company = null;

    if (props.company_id != null && props.company_id > 0) {
      selectedOptions.id = props.company_id;
      selectedOptions.is_active = true;
      company = await $ExploitationApiService.updateCompany(selectedOptions);
    }
    else {
      company = await $ExploitationApiService.createCompany(selectedOptions);
    }

    // `is_default` viu a CompanyBank, no a Company: el desem a part perquè el
    // compte predeterminat és el que recull tot el que l'encaminament de
    // remeses no assigna a cap altre compte.
    const companyId = company?.id || props.company_id;
    if (companyId && banks.value.length) {
      try {
        const defaultBank = banks.value.find(bank => bank.is_default);
        await $ExploitationApiService.setDefaultCompanyBank(companyId, defaultBank ? defaultBank.id : null);
      } catch (error) {
        console.error(error);
        toast.error(t('common.error'));
      }
    }

    finishAndClose(company);
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}

const getData = () => {
  if (props.company_id != null && props.company_id > 0) {
    $ExploitationApiService.getCompany(props.company_id).then((company) => {
      name.value = company.name;
      alias.value = company.alias;
      vat.value = company.vat;
      website.value = company.website;
      phone.value = company.phone;
      phone2.value = company.phone2;
      email.value = company.email;
      contact_name.value = company.contact_name;
      contact_phone.value = company.contact_phone;
      contact_email.value = company.contact_email;
      barcode_ident.value = company.barcode_ident;
      supply_code.value = company.supply_code;
      invoice_main_color.value = company.invoice_main_color || configInvoiceMainColor.value;
      invoice_secondary_color.value = company.invoice_secondary_color || configInvoiceSecondaryColor.value;
      invoice_footer_text.value = company.invoice_footer_text || '';
      data_protection_law_text.value = company.data_protection_law_text || '';
      invoice_footer_text_translations.value = Object.entries(company.invoice_footer_text_translations || {}).map(([language, name]) => ({ language, name }));
      data_protection_law_text_translations.value = Object.entries(company.data_protection_law_text_translations || {}).map(([language, name]) => ({ language, name }));
      selectedCompanyType.value = company.type ? { value: company.type.id, label: company.type.name } : null;
      is_provider.value = company.is_provider ?? false;
      logoUrl.value = company.logo;

      if (company.address != null) {
        address_id.value = company.address.id;
        address.value = company.address;
      }

      config_data.value = company.config;

    })
      .catch((error) => {
        console.error(error);
      });
  }
  else {
    name.value = null;
    alias.value = null;
    vat.value = null;
    address_id.value = null;
    address.value = null;
    phone.value = null;
    phone2.value = null;
    website.value = null;
    email.value = null;
    contact_name.value = null;
    contact_phone.value = null;
    contact_email.value = null;
    barcode_ident.value = null;
    supply_code.value = null;
    invoice_main_color.value = configInvoiceMainColor.value;
    invoice_secondary_color.value = configInvoiceSecondaryColor.value;
    invoice_footer_text.value = '';
    data_protection_law_text.value = '';
    invoice_footer_text_translations.value = [];
    data_protection_law_text_translations.value = [];
    is_provider.value = false;
  }
}

const getBanks = async () => {
  banks.value = [];
  if (props.company_id) {
    const result = await $ExploitationApiService.getCompanyBanks(props.company_id);
    banks.value = result.results;

  }
}

const getCompanyTypes = async () => {
  loadingCompanyTypes.value = true;
  try {
    companyTypes.value = [];
    const result = await $ConfiglistApiService.getAll('service/company-type');
    result.results.forEach(type => {
      companyTypes.value.push({
        value: type.id,
        label: type.name
      });
    });
  } catch (error) {
    console.error(error);
  } finally {
    loadingCompanyTypes.value = false;
  }
}

const finishAndClose = (company) => {
  if (props.isSubRegionOpen.value) {
    saving.value = false;
    emit('new-company', company);
  } else {
    return navigateTo('/service/companies/')
  }

}

const openRegion = (region) => {
  closeSubRegion()
  switch (region) {
    case 'address':
      addingAddress.value = true;
      break;
    case 'bank':
      addingBank.value = true;
      break;
    case 'config':
      openConfigRegion.value = true;
      break;
    case 'routing':
      // Va en una region pròpia, per sobre del contingut: és una taula ampla i
      // no té sentit que estrenyi el formulari de l'empresa mentre s'hi treballa.
      openRoutingRegion.value = true;
      return;
    default:
      null;
      break;
  }
  showSubRegion()
}

const isValid = () => {
  if (name.value == '') return false;
  if (vat.value == '') return false;
  if (phone.value == '') return false;
  if (email.value == '') return false;
  //if (barcode_ident.value != null && barcode_ident.value.length != 6) return false;
  return true;
}

const newAddress = (new_address) => {
  address_id.value = new_address.id;
  address.value = new_address;

  closeSubRegion();
}


const editAddress = (edit) => {
  if (edit) {
    openRegion('address');
  }
  else {
    address_id.value = null;
    address.value = null;
  }

}

const changeConfig = (config) => {
  config_data.value = config;
  closeSubRegion();
}

const defaultBankChange = (item) => {
  banks.value.forEach(c => {
    c.is_default = false;
  });
  item.is_default = true;
}

const createBank = () => {
  selectedBank.value = null;
  openRegion('bank');
};

const editBank = (bank) => {
  selectedBank.value = bank;
  openRegion('bank');
};

const deleteBank = async (bank) => {
  if (confirm(t("confirmation_text_block.confirm_delete"))) {
    await $ExploitationApiService.deleteCompanyBank(bank.id)
    getData()
    getBanks()
  }
}

const newBank = (bank) => {
  const index = banks.value.findIndex(b => b.id === bank.id);
  if (index !== -1) {
    banks.value[index] = bank;
  } else {
    banks.value.push(bank);
  }
  closeSubRegion();
};

const updateLogo = (new_logo) => {
  logo.value = new_logo;
  deleteCurrentLogo.value = false;
}

const deleteLogo = () => {
  logo.value = null;
  logoUrl.value = null;
  deleteCurrentLogo.value = true;
}

const closeSubRegion = function () {
  addingAddress.value = false;
  addingBank.value = false;
  openConfigRegion.value = false;
  openRoutingRegion.value = false;
  openSubRegion.value = false;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  openSubRegion.value = true;
  emit('show-subregion', true);
}

const deleteCompany = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete_company'))) {
    saving.value = true;
    await $ExploitationApiService.deleteCompany(props.company_id)
    return navigateTo('/service/companies/')
  }
}

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close');
  }
  await loadConfigInvoiceDefaults();
  getData();
  getBanks();
  getCompanyTypes();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  openSubRegion.value = newValue;
});
watch(() => props.company_id, (newValue) => {
  getData();
});

</script>

<template>
  <div class="region__content h-full">
    <div v-if="objectPermissions" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !props.isSubRegion, 'mr-[48vw]': openSubRegion }">
      <div class="flex justify-between items-center mb-2">
        <H1 class="flex items-center gap-2">
          {{ props.company_id > 0 ? `${$t('common.modify')} ${t('company')}` : $t('service_block.new_company') }}
          <abbr v-if="!config_data" :title="t('service_block.missing_company_config')">
            <Icon name="fa6-solid:circle-info" class="text-orange-600 opacity-70 text-lg" />
          </abbr>
        </H1>
        <button @click="openRegion('config')" class="flex items-center gap-2">
          <span class="text-sm text-slate-500">
            {{ t('common.settings') }}
          </span>
          <Icon name="fa6-solid:gear" class="text-slate-500 text-lg hover:text-slate-800" />
        </button>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.fiscal_name') }} *</label>
          <input required type="text" v-model="name" :class="{ 'invalid': attemptedSave && name == '' }"
            class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.alias') }}</label>
          <input type="text" v-model="alias" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.vat') }} *</label>
          <input type="text" v-model="vat" :class="{ 'invalid': attemptedSave && vat == '' }" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.supply_code') }}</label>
          <input type="text" v-model="supply_code" class="input" />
        </div>
        <!-- <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.barcode_ident') }} *</label>
          <input type="text" v-model="barcode_ident"
          :class="{ 'invalid': attemptedSave && (barcode_ident != null && barcode_ident.length != 6) }"
          class="input" />
        </div> -->
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.regime') }}</label>
          <v-select class="block w-full mr-1 custom-select" v-model="selectedCompanyType" :options="companyTypes"
            :loading="loadingCompanyTypes" />
        </div>

        <div class="mb-2">
          <label for="logo" class="block text-sm font-medium text-slate-500">{{ t('service_block.logo') }}</label>
          <AtomsInputImage @update="updateLogo" @delete="deleteLogo" :uploaded="logoUrl" :parentId="props.company_id" />
        </div>
        <div class="mb-2 self-start">
          <label for="is_provider" class="flex cursor-pointer select-none items-center gap-2.5">
            <input v-model="is_provider" type="checkbox" id="is_provider" name="is_provider"
              class="checkbox size-4 shrink-0" />
            <span class="text-sm font-medium leading-normal text-slate-500">{{ t('service_block.is_provider') }}</span>
          </label>
        </div>
        <hr class="mb-2 col-span-2" />
        <div class="mb-2 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.address') }} *</label>
          <div class="footering text-gray-900 rounded shadow" v-if="address_id == null">
            <button @click="openRegion('address')" :class="{ 'invalid': attemptedSave && address_id == null }"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('address_block.assign_address') }}
            </button>
          </div>
          <div class="relative group footering text-slate-500 rounded shadow p-2" v-else v-if="address != null">
            {{ address.address_complete }}
            <button
              class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-8 top-1 rounded-md text-slate-600 hover:text-blue-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
              @click="editAddress(true)">
              <Icon name="fa6-solid:pencil" />
            </button>
            <button
              class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
              @click="editAddress(false)">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.customer_service_tlf') }} *</label>
          <input type="text" v-model="phone" :class="{ 'invalid': attemptedSave && phone == '' }" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.breakdowns_tlf') }}</label>
          <input type="text" v-model="phone2" class="input" />
        </div>
        <div class="mb-2 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.email_long') }} *</label>
          <input type="email" placeholder="example@example.com" v-model="email"
            :class="{ 'invalid': attemptedSave && email == '' }" class="input" v-validate-email />
        </div>
        <div class="mb-2 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.web_page') }} *</label>
          <input type="text" v-model="website" class="input" />
        </div>
        <hr class="mb-2 col-span-2" />
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.contact_name') }}</label>
          <input type="text" v-model="contact_name" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.contact_tlf') }}</label>
          <input type="text" v-model="contact_phone" class="input" />
        </div>
        <div class="mb-4 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.contact_email') }}</label>
          <input type="text" v-model="contact_email" class="input" />
        </div>
        <hr class="mb-2 col-span-2" />
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.invoice_main_color') }}</label>
          <div class="flex items-center gap-2">
            <input type="color" v-model="invoice_main_color" class="h-9 w-14 cursor-pointer rounded border border-slate-300 p-0.5" />
            <input type="text" v-model="invoice_main_color" class="input flex-1 font-mono text-sm" placeholder="#000000" maxlength="7" />
          </div>
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.invoice_secondary_color') }}</label>
          <div class="flex items-center gap-2">
            <input type="color" v-model="invoice_secondary_color" class="h-9 w-14 cursor-pointer rounded border border-slate-300 p-0.5" />
            <input type="text" v-model="invoice_secondary_color" class="input flex-1 font-mono text-sm" placeholder="#ffffff" maxlength="7" />
          </div>
        </div>
        <div class="mb-4 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.invoice_footer_text') }}</label>
          <textarea v-model="invoice_footer_text" rows="4" class="input" :placeholder="t('billing_block.invoice_footer_text_placeholder')"></textarea>
          <TranslatableNameField v-model="invoice_footer_text_translations"
            :label="`${t('common.translations')} - ${t('billing_block.invoice_footer_text')}`" multiline />
        </div>
        <div class="mb-4 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.data_protection_law_text') }}</label>
          <textarea v-model="data_protection_law_text" rows="4" class="input" :placeholder="t('billing_block.data_protection_law_text_placeholder')"></textarea>
          <TranslatableNameField v-model="data_protection_law_text_translations"
            :label="`${t('common.translations')} - ${t('billing_block.data_protection_law_text')}`" multiline />
        </div>
      </div>
      <hr class="mb-2 col-span-2" />
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.bank_data') }}</label>
        <div class="mx-20 mt-2 border border-slate-200">
          <div class="">
            <div class="grid grid-cols-[100px,2fr,1fr,1fr] divide-x text-xs font-medium uppercase tracking-wide text-slate-500 bg-slate-50 border-b">
              <div class="p-2">{{ $t('billing_block.by_default') }}</div>
              <div class="p-2">{{ $t('common.iban') }}</div>
              <div class="p-2">{{ $t('common.swift') }}</div>
              <div class="p-2">{{ $t('common.bank') }}</div>
            </div>
            <div v-for="item in banks"
              class="group grid grid-cols-[100px,2fr,1fr,1fr] divide-x text-sm leading-4 border-b transition-all duration-100 items-center"
              :class="item.is_default ? 'bg-sky-50' : ''">
              <div class="p-2 text-slate-800 flex items-center gap-2">
                <input type="radio" name="default_bank" class="ml-2" :value="item.id" :checked="item.is_default"
                  @change="defaultBankChange(item)" />
                <Icon v-if="item.is_default" name="fa6-solid:circle-check" class="text-sky-600" />
              </div>
              <div class="footering text-slate-500 p-2 ">
                <!-- {{ item.iban?.match(/.{1,4}/g).join(' ').toUpperCase() }} -->
                <div class="flex items-center justify-between gap-2">
                  <span class="flex items-center gap-2">
                    <AtomsIBAN :value="item.iban" />
                    <span v-if="item.is_default"
                      class="text-[11px] font-semibold uppercase tracking-wide text-sky-700 border border-sky-300 bg-sky-100 rounded-md px-1.5 py-0.5 whitespace-nowrap">
                      {{ $t('billing_block.by_default') }}
                    </span>
                  </span>
                  <span v-if="item.is_sepa"
                    class="text-slate-600 text-sm font-semibold italic border border-slate-400 rounded-md px-2 py-1 bg-yellow-50">
                    {{ t('common.sepa') }}
                  </span>
                </div>
              </div>
              <div class="footering text-slate-500 p-2">
                {{ item.swift }}
              </div>
              <div class="footering text-slate-500 p-2 relative w-full">
                {{ item.bank?.name }}
                <button
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
          </div>

          <button @click="createBank"
            class="display-block block w-full px-1 py-1 text-base text-slate-400 hover:bg-slate-200 text-left active:bg-slate-300 ">
            <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_bank_data') }}
          </button>
        </div>
        <p class="mx-20 mt-1 text-xs" :class="banks.length && !banks.some(bank => bank.is_default) ? 'text-amber-700' : 'text-slate-500'">
          {{ banks.length && !banks.some(bank => bank.is_default)
            ? $t('billing_block.info_no_default_bank')
            : $t('billing_block.info_default_bank') }}
        </p>

        <!-- Mapa entitat pagadora -> compte, per repartir les remeses SEPA -->
        <div v-if="company_id ? activeBanksCount > 1 : true" class="mx-20 mt-2 flex justify-end">
          <button v-if="company_id" @click="openRegion('routing')" type="button"
            class="flex items-center gap-2 text-sm text-sky-600 hover:text-sky-800">
            <Icon name="fa6-solid:code-branch" />
            {{ $t('billing_block.bank_routing') }}
          </button>
          <span v-else class="text-xs text-slate-400">{{ $t('billing_block.info_routing_after_save') }}</span>
        </div>

      </div>
      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button v-if="company_id" @click="deleteCompany" :disabled="saving" class="button-default mx-5">
          &nbsp; {{ $t('common.delete') }}
        </button>
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->
    </div>

    <div v-if="openSubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': openSubRegion, 'translate-x-full': !openSubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <MoleculesAddAddress :selectedAddress="address" @new-address="newAddress" v-if="addingAddress"
          :isSubRegion="isSubRegionOpen" />
        <AddCompanyBanks :company_id="company_id" :vat="vat" :isSubRegionOpen="isSubRegionOpen" v-if="addingBank"
          :bank="selectedBank" @new-bank="newBank" />
        <AddCompanyConfig :company_id="company_id" :config_data="config_data" v-if="openConfigRegion"
          @change="changeConfig" />
      </div>
    </div>

    <div v-if="openRoutingRegion" role="region" id="routing_region"
      class="fixed top-0 right-0 h-full w-[70vw] max-w-[1200px] border-l border-gray-100 bg-white z-[110] flex flex-col shadow-xl">
      <div class="px-3 pt-2 mb-2">
        <button @click="openRoutingRegion = false"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-6 flex-1 overflow-y-auto pb-10">
        <CompanyBankRouting :company_id="company_id" />
      </div>
    </div>
  </div><!-- end wrapper -->
</template>

<style scoped>
.selected {
  margin-left: 15px
}
</style>