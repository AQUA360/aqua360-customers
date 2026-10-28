<script setup>
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatMoney } from '~/utils/money';
import Date from '~/components/atoms/Date.vue';
import InvoiceRegion from './InvoiceRegion.vue';

const props = defineProps({
  invoices: {
    type: Array,
    default: () => []
  }
});

const { t } = useI18n();
const emit = defineEmits(['show-subregion']);

const searchQuery = ref('');

const showRegion = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = (component, id) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-subregion', true);
};

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  emit('show-subregion', false);
};

const filteredInvoices = computed(() => {
  const query = searchQuery.value?.trim().toLowerCase();
  if (!query) return props.invoices;

  return props.invoices.filter(invoice => {
    return invoice.invoice_serie?.toLowerCase().includes(query)
      || invoice.customer?.toLowerCase().includes(query)
      || invoice.customer_token?.toLowerCase().includes(query)
      || invoice.contract_request_token?.toLowerCase().includes(query);
  });
});

const reasonLabel = (reason) => {
  if (!reason) return '';
  return t(`claim_block.unlinked_reason_${reason}`);
};

const totalAmount = computed(() => {
  return filteredInvoices.value.reduce((acc, invoice) => acc + parseFloat(invoice.amount || 0), 0);
});
</script>

<template>
  <div class="region__content pr-1">
    <div class="h-full flex flex-col transition-all duration-500 ease" :class="{ 'mr-[48vw]': showRegion }">
      <h3 class="text-lg font-semibold mb-4">{{ $t('claim_block.unlinked_invoices') }}</h3>

      <div class="bg-orange-50 border-l-4 border-orange-400 px-4 py-2 mb-4 grid grid-cols-[auto,1fr] items-center gap-3">
        <Icon name="fa6-solid:triangle-exclamation" class="text-lg text-orange-400" />
        <p class="text-sm text-orange-600">{{ $t('claim_block.unlinked_invoices_info') }}</p>
      </div>

      <div class="relative mb-4">
        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Icon name="fa6-solid:magnifying-glass" class="text-gray-400" />
        </div>
        <input v-model="searchQuery" type="text"
          :placeholder="`${$t('dashboard.search')} ${$t('invoice')}, ${$t('common.name')} ${$t('common.or')} ${$t('contract_request')}`"
          class="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500" />
      </div>

      <div class="flex gap-3 items-center mb-4">
        <div>{{ $t('invoices') }}: {{ filteredInvoices.length }}</div>
        <div>{{ $t('common.amount') }}: {{ formatMoney(totalAmount) }} €</div>
      </div>

      <div class="flex-1 overflow-y-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('invoice') }}</th>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('contract_request') }}</th>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.client') }}</th>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.due_date') }}</th>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.amount') }}</th>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('order_block.reason') }}</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-if="filteredInvoices.length === 0">
              <td colspan="6" class="px-3 py-2 text-sm text-slate-500">{{ $t('common.no_data_found') }}</td>
            </tr>
            <tr v-for="(invoice, index) in filteredInvoices" :key="invoice.invoice_id"
              :class="index % 2 === 0 ? 'bg-sky-50' : 'bg-white'">
              <td class="px-3 py-1 whitespace-nowrap">
                <button @click="showDetail('InvoiceRegion', invoice.invoice_id)"
                  class="text-sm text-sky-600 hover:text-sky-900 underline"
                  :title="`${$t('common.show')} ${$t('common.details')}`">
                  {{ invoice.invoice_serie || `#${invoice.invoice_id}` }}
                </button>
              </td>
              <td class="px-3 py-1 whitespace-nowrap">
                <span class="text-sm text-gray-900">{{ invoice.contract_request_token || '-' }}</span>
                <span v-if="invoice.contract_request_status" class="text-xs text-gray-500 ml-1">
                  ({{ invoice.contract_request_status }})
                </span>
              </td>
              <td class="px-3 py-1">
                <span class="text-sm text-gray-900">{{ invoice.customer }}</span>
                <span v-if="invoice.customer_token" class="text-xs text-gray-500 ml-1">
                  ({{ invoice.customer_token }})
                </span>
              </td>
              <td class="px-3 py-1 whitespace-nowrap">
                <Date :date="invoice.due_date" />
              </td>
              <td class="px-3 py-1 whitespace-nowrap">
                <span class="text-sm text-gray-900">{{ formatMoney(invoice.amount) }} €</span>
              </td>
              <td class="px-3 py-1">
                <span class="text-sm text-orange-700">{{ reasonLabel(invoice.reason) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="showRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
