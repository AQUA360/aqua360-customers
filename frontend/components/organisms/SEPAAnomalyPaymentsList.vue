<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import { formatMoneyWithCurrency } from '~/utils/money';
import { formatDate } from '~/utils/date';
import PaymentRegion from '~/components/organisms/PaymentRegion.vue';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import CommitmentDepositRegion from '~/components/organisms/CommitmentDepositRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const props = defineProps({
  payments: {
    type: [Array, Object],
    default: () => ({})
  },
  searchData: {
    type: Object,
    default: null
  },
  isRegion: {
    type: Boolean,
    default: false
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close', 'show-detail', 'change', 'exclude_change']);
const { $PaymentApiService } = useNuxtApp();

const loading = ref(false);
const searchQuery = ref('');
const searchInput = ref(null);
const localAnomalies = ref({});

const loadingPaymentId = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const ANOMALY_KEYS = ['negative_total', 'validate_iban_not', 'validate_nif_not'];

const anomalyGroups = computed(() => {
  const anomalies = localAnomalies.value;
  if (!anomalies || typeof anomalies !== 'object' || Array.isArray(anomalies)) {
    return [];
  }
  return ANOMALY_KEYS
    .filter(key => Array.isArray(anomalies[key]) && anomalies[key].length > 0)
    .map(key => ({
      key,
      label: t(`billing_block.anomaly_${key}`) || key,
      payments: anomalies[key]
    }));
});

const totalPaymentsCount = computed(() => {
  const seen = new Set();
  anomalyGroups.value.forEach(group => {
    group.payments.forEach(p => { if (p?.id) seen.add(p.id); });
  });
  return seen.size;
});

const filterPayments = (payments, query) => {
  if (!query?.trim()) return payments;
  const q = query.trim().toLowerCase();
  return payments.filter(p => {
    const customer = ((p.customer_final || '') + ' ' + (p.customer_token_final || '')).toLowerCase();
    const token = (p.token || '').toLowerCase();
    return customer.includes(q) || token.includes(q);
  });
};

const showDetail = (component, id) => {
  closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-detail', true);
}

const loadPayments = async () => {
  loading.value = true;
  try {
    if (props.searchData) {
      props.searchData.search = searchQuery.value;
      const response = await $PaymentApiService.getSEPAAnomalies(props.searchData);
      if (response && response.anomalies) {
        localAnomalies.value = response.anomalies;
      } else {
        localAnomalies.value = { negative_total: [], validate_iban_not: [], validate_nif_not: [] };
      }
    } else {
      syncAnomalies();
    }
  } catch (error) {
    toast.error(t('Error al carregar els contractes'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};


const excludePayment = async (payment) => {
  let text = props.is_excluded ? t('confirmation_text_block.confirm_include_payment') : t('confirmation_text_block.confirm_exclude_payment');
  if (!confirm(text)) return;

  try {
    let save_data = {
      id: payment.id,
      is_excluded: !payment.is_excluded,
    }
    let response = await $PaymentApiService.save(save_data);
    if (response) {
      toast.success(payment.is_excluded ? t('informative_block.info_include_correct') : t('informative_block.info_exclude_correct'));
      payment.is_excluded = !payment.is_excluded;
      emit('exclude_change', payment);
    }
    
  } catch (error) {
    toast.error(t('common.error'));
    console.error(error);
  } finally {
    loadingPaymentId.value = null;
  }
};

const excludeAllPayments = async () => {
  if (!confirm(t('confirmation_text_block.confirm_exclude_payments'))) return;
  try {
    const searchData = {
      ...props.searchData,
      exclude_all: true
    }
    const response = await $PaymentApiService.getSEPAAnomalies(searchData);
    if (response) {
      toast.success(t('informative_block.info_exclude_correct'));
      loadPayments();
    }
  } catch (error) {
    toast.error(t('common.error'));
    console.error(error);
  }
}


const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null
  regionDetailId.value = null
  emit('show-detail', false);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const syncAnomalies = () => {
  if (props.searchData) return;
  const data = props.payments;
  localAnomalies.value = (data && typeof data === 'object' && !Array.isArray(data))
    ? { negative_total: data.negative_total || [], validate_iban_not: data.validate_iban_not || [], validate_nif_not: data.validate_nif_not || [] }
    : { negative_total: [], validate_iban_not: [], validate_nif_not: [] };
};

const debouncedGetData = debounce((query) => {
  loadPayments(query);
}, 300);

const handleSearch = () => {
  debouncedGetData(searchInput.value);
}

watch(() => props.searchData, loadPayments, { deep: true });
watch(() => props.payments, syncAnomalies, { deep: true });

onMounted(async () => {
  await loadPayments();
  searchInput.value?.focus();
});
</script>

<template>
  <div class="region__content pr-1 w-full">

    <div class="h-full flex flex-col w-full min-w-0 transition-all duration-500 ease" :class="{ 'mr-[50%]': showRegion && !isSubRegionOpen, 'mr-[95%]': showRegion && isSubRegionOpen }">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h3 class="text-base font-semibold text-slate-700">{{ $t('billing_block.payments_list') }}</h3>
        <span class="text-xs text-slate-500">{{ $t('common.total') }}: {{ totalPaymentsCount }}</span>
      </div>

      <div class="flex flex-wrap items-center gap-2 mb-2 justify-between">
        <div class="relative flex-1 min-w-[180px] max-w-sm">
          <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
            <Icon name="fa6-solid:magnifying-glass" class="text-sm" />
          </div>
          <input ref="searchInput" v-model="searchQuery" type="text" @input="handleSearch" id="searchInput"
            :placeholder="`${$t('dashboard.search')} ${$t('common.client')} ${$t('common.or')} ${$t('common.identificator')}`"
            class="pl-8 pr-3 py-1.5 w-full text-sm border border-slate-300 rounded focus:ring-1 focus:ring-slate-400 focus:border-slate-400" />
        </div>

        <div>
          <button class="button-default flex items-center gap-1" @click="excludeAllPayments">
            <Icon name="fa6-solid:ban" class="text-red-600 text-sm" />
            <span class="text-red-600 text-sm">{{ $t('billing_block.exclude_all') }}</span>
          </button>
        </div>
      </div> 

      <div class="flex-1 min-h-0 flex flex-col border border-slate-200 rounded bg-white">
        <div v-if="loading && !totalPaymentsCount" class="flex justify-center items-center flex-1 py-12">
          <AppLoading :text="$t('common.loading')" :size="40" />
        </div>
        <template v-else>
          <div class="overflow-auto flex-1 min-h-0" style="max-height: 80vh;">
            <table class="w-full text-sm border-collapse">
              <thead class="sticky top-0 bg-slate-100 border-b border-slate-200 text-slate-600 font-medium">
                <tr>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ t('billing_block.payment') }}</th>
                  <th class="text-right py-1.5 px-2 whitespace-nowrap">{{ t('common.total') }}</th>
                  <th class="text-left py-1.5 px-2 min-w-0 max-w-[140px]">{{ t('common.client') }}</th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ $t('common.iban') }}</th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ t('billing_block.payment_date') }}</th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ t('common.status') }}</th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ t('invoice') }} / {{ t('claim_block.commitment') }}</th>
                  <th class="w-20 py-1.5 px-1"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="anomalyGroups.length === 0">
                  <td colspan="8" class="py-4 px-2 text-center text-slate-500 text-sm">
                    {{ t('common.no_data_found') }}
                  </td>
                </tr>
                <template v-for="group in anomalyGroups" :key="group.key">
                  <tr v-if="filterPayments(group.payments, searchQuery).length" class="bg-red-100 border-b border-slate-200">
                    <td colspan="8" class="py-2 px-2 font-medium text-slate-700">{{ group.label }}</td>
                  </tr>
                  <tr v-for="(payment, index) in filterPayments(group.payments, searchQuery)" :key="`${group.key}-${payment.id}-${index}`"
                    class="border-b border-slate-100 group"
                  :class="{ 'bg-orange-50': payment.is_excluded }">
                  <td v-if="loadingPaymentId === payment.id" colspan="8"
                    class="py-2 bg-white/95 text-center">
                    <AppLoading :size="24" />
                  </td>
                  <template v-else>
                    <td class="py-1 px-2 align-middle">
                      <button @click="showDetail('PaymentRegion', payment.id)"
                        class="text-slate-700 hover:text-sky-600 underline truncate max-w-[100px] block text-left"
                        :title="`${$t('common.show')} ${$t('common.details')}`">
                        {{ payment.token }}
                      </button>
                    </td>
                    <td class="py-1 px-2 text-right align-middle" :class="{ 'text-red-600': payment.amount == 0 }">
                      {{ formatMoneyWithCurrency(payment.amount) }}
                    </td>
                    <td class="py-1 px-2 truncate max-w-[140px] align-middle" :title="(payment.customer_final || '') + ' ' + (payment.customer_token_final || '')">
                      <span class="font-medium">
                        {{ payment.customer_token_final }} 
                      </span>
                      {{ payment.customer_final }}
                    </td>
                    <td class="py-1 px-2 align-middle">
                      <AtomsIBAN :value="payment.payment_bank" />
                    </td>
                    <td class="py-1 px-2 whitespace-nowrap align-middle">
                      {{ payment.payment_date ? formatDate(payment.payment_date) : '–' }}
                    </td>
                    <td class="py-1 px-2 align-middle">
                      <AtomsColorBadge :color="payment.status?.color" :value="payment.status?.name" />
                    </td>
                    <td class="py-1 px-2 align-middle">
                      <button v-if="payment.invoice" @click="showDetail('InvoiceRegion', payment.invoice.id)"
                        class="text-slate-700 hover:text-sky-600 underline truncate block text-left">
                        {{ payment.invoice.token }}
                      </button>
                      <button v-else-if="payment.commitment_deposit"
                        @click="showDetail('CommitmentDepositRegion', payment.commitment_deposit.id)"
                        class="text-slate-700 hover:text-sky-600 underline truncate block text-left">
                        {{ payment.commitment_deposit.token }}
                      </button>
                      <span v-else class="text-slate-400">–</span>
                    </td>
                    <td class="py-1 px-1 align-middle w-20">
                      <button @click="excludePayment(payment)"
                        class="text-red-600 hover:text-red-800 text-xs flex items-center gap-1 py-0.5 px-1 rounded"
                        :disabled="loadingPaymentId === payment.id"
                        :title="payment.is_excluded ? $t('billing_block.include') : $t('billing_block.exclude')">
                        <Icon :name="payment.is_excluded ? 'fa6-solid:arrow-up-from-bracket' : 'fa6-solid:ban'" class="text-xs" />
                        {{ payment.is_excluded ? $t('billing_block.include') : $t('billing_block.exclude') }}
                      </button>
                    </td>
                  </template>
                </tr>
                </template>
              </tbody>
            </table>
          </div>
          
        </template>
      </div>
    </div>
    <div role="region" :id="isRegion ? 'subregion' : 'right_page'"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 z-10" :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[50%]': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PaymentRegion v-if="showRegionDetailComponent == 'PaymentRegion'" :id="parseInt(regionDetailId)"
          :isSubRegionOpen="isSubRegionOpen" :isSubRegion="isRegion" @show-subregion="handleSubRegionEvent">
        </PaymentRegion>
        <InvoiceRegion v-if="showRegionDetailComponent == 'InvoiceRegion'" :id="parseInt(regionDetailId)"
          :isSubRegionOpen="isSubRegionOpen" :isSubRegion="isRegion" @show-subregion="handleSubRegionEvent">
        </InvoiceRegion>
        <CommitmentDepositRegion v-if="showRegionDetailComponent == 'CommitmentDepositRegion'" :id="parseInt(regionDetailId)"
          :isSubRegionOpen="isSubRegionOpen" :isSubRegion="isRegion" @show-subregion="handleSubRegionEvent">
        </CommitmentDepositRegion>
      </div>
    </div>
  </div>
</template>