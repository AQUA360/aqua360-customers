<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import BankDetail from '~/components/molecules/BankDetail.vue';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import PersonBankSelect from './PersonBankSelect.vue';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';

const { t } = useI18n();
const toast = useToast();
const props = defineProps({
  data: Object,
  id: Number, // ID de l'element
  persons: Array,
  isPerson: false
});

const { $PiggyBankApiService, $PersonPiggyBankApiService, $PersonApiService } = useNuxtApp();
const emit = defineEmits(['close']);
const loading = ref(false)
const JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS = [
  'BALANCE',
  'DIRECT_DEBIT',
  'ELECTRONIC_INVOICE',
  'CONFIRMING60',
  'CONFIRMING180',
  'TPV_ONLINE',
];

const localData = ref(props.data ? props.data : null);

const paymentTypeOptionsById = ref([]);

const onPaymentTypesLoaded = ({ byId }) => {
  paymentTypeOptionsById.value = byId;
};

const selectedPaymentType = ref(null);
const selectedBankDebit = ref(null);
const paymentData = ref(null);
const returnAmount = ref(null);
const returnDate = ref(new Date().toISOString().split('T')[0]);

const showRegion = ref(false);
const showRegionComponent = ref(null);
const regionDetailId = ref(null);
const personBanks = ref([])
const markAsPaid = ref(false);

const isBankTransfer = computed(() => paymentTypeOptionsById.value[selectedPaymentType.value]?.token === 'BANK_TRANSFER');

const loadData = async () => {
  try {
    returnAmount.value = props.data.amount;
    selectedPaymentType.value = props.data.contract_payment?.type?.id;
    selectedBankDebit.value = props.data.contract_payment?.IBAN || null;
    paymentData.value = {
      type_id: props.data.contract_payment?.type?.id,
      IBAN: props.data.contract_payment?.IBAN?.id || null,
    }
    await loadPersonBanks();
  } catch (error) {
    console.error(error)
  }
}

const loadPersonBanks = async () => {
  try {
    for (const person of props.persons) {
      const person_id = person?.id ? person.id : person;
      const personBankResponse = await $PersonApiService.getFullDetail(person_id);
      personBanks.value.push(personBankResponse);
    }
  } catch (error) {
    console.error(error)
  }
}

const save = async () => {
  try {
    let save_data = {
      payment_type_id: selectedPaymentType.value,
      bank_debit_id: selectedBankDebit.value ? selectedBankDebit.value.id : null,
      amount: returnAmount.value,
      return_date: returnDate.value,
    }
    if (isBankTransfer.value) {
      save_data.mark_as_paid = markAsPaid.value
    }
    let response = null;
    if (props.isPerson) {
      response = await $PersonPiggyBankApiService.returnMoney(props.id, save_data);
    } else {
      response = await $PiggyBankApiService.returnMoney(props.id, save_data);
    }
    if (response) {
      emit('close');
    }
  } catch (error) {
    console.error(error)
  }
}

const onPersonBankSelected = (bank) => {
  selectedBankDebit.value = bank;
  closeAllRegions();
};

const openPersonBankSelect = () => {
  closeAllRegions();
  showRegionComponent.value = props.company ? 'CompanyBankSelect' : 'PersonBankSelect';
  showRegion.value = true;
};

const showDetail = (component, id) => {
  showRegionComponent.value = component;
  regionDetailId.value = id;
  toggleRegion(true);
}
const closeAllRegions = () => {
  showRegionComponent.value = null;
  regionDetailId.value = null;
  showRegion.value = false;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    showRegionComponent.value = null;
    regionDetailId.value = null;

  }
}

onMounted(async () => {
  await loadData()
})

watch(returnAmount, () => {
  if (returnAmount.value > localData.value.amount) {
    returnAmount.value = localData.value.amount;
    toast.warning(t('warning_block.warning_return_balance'));
  }
})

</script>

<template>
  <div class="h-full">
    <div v-if="loading" class="flex h-full items-center justify-center px-2 py-4">
      <div
        class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-sm text-slate-600 shadow-sm">
        <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500" />
        <span>{{ $t('common.loading') }}...</span>
      </div>
    </div>

    <div v-else-if="localData" class="region__content px-2 py-2">
      <div class="mb-4 flex items-center justify-between gap-2">
        <H1Region>
          {{ $t('common.generate') }} {{ $t('common.return') }}
        </H1Region>

        <div
          class="inline-flex border border-sky-200 items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-600">
          <Icon name="fa6-solid:piggy-bank" class="text-sky-500" />
          <span class="uppercase tracking-wide">
            {{ t('contract_block.available_balance') }}
          </span>
          <span class="text-emerald-600 font-bold">
            {{ formatMoneyWithCurrency(localData.amount) }}
          </span>
        </div>
      </div>

      <section class="rounded-xl border border-slate-200 bg-white/80 px-4 py-4 text-sm shadow-sm md:px-6 md:py-5"
        aria-labelledby="payment_method">
        <div class="mb-3 flex items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div>
            <h2 id="payment_method" class="text-sm font-semibold text-slate-800">
              {{ $t('common.payment_method') }}
            </h2>
            <p class="mt-0.5 text-xs text-slate-500">
              {{ $t('common.select_payment_method') }}
            </p>
          </div>
        </div>

        <div class="max-w-xl">
          <SelectPaymentType v-model="selectedPaymentType" :model-as-number="true" :exclude-tokens="JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS"
            select-class="input w-full text-sm" @loaded="onPaymentTypesLoaded" />
        </div>

        <div
          v-if="paymentTypeOptionsById[selectedPaymentType] && (paymentTypeOptionsById[selectedPaymentType].token == 'DIRECT_DEBIT' || paymentTypeOptionsById[selectedPaymentType].token == 'BANK_TRANSFER')"
          class="mt-4 max-w-xl">
          <p class="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            {{ $t('common.bank_data') }}
          </p>

          <div v-if="selectedBankDebit"
            class="group relative overflow-hidden rounded-lg border border-emerald-100 bg-emerald-50/80 px-4 py-3">
            <BankDetail :item="selectedBankDebit" />
            <button type="button" @click="showDetail('PersonBankSelect', null)"
              class="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-xs text-slate-600 shadow-sm transition-opacity duration-200 group-hover:opacity-100 sm:opacity-0">
              <Icon name="fa6-solid:pencil" />
            </button>
          </div>

          <ButtonSeleccio v-else class="mt-1 w-full justify-center py-2 text-sm"
            @click="showDetail('PersonBankSelect', null)">
            <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
            <span class="ml-1">
              {{ $t('common.select') }} {{ $t('common.iban') }}
            </span>
          </ButtonSeleccio>
        </div>

        <label v-if="isBankTransfer" class="mt-4 flex items-start gap-2 text-sm text-slate-600">
          <input type="checkbox" v-model="markAsPaid" class="mt-0.5" />
          <span>
            {{ $t('billing_block.mark_return_as_paid') }}
            <span class="mt-0.5 block text-xs text-slate-500">
              {{ $t('billing_block.mark_return_as_paid_hint') }}
            </span>
          </span>
        </label>
      </section>

      <section
        class="mt-4 flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm md:flex-row md:items-center md:justify-between">
        <div class="flex items-baseline gap-2">
          <span class="text-xs font-medium uppercase tracking-wide text-slate-500">
            {{ t('billing_block.total_to_return') }}
          </span>
          <div class="flex items-center">
            <input v-model="returnAmount" type="number" min="0" class="input w-28 text-right text-sm" />
          </div>
        </div>

        <div class="flex items-center gap-3">
          <AtomsInputDate v-model="returnDate" :label="t('common.return_date')" class="mb-0" />
        </div>
      </section>

      <div class="mt-4 flex justify-end">
        <button class="button-primary min-w-[8rem] justify-center"
          :disabled="!selectedPaymentType || (!selectedBankDebit && ['DIRECT_DEBIT', 'BANK_TRANSFER'].includes(paymentTypeOptionsById[selectedPaymentType]?.token)) || returnAmount <= 0 || returnDate === '' || returnDate === null"
          @click="save">
          {{ t('common.save') }}
        </button>
      </div>
    </div>
    <div v-if="showRegion" id="subregion" role="region"
      class="fixed top-0 right-0 z-10 h-full w-[90%] overflow-y-auto overflow-x-hidden border-l border-gray-100 bg-white text-base shadow-xl transition-all duration-500 ease-out">
      <div id="region_nav" class="my-3 px-3">
        <button type="button" @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-8 pb-6 pt-2">
        <PersonBankSelect v-if="showRegionComponent === 'PersonBankSelect'"
          :title="`${$t('common.select')} ${$t('common.iban')}`" :persons="personBanks"
          @selected-item="onPersonBankSelected" />
      </div>
    </div>
  </div>
</template>
