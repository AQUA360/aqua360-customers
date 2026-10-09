<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';

import InputIban from '~/components/atoms/InputIban.vue';
import InputSwift from '../atoms/InputSwift.vue';
import H1 from '~/components/atoms/H1.vue';
import { se } from 'date-fns/locale';

const { t } = useI18n();
const { $AddressApiService } = useNuxtApp();
const emit = defineEmits(['new-bank']);

const props = defineProps({
  selectedBank: Object,
  defaultPerson: Object,
  selectedCountry: Object
});

const defaultCountry = ref(null)
const countries = ref([])
const banks = ref([])
const country = ref(null)

const loading_banks = ref(true);
const loading_countries = ref(true);
const loading = ref(true);
const isSwiftAutomatic = ref(false);
// True si el SWIFT l'ha escrit l'usuari o ja venia desat complet: les deteccions automàtiques
// (catàleg o registre oficial) no el trepitgen mentre l'IBAN no canviï.
const swiftManual = ref(false);
let lastIban = null;

// El catàleg de bancs pot portar només el codi d'entitat de 4 lletres ("BSAB"), que no és un BIC.
const isCompleteBic = (bic) => !!bic && [8, 11].includes(String(bic).trim().length);

const selectedBankEntity = ref(null)
const selectedBank = ref(null)
const selectedName = ref(null)
const selectedDni = ref(null)
const selectedRole = ref(null)
const selectedCountry = ref(null)

const assignValues = async () => {
  selectedBank.value = props.selectedBank ? _.cloneDeep(props.selectedBank) : {};
  if (props.selectedBank) {
    selectedName.value = props.selectedBank?.surname ? `${props.selectedBank?.name} ${props.selectedBank?.surname}` : props.selectedBank?.name
    selectedDni.value = props.selectedBank?.dni
    selectedRole.value = props.selectedBank?.role
    if (props.selectedBank?.bank) {
      if (typeof props.selectedBank.bank === 'object') {
        selectedBankEntity.value = {
          code: props.selectedBank.bank.id,
          label: (props.selectedBank.bank.name || '') + ' - ' + (props.selectedBank.bank.token || ''),
          bic: props.selectedBank.bank.bic
        }
      } else {
        selectedBankEntity.value = null;
      }
    } else {
      selectedBankEntity.value = null;
    }
  } else if (props.defaultPerson) {
    selectedName.value = props.defaultPerson?.surname ? `${props.defaultPerson?.name} ${props.defaultPerson?.surname}` : props.defaultPerson?.name
    selectedDni.value = props.defaultPerson?.token
    selectedRole.value = props.defaultPerson?.role
  } else {
    selectedBankEntity.value = null
    selectedName.value = null
    selectedDni.value = null
    selectedRole.value = null
  }
  if (props.selectedCountry) {
    selectedCountry.value = props.selectedCountry;
  }
  if (selectedBank.value.swift) {
    isSwiftAutomatic.value = true;
  }
  swiftManual.value = isCompleteBic(selectedBank.value.swift);
}

const onIbanChanged = (value) => {
  if (value.iban !== undefined) {
    // L'IBAN ha canviat de debò (no és només un focus/blur del camp): el SWIFT anterior ja no li correspon
    if (lastIban && value.iban !== lastIban) {
      swiftManual.value = false;
      selectedBank.value.swift = null;
    }
    lastIban = value.iban;
    selectedBank.value.iban = value.iban;
  }

  if (value.detectedCountry) {
    const foundCountry = countries.value.find(
      c => c.iso_code === value.detectedCountry
    );

    if (foundCountry) {
      country.value = foundCountry;
      selectedBank.value.country = foundCountry.iso_code;
    }
  }

  let foundBank = null;
  if (value.detectedBank) {
    foundBank = banks.value.find(
      b => b.token === value.detectedBank
    );

    if (foundBank) {
      selectedBankEntity.value = foundBank;
      selectedBank.value.control = foundBank.token;
    }
  } else {
    selectedBankEntity.value = null;
    selectedBank.value.control = null;
  }

  // SWIFT automàtic: primer el del registre oficial (value.swift), si no el del catàleg si és complet
  if (!swiftManual.value) {
    const autoSwift = value.swift || (isCompleteBic(foundBank?.bic) ? foundBank.bic : null);
    if (autoSwift) {
      selectedBank.value.swift = autoSwift;
      isSwiftAutomatic.value = true;
    }
  }
};

const onSwiftChanged = (value) => {
  if (value.swift !== undefined) {
    selectedBank.value.swift = value.swift;
    swiftManual.value = !!value.swift;
    isSwiftAutomatic.value = false;
  }
};

const getData = async () => {
  loading.value = true;
  await getCountries();
  await getBanks();

  // If editing, try to match and set the bank option in v-select from the loaded banks
  if (props.selectedBank?.bank) {
    const bankVal = typeof props.selectedBank.bank === 'object' ? props.selectedBank.bank.id : props.selectedBank.bank;
    const foundBank = banks.value.find(b => b.code === bankVal);
    if (foundBank) {
      selectedBankEntity.value = foundBank;
      if (selectedBank.value) {
        selectedBank.value.control = foundBank.token;
        if (!swiftManual.value && isCompleteBic(foundBank.bic)) {
          selectedBank.value.swift = foundBank.bic;
          isSwiftAutomatic.value = true;
        }
      }
    }
  }

  if (props.selectedCountry) {
    await assignValues()
  }
  loading.value = false;
};

const updateSelected = (e) => {
  if (e.entity == 'country') {
    country.value = e.id;
    selectedBank.value.country = country.value.iso_code;

  } else if (e.entity == 'bank') {
    selectedBankEntity.value = e.id;
    selectedBank.value.control = e.id?.token;
    if (isCompleteBic(e.id?.bic)) {
      selectedBank.value.swift = e.id.bic;
      swiftManual.value = false;
      isSwiftAutomatic.value = true;
    }
  }
}

const getCountries = async () => {
  loading_countries.value = true;
  const result = await $AddressApiService.getCountries();

  countries.value = [];

  // country.value = null;

  result.results.forEach(country => {
    if (country.name != '' && country.iso_code != '') {
      countries.value.push({
        label: country.name,
        code: country.id,
        has_iban: country.has_iban,
        iso_code: country.iso_code
      })
      if (country.is_default) {
        defaultCountry.value = {
          label: country.name,
          code: country.id,
          has_iban: country.has_iban,
          iso_code: country.iso_code
        };
      }
    }
  });
  if (props.selectedBank?.country) {
    const searchVal = typeof props.selectedBank.country === 'object' ? props.selectedBank.country.id : props.selectedBank.country;
    const found = countries.value.find(c => c.code === searchVal || c.iso_code === searchVal);
    if (found) {
      country.value = found;
    }
  }
  if (!country.value && defaultCountry.value) {
    country.value = defaultCountry.value;
  }
  if (country.value && selectedBank.value) {
    selectedBank.value.country = country.value.iso_code;
  }
  loading_countries.value = false;
};

const getBanks = async () => {
  try {
    loading_banks.value = true; // Start loading
    const result = await $AddressApiService.getBanks();
    banks.value = [];
    result.forEach(bank => {
      if (bank.name != '') {
        banks.value.push({
          label: bank.name + ' - ' + bank.token,
          code: bank.id,
          bic: bank.bic,
          token: bank.token,
        });
      }
    });
  } catch (er) {
    console.error(er);
  } finally {
    loading_banks.value = false; // Stop loading
  }
};


// saving

const save = async () => {

  const isSpanish = country.value?.iso_code === 'ES';
  if (!selectedBankEntity.value && isSpanish) {
    if (!confirm(t('warning_block.warning_no_bank_selected_continue'))) {
      return;
    }
  }

  let data = {
    ...props.selectedBank,
    name: selectedName.value,
    token: selectedDni.value,
    dni: selectedDni.value,
    role: selectedRole.value,
    iban: selectedBank.value.iban,
    country: country.value?.code,
    account_number: selectedBank.value.account_number,
    swift: selectedBank.value.swift,
    bank: isSpanish ? (selectedBankEntity.value?.code ?? null) : null
  };
  emit('new-bank', data);
}

onMounted(() => {
  getData(),
    assignValues()
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('common.bank_data') }}</H1>
    </div>
    <div class="row">

      <div class="field mb-3">
        <label for="iban" class="text-slate-500">{{ $t('contract_block.holder_name') }}</label>
        <input class="input mt-1" type="text" v-model="selectedName" />
      </div>

      <div class="field mb-3">
        <label for="iban" class="text-slate-500">{{ $t('contract_block.holder_role') }}</label>
        <input class="input mt-1" type="text" v-model="selectedRole" />
      </div>

      <div class="field mb-3">
        <label for="dni" class="text-slate-500">{{ $t('common.person_id') }}</label>
        <input class="input mt-1" type="text" v-model="selectedDni" />
      </div>

      <div class="field mb-3">
        <label for="dni" class="text-slate-500">{{ $t('address_block.country') }}</label>

        <v-select class="block w-full mr-2 required" :disabled="loading_countries || countries.length == 0"
          :model-value="country" @update:modelValue="updateSelected({ entity: 'country', id: $event })"
          :options="countries"></v-select>

      </div>
      <div v-if="country && country.iso_code === 'ES'" class="field mb-3">
        <label class="text-slate-500">{{ $t('common.bank') }}</label>
        <v-select class="block w-full mr-2 required" :disabled="banks.length == 0 || loading_banks"
          :loading="loading_banks" :model-value="selectedBankEntity"
          @update:modelValue="updateSelected({ entity: 'bank', id: $event })" :options="banks">
        </v-select>
      </div>


      <div class="field mb-3 grid grid-cols-2 gap-4">
        <div class="col-span-2">
          <InputIban class="mt-1" :value="selectedBank" :country="country" :disabled="banks.length == 0 || loading_banks"
          :loading="loading_banks" :banks="banks" @change="onIbanChanged" />
        </div>
        <div class="col-span-2">
          <label for="swift" class="text-slate-500">
            {{ $t('common.swift') }}/{{ $t('common.bic') }}
            <span v-if="isSwiftAutomatic && selectedBank?.swift" class="ml-1 text-[10px] text-slate-400 italic">({{ $t('common.swift_from_iban') }})</span>
          </label>
          <InputSwift class="mt-1" :value="selectedBank" @change="onSwiftChanged" />
        </div>
      </div>

    </div>
    <div class="flex flex-row-reverse mt-4">
      <button @click="save" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
          $t('common.save')
        }}
      </button>
    </div>
  </div>
</template>