<script setup>
// Canvi de la forma de pagament d'un rebut pendent d'un compromís de pagament.
// El servidor torna a validar-ho tot (rebut pendent, fora de remeses pendents...) i
// també canvia el termini del compromís; aquí només es tria la forma i el compte.
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';

const props = defineProps({
  id: Number, // ID del rebut
});
const emit = defineEmits(['changed']);

const { t } = useI18n();
const toast = useToast();
const { $PaymentApiService } = useNuxtApp();

const loading = ref(true);
const saving = ref(false);
const loadError = ref(null);
const saveError = ref(null);
const options = ref(null);

const selectedPaymentType = ref(null);
const selectedCompanyBank = ref(null);
const selectedPersonBank = ref(null);

const paymentTypes = computed(() =>
  (options.value?.payment_types || []).filter(pt => pt.token !== options.value?.current_payment_type_token)
);
const selectedToken = computed(() =>
  paymentTypes.value.find(pt => pt.id == selectedPaymentType.value)?.token || null
);
const isTransfer = computed(() => selectedToken.value === 'BANK_TRANSFER');
const isDirectDebit = computed(() => selectedToken.value === 'DIRECT_DEBIT');
const companyBanks = computed(() => options.value?.company_banks || []);
const personBanks = computed(() => options.value?.person_banks || []);

const canSave = computed(() => {
  if (!options.value?.can_change || !selectedPaymentType.value || saving.value) return false;
  if (isTransfer.value && companyBanks.value.length > 0 && !selectedCompanyBank.value) return false;
  if (isDirectDebit.value && !selectedPersonBank.value) return false;
  return true;
});

watch(selectedPaymentType, () => {
  saveError.value = null;
  selectedCompanyBank.value = companyBanks.value.length === 1 ? companyBanks.value[0].id : null;
  selectedPersonBank.value = personBanks.value.find(b => b.is_default)?.id
    || (personBanks.value.length === 1 ? personBanks.value[0].id : null);
});

const getOptions = async () => {
  loading.value = true;
  loadError.value = null;
  try {
    options.value = await $PaymentApiService.getCommitmentPaymentMethodOptions(props.id);
  } catch (err) {
    console.error(err);
    loadError.value = t('common.error');
  } finally {
    loading.value = false;
  }
};

const save = async () => {
  if (!canSave.value) return;
  if (!confirm(t('confirmation_text_block.confirm_change_commitment_payment_method'))) return;
  saving.value = true;
  saveError.value = null;
  try {
    await $PaymentApiService.changeCommitmentPaymentMethod(props.id, {
      payment_type_id: selectedPaymentType.value,
      company_bank_id: isTransfer.value ? selectedCompanyBank.value : null,
      person_bank_id: isDirectDebit.value ? selectedPersonBank.value : null,
    });
    toast.success(t('common.correct_save'));
    emit('changed');
  } catch (err) {
    console.error(err);
    saveError.value = err?.response?._data?.error || t('common.error');
  } finally {
    saving.value = false;
  }
};

watch(() => props.id, () => {
  selectedPaymentType.value = null;
  getOptions();
});

onMounted(getOptions);
</script>

<template>
  <div>
    <H1Region class="mb-3">{{ t('billing_block.change_commitment_payment_method') }}</H1Region>

    <div v-if="loading" class="flex gap-3 p-1 text-slate-500">
      <Icon name="fa6-solid:spinner" class="animate-spin" /> {{ t('common.loading') }}...
    </div>
    <p v-else-if="loadError" class="px-2 border-l-2 border-red-500 bg-red-100 text-red-600 text-sm">
      {{ loadError }}
      <button @click="getOptions" class="underline ml-2">{{ t('common.load_again') }}</button>
    </p>
    <div v-else-if="options">
      <p v-if="!options.can_change" class="px-2 py-1 border-l-2 border-red-500 bg-red-100 text-red-600 text-sm">
        {{ options.error }}
      </p>
      <template v-else>
        <p class="text-sm text-slate-500 mb-4">{{ t('billing_block.info_change_commitment_payment_method') }}</p>

        <label class="block font-medium text-slate-500" for="commitment_payment_type">{{ t('common.payment_method') }}</label>
        <select id="commitment_payment_type" v-model="selectedPaymentType"
          class="w-full text-base border border-gray-300 rounded p-2 my-2">
          <option :value="null">-- {{ t('common.select') }} {{ t('common.payment_method') }}</option>
          <option v-for="paymentType in paymentTypes" :key="paymentType.id" :value="paymentType.id">
            {{ paymentType.name }}
          </option>
        </select>

        <template v-if="isTransfer && companyBanks.length > 0">
          <label class="block font-medium text-slate-500 mt-2" for="commitment_company_bank">
            {{ t('billing_block.company_bank_account') }}
          </label>
          <select id="commitment_company_bank" v-model="selectedCompanyBank"
            class="w-full text-base border border-gray-300 rounded p-2 my-2">
            <option :value="null">-- {{ t('common.select') }}</option>
            <option v-for="bank in companyBanks" :key="bank.id" :value="bank.id">
              {{ bank.iban }}{{ bank.name ? ` · ${bank.name}` : '' }}
            </option>
          </select>
        </template>

        <template v-if="isDirectDebit">
          <label class="block font-medium text-slate-500 mt-2" for="commitment_person_bank">
            {{ t('billing_block.person_bank_account') }}
          </label>
          <p v-if="personBanks.length === 0" class="text-sm text-red-600 my-2">{{ t('billing_block.no_bank_accounts') }}</p>
          <select v-else id="commitment_person_bank" v-model="selectedPersonBank"
            class="w-full text-base border border-gray-300 rounded p-2 my-2">
            <option :value="null">-- {{ t('common.select') }}</option>
            <option v-for="bank in personBanks" :key="bank.id" :value="bank.id">
              {{ bank.iban }}{{ bank.person ? ` · ${bank.person}` : '' }}
            </option>
          </select>
        </template>

        <p v-if="saveError" class="px-2 py-1 my-2 border-l-2 border-red-500 bg-red-100 text-red-600 text-sm">
          {{ saveError }}
        </p>

        <div class="flex justify-end mt-4">
          <button class="button-primary" :disabled="!canSave" @click="save">
            <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin mr-1" />
            {{ t('common.save') }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
