<script setup>
import { ref, computed, onMounted, watch } from 'vue';
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
    type: Array,
    default: () => []
  },
  searchData: {
    type: Object,
    default: null
  },
  isRegion: {
    type: Boolean,
    default: false
  },
  is_excluded: {
    type: Boolean,
    default: false
  },
  is_anomaly: {
    type: Boolean,
    default: false
  },
  // Comptes on es pot remesar (els de les empreses seleccionades), per poder
  // canviar a mà el que ha decidit el mapa d'encaminament.
  banks: {
    type: Array,
    default: () => []
  },
  // { id_pagament: id_compte } amb només les excepcions que ha marcat l'usuari.
  // És el que el backend rep com a `bank_assignments`.
  bankAssignments: {
    type: Object,
    default: () => ({})
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close', 'show-detail', 'change', 'exclude_change', 'update:bankAssignments']);

// La columna de compte només té sentit si n'hi ha més d'un on triar.
const showBankColumn = computed(() => props.banks.length > 1);
const columnCount = computed(() => (showBankColumn.value ? 10 : 9));

// `routed_company_bank` és el compte que ha decidit el mapa d'encaminament de
// l'empresa; el valor buit vol dir "el que digui el mapa".
const bankOf = (payment) => {
  const assigned = props.bankAssignments ? props.bankAssignments[payment.id] : null;
  if (assigned != null) return assigned;
  return payment.routed_company_bank != null ? payment.routed_company_bank : '';
};

const setBank = (payment, bankValue) => {
  const next = { ...(props.bankAssignments || {}) };
  if (!bankValue || String(bankValue) === String(payment.routed_company_bank)) {
    // Si es torna al compte que toca per mapa, no cal desar cap excepció: així
    // no queda obsoleta si després es canvia la configuració.
    delete next[payment.id];
  } else {
    next[payment.id] = bankValue;
  }
  emit('update:bankAssignments', next);
};

// Marca les files que l'usuari ha mogut a mà respecte del mapa.
const isOverridden = (payment) => Boolean(props.bankAssignments && props.bankAssignments[payment.id]);
const { $PaymentApiService } = useNuxtApp();

const loading = ref(false);
const searchQuery = ref('');
const searchInput = ref(null);
const localPayments = ref([]);
const expandedContracts = ref(new Set());
const showExcluded = ref(false);

const loadingPaymentId = ref(null);
const serverTotal = ref(0);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

// Funcions per gestionar els contractes expandits
const togglePayment = (payment) => {
  if (expandedContracts.value.has(payment)) {
    expandedContracts.value.delete(payment)
  } else {
    expandedContracts.value.add(payment)
  }
}

const isPaymentExpanded = (payment) => {
  return expandedContracts.value.has(payment)
}

// Funció per mostrar detalls
const showDetail = (component, id) => {
  closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-detail', true);
}

// Carregar els contractes associats a la reclamació
const loadPayments = async () => {
  loading.value = true;
  try {
    if (props.searchData) {
      let payload = { ...props.searchData };
      if (searchQuery.value) {
        payload.search = searchQuery.value;
      }
      payload.page_size = pageSize.value;

      const response = await $PaymentApiService.getSEPAInvoices(payload, currentPage.value);
      if (response && response.results) {
        localPayments.value = response.results;
        serverTotal.value = response.count || 0;
      } else {
        localPayments.value = [];
        serverTotal.value = 0;
      }
    } else {
      localPayments.value = props.payments;
    }
  } catch (error) {
    toast.error(t('Error al carregar els contractes'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// Filtrar els contractes basats en la cerca i l'estat d'exclusió
const filteredPayments = computed(() => {
  let payments = localPayments.value || [];

  /* if (!showExcluded.value) {
    payments = payments.filter(payment => !payment.exclude);
  } */

  // Filtrar per cerca
  if (!searchQuery.value) return payments;

  const query = searchQuery.value.toLowerCase();
  return payments.filter(payment => {
    const fullName = `${payment.invoice ? payment.invoice?.customer_final : payment.commitment_deposit?.customer_final}`.toLowerCase();
    const customerToken = `${payment.invoice ? payment.invoice?.customer_token_final : payment.commitment_deposit?.customer_token_final}`.toLowerCase();
    const token = payment.token?.toLowerCase() || '';

    return fullName.includes(query) ||
      customerToken.includes(query) ||
      token.includes(query);
  });
});

// Ordenació
const sortBy = ref(null);
const sortDesc = ref(false);

const sortedPayments = computed(() => {
  const list = [...filteredPayments.value];
  if (!sortBy.value) return list;

  const getValue = (payment) => {
    switch (sortBy.value) {
      case 'token':
        return payment.token || '';
      case 'amount':
        return Number(payment.amount) || 0;
      case 'client':
        return `${payment.customer_final || ''} ${payment.customer_token_final || ''}`.toLowerCase();
      case 'iban':
        return payment.payment_bank || '';
      case 'payment_date':
        return payment.payment_date ? new Date(payment.payment_date).getTime() : 0;
      case 'status':
        return payment.status?.name || '';
      case 'return_reason':
        return payment.reject_name || payment.reject?.name || '';
      case 'document':
        return payment.invoice?.token || payment.commitment_deposit?.token || '';
      default:
        return '';
    }
  };

  return list.sort((a, b) => {
    const av = getValue(a);
    const bv = getValue(b);

    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDesc.value ? bv - av : av - bv;
    }

    const as = String(av);
    const bs = String(bv);
    const cmp = as.localeCompare(bs, undefined, { numeric: true, sensitivity: 'base' });
    return sortDesc.value ? -cmp : cmp;
  });
});

const setSort = (column) => {
  if (sortBy.value === column) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = column;
    sortDesc.value = false;
  }
};

// Pagination
const PAGE_SIZES = [25, 50, 100];
const pageSize = ref(50);
const currentPage = ref(1);

const totalFiltered = computed(() => {
  if (props.searchData) return serverTotal.value;
  return filteredPayments.value.length;
});
const totalPages = computed(() => Math.max(1, Math.ceil(totalFiltered.value / pageSize.value)));
const paginatedPayments = computed(() => {
  if (props.searchData) return localPayments.value || [];
  const list = filteredPayments.value;
  const start = (currentPage.value - 1) * pageSize.value;
  return list.slice(start, start + pageSize.value);
});

watch([searchQuery, pageSize], () => { 
  currentPage.value = 1; 
  if (props.searchData) {
    loadPayments(); 
  }
});
watch(currentPage, () => {
  if (props.searchData) {
    loadPayments();
  }
});
watch(filteredPayments, () => { if (!props.searchData) currentPage.value = 1; }, { flush: 'sync' });

const excludePayment = async (payment) => {
  if (!payment.is_excluded) {
    let text = t('confirmation_text_block.confirm_exclude_payment');
    if (!confirm(text)) return;
  }

  try {
    loadingPaymentId.value = payment.id;
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

const hasExcludedPayments = computed(() => {
  if (props.searchData) {
    return props.is_excluded ? serverTotal.value > 0 : localPayments.value.some(p => p.is_excluded);
  }
  return filteredPayments.value.some(payment => payment.is_excluded);
});

const hasIncludedPayments = computed(() => {
  if (props.searchData) {
    return props.is_excluded ? localPayments.value.some(p => !p.is_excluded) : serverTotal.value > 0;
  }
  return filteredPayments.value.some(payment => !payment.is_excluded);
});

const toggleAllPayments = async (include) => {
  if (!include) {
    let text = t('confirmation_text_block.confirm_exclude_payments');
    if (!confirm(text)) return;
  }

  loading.value = true;
  try {
    if (props.searchData) {
      let payload = { ...props.searchData };
      if (searchQuery.value) {
        payload.search = searchQuery.value;
      }
      await $PaymentApiService.bulkExcludeSEPAInvoices(payload, !include);
      emit('change');
    } else {
      const paymentsToChange = filteredPayments.value.filter(payment => 
        include ? payment.is_excluded : !payment.is_excluded
      );

      for (const payment of paymentsToChange) {
        let save_data = {
          id: payment.id,
          is_excluded: !include,
        };
        let response = await $PaymentApiService.save(save_data);
        if (response) {
          payment.is_excluded = !include;
          emit('exclude_change', { ...payment, is_excluded: !include });
        }
      }
    }
    toast.success(include ? t('informative_block.info_include_correct') : t('informative_block.info_exclude_correct'));
    await loadPayments();
  } catch (error) {
    toast.error(t('common.error'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};


// Marca com a exclosos, dins dels filtres actuals, NOMÉS els pagaments de
// contractes amb factures pendents de pagar (vençudes/impagades) — la mateixa
// acció que fa l'interruptor del pas de filtres, aquí a demanda. Es força
// `exclude_contracts_with_pending_invoices: false` perquè el backend li dona
// prioritat i, si arribés actiu, marcaria justament la resta de pagaments.
const excludePaymentsOfContractsWithPendingInvoices = async () => {
  if (!confirm(t('confirmation_text_block.confirm_exclude_payments'))) return;

  loading.value = true;
  try {
    let payload = {
      ...props.searchData,
      exclude_contracts_with_pending_invoices: false,
      only_contracts_with_pending_invoices: true,
    };
    if (searchQuery.value) {
      payload.search = searchQuery.value;
    }
    const response = await $PaymentApiService.bulkExcludeSEPAInvoices(payload, true);
    emit('change');
    toast.success(response?.updated_count !== undefined
      ? `${t('informative_block.info_exclude_correct')} (${response.updated_count})`
      : t('informative_block.info_exclude_correct'));
    await loadPayments();
  } catch (error) {
    toast.error(t('common.error'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null
  regionDetailId.value = null
  emit('show-detail', false);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

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
        <span class="text-xs text-slate-500">{{ $t('common.total') }}: {{ totalFiltered }}</span>
      </div>

      <div class="flex flex-wrap items-center gap-2 mb-2">
        <div class="relative flex-1 min-w-[180px] max-w-sm">
          <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
            <Icon name="fa6-solid:magnifying-glass" class="text-sm" />
          </div>
          <input ref="searchInput" v-model="searchQuery" type="text"
            :placeholder="`${$t('dashboard.search')} ${$t('common.client')} ${$t('common.or')} ${$t('common.identificator')}`"
            class="pl-8 pr-3 py-1.5 w-full text-sm border border-slate-300 rounded focus:ring-1 focus:ring-slate-400 focus:border-slate-400" />
        </div>
        <button v-if="hasExcludedPayments" type="button" @click="toggleAllPayments(true)" :disabled="loading"
          class="px-3 py-1.5 text-sm font-medium rounded border transition-colors flex items-center gap-1.5 bg-sky-50 text-sky-700 border-sky-200 hover:bg-sky-100 disabled:opacity-50 disabled:cursor-not-allowed">
          <Icon name="fa6-solid:arrow-up-from-bracket" class="text-xs" />
          {{ $t('billing_block.include_all') }}
        </button>
        <button v-if="hasIncludedPayments" type="button" @click="toggleAllPayments(false)" :disabled="loading"
          class="px-3 py-1.5 text-sm font-medium rounded border transition-colors flex items-center gap-1.5 bg-red-50 text-red-700 border-red-200 hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed">
          <Icon name="fa6-solid:ban" class="text-xs" />
          {{ $t('billing_block.exclude_all') }}
        </button>
        <button v-if="searchData && !is_excluded && hasIncludedPayments" type="button"
          @click="excludePaymentsOfContractsWithPendingInvoices" :disabled="loading"
          :title="$t('billing_block.info_exclude_contracts_with_pending_invoices')"
          class="px-3 py-1.5 text-sm font-medium rounded border transition-colors flex items-center gap-1.5 bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed">
          <Icon name="fa6-solid:hand-holding-dollar" class="text-xs" />
          {{ $t('billing_block.exclude_contracts_with_pending_invoices_action') }}
        </button>
      </div>

      <div class="flex-1 min-h-0 flex flex-col border border-slate-200 rounded bg-white">
        <div v-if="loading && !localPayments.length" class="flex justify-center items-center flex-1 py-12">
          <AppLoading :text="$t('common.loading')" :size="40" />
        </div>
        <template v-else>
          <div class="overflow-auto flex-1 min-h-0" style="max-height: 80vh;">
            <table class="w-full text-sm border-collapse">
              <thead class="sticky top-0 bg-slate-100 border-b border-slate-200 text-slate-600 font-medium">
                <tr>
                  <th class="text-left py-0.5 px-1 whitespace-nowrap">
                    <button type="button" class="inline-flex items-center gap-1 hover:text-sky-700"
                      @click="setSort('token')">
                      <span>{{ t('billing_block.payment') }}</span>
                      <Icon v-if="sortBy === 'token'" :name="sortDesc ? 'fa6-solid:sort-down' : 'fa6-solid:sort-up'"
                        class="text-[11px]" />
                    </button>
                  </th>
                  <th class="text-right py-1.5 px-2 whitespace-nowrap">
                    <button type="button" class="inline-flex items-center gap-1 hover:text-sky-700"
                      @click="setSort('amount')">
                      <span>{{ t('common.total') }}</span>
                      <Icon v-if="sortBy === 'amount'" :name="sortDesc ? 'fa6-solid:sort-down' : 'fa6-solid:sort-up'"
                        class="text-[11px]" />
                    </button>
                  </th>
                  <th class="text-left py-1.5 px-2 min-w-0 max-w-[140px]">
                    <button type="button" class="inline-flex items-center gap-1 hover:text-sky-700"
                      @click="setSort('client')">
                      <span>{{ t('common.client') }}</span>
                      <Icon v-if="sortBy === 'client'" :name="sortDesc ? 'fa6-solid:sort-down' : 'fa6-solid:sort-up'"
                        class="text-[11px]" />
                    </button>
                  </th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">
                    <button type="button" class="inline-flex items-center gap-1 hover:text-sky-700"
                      @click="setSort('iban')">
                      <span>{{ $t('common.iban') }}</span>
                      <Icon v-if="sortBy === 'iban'" :name="sortDesc ? 'fa6-solid:sort-down' : 'fa6-solid:sort-up'"
                        class="text-[11px]" />
                    </button>
                  </th>
                  <th v-if="showBankColumn" class="text-left py-1.5 px-2 whitespace-nowrap">
                    {{ $t('common.bank') }}
                  </th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">
                    <button type="button" class="inline-flex items-center gap-1 hover:text-sky-700"
                      @click="setSort('payment_date')">
                      <span>{{ t('billing_block.payment_date') }}</span>
                      <Icon v-if="sortBy === 'payment_date'"
                        :name="sortDesc ? 'fa6-solid:sort-down' : 'fa6-solid:sort-up'" class="text-[11px]" />
                    </button>
                  </th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">
                    <button type="button" class="inline-flex items-center gap-1 hover:text-sky-700"
                      @click="setSort('status')">
                      <span>{{ t('common.status') }}</span>
                      <Icon v-if="sortBy === 'status'" :name="sortDesc ? 'fa6-solid:sort-down' : 'fa6-solid:sort-up'"
                        class="text-[11px]" />
                    </button>
                  </th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">
                    <button type="button" class="inline-flex items-center gap-1 hover:text-sky-700"
                      @click="setSort('return_reason')">
                      <span>{{ t('common.return_reason') }}</span>
                      <Icon v-if="sortBy === 'return_reason'"
                        :name="sortDesc ? 'fa6-solid:sort-down' : 'fa6-solid:sort-up'" class="text-[11px]" />
                    </button>
                  </th>
                  <th class="text-left py-1.5 px-2 whitespace-nowrap">
                    <button type="button" class="inline-flex items-center gap-1 hover:text-sky-700"
                      @click="setSort('document')">
                      <span>{{ t('invoice') }} / {{ t('claim_block.commitment') }}</span>
                      <Icon v-if="sortBy === 'document'"
                        :name="sortDesc ? 'fa6-solid:sort-down' : 'fa6-solid:sort-up'" class="text-[11px]" />
                    </button>
                  </th>
                  <th class="w-20 py-1.5 px-1"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="paginatedPayments.length === 0">
                  <td :colspan="columnCount" class="py-4 px-2 text-center text-slate-500 text-sm">
                    {{ t('common.no_data_found') }}
                  </td>
                </tr>
                <tr v-for="(payment, index) in paginatedPayments" :key="payment.id"
                  class="border-b border-slate-100 group"
                  :class="{ 'bg-orange-50': payment.is_excluded }">
                  <td v-if="loadingPaymentId === payment.id" :colspan="columnCount"
                    class="py-2 bg-white/95 text-center">
                    <AppLoading :size="24" />
                  </td>
                  <template v-else>
                    <td class="py-1 px-0.5 align-middle">
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
                    <td v-if="showBankColumn" class="py-1 px-2 align-middle">
                      <select
                        class="py-0.5 px-1 max-w-[170px] text-xs border rounded bg-white text-slate-700"
                        :class="isOverridden(payment) ? 'border-sky-400 ring-1 ring-sky-200' : 'border-slate-300'"
                        :value="String(bankOf(payment))" @change="setBank(payment, $event.target.value)"
                        :title="isOverridden(payment) ? $t('billing_block.manual_bank_override') : $t('billing_block.bank_routing')">
                        <option value="">{{ $t('billing_block.use_default_routing') }}</option>
                        <option v-for="bank in banks" :key="bank.value" :value="String(bank.value)">
                          {{ bank.label }}
                        </option>
                      </select>
                    </td>
                    <td class="py-1 px-2 whitespace-nowrap align-middle">
                      {{ payment.payment_date ? formatDate(payment.payment_date) : '–' }}
                    </td>
                    <td class="py-1 px-2 align-middle">
                      <AtomsColorBadge :color="payment.status?.color" :value="payment.status?.name" />
                    </td>
                    <td class="py-1 px-2 align-middle max-w-[140px] truncate" :title="payment.reject?.name || '–'">
                      <span v-if="payment.reject_name" class="inline-flex items-center rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-900">
                        {{ payment.reject_name }}
                      </span>
                      <span v-else class="text-slate-400">–</span>
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
              </tbody>
            </table>
          </div>
          <div v-if="totalPages > 1 || totalFiltered > PAGE_SIZES[0]" class="flex flex-wrap items-center justify-between gap-2 py-1.5 px-2 border-t border-slate-200 bg-slate-50 text-xs text-slate-600">
            <div class="flex items-center gap-2">
              <span class="whitespace-nowrap">{{ (currentPage - 1) * pageSize + 1 }}-{{ Math.min(currentPage * pageSize, totalFiltered) }} {{ $t('common.of') }} {{ totalFiltered }}</span>
              <select v-model.number="pageSize" class="py-0.5 px-1 border border-slate-300 rounded text-slate-700 bg-white">
                <option v-for="n in PAGE_SIZES" :key="n" :value="n">{{ n }}</option>
              </select>
              <span class="whitespace-nowrap">/ {{ $t('common.page') }}</span>
            </div>
            <div class="flex items-center gap-1">
              <button type="button" :disabled="currentPage <= 1" @click="currentPage = 1"
                class="p-1 rounded disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-200" :aria-label="`${$t('common.page')} 1`">
                <Icon name="fa6-solid:angles-left" class="text-xs" />
              </button>
              <button type="button" :disabled="currentPage <= 1" @click="currentPage--"
                class="p-1 rounded disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-200" :aria-label="$t('common.previous')">
                <Icon name="fa6-solid:chevron-left" class="text-xs" />
              </button>
              <span class="px-1 min-w-[4rem] text-center">{{ currentPage }} / {{ totalPages }}</span>
              <button type="button" :disabled="currentPage >= totalPages" @click="currentPage++"
                class="p-1 rounded disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-200" :aria-label="$t('common.next')">
                <Icon name="fa6-solid:chevron-right" class="text-xs" />
              </button>
              <button type="button" :disabled="currentPage >= totalPages" @click="currentPage = totalPages"
                class="p-1 rounded disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-200" :aria-label="`${$t('common.page')} ${totalPages}`">
                <Icon name="fa6-solid:angles-right" class="text-xs" />
              </button>
            </div>
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