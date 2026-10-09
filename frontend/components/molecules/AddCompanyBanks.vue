<script setup>
import { ref, onMounted, watch } from 'vue';
import H1Region from '../atoms/H1Region.vue';
import _ from 'lodash';

import InputIban from '~/components/atoms/InputIban.vue';
import InputSwift from '../atoms/InputSwift.vue';

const { t } = useI18n();

const props = defineProps({
  isSubRegionOpen: Boolean,
  company_id: Number,
  bank: Object,
  vat: String
});

const emit = defineEmits(['show-subregion', 'new-bank']);
const { $ExploitationApiService, $AddressApiService } = useNuxtApp();

const company = ref(null);
const company_vat = ref(null);
const bank_instance = ref(null);

const iban = ref(null);
const swift = ref(null);
const account_number = ref(null);
const bank_data = ref({});
const is_sepa = ref(false);
const sepa_cred_identifier = ref('CCZZXXXAAAAAAAAA');
const barcode_cif = ref(null);
const barcode_suffix = ref('501');
const selectedCountry = ref(null);
const selectedBank = ref(null);

const banks = ref([]);
const countries = ref([]);
const defaultCountry = ref(null);

const attemptedSave = ref(false);
const openSubRegion = ref(props.isSubRegionOpen);
const showRegion = ref(false);
const saving = ref(false);

const loading_banks = ref(true);
const loading_countries = ref(true);
const isSwiftAutomatic = ref(false);
// True si el SWIFT l'ha escrit l'usuari o ja venia desat complet: les deteccions automàtiques
// (catàleg o registre oficial) no el trepitgen mentre l'IBAN no canviï.
const swiftManual = ref(false);
let lastIban = null;

// El catàleg de bancs pot portar només el codi d'entitat de 4 lletres ("BSAB"), que no és un BIC.
const isCompleteBic = (bic) => !!bic && [8, 11].includes(String(bic).trim().length);

const save = async () => {
  if (!selectedBank.value) {
    if (!confirm(t('warning_block.warning_no_bank_selected_continue'))) {
      return;
    }
  }

  if (isValid()) {
    try {
      saving.value = true;

      const data = {
        id: bank_instance.value ? bank_instance.value.id : null,
        token: (company_vat.value ?? '') + '-' + _.random(1000, 9999),
        company_id: props.company_id ?? null,
        country_id: selectedCountry.value?.code ?? null,
        bank_id: selectedBank.value?.code ?? null,
        iban: bank_data.value?.iban ?? null,
        swift: bank_data.value?.swift ?? null,
        account_number: bank_data.value?.account_number ?? null,
        is_sepa: is_sepa.value,
        sepa_cred_identifier: sepa_cred_identifier.value,
        barcode_cif: barcode_cif.value,
        barcode_suffix: barcode_suffix.value
      };

      const new_bank = await $ExploitationApiService.saveCompanyBank(data);
      emit('new-bank', new_bank);
    } catch (er) {
      console.error(er);
    } finally {
      saving.value = false;
    }
  } else {
    attemptedSave.value = true;
    saving.value = false;
  }
};

const getData = async () => {
  bank_instance.value = props.bank ?? null;
  company_vat.value = props.vat ?? null;
  bank_data.value = bank_instance.value
    ? {
        swift: props.bank?.swift ?? null,
        iban: props.bank?.iban ?? null,
        account_number: props.bank?.account_number ?? null
      }
    : {};

  if (props.company_id != null && props.company_id > 0) {
    try {
      const result = await $ExploitationApiService.getCompany(props.company_id);
      company.value = result;
    } catch (er) {
      console.error(er);
    }
  }

  if (props.bank?.bank) {
    selectedBank.value = {
      code: props.bank.bank.id,
      label: props.bank.bank.name + ' - ' + (props.bank.bank.token ?? ''),
      bic: props.bank.bank.bic,
      token: props.bank.bank.token
    };
  }

  is_sepa.value = props.bank?.is_sepa ?? false;
  barcode_cif.value = props.bank?.barcode_cif ?? null;
  barcode_suffix.value = props.bank?.barcode_suffix ?? '501';
  sepa_cred_identifier.value = props.bank?.sepa_cred_identifier ?? null;
  if (bank_data.value.swift) {
    isSwiftAutomatic.value = true;
  }
  swiftManual.value = isCompleteBic(bank_data.value.swift);
  lastIban = null;
};

const getCountries = async () => {
  try {
    loading_countries.value = true;
    const result = await $AddressApiService.getCountries();
    countries.value = [];

    result.results.forEach(country => {
      if (country.name !== '' && country.iso_code !== '') {
        const node = {
          label: country.name,
          code: country.id,
          has_iban: country.has_iban,
          iso_code: country.iso_code
        };
        countries.value.push(node);

        if (country.is_default) {
          defaultCountry.value = node;
        }
      }
    });

    if (defaultCountry.value) {
      selectedCountry.value = defaultCountry.value;
    }
  } catch (er) {
    console.error(er);
  } finally {
    loading_countries.value = false;
  }
};

const getBanks = async () => {
  try {
    loading_banks.value = true;
    const result = await $AddressApiService.getBanks();
    banks.value = [];
    result.forEach(bank => {
      if (bank.name !== '') {
        banks.value.push({
          label: bank.name + ' - ' + bank.token,
          code: bank.id,
          bic: bank.bic,
          token: bank.token
        });
      }
    });
  } catch (er) {
    console.error(er);
  } finally {
    loading_banks.value = false;
  }
};

const onIbanChanged = (value) => {
  const newIban = value?.iban ?? null;
  // L'IBAN ha canviat de debò (no és només un focus/blur del camp): el SWIFT anterior ja no li correspon
  if (lastIban && newIban !== lastIban) {
    swiftManual.value = false;
    swift.value = null;
    bank_data.value.swift = null;
  }
  lastIban = newIban;
  iban.value = newIban;
  bank_data.value.iban = newIban;

  if (value?.detectedCountry) {
    const foundCountry = countries.value.find(c => c.iso_code === value.detectedCountry);
    if (foundCountry) {
      selectedCountry.value = foundCountry;
      bank_data.value.country = foundCountry.iso_code;
    }
  }

  let foundBank = null;
  if (value?.detectedBank) {
    foundBank = banks.value.find(b => b.token === value.detectedBank);
    if (foundBank) {
      selectedBank.value = foundBank;
      bank_data.value.control = foundBank.token;
    }
  } else {
    selectedBank.value = null;
    bank_data.value.control = null;
  }

  // SWIFT automàtic: primer el del registre oficial (value.swift), si no el del catàleg si és complet
  if (!swiftManual.value) {
    const autoSwift = value?.swift || (isCompleteBic(foundBank?.bic) ? foundBank.bic : null);
    if (autoSwift) {
      swift.value = autoSwift;
      bank_data.value.swift = autoSwift;
      isSwiftAutomatic.value = true;
    }
  }
  if (value?.account_number) {
    account_number.value = value.account_number;
    bank_data.value.account_number = value.account_number;
  }
};

const onSwiftChanged = (value) => {
  swift.value = value?.swift ?? null;
  account_number.value = value?.account_number ?? null;
  bank_data.value.swift = swift.value;
  bank_data.value.account_number = account_number.value;
  swiftManual.value = !!swift.value;
  isSwiftAutomatic.value = false;
};

const updateSelected = (e) => {
  if (e.entity === 'country') {
    selectedCountry.value = e.id;
    bank_data.value.country = e.id.iso_code;
  } else if (e.entity === 'bank') {
    selectedBank.value = e.id;
    bank_data.value.control = e.id?.token;
    if (isCompleteBic(e.id?.bic)) {
      bank_data.value.swift = e.id.bic;
      swiftManual.value = false;
      isSwiftAutomatic.value = true;
    }
  }
};

const isValid = () => {
  const hasIban = !!bank_data.value?.iban && bank_data.value.iban !== '';
  const hasSwift = !!bank_data.value?.swift && bank_data.value.swift !== '';
  if (!selectedCountry.value?.code) return false;
  if (!hasIban && !hasSwift) return false;
  return true;
};

const closeSubRegion = function () {
  openSubRegion.value = false;
  emit('show-subregion', false);
};
const showSubRegion = function () {
  openSubRegion.value = true;
  emit('show-subregion', true);
};

onMounted(async () => {
  await getCountries();
  await getBanks();
  await getData();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  openSubRegion.value = newValue;
});
watch(() => props.company_id, () => {
  getData();
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="pr-5 justify-between mb-2 w-full">
      <div class="transition-all duration-500 ease" :class="{ 'mr-[47%]': openSubRegion }">
        <div class="flex justify-between items-center mb-3" :class="{ 'grid grid-cols-2': openSubRegion }">
          <H1Region>{{ bank_instance ? `${$t('common.modify')} ${t('common.bank')}` : $t('common.new_bank') }}</H1Region>
        </div>

        <div class="field mb-3 grid grid-cols-2 gap-5">
          <div>
            <label class="text-slate-500">{{ $t('address_block.country') }}</label>
            <v-select
              class="block w-full mr-2 required"
              :disabled="loading_countries || countries.length === 0"
              :model-value="selectedCountry"
              @update:modelValue="updateSelected({ entity: 'country', id: $event })"
              :options="countries"
            />
          </div>

          <div v-if="selectedCountry && selectedCountry.iso_code === 'ES'">
            <label class="text-slate-500">{{ $t('common.bank') }}</label>
            <v-select
              class="block w-full mr-2 required"
              :disabled="banks.length === 0 || loading_banks"
              :model-value="selectedBank"
              :loading="loading_banks"
              @update:modelValue="updateSelected({ entity: 'bank', id: $event })"
              :options="banks"
            />
          </div>
        </div>

        <hr class="mb-2 col-span-2" />

        <div v-if="selectedCountry" class="field mb-3 grid grid-cols-2 gap-4">
          <div class="col-span-2">
            <InputIban
              class="mt-1"
              :value="bank_data"
              :country="selectedCountry"
              :banks="banks"
              :loading="loading_banks"
              @change="onIbanChanged"
            />
          </div>
          <div class="col-span-2">
            <label for="swift" class="text-slate-500">
              {{ $t('common.swift') }}/{{ $t('common.bic') }}
              <span v-if="isSwiftAutomatic && bank_data?.swift" class="ml-1 text-[10px] text-slate-400 italic">({{ $t('common.swift_from_iban') }})</span>
            </label>
            <InputSwift class="mt-1" :value="bank_data" @change="onSwiftChanged" />
          </div>
        </div>

        <hr class="mb-2 col-span-2" />

        <!-- SEPA -->
        <div>
          <div class="grid grid-cols-[auto,1fr] gap-5 items-center my-2">
            <label for="checkbox_sepa" class="text-slate-500">{{ $t('common.is_sepa') }}</label>
            <input id="checkbox_sepa" type="checkbox" :checked="is_sepa" class="mr-2" @change="is_sepa = !is_sepa" />
          </div>

          <div class="grid grid-cols-[auto,1fr] gap-5 items-center my-2 w-[60%]">
            <label for="sepa_id" class="text-slate-500">{{ t("common.identification") + ' ' + $t("common.sepa")}}</label>
            <input
              type="text"
              id="sepa_id"
              v-model="sepa_cred_identifier"
              class="p-2 mx-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400"
            />
          </div>
        </div>
        <div>
          <div class="grid grid-cols-[auto,1fr] gap-5 items-center my-2 w-[60%]">
            <label for="barcode_cif" class="text-slate-500">{{ $t('common.barcode_cif') }}</label>
            <input
              type="text"
              id="barcode_cif"
              v-model="barcode_cif"
              class="p-2 mx-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400"
            />
          </div>
          <div class="grid grid-cols-[auto,1fr] gap-5 items-center my-2 w-[60%]">
            <label for="barcode_suffix" class="text-slate-500">{{ $t('common.barcode_suffix') }}</label>
            <input
              type="text"
              id="barcode_suffix"
              v-model="barcode_suffix"
              class="p-2 mx-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400"
            />
          </div>
        </div>

        <hr class="my-2" />
        <div class="flex flex-row-reverse mt-4">
          <button @click="save" class="button-primary" :disabled="saving">
            <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
          </button>
        </div>
      </div>

      <!-- Subregió -->
      <div
        role="region"
        id="subregion"
        v-if="showRegion"
        class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-y-auto overflow-x-hidden fixed top-0 right-0 w-[47%] z-10"
        :class="{ 'translate-x-0': openSubRegion, 'translate-x-full': !openSubRegion }"
      >
        <div id="region_nav" class="mb-3 px-3">
          <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="pl-10"></div>
      </div>
    </div>
  </div>
</template>
