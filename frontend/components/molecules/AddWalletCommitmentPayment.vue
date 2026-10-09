<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import H1Region from '../atoms/H1Region.vue';
import BankDetail from '~/components/molecules/BankDetail.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonBankSelect from '~/components/molecules/PersonBankSelect.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';
import CompanyBankSelect from '~/components/molecules/CompanyBankSelect.vue';

const props = defineProps({
  id: Number,
});

const { t } = useI18n();
const emit = defineEmits(['change']);
const { $CommitmentDepositApiService, $PaymentCommitmentApiService, $ConfigProjectApiService, $ExploitationApiService, $ContractApiService } = useNuxtApp();

/* ────────────────────────────────────────────────────────────────────────────
   ESTATS BÀSICS
───────────────────────────────────────────────────────────────────────────── */
const loading = ref(true);
const error = ref(null);
const saving = ref(false);
const attemptedSave = ref(false);
const cancelStatusDepositToken = ref(null);
const paidStatusDepositToken = ref(null);

/* ────────────────────────────────────────────────────────────────────────────
   DADES PENDENTS DE COBRAR
───────────────────────────────────────────────────────────────────────────── */
const depositData = ref(null);
const depositGuidePayments = ref([]);
const persons = ref([]);

/* ────────────────────────────────────────────────────────────────────────────
   ESTAT PER FILA DE LA TAULA
───────────────────────────────────────────────────────────────────────────── */
const rowStates = reactive({});

const ensureRowState = (payment) => {
  if (!rowStates[payment.id]) {
    rowStates[payment.id] = {
      checked: false,
      paymentDate: payment.wallet_payment_date || (payment.payment_date ? payment.payment_date.split('T')[0] : null),
    };
  }
  return rowStates[payment.id];
};

/* ────────────────────────────────────────────────────────────────────────────
   MÈTODE DE PAGAMENT GLOBAL + IBAN
───────────────────────────────────────────────────────────────────────────── */
const paymentTypeOptionsById = ref([]);
const selectedPaymentMethod = ref(null);

const onPaymentTypesLoaded = ({ byId }) => {
  paymentTypeOptionsById.value = byId;
};
const selectedBankDebit = ref(null);
const selectedCompanyBankDebit = ref(null);
const companyBanks = ref([]);

const localCompany = ref(null);

const resolvedCompany = computed(() => {
  if (localCompany.value) {
    return {
      ...localCompany.value,
      company_banks: companyBanks.value?.length ? companyBanks.value : localCompany.value.company_banks
    };
  }
  const d = depositData.value?.results ? depositData.value.results[0] : depositData.value;
  let comp = d?.contract?.company || d?.contract?.exploitation?.company || d?.company;
  if (comp && typeof comp === 'object') {
    return {
      ...comp,
      company_banks: companyBanks.value?.length ? companyBanks.value : comp.company_banks
    };
  }
  if (companyBanks.value?.length) {
    return {
      name: t('company'),
      company_banks: companyBanks.value
    };
  }
  return null;
});

/* ────────────────────────────────────────────────────────────────────────────
   REGION (selector IBAN)
───────────────────────────────────────────────────────────────────────────── */
const showRegion = ref(false);
const showRegionComponent = ref('');

const openPersonBankSelect = () => {
  showRegionComponent.value = 'PersonBankSelect';
  showRegion.value = true;
};

const openCompanyBankSelect = () => {
  showRegionComponent.value = 'CompanyBankSelect';
  showRegion.value = true;
};

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionComponent.value = '';
};

const onPersonBankSelected = (bank) => {
  selectedBankDebit.value = bank;
  closeAllRegions();
};

const onCompanyBankSelected = (bank) => {
  selectedCompanyBankDebit.value = bank;
  closeAllRegions();
};

const onSelectPaymentMethod = () => {
  selectedBankDebit.value = null;
  selectedCompanyBankDebit.value = null;
  if (paymentTypeOptionsById.value[selectedPaymentMethod.value]?.token === 'BANK_TRANSFER') {
    if (companyBanks.value?.length === 1) {
      selectedCompanyBankDebit.value = companyBanks.value[0];
    } else if (companyBanks.value?.length > 1) {
      openCompanyBankSelect();
    }
  }
};

/* ────────────────────────────────────────────────────────────────────────────
   FETCH: DADES DEL COMMITMENT
───────────────────────────────────────────────────────────────────────────── */
const getData = async () => {
  loading.value = true;
  try {
    const data = await $CommitmentDepositApiService.getDetail(props.id);
    depositData.value = data;
    persons.value = [data.contract.holder];
    console.log(data.contract);
    if (data.contract.owner) {
      persons.value.push(data.contract.owner);
    }
    if (data.contract.tenant) {
      persons.value.push(data.contract.tenant);
    }

    const d = data?.results ? data.results[0] : data;
    let compId = 
      (typeof d?.contract?.company === 'object' ? d?.contract?.company?.id : d?.contract?.company) || 
      (typeof d?.contract?.exploitation?.company === 'object' ? d?.contract?.exploitation?.company?.id : d?.contract?.exploitation?.company) || 
      (typeof d?.company === 'object' ? d?.company?.id : d?.company);

    if (!compId && d?.contract) {
      let contractId = typeof d.contract === 'object' ? d.contract.id : d.contract;
      if (contractId) {
        try {
          const contractResp = await $ContractApiService.getDetail(contractId);
          const cr = contractResp?.results ? contractResp.results[0] : contractResp;
          let cc = cr?.company;
          if (!cc) {
            let explId = typeof cr?.exploitation === 'object' ? cr?.exploitation?.id : cr?.exploitation;
            if (!explId) {
              const spExpl = cr?.supply_point_default?.exploitation || cr?.supply_point?.exploitation;
              explId = typeof spExpl === 'object' ? spExpl?.id : spExpl;
            }
            if (explId) {
              try {
                const explDetail = await $ExploitationApiService.getDetail(explId);
                cc = explDetail?.company || explDetail?.results?.[0]?.company;
              } catch(e) {
                console.error(e);
              }
            }
          }
          compId = typeof cc === 'object' ? cc?.id : cc;
        } catch(err) {
          console.error(err);
        }
      }
    }
    if (!compId) {
      const lsComp = typeof window !== 'undefined' ? localStorage.getItem('company') : null;
      if (lsComp && lsComp !== 'undefined' && lsComp !== 'null') {
        compId = parseInt(lsComp, 10);
      }
    }
    if (!compId) {
      try {
        const compsResp = await $ExploitationApiService.getCompanies();
        if (compsResp?.results?.length > 0) {
          compId = compsResp.results[0].id;
        }
      } catch (err) {
        console.error(err);
      }
    }
    if (compId) {
      try {
        try {
          const compResp = await $ExploitationApiService.getCompany(compId);
          if (compResp) {
            localCompany.value = compResp;
          }
        } catch(err) {
          console.error(err);
        }
        const banksResp = await $ExploitationApiService.getCompanyBanks(compId);
        companyBanks.value = banksResp?.results || banksResp || [];
      } catch(e) {
        console.error(e);
      }
    }
    if (companyBanks.value?.length === 1 && paymentTypeOptionsById.value[selectedPaymentMethod.value]?.token === 'BANK_TRANSFER' && !selectedCompanyBankDebit.value) {
      selectedCompanyBankDebit.value = companyBanks.value[0];
    }

    await getGuidePayments();
  } catch (err) {
    error.value = err;
  } finally {
    loading.value = false;
  }
};

const getGuidePayments = async () => {
  const pendingStatusToken = await $ConfigProjectApiService.get('payment_commitment_status_pending_token');
  const response = await $PaymentCommitmentApiService.getByDeposit(props.id, true, [pendingStatusToken]);
  depositGuidePayments.value = response.results;
  depositGuidePayments.value.forEach(p => ensureRowState(p));
};

/* ────────────────────────────────────────────────────────────────────────────
   VALIDACIÓ
───────────────────────────────────────────────────────────────────────────── */
const isAnySelected = computed(() =>
  depositGuidePayments.value.some(p => rowStates[p.id].checked)
);

const invalidRows = computed(() =>
  depositGuidePayments.value
    .filter(p => rowStates[p.id].checked && !rowStates[p.id].paymentDate)
    .map(p => p.id)
);

const isPaymentMethodValid = computed(() => selectedPaymentMethod.value != null);

/* ────────────────────────────────────────────────────────────────────────────
   SAVE
───────────────────────────────────────────────────────────────────────────── */
const save = async () => {
  attemptedSave.value = true;

  if (!isAnySelected.value) return;
  if (invalidRows.value.length > 0) return;
  if (!isPaymentMethodValid.value) return;

  if (!confirm(t('confirmation_text_block.confirm_commitment_payment'))) return;

  saving.value = true;

  try {
    const selectedRows = depositGuidePayments.value.filter(p => rowStates[p.id].checked);
    const isDirectDebit = paymentTypeOptionsById.value[selectedPaymentMethod.value]?.token === 'DIRECT_DEBIT';
    const isTransfer = paymentTypeOptionsById.value[selectedPaymentMethod.value]?.token === 'BANK_TRANSFER';

    const payload = {
      payment_type_id: selectedPaymentMethod.value,
      payment_bank: isDirectDebit ? (selectedBankDebit.value?.id || null) : null,
      company_iban: isTransfer ? (selectedCompanyBankDebit.value?.id || null) : null,
      payment_bank_final: isDirectDebit ? (selectedBankDebit.value?.iban || null) : (isTransfer ? (selectedCompanyBankDebit.value?.iban || null) : null),
      payment_swift_final: isDirectDebit ? (selectedBankDebit.value?.swift || null) : (isTransfer ? (selectedCompanyBankDebit.value?.swift || null) : null),
      payments: selectedRows.map(p => ({
        id: p.id,
        wallet_payment_date: rowStates[p.id].paymentDate,
      })),
    };

    await $PaymentCommitmentApiService.saveBulk(payload);

    emit('change');
  } catch (err) {
    console.error(err);
  } finally {
    saving.value = false;
    attemptedSave.value = false;
  }
};

/* ────────────────────────────────────────────────────────────────────────────
   MOUNT
───────────────────────────────────────────────────────────────────────────── */
onMounted(async () => {
  getData();
  cancelStatusDepositToken.value = await $ConfigProjectApiService.get('commitment_deposit_status_cancelled_token');
  paidStatusDepositToken.value = await $ConfigProjectApiService.get('commitment_deposit_status_paid_token');
});

/* ────────────────────────────────────────────────────────────────────────────
   ESTILS TAULA
───────────────────────────────────────────────────────────────────────────── */
const columnClass = 'grid-cols-[40px_minmax(0,1fr)_120px_220px]';
</script>

<template>
  <div class="region__content">

    <!-- LOADING -->
    <div v-if="loading">{{ $t('common.loading') }}...</div>

    <!-- ERROR -->
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <button @click="getData" class="underline text-sky-500">
        {{ $t('common.load_again') }}
      </button>
    </div>

    <!-- CONTINGUT PRINCIPAL -->
    <div v-else>
      <H1Region class="mb-4">{{ $t('billing_block.request_payment') }}</H1Region>

      <!-- TAULA -->
      <div class="text-base">

        <!-- Capçalera -->
        <div :class="['grid', columnClass, 'gap-3', 'border-b', 'pb-2']">
          <span class="text-slate-400">#</span>
          <span class="text-slate-400">{{ t('billing_block.payment') }}</span>
          <span class="text-slate-400">{{ t('common.status') }}</span>
          <span class="text-slate-400">{{ t('common.send_date') }}</span>
        </div>

        <!-- Files -->
        <div v-for="payment in depositGuidePayments" :key="payment.id"
          :class="['grid', columnClass, 'gap-3', 'border-b', 'items-center', 'bg-white']">
          <!-- Checkbox -->
          <span class="p-2 border-r">
            <input type="checkbox" v-model="rowStates[payment.id].checked" :disabled="payment.status.token !== '0'" />
          </span>

          <!-- Informació del pagament -->
          <span class="p-2 border-r">
            {{ formatMoneyWithCurrency(payment.amount) }}
            — {{ formatDate(payment.due_date) }}
            <div v-if="payment.status.token !== '0' && payment.payment_type" class="text-xs text-slate-400 mt-1">
              {{ payment.payment_type.name }}
            </div>
          </span>

          <!-- Status -->
          <span class="p-2 border-r flex justify-center">
            <AtomsColorBadge :value="payment.status?.name" :color="payment.status?.color" />
          </span>

          <!-- Data enviament -->
          <span class="p-2">
            <AtomsInputDate v-model="rowStates[payment.id].paymentDate"
              :disabled="!rowStates[payment.id].checked || payment.status.token !== '0'" :class="{
                'invalid': attemptedSave &&
                  rowStates[payment.id].checked &&
                  !rowStates[payment.id].paymentDate
              }" />
          </span>
        </div>
      </div>

      <!-- SELECT GLOBAL MÈTODE DE PAGAMENT -->
      <div class="mt-6 w-[70%]">
        <SelectPaymentType v-model="selectedPaymentMethod" select-class="w-full border p-2 rounded"
          :invalid="attemptedSave && selectedPaymentMethod == null" :model-as-number="true"
          @change="onSelectPaymentMethod" @loaded="onPaymentTypesLoaded" />

        <!-- IBAN (només DIRECT_DEBIT) -->
        <div class="select_bank mt-3 max-w-xl"
          v-if="paymentTypeOptionsById[selectedPaymentMethod]?.token === 'DIRECT_DEBIT'">
          <!-- Si ja hi ha banc -->
          <div v-if="selectedBankDebit" class="bg-green-100 p-4 rounded relative group">
            <BankDetail :item="selectedBankDebit" />
            <button @click="openPersonBankSelect" class="absolute right-3 top-3 w-8 h-8 bg-white shadow-md rounded">
              <Icon name="fa6-solid:pencil" />
            </button>
          </div>

          <!-- Si encara no hi ha banc -->
          <ButtonSeleccio v-else @click="openPersonBankSelect" class="py-3">
            <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
            {{ $t('common.select') }} {{ $t('common.iban') }}
          </ButtonSeleccio>
        </div>

          <!-- IBAN (només BANK_TRANSFER quan hi ha > 1 banc d'empresa) -->
          <div
            class="select_bank mt-3 max-w-xl"
            v-if="paymentTypeOptionsById[selectedPaymentMethod]?.token === 'BANK_TRANSFER' && companyBanks.length > 1"
          >
            <label class="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">{{ $t('common.bank_data') }} ({{ $t('company') }})</label>
            <!-- Si ja hi ha banc d'empresa -->
            <div v-if="selectedCompanyBankDebit" class="bg-sky-50 border border-sky-100 p-4 rounded relative group">
              <BankDetail :item="selectedCompanyBankDebit" />
              <button
                @click="openCompanyBankSelect"
                class="absolute right-3 top-3 w-8 h-8 bg-white shadow-md rounded"
              >
                <Icon name="fa6-solid:pencil" />
              </button>
            </div>
  
            <!-- Si encara no hi ha banc d'empresa -->
            <ButtonSeleccio v-else @click="openCompanyBankSelect" class="py-3">
              <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
              {{ $t('common.select') }} {{ $t('common.iban') }}
            </ButtonSeleccio>
          </div>
      </div>

      <hr class="my-6" />

      <!-- BOTÓ GUARDAR -->
      <div class="flex justify-end">
        <button @click="save" class="button-primary"
          :disabled="saving || depositData?.status?.token === cancelStatusDepositToken || depositData?.status?.token === paidStatusDepositToken">
          <Icon name="fa6-solid:floppy-disk" /> {{ t('common.save') }}
        </button>
      </div>
    </div>

    <!-- REGION LATERAL (SELECTOR IBAN) -->
    <div v-if="showRegion"
      class="fixed top-0 right-0 h-full w-[47%] bg-white border-l transition-transform duration-500 z-10">
      <div class="p-3">
        <button @click="closeAllRegions" class="text-sky-500">
          <Icon name="fa6-solid:angles-right" />
        </button>
      </div>

      <div class="px-10">
        <PersonBankSelect v-if="showRegionComponent === 'PersonBankSelect'"
          :title="`${t('common.select')} ${t('common.iban')}`" :persons="persons"
          @selected-item="onPersonBankSelected" />
          <CompanyBankSelect
            v-if="showRegionComponent === 'CompanyBankSelect'"
            :title="`${t('common.select')} ${t('common.iban')}`"
            :company="resolvedCompany"
            @selected-item="onCompanyBankSelected"
          />
      </div>
    </div>
  </div>
</template>