<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { formatMoneyWithCurrency, parseAmountInput } from '~/utils/money';
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
const saving = ref(false);
const summary_data = ref({});
const showSummary = ref(false);
const error = ref(false);
// Descarta les respostes de cerques antigues si els filtres canvien mentre es carrega
let request_counter = 0;

// Els mateixos filtres que la llista de factures (veure buildInvoiceFilterQuery)
const buildFilterData = () => {
  const filter_data = {
    search: props.filters.searchInput || '',
    status: (props.filters.statuses || []).join(','),
    origin: props.filters.origin || null,
    billing: props.filters.billing || null,
    total_final: parseAmountInput(props.filters.searchInputTotalFinal),
    line_item: props.filters.line_item || null,
    start_issue_date: props.filters.issue_date?.start_date || null,
    end_issue_date: props.filters.issue_date?.end_date || null,
    start_due_date: props.filters.due_date?.start_date || null,
    end_due_date: props.filters.due_date?.end_date || null,
    serie: (props.filters.serie || []).join(','),
    payment_type_tokens: (props.filters.payment_types || []).join(','),
  };
  const exploitation_id = localStorage.getItem('exploitation');
  if (exploitation_id) {
    filter_data.exploitation = exploitation_id;
  }
  // django-filter no accepta valors buits en camps numèrics o de data
  return Object.fromEntries(
    Object.entries(filter_data).filter(([, value]) => value !== null && value !== undefined && value !== '')
  );
};

const getSummary = async () => {
  const request_id = ++request_counter;
  error.value = false;
  showSummary.value = false;
  summary_data.value = {};
  loading_invoices.value = true;
  try {
    const response = await $InvoiceApiService.manageMassivelyPaid({ ...buildFilterData(), saving: false });
    if (request_id !== request_counter) return;
    summary_data.value = response;
  } catch (err) {
    if (request_id !== request_counter) return;
    error.value = true;
    console.error(err);
  } finally {
    if (request_id === request_counter) {
      pending.value = false;
      loading_invoices.value = false;
    }
  }
};

const canConfirm = computed(() => (
  !loading_invoices.value && !saving.value && !error.value && (summary_data.value.count || 0) > 0
));

const handleConfirm = () => {
  if (!canConfirm.value) {
    if (summary_data.value.count === 0) {
      toast.error(t('billing_block.no_invoices_selected'));
    }
    return;
  }
  showSummary.value = true;
};

const save = async (confirmed) => {
  showSummary.value = false;
  if (!confirmed || !canConfirm.value) {
    return;
  }

  saving.value = true;
  try {
    const response = await $InvoiceApiService.manageMassivelyPaid({
      ...buildFilterData(),
      saving: true,
      invoice_ids: summary_data.value.invoice_ids,
    });

    toast.success(t('common.correct_finish') + ': ' + response.updated_count + ' ' + t('billing_block.affected_invoices'));
    if (response.skipped_count) {
      toast.warning(t('billing_block.bulk_pay_skipped_on_save', { count: response.skipped_count }));
    }
    if (response.error_count) {
      toast.error(t('billing_block.bulk_pay_errors_on_save', { count: response.error_count }));
    }
    emit('changed');
    emit('close');
  } catch (err) {
    toast.error(t('common.error_save'));
    console.error(err);
  } finally {
    saving.value = false;
  }
};

onMounted(() => {
  getSummary();
});

// La llista passa un objecte nou a cada render: només es torna a cercar si canvien els filtres
watch(() => JSON.stringify(buildFilterData()), (value, old_value) => {
  if (value !== old_value) {
    getSummary();
  }
});

</script>

<template>
  <Teleport to="body">
    <div v-if="showSummary" @click="showSummary = false"
      class="fixed inset-0 text-sm flex items-center justify-center bg-black bg-opacity-50 z-[100]">
      <ManageInvoicesPaidView :summary="summary_data" :filter-data="buildFilterData()"
        class="p-4 bg-white shadow-lg rounded-lg" @save="save" @click.stop />
    </div>
  </Teleport>

  <div class="region__content">
    <div v-if="pending || saving" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else>
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('billing_block.manage_massively_paid') }}
        </H1Region>
      </div>

      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-6 text-sm">
        <p>{{ $t('billing_block.bulk_pay_load_error') }}</p>
        <p><button @click="getSummary" class="underline hover:no-underline">{{ $t('common.load_again') }}</button></p>
      </div>

      <div v-else class="bg-sky-50 border border-sky-100 p-4 rounded-lg mb-6">
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
              {{ $t('billing_block.bulk_pay_amount_left') }}
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

        <div v-if="!loading_invoices && summary_data.skipped?.length" class="mt-4 text-sm text-amber-800">
          <p class="font-semibold mb-1">{{ $t('billing_block.bulk_pay_skipped_title') }}</p>
          <ul class="list-disc pl-5">
            <li v-for="item in summary_data.skipped" :key="item.reason">
              {{ $t(`billing_block.bulk_pay_skipped_${item.reason}`, { count: item.count }) }}
            </li>
          </ul>
        </div>
      </div>

      <div class="flex flex-row-reverse mt-4">
        <button @click="handleConfirm" :disabled="!canConfirm" class="button-primary">
          <Icon name="fa6-solid:check-double" class="mr-2" /> {{ $t('billing_block.mark_as_paid_bulk') }}
        </button>
      </div>
    </div>
  </div>
</template>
