<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  report: {
    type: Object,
    required: true
  },
  queueItem: {
    type: Object,
    default: null
  },
  exploitationOptions: {
    type: Array,
    default: () => []
  },
  loadingExploitations: {
    type: Boolean,
    default: false
  },
  reportTypes: {
    type: Array,
    default: () => []
  },
  paymentTypes: {
    type: Array,
    default: () => []
  },
  products: {
    type: Array,
    default: () => []
  },
  selectedBilling: {
    type: Object,
    default: null
  },
  selectedRemittance: {
    type: Object,
    default: null
  },
  globalDateRange: {
    type: Array,
    default: null
  },
  globalExploitationId: {
    type: [String, Number],
    default: 'all'
  },
  globalIncludePreinvoices: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits([
  'download',
  'select-billing',
  'select-remittance',
  'unselect-billing',
  'unselect-remittance',
  'check-task'
]);

const { t } = useI18n();

const getPaymentTypeName = (pay) => {
  const token = (pay.token || '').toLowerCase();
  const key = `reports_block.payment_method_${token}`;
  const translated = t(key);
  if (translated && !translated.startsWith('reports_block.payment_method_')) {
    return translated;
  }
  return pay.name || pay.token;
};

const form = ref({
  date_range: null,
  exploitation_id: 'all',
  billing_id: null,
  remittance_id: null,
  report_type_id: 'null',
  include_preinvoices: false,
  selected_product_ids: [],
  selected_payment_type_ids: [],
  include_tax_free_lines: false,
  model_347_year: new Date().getFullYear() - 1,
});

watch(() => props.globalDateRange, (newVal) => {
  if (newVal) {
    form.value.date_range = newVal;
  }
}, { immediate: true });

watch(() => props.globalExploitationId, (newVal) => {
  if (newVal !== undefined) {
    form.value.exploitation_id = newVal;
  }
}, { immediate: true });

watch(() => props.globalIncludePreinvoices, (newVal) => {
  if (newVal !== undefined) {
    form.value.include_preinvoices = newVal;
  }
}, { immediate: true });

watch(() => props.products, (newProducts) => {
  if (newProducts && newProducts.length > 0) {
    form.value.selected_product_ids = newProducts.map(p => p.id);
  }
}, { immediate: true });

watch(() => props.paymentTypes, (newTypes) => {
  if (newTypes && newTypes.length > 0) {
    form.value.selected_payment_type_ids = newTypes.map(pt => pt.id);
  }
}, { immediate: true });

watch(() => props.selectedBilling, (newBilling) => {
  form.value.billing_id = newBilling ? newBilling.id : null;
}, { immediate: true });

watch(() => props.selectedRemittance, (newRemittance) => {
  form.value.remittance_id = newRemittance ? newRemittance.id : null;
}, { immediate: true });


const hasField = (fieldNames) => {
  if (!props.report || !props.report.required_fields) return false;
  return props.report.required_fields.some(f => fieldNames.includes(f));
};

const showDateRange = computed(() => {
  // Les dates es recullen sempre del filtre genèric (global) de la pàgina
  return false;
});
const showExploitation = computed(() => hasField(['exploitation_id', 'exploitation']));
const showBilling = computed(() => hasField(['billing_id', 'billing']));
const showRemittance = computed(() => hasField(['remittance_id', 'remittance']));
const showReportType = computed(() => hasField(['report_type_id', 'type_id', 'report_type']));
const showPreinvoices = computed(() => hasField(['include_preinvoices', 'preinvoices']));

const showProducts = computed(() => {
  const productFuncs = [
    'register_billing_summary',
    'mini_register_billing_summary',
    'billing_taxes_detailed_summary',
    'detailed_billing_summary',
    'billing_summary_by_supply_type'
  ];
  return hasField(['products', 'product_ids', 'product']) || productFuncs.includes(props.report.function_name);
});

const showPaymentTypes = computed(() => {
  return hasField(['payment_types', 'payment_type_ids', 'payment_type']) || 
    ['billing_cobraments_summary', 'cobraments_excel_report'].includes(props.report.function_name);
});

const showTaxFree = computed(() => {
  return hasField(['include_tax_free_lines', 'tax_free']) || 
    ['model_347', 'report_billing_347'].includes(props.report.function_name);
});

const showModelYear = computed(() => {
  return hasField(['model_347_year', 'year']) || 
    ['model_347', 'report_billing_347'].includes(props.report.function_name);
});

const model347YearOptions = computed(() => {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: currentYear - 2020 + 1 }, (_, i) => currentYear - i);
});



const onDownload = () => {
  emit('download', props.report, form.value);
};
</script>

<template>
  <div class="space-y-4 bg-slate-50 p-5 rounded-lg border border-slate-200 mt-2 shadow-inner">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- Date range -->
      <div v-if="showDateRange" class="flex flex-col">
        <label class="text-sm font-semibold text-slate-700 mb-1">
          {{ t('reports_block.select_dates') || 'Selecciona dates' }}
        </label>
        <Datepicker
          v-model="form.date_range"
          range
          :enableTimePicker="false"
          :format="'dd-MM-yyyy'"
          class="custom-datepicker"
          placeholder="Selecciona les dates"
        />
      </div>

      <!-- Report Type -->
      <div v-if="showReportType" class="flex flex-col">
        <label class="text-sm font-semibold text-slate-700 mb-1">
          {{ t('reports_block.report_type') || 'Tipus d\'informe' }}
        </label>
        <v-select
          v-model="form.report_type_id"
          :options="reportTypes"
          :reduce="option => option.code"
          :clearable="false"
          class="custom-select bg-white rounded"
        />
      </div>

      <!-- Model 347 Year -->
      <div v-if="showModelYear" class="flex flex-col">
        <label class="text-sm font-semibold text-slate-700 mb-1">
          {{ t('billing_block.year') || 'Any' }}
        </label>
        <v-select
          v-model="form.model_347_year"
          :options="model347YearOptions"
          :clearable="false"
          class="custom-select bg-white rounded"
        />
      </div>
    </div>

    <!-- Billing selector -->
    <div v-if="showBilling" class="flex flex-col">
      <label class="text-sm font-semibold text-slate-700 mb-1">
        {{ t('reports_block.billing') || 'Facturació' }}
      </label>
      <div class="flex items-center gap-2">
        <ButtonOutline type="button" @click="emit('select-billing')">
          {{ t('reports_block.select_billing') }}
        </ButtonOutline>
        <div v-if="selectedBilling" class="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-300 rounded text-xs font-medium text-green-800">
          <span>{{ selectedBilling.name }} ({{ selectedBilling.token }})</span>
          <button type="button" @click="emit('unselect-billing')" class="text-red-500 hover:text-red-700 font-bold ml-1">
            &times;
          </button>
        </div>
        <span v-else class="text-xs text-slate-400 italic">Cap facturació seleccionada</span>
      </div>
    </div>

    <!-- Remittance selector -->
    <div v-if="showRemittance" class="flex flex-col">
      <label class="text-sm font-semibold text-slate-700 mb-1">
        {{ t('reports_block.remittance') || 'Remesa SEPA' }}
      </label>
      <div class="flex items-center gap-2">
        <ButtonOutline type="button" @click="emit('select-remittance')">
          {{ t('reports_block.select_remittance') }}
        </ButtonOutline>
        <div v-if="selectedRemittance" class="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-300 rounded text-xs font-medium text-green-800">
          <span>{{ selectedRemittance.token }} ({{ selectedRemittance.status_name }})</span>
          <button type="button" @click="emit('unselect-remittance')" class="text-red-500 hover:text-red-700 font-bold ml-1">
            &times;
          </button>
        </div>
        <span v-else class="text-xs text-slate-400 italic">Cap remesa seleccionada</span>
      </div>
    </div>

    <!-- Checkboxes row -->
    <div class="flex flex-wrap gap-5 mt-2">
      <!-- Include preinvoices -->
      <div v-if="showPreinvoices" class="flex items-center gap-2 bg-white px-3 py-2 rounded border border-slate-100 shadow-sm">
        <input
          v-model="form.include_preinvoices"
          type="checkbox"
          id="generic_include_preinvoices"
          class="checkbox rounded border-slate-300 text-sky-600 focus:ring-sky-500"
        />
        <label for="generic_include_preinvoices" class="text-sm font-medium text-slate-700 cursor-pointer">
          {{ t('reports_block.include_preinvoices') }}
        </label>
      </div>

      <!-- Include tax free lines -->
      <div v-if="showTaxFree" class="flex items-center gap-2 bg-white px-3 py-2 rounded border border-slate-100 shadow-sm">
        <input
          v-model="form.include_tax_free_lines"
          type="checkbox"
          id="generic_include_tax_free_lines"
          class="checkbox rounded border-slate-300 text-sky-600 focus:ring-sky-500"
        />
        <label for="generic_include_tax_free_lines" class="text-sm font-medium text-slate-700 cursor-pointer">
          {{ t('reports_block.include_tax_free_lines') }}
        </label>
      </div>
    </div>

    <!-- Products list selector -->
    <div v-if="showProducts && products.length > 0" class="mt-2 p-4 bg-white border border-slate-200 rounded-md">
      <span class="text-sm font-semibold text-slate-700 block mb-3 border-b border-slate-100 pb-1.5">{{ t('reports_block.shown_products') }}</span>
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 text-xs">
        <div v-for="product in products" :key="product.id" class="flex items-center gap-2 hover:bg-slate-50 p-1 rounded">
          <input
            type="checkbox"
            :id="'p-' + product.id"
            :value="product.id"
            v-model="form.selected_product_ids"
            class="checkbox rounded border-slate-300 text-sky-600 focus:ring-sky-500"
          />
          <label :for="'p-' + product.id" class="text-slate-600 truncate cursor-pointer select-none" :title="product.name">
            {{ product.name }}<template v-if="['register_billing_summary', 'mini_register_billing_summary', 'detailed_billing_summary'].includes(props.report.function_name) && product.exploitation"> {{ product.exploitation.name }}</template>
          </label>
        </div>
      </div>
    </div>

    <!-- Payment Types list selector -->
    <div v-if="showPaymentTypes && paymentTypes.length > 0" class="mt-2 p-4 bg-white border border-slate-200 rounded-md">
      <span class="text-sm font-semibold text-slate-700 block mb-3 border-b border-slate-100 pb-1.5">{{ t('reports_block.shown_payment_types') }}</span>
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 text-xs">
        <div v-for="pay in paymentTypes" :key="pay.id" class="flex items-center gap-2 hover:bg-slate-50 p-1 rounded">
          <input
            type="checkbox"
            :id="'pay-' + pay.id"
            :value="pay.id"
            v-model="form.selected_payment_type_ids"
            class="checkbox rounded border-slate-300 text-sky-600 focus:ring-sky-500"
          />
          <label :for="'pay-' + pay.id" class="text-slate-600 truncate cursor-pointer select-none" :title="getPaymentTypeName(pay)">
            {{ getPaymentTypeName(pay) }}
          </label>
        </div>
      </div>
    </div>

    <!-- Action button / badge -->
    <div class="pt-3 flex flex-col items-end gap-2 border-t border-slate-200/60 w-full">
      <template v-if="props.queueItem && props.queueItem.status === 'pending'">
        <div class="flex items-center gap-2">
          <Icon name="mdi:loading" class="animate-spin text-sky-500 text-lg" />
          <span class="text-xs text-slate-500">Esperant el seu torn a la cua...</span>
        </div>
      </template>
      <template v-else-if="props.queueItem && props.queueItem.status === 'running'">
        <div class="w-full">
          <div class="flex justify-between items-center text-xs text-sky-700 mb-1 px-1">
            <span class="font-medium flex items-center gap-1">
              <Icon name="mdi:loading" class="animate-spin text-sky-500" />
              Generant informe...
            </span>
            <span>{{ props.queueItem.percent || 0 }}% ({{ props.queueItem.processed_items || 0 }} / {{ props.queueItem.total_items || 0 }})</span>
          </div>
          <div class="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
            <div class="bg-sky-500 h-full transition-all duration-300 ease-out" :style="{ width: (props.queueItem.percent || 0) + '%' }"></div>
          </div>
        </div>
      </template>
      <template v-else>
        <button
          type="button"
          class="button-secondary flex items-center gap-2 shadow-sm font-medium"
          @click="onDownload"
        >
          <Icon name="fa6-solid:file-excel" />
          <span>{{ report.download_button_name || t('common.download') }}</span>
        </button>
      </template>
    </div>
  </div>
</template>
