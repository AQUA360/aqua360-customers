<script setup>
import { ref, watch, computed, nextTick } from 'vue';
const { t } = useI18n();

const props = defineProps({
  value: {
    type: Object,
    default: () => ({}),
  },
  country: {
    type: Object,
    default: () => ({}),
  },
  banks: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['change']);

const ibanRaw = ref('');
const controlFailed = ref(false);
const controlWarning = ref(false);
const detectedCountry = ref(null);
const detectedBank = ref(null);
const touched = ref(false);

const { $AddressApiService } = useNuxtApp();
const errorMessage = ref(t('common.iban_control_error'));
const warningMessage = ref(t('common.warning_foreign'));
const ibanInput = ref(null);

const swift = ref(null);
// Nom de l'entitat segons el registre oficial (schwifty): serveix per avisar quan el banc no és al catàleg
const registryBankName = ref(null);

async function identifySwift(iban) {
  if (iban && iban.length > 8) {
    // We only send the first 12 characters (Country + Check + Bank Code prefix)
    // to avoid sending the full sensitive account number.
    const ibanPrefix = iban.substring(0, 12);
    const result = await $AddressApiService.getSwiftFromIban(ibanPrefix);
    if (result && result.bic) {
      swift.value = result.bic;
    } else {
      swift.value = null;
    }
    registryBankName.value = result?.bank_name || null;
    emitChange();
  }
}

watch(
  () => ibanRaw.value,
  (newIban) => {
    swift.value = null;
    registryBankName.value = null;
    if (newIban && validateIBAN(newIban)) {
      identifySwift(newIban);
    } else {
      emitChange();
    }
  }
);

const ES_IBAN_LENGTH = 24;

function sanitizeIBAN(input) {
  return input
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9]/g, '')
    .toUpperCase();
}

const ibanFormatted = computed({
  get() {
    return ibanRaw.value
      .replace(/\s+/g, '')
      .replace(/(.{4})/g, '$1 ')
      .trim();
  },
  set(val) {
    const clean = sanitizeIBAN(val);
    ibanRaw.value = clean;
  }
});

function validateIBAN(iban) {
  const clean = iban.replace(/\s+/g, '').toUpperCase();

  if (!/^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$/.test(clean)) {
    return false;
  }

  const rearranged = clean.slice(4) + clean.slice(0, 4);

  const expanded = rearranged.replace(/[A-Z]/g, letter =>
    letter.charCodeAt(0) - 55
  );

  let remainder = 0;
  for (let i = 0; i < expanded.length; i += 7) {
    const part = String(remainder) + expanded.substring(i, i + 7);
    remainder = parseInt(part, 10) % 97;
  }

  return remainder === 1;
}

function findSpanishBank(iban) {
  const clean = iban.replace(/\s+/g, '').toUpperCase();
  if (clean.length < 8) return null;
  const bankTokenCut = clean.slice(4, 8);
  const bankToken = bankTokenCut.replace(/^0+/, '');
  // El catàleg pot portar el codi amb zeros a l'esquerra («0081») o sense («81»): es comparen tots dos
  // sense zeros, com fa el backend (`get_spanish_bank_code_candidates`).
  return props.banks.find(b => String(b.token).replace(/^0+/, '') === bankToken) || null;
}

function validateSpanishIBAN(iban) {
  const clean = iban.replace(/\s+/g, '').toUpperCase();
  if (!clean.startsWith('ES')) return false;
  if (clean.length !== ES_IBAN_LENGTH) return false;
  if (!validateIBAN(clean)) return false;

  const bank = findSpanishBank(clean);
  detectedBank.value = bank?.token ?? null;

  return !!bank;
}

function detectCountryFromIBAN(iban) {
  if (!iban || iban.length < 2) return null;
  return iban.slice(0, 2).toUpperCase();
}

function checkControlDigit() {
  const clean = ibanRaw.value.replace(/\s+/g, '').toUpperCase();

  controlFailed.value = false;
  controlWarning.value = false;
  errorMessage.value = t('common.iban_control_error');
  warningMessage.value = t('common.warning_foreign');
  detectedBank.value = null;

  if (!clean) {
    return;
  }

  const countryISO = props.country?.iso_code || null;
  const detected = detectCountryFromIBAN(clean);
  detectedCountry.value = detected;

  if (countryISO === 'ES') {
    if (clean.length < ES_IBAN_LENGTH) {
      controlFailed.value = touched.value;
      errorMessage.value = t('common.min_length_error', { min: ES_IBAN_LENGTH });
      controlWarning.value = false;
      return;
    }

    const generalValid = validateIBAN(clean);
    if (!generalValid) {
      controlFailed.value = touched.value;
      errorMessage.value = t('common.iban_control_error');
      controlWarning.value = false;
      return;
    }

    // Que el banc no sigui al catàleg és una mancança de dades nostra, no un error de l'IBAN
    // (el control ja ha passat): s'avisa però es deixa desar.
    const bankOK = validateSpanishIBAN(clean);
    if (!bankOK && props.banks.length > 0) {
      controlFailed.value = false;
      controlWarning.value = true;
      warningMessage.value = t('common.bank_not_in_catalog', {
        name: registryBankName.value ? ` (${registryBankName.value})` : ''
      });
      return;
    }

    controlFailed.value = false;
    controlWarning.value = false;
    return;
  }

  if (countryISO && detected && countryISO !== detected) {
    controlWarning.value = true;
  } else {
    controlWarning.value = true;
  }

  controlFailed.value = false;
}


function onInput(event) {
  const input = event.target;
  const oldCursor = input.selectionStart;
  const oldValue = input.value;

  // Wait for Vue to update the value through the computed setter/getter
  nextTick(() => {
    const newValue = input.value;
    
    // Calculate new cursor position based on non-space characters preserved
    const charsBefore = oldValue.slice(0, oldCursor).replace(/\s/g, '').length;
    let newCursor = 0;
    let charsFound = 0;
    
    while (charsFound < charsBefore && newCursor < newValue.length) {
      if (newValue[newCursor] !== ' ') {
        charsFound++;
      }
      newCursor++;
    }

    // If we are at a space, and we were typing (not deleting), we move past it
    if (newCursor < newValue.length && newValue[newCursor] === ' ' && oldCursor >= oldValue.length - 1) {
      // optional move forward
    }

    input.setSelectionRange(newCursor, newCursor);
  });

  emitChange();
}

function onPaste(event) {
  const pasted = event.clipboardData.getData('text');
  const clean = sanitizeIBAN(pasted);

  event.preventDefault();

  ibanRaw.value = '';
  nextTick(() => {
    ibanRaw.value = clean;
    emitChange();
  });
}

function emitChange() {
  touched.value = true;
  checkControlDigit();

  emit('change', {
    ...props.value,
    iban: ibanRaw.value,
    detectedCountry: detectedCountry.value,
    detectedBank: detectedBank.value,
    swift: swift.value
  });
}

watch(
  [() => props.value?.iban, () => props.banks],
  ([newIban, newBanks]) => {
    const clean = newIban ? sanitizeIBAN(newIban) : '';
    if (clean !== ibanRaw.value) {
      ibanRaw.value = clean;
    }
    
    checkControlDigit();

    // Emit findings so parent can auto-select country/bank
    if (ibanRaw.value) {
      emitChange();
    }
  },
  { immediate: true }
);

watch(
  () => props.country,
  () => {
    checkControlDigit();
    if (ibanRaw.value) {
      emitChange();
    }
  },
  { deep: true }
);
</script>

<template>
  <div>
    <label for="iban" class="text-slate-500">
      {{ $t('common.iban') }}
    </label>

    <div
      class="border border-gray-300 bg-white rounded-md shadow-sm focus-within:ring-indigo-500 focus-within:border-indigo-500 sm:text-sm"
    >
      <input
        ref="ibanInput"
        id="iban"
        type="text"
        v-model="ibanFormatted"
        @input="onInput"
        @blur="onInput"
        @keyup="onInput"
        @change="onInput"
        @focus="onInput"
        @paste="onPaste"
        placeholder="ES91 2100 0418 4502 0005 1332"
        class="bg-transparent w-full p-2 rounded-md tracking-widest"
      />
    </div>

    <label>
      <abbr
        v-if="controlFailed"
        class="transition-all duration-300 ease text-sm text-red-500 px-2"
      >
        <Icon name="fa6-solid:circle-exclamation" class="text-red-500 text-[12px]" />
        {{ errorMessage }}
      </abbr>

      <abbr
        v-if="!controlFailed && controlWarning"
        class="transition-all duration-300 ease text-sm text-red-500 px-2"
      >
        <Icon name="fa6-solid:triangle-exclamation" class="text-orange-500 text-[12px]" />
        {{ warningMessage }}
      </abbr>
    </label>
  </div>
</template>