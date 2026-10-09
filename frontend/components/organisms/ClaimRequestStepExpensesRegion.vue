<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import { formatMoneyWithCurrency } from '~/utils/money';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import ContractRegion from './ContractRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import JoinedPaymentRegion from './JoinedPaymentRegion.vue';

const props = defineProps({
  step: {
    type: Object,
    required: true
  },
  title: {
    type: String,
    default: 'claim_block.show_generated_expenses'
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['show-detail']);
const { $ClaimRequestApiService } = useNuxtApp();

const loading = ref(false);
const expenses = ref([]);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  isFiltered: false
});

const totalAmount = computed(() => {
  return expenses.value.reduce((total, expense) => {
    return total + parseFloat(expense.payment?.amount ?? 0);
  }, 0);
});

const showGroupedPayments = computed(() => {
  console.log("showGroupedPayments", expenses.value.filter(expense => expense.joined_payment).length);
  return expenses.value.filter(expense => expense.joined_payment).length > 0;
});

const loadExpenses = async () => {
  loading.value = true;
  try {
    const response = await $ClaimRequestApiService.getStepExpenses(props.step.id, pagination.value.page);
    expenses.value = response?.results ?? [];
    console.log("expenses", expenses.value);
    pagination.value.total = response?.count ?? expenses.value.length;
    pagination.value.totalPages = Math.ceil(pagination.value.total / pagination.value.perPage);
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
    expenses.value = [];
  } finally {
    loading.value = false;
  }
};

const onPageChange = async (page) => {
  if (page < 1 || page > pagination.value.totalPages) return;
  pagination.value.page = page;
  await loadExpenses();
};

const showDetail = (component, id) => {
  if (!id) return;
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
};

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  isSubRegionOpen.value = false;
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

onMounted(async () => {
  await loadExpenses();
});
</script>

<template>
  <div class="h-full">
    <div class="h-full flex flex-col gap-3 min-h-0 overflow-hidden">
      <!-- Header -->
      <div class="flex items-center justify-between gap-3">
        <H1Region>{{ $t(title) }}</H1Region>
        <div class="flex items-center gap-2 text-xs">
          <span
            class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-medium text-slate-500">
            {{ $t('common.amount') }} ({{ $t('common.page') }})
            <span class="font-semibold tabular-nums text-slate-800">{{ formatMoneyWithCurrency(totalAmount) }}</span>
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-medium text-slate-500">
            {{ $t('common.total') }}
            <span class="font-semibold tabular-nums text-slate-800">{{ pagination.total }}</span>
          </span>
        </div>
      </div>

      <div class="overflow-auto" :style="{
        minHeight: 'calc(100vh - 200px)',
        maxHeight: 'calc(100vh - 200px)',
      }">
        <AtomsAppLoading v-if="loading" />
        <div v-else-if="!expenses.length"
          class="flex flex-col items-center justify-center py-8 text-xs text-slate-400 h-full">
          <Icon name="fa6-solid:inbox" class="text-slate-300 text-xl mb-1" />
          <span>{{ $t('common.no_data') }}</span>
        </div>
        <table v-else class="min-w-full text-sm">
          <thead class="sticky top-0 z-10 bg-slate-50/95 backdrop-blur-sm">
            <tr>
              <th
                class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {{ $t('invoice') }}</th>
              <th
                class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {{ $t('common.status') }}</th>
              <th
                class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {{ $t('common.amount') }}</th>
              <th v-if="showGroupedPayments"
                class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {{ $t('billing_block.joined_payment') }}</th>
              <th
                class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {{ $t('contract') }}</th>
              <th
                class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {{ $t('contract_block.holder') }}</th>
              <th
                class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {{ $t('supply_point') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="expense in expenses" :key="expense.id" class="transition-colors hover:bg-slate-50/80"
              :class="{ 'bg-red-50': expense.is_excluded }">
              <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                <button v-if="expense.payment?.invoice_id"
                  @click="showDetail('InvoiceRegion', expense.payment.invoice_id)"
                  class="text-sm font-medium leading-tight text-sky-500 underline hover:text-sky-700 text-left"
                  :title="`${$t('common.show')} ${$t('common.details')}`">
                  {{ expense.payment.invoice_serie_final || expense.payment.invoice_token }}
                </button>
                <span v-else class="text-xs text-slate-300">—</span>
              </td>
              <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                <ColorBadge v-if="expense.payment?.invoice_status_color" :color="expense.payment?.invoice_status_color"
                  :value="expense.payment?.invoice_status_name" />
                <span v-else class="text-xs text-slate-300">—</span>
              </td>
              <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                <span class="font-medium tabular-nums text-slate-800">
                  {{ formatMoneyWithCurrency(expense.payment?.amount ?? 0) }}
                </span>
              </td>
              <td v-if="showGroupedPayments" class="whitespace-nowrap px-3 py-1.5 align-middle">
                <button v-if="expense.joined_payment?.id" @click="showDetail('JoinedPaymentRegion', expense.joined_payment.id)"
                  class="text-sm font-medium leading-tight text-sky-500 underline hover:text-sky-700 text-left"
                  :title="`${$t('common.show')} ${$t('common.details')}`">
                  {{ expense.joined_payment.token }} ({{ formatMoneyWithCurrency(expense.joined_payment.total_final) }})
                </button>
                <span v-else class="text-xs text-slate-300">—</span>
              </td>
              <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                <button v-if="expense.contract?.id" @click="showDetail('ContractRegion', expense.contract.id)"
                  class="text-sm font-medium leading-tight text-sky-500 underline hover:text-sky-700 text-left"
                  :title="`${$t('common.show')} ${$t('common.details')}`">
                  {{ expense.contract.token }}
                </button>
                <span v-else class="text-xs text-slate-300">—</span>
              </td>
              <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                <div class="text-sm font-medium leading-tight text-slate-800">{{ expense.contract?.holder || '—' }}
                </div>
                <div class="text-[11px] text-slate-500 [font-family:ui-monospace,monospace]">
                  {{ expense.contract?.holder_token }}
                </div>
              </td>
              <td class="px-3 py-1.5 align-middle">
                <span class="text-xs text-slate-500">{{ expense.contract?.supply_point || '—' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="pagination.totalPages > 1" class="border-t border-slate-100 pt-1">
        <Pagination :pagination="pagination" @update:page="onPageChange" />
      </div>
    </div>

    <div role="region" id="subregion"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-20 shadow-2xl"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[55%]': !isSubRegionOpen,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 h-full overflow-y-auto pb-24">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId" :isSubRegion="true"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
          @close-subregion="closeAllRegions" />
        <JoinedPaymentRegion v-if="showRegionDetailComponent === 'JoinedPaymentRegion'" :id="regionDetailId" :isSubRegion="true"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
          @close-subregion="closeAllRegions" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
          @close-subregion="closeAllRegions" />
      </div>
    </div>
  </div>
</template>
