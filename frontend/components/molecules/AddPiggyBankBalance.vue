<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';

const { t } = useI18n();
const toast = useToast();
const { $ContractApiService, $ConfiglistApiService, $PersonApiService } = useNuxtApp();

const props = defineProps({
  id: Number,
  contractId: Number,
  personId: Number,
  data: Object,
});

const emit = defineEmits(['close', 'change']);

const amount = ref(null);
const movement_date = ref(new Date().toISOString().split('T')[0]);
const payment_method = ref(null);
const attemptedSave = ref(false);

const methods = ref([]);

const loading = ref(false);
const loadingMethods = ref(false);

const getPaymentMethods = async () => {
  loadingMethods.value = true;
  try {
    const response = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    response.results.forEach(method => {
      if (
        method.token != 'BALANCE' &&
        method.token != 'DIRECT_DEBIT' &&
        method.token != 'TPV_ONLINE'
      ) {
        methods.value.push({
          value: method.id,
          label: method.name,
        });
      }
    });
  } catch (error) {
    console.error(error);
  } finally {
    loadingMethods.value = false;
  }
};

const save = async () => {
  attemptedSave.value = true;
  if (!amount.value || amount.value <= 0 || !payment_method.value || !movement_date.value) return;

  loading.value = true;
  try {
    const save_data = {
      amount: amount.value,
      movement_date: movement_date.value,
      payment_method_id: payment_method.value?.value,
    };
    if (props.personId) {
      await $PersonApiService.addBalance(props.personId, save_data);
    } else {
      await $ContractApiService.addBalance(props.contractId, save_data);
    }
    toast.success(t('common.correct_save'));
    emit('change', true);
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  getPaymentMethods();
});

</script>

<template>
  <div class="region__content px-4 pb-4 pt-2 md:px-6 md:pb-6">
    <div class="mb-4 flex items-center justify-between gap-2">
      <H1Region>
        {{ t('common.add') }} {{ t('contract_block.balance') }}
      </H1Region>

      <div v-if="data"
        class="inline-flex border border-sky-200 items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-600">
        <Icon name="fa6-solid:piggy-bank" class="text-sky-500" />
        <span class="uppercase tracking-wide">
          {{ t('contract_block.available_balance') }}
        </span>
        <span class="text-emerald-600 font-bold">
          {{ formatMoneyWithCurrency(data.amount) }}
        </span>
      </div>
    </div>

    <section class="mt-4 rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <div class="grid md:grid-cols-2 gap-2">

        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
            {{ t('common.payment_method') }}
          </label>
          <v-select class="block w-full custom-select" v-model="payment_method" :options="methods"
            :loading="loadingMethods" :class="{ 'invalid': attemptedSave && !payment_method }" />
        </div>

        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
            for="movement_date_input">
            {{ t('common.date') }}
          </label>
          <input id="movement_date_input" v-model="movement_date" type="date" class="input w-full text-sm"
            :class="{ 'border-red-400 focus:border-red-500': attemptedSave && !movement_date }" />
        </div>
        <div>

          <label class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
            for="add_balance_input">
            {{ t('common.amount') }}
          </label>
          <input id="add_balance_input" v-model="amount" type="number" min="0" step="0.01" :placeholder="'0.00'"
            class="input w-full text-right text-sm"
            :class="{ 'border-red-400 focus:border-red-500': attemptedSave && (!amount || amount <= 0) }" />
        </div>
      </div>
    </section>

    <div class="mt-4 flex justify-end">
      <button class="button-primary flex items-center gap-2"
        :disabled="!amount || amount <= 0 || !payment_method || !movement_date || loading" @click="save">
        <Icon :name="loading ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin mr-2': loading }" />
        {{ t('common.save') }}
      </button>
    </div>
  </div>
</template>
