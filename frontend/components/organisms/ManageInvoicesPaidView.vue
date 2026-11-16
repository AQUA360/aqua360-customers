<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  // Resum del servidor: ja porta la primera pàgina de les factures que es pagaran
  summary: {
    type: Object,
    required: true,
  },
  // Els mateixos filtres amb què s'ha fet el resum, per demanar les pàgines següents
  filterData: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(['save']);
const { $InvoiceApiService } = useNuxtApp();

const data = ref([...(props.summary.results || [])]);
const page = ref(props.summary.page || 1);
const loadingMore = ref(false);
const allDataLoaded = ref(!props.summary.has_next);

const getData = async () => {
  if (loadingMore.value || allDataLoaded.value) return;

  loadingMore.value = true;
  try {
    const response = await $InvoiceApiService.manageMassivelyPaid({
      ...props.filterData,
      saving: false,
      page: page.value + 1,
    });
    // Només s'afegeixen les factures que formen part de la confirmació
    const confirmed_ids = new Set(props.summary.invoice_ids || []);
    data.value = data.value.concat((response.results || []).filter((item) => confirmed_ids.has(item.id)));
    page.value = response.page;
    allDataLoaded.value = !response.has_next;
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_load'));
  } finally {
    loadingMore.value = false;
  }
};

const save = () => {
  emit('save', true);
};

const onScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollHeight - scrollTop <= clientHeight + 50) {
    getData();
  }
};
</script>

<template>
  <div class="region__content w-[80vw] h-[85vh] flex flex-col">
    <div class="flex-shrink-0 p-4 border-b">
      <H1Region>
        {{ t('billing_block.confirm_bulk_payment') }}
      </H1Region>
      <div class="mt-2 flex gap-4">
        <div class="bg-sky-50 px-3 py-1 rounded-md border border-sky-200">
          <span class="text-xs font-semibold text-sky-700 uppercase">{{ t('invoices') }}:</span>
          <span class="ml-2 font-bold">{{ summary.count }}</span>
        </div>
        <div class="bg-sky-50 px-3 py-1 rounded-md border border-sky-200">
          <span class="text-xs font-semibold text-sky-700 uppercase">{{ t('billing_block.bulk_pay_amount_left') }}:</span>
          <span class="ml-2 font-bold">{{ formatMoneyWithCurrency(summary.total_amount || 0) }}</span>
        </div>
      </div>
      <p class="mt-3 text-sm text-red-600 font-medium">
        <Icon name="fa6-solid:triangle-exclamation" class="mr-1" />
        {{ t('confirmation_text_block.confirm_save_bulk_payment') }}
      </p>
    </div>

    <div class="flex-1 overflow-auto p-4" @scroll="onScroll">
      <table class="min-w-full table-auto text-sm">
        <thead class="bg-gray-50 sticky top-0 z-10">
          <tr>
            <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.identification') }}</th>
            <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.date') }}</th>
            <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('contract_block.holder') }}</th>
            <th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">{{ $t('billing_block.total_invoice') }}</th>
            <th class="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">{{ $t('billing_block.bulk_pay_amount_left') }}</th>
            <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('payment_types') }}</th>
            <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.status') }}</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="item in data" :key="item.id">
            <td class="px-4 py-2 whitespace-nowrap font-medium">{{ item.serie_final }}</td>
            <td class="px-4 py-2 whitespace-nowrap">{{ formatDate(item.issue_date) }}</td>
            <td class="px-4 py-2 whitespace-nowrap truncate max-w-[200px]" :title="item.customer_final">{{ item.customer_final }}</td>
            <td class="px-4 py-2 whitespace-nowrap text-right">{{ formatMoneyWithCurrency(item.total_final) }}</td>
            <td class="px-4 py-2 whitespace-nowrap text-right font-semibold">{{ formatMoneyWithCurrency(item.left_to_pay) }}</td>
            <td class="px-4 py-2 whitespace-nowrap">{{ item.payment_type_final }}</td>
            <td class="px-4 py-2 whitespace-nowrap">
              <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="loadingMore" class="text-center py-4 text-gray-500">
        <Icon name="fa6-solid:spinner" class="animate-spin mr-2" /> {{ $t('common.loading') }}...
      </div>
      <div v-if="allDataLoaded && data.length > 0" class="text-center py-4 text-xs text-gray-400">
        {{ $t('common.all_data_loaded') }}
      </div>
    </div>

    <div class="flex-shrink-0 p-4 border-t flex flex-row-reverse gap-3">
      <button @click="save" :disabled="loadingMore" class="button-primary">
        <Icon name="fa6-solid:circle-check" class="mr-1" /> {{ $t('common.confirm') }}
      </button>
      <button @click="emit('save', false)" :disabled="loadingMore" class="button-default">
        {{ $t('common.cancel') }}
      </button>
    </div>
  </div>
</template>
