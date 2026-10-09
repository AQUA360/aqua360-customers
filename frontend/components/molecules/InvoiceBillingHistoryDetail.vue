<script setup>
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';

const { t } = useI18n();
const { $BillingConsumptionApiService } = useNuxtApp();

const props = defineProps({
  invoice: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  show: {
    type: Boolean,
    default: false
  },
  finalized: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-history', 'show-edit']);

const history = ref([]);
const loaded = ref(false);
const loading = ref(false);

const currentTotal  = computed(() => props.invoice?.total_final);
const avgAmount     = computed(() => {
  if (!history.value.length) return null;
  const sum = history.value.reduce((acc, r) => acc + parseFloat(r.total_amount || 0), 0);
  return sum / history.value.length;
});
const isAnomaly = computed(() => {
  if (!avgAmount.value || !currentTotal.value) return false;
  return parseFloat(currentTotal.value) > avgAmount.value * 1.5;
});

const getData = async () => {
  if (!props.invoice?.contract) return;
  loading.value = true;
  try {
    const data = await $BillingConsumptionApiService.getByContract(props.invoice.contract);
    // Sort by year desc, month desc
    history.value = (Array.isArray(data) ? data : (data.results || [])).sort((a, b) => {
      if (b.year !== a.year) return b.year - a.year;
      return b.month - a.month;
    });
    loaded.value = true;
  } catch (e) {
    console.error('Error loading billing history:', e);
  } finally {
    loading.value = false;
  }
};

watch(() => props.show, (newValue) => {
  if (newValue) {
    getData();
  } else {
    history.value = [];
    loaded.value = false;
  }
});
</script>

<template>
  <div
    class="overflow-hidden transition-all duration-300 ease-in-out"
    :style="{
      height: loaded ? 'auto' : '0px',
      opacity: loaded ? '1' : '0',
      marginBottom: loaded ? '1rem' : '0',
      padding: loaded ? '0.75rem 1rem' : '0'
    }"
  >
    <!-- Summary header -->
    <div v-if="loaded" class="flex flex-wrap items-center gap-4 mb-3">
      <span class="text-sm text-slate-500">
        {{ $t('contract') }}: <strong class="text-slate-700">{{ invoice?.contract_token }}</strong>
      </span>
      <span v-if="avgAmount" class="text-sm text-slate-500">
        {{ $t('billing_block.total_amount') }} {{ $t('common.avg') }}:
        <strong class="text-slate-700">{{ formatMoneyWithCurrency(avgAmount) }}</strong>
      </span>
      <span v-if="isAnomaly" class="inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full bg-red-100 text-red-700">
        <Icon name="fa6-solid:triangle-exclamation" />
        {{ $t('billing_block.high_billing_amount') }}
      </span>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex items-center gap-2 text-slate-400 py-2 text-sm">
      <Icon name="fa6-solid:spinner" class="animate-spin" />
      {{ $t('common.loading') }}...
    </div>

    <!-- Table -->
    <div v-else-if="loaded" class="overflow-x-auto rounded border border-slate-100 max-h-[300px] overflow-y-auto">
      <table class="min-w-full table-fixed border-collapse text-sm">
        <thead class="bg-slate-100 border-b border-slate-200 sticky top-0 z-10">
          <tr>
            <th class="p-2 text-left font-medium text-slate-500 w-20 bg-slate-100">{{ $t('billing_block.year') }}</th>
            <th class="p-2 text-left font-medium text-slate-500 w-20 bg-slate-100">{{ $t('billing_block.month') }}</th>
            <th class="p-2 text-right font-medium text-slate-500">{{ $t('billing_block.consumption') }}</th>
            <th class="p-2 text-right font-medium text-slate-500">{{ $t('billing_block.consumption_daily_avg') }}</th>
            <th class="p-2 text-right font-medium text-slate-500">{{ $t('billing_block.net_amount') }}</th>
            <th class="p-2 text-right font-medium text-slate-500">{{ $t('billing_block.tax_amount') }}</th>
            <th class="p-2 text-right font-semibold text-slate-600 bg-slate-100">{{ $t('billing_block.total_amount') }}</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="row in history" :key="row.id" class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
            <td class="p-2 w-20">{{ row.year }}</td>
                  <td class="p-2 w-20">{{ row.month }}</td>
                  <td class="p-2 text-right">
                    {{ row.consumption != null ? `${parseFloat(row.consumption).toFixed(2)} m³` : '-' }}
                  </td>
                  <td class="p-2 text-right">
                    {{ row.consumption_daily_avg != null ? `${parseFloat(row.consumption_daily_avg).toFixed(2)} m³` : '-' }}
                  </td>
                  <td class="p-2 text-right">{{ formatMoneyWithCurrency(row.net_amount) }}</td>
                  <td class="p-2 text-right">{{ formatMoneyWithCurrency(row.tax_amount) }}</td>
                  <td class="p-2 text-right font-semibold">
                    <span :class="{ 'text-red-600': avgAmount && parseFloat(row.total_amount) > avgAmount * 1.5 }">
                      {{ formatMoneyWithCurrency(row.total_amount) }}
                    </span>
                  </td>
            </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
