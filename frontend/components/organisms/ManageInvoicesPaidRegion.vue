<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { formatMoneyWithCurrency } from '~/utils/money';
import ManageInvoicesPaidView from './ManageInvoicesPaidView.vue';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  filters: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(['close', 'changed']);
const { $InvoiceApiService } = useNuxtApp();

const pending = ref(true);
const loading_invoices = ref(false);
const summary_data = ref({});
const showSummary = ref(false);
const error = ref(null);

const getSummary = async () => {
  error.value = null;
  loading_invoices.value = true;
  try {
    const filter_data = {
      search: props.filters.searchInput,
      status: props.filters.statuses.join(','),
      origin: props.filters.origin,
      billing: props.filters.billing,
      left_to_pay: props.filters.searchInputTotalFinal?.replace(',', '.'),
      start_issue_date: props.filters.issue_date?.start_date,
      end_issue_date: props.filters.issue_date?.end_date,
      start_due_date: props.filters.due_date?.start_date,
      end_due_date: props.filters.due_date?.end_date,
      serie: props.filters.serie?.join(','),
      payment_type_tokens: props.filters.payment_types?.join(','),
      saving: false,
    };

    const response = await $InvoiceApiService.manageMassivelyPaid(filter_data);
    summary_data.value = response;
  } catch (err) {
    error.value = err;
    console.error(err);
  } finally {
    pending.value = false;
    loading_invoices.value = false;
  }
};

const handleConfirm = () => {
  if (summary_data.value.count === 0) {
    toast.error(t('billing_block.no_invoices_selected'));
    return;
  }
  showSummary.value = true;
};

const save = async (saving) => {
  if (!saving) {
    showSummary.value = false;
    return;
  }
  
  showSummary.value = false;
  pending.value = true;
  try {
    const filter_data = {
      search: props.filters.searchInput,
      status: props.filters.statuses.join(','),
      origin: props.filters.origin,
      billing: props.filters.billing,
      left_to_pay: props.filters.searchInputTotalFinal?.replace(',', '.'),
      start_issue_date: props.filters.issue_date?.start_date,
      end_issue_date: props.filters.issue_date?.end_date,
      start_due_date: props.filters.due_date?.start_date,
      end_due_date: props.filters.due_date?.end_date,
      serie: props.filters.serie?.join(','),
      payment_type_tokens: props.filters.payment_types?.join(','),
      saving: true,
    };

    const response = await $InvoiceApiService.manageMassivelyPaid(filter_data);
    
    toast.success(t('common.correct_finish') + ': ' + response.updated_count + ' ' + t('billing_block.affected_invoices'));
    emit('changed');
    emit('close');
  } catch (err) {
    toast.error(t('common.error_save'));
    console.error(err);
  } finally {
    pending.value = false;
  }
};

onMounted(() => {
  getSummary();
});

watch(() => props.filters, () => {
  getSummary();
}, { deep: true });

</script>

<template>
  <Teleport to="body">
    <div v-if="showSummary" @click="showSummary = false"
      class="fixed inset-0 text-sm flex items-center justify-center bg-black bg-opacity-50 z-[100]">
      <ManageInvoicesPaidView :summary="summary_data" :filters="filters"
        class="p-4 bg-white shadow-lg rounded-lg" @save="save" @click.stop />
    </div>
  </Teleport>

  <div class="region__content">
    <div v-if="pending && !loading_invoices" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getSummary" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again') }}</button></p>
    </div>
    <div v-else>
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('billing_block.manage_massively_paid') }}
        </H1Region>
      </div>

      <div class="bg-sky-50 border border-sky-100 p-4 rounded-lg mb-6">
        <p class="text-sky-800 text-sm mb-4">
          {{ $t('billing_block.bulk_pay_description') }}
        </p>
        
        <div class="grid grid-cols-2 gap-4">
          <div class="bg-white p-3 rounded border border-sky-200">
            <span class="block text-xs text-sky-600 font-semibold uppercase tracking-wider mb-1">
              {{ $t('billing_block.invoices_to_be_paid') }}
            </span>
            <span class="text-2xl font-bold text-sky-900">
              <span v-if="loading_invoices">
                <Icon name="fa6-solid:spinner" class="animate-spin" />
              </span>
              <span v-else>
                {{ summary_data.count }}
              </span>
            </span>
          </div>
          
          <div class="bg-white p-3 rounded border border-sky-200">
            <span class="block text-xs text-sky-600 font-semibold uppercase tracking-wider mb-1">
              {{ $t('billing_block.total_amount') }}
            </span>
            <span class="text-2xl font-bold text-sky-900">
              <span v-if="loading_invoices">
                <Icon name="fa6-solid:spinner" class="animate-spin" />
              </span>
              <span v-else>
                {{ formatMoneyWithCurrency(summary_data.total_amount || 0) }}
              </span>
            </span>
          </div>
        </div>
      </div>

      <div class="flex flex-row-reverse mt-4">
        <button @click="handleConfirm" :disabled="loading_invoices || summary_data.count === 0" class="button-primary">
          <Icon name="fa6-solid:check-double" class="mr-2" /> {{ $t('billing_block.mark_as_paid_bulk') }}
        </button>
      </div>
    </div>
  </div>
</template>
