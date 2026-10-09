<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDate } from '~/utils/date';
import AppLoading from '~/components/atoms/AppLoading.vue';
import H1 from '~/components/atoms/H1.vue';
import DatePicker from '~/components/atoms/DatePicker.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';

const { t } = useI18n();
const toast = useToast();
const router = useRouter();
const { $ReadingBatchTemplateApiService, $ContractEstimationApiService, $ReadingApiService, $ReadingBatchApiService, $ConfigProjectApiService } = useNuxtApp();

const loading = ref(false);
const is_fetching = ref(false);
const saving = ref(false);

const templates = ref([]);
const selectedTemplates = ref([]);
const lastInvoiceDateRange = ref(null);
const contractsHasRecent = ref([]);
const contractsNeedsEstimation = ref([]);
const estimatedDays = ref(90);
const dryRun = ref(true);
const periodChoices = ref([]);
const statisticChoices = ref([]);
const selectedPeriod = ref(null);
const selectedStatistic = ref(null);
const selectedContractsHasRecent = ref([]);
const selectedContractsNeedsEstimation = ref([]);

const executionResult = ref(null);
const showResultsRegion = ref(false);
const hasExecutedReal = ref(false);
const creatingBatch = ref(false);
const { fireUsageTypeTokens, fetchFireUsageTypeTokens } = useFireUsageTypeTokens();

const expandedRows = ref(new Set());
const histories = ref({}); // { contractId: [readings] }

const isDateDropdownVisible = ref(false);

const showContractRegion = ref(false);
const selectedContractId = ref(null);

const { $ContractApiService } = useNuxtApp();

const handleDateRangeSelected = (range) => {
  lastInvoiceDateRange.value = range;
  isDateDropdownVisible.value = false;
};

// Close dropdown on click outside
if (process.client) {
  window.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown-container-local')) {
      isDateDropdownVisible.value = false;
    }
  });
}

// Watch for filter changes to re-enable button
watch([selectedTemplates, lastInvoiceDateRange, estimatedDays, dryRun, selectedPeriod, selectedStatistic], () => {
  hasExecutedReal.value = false;
  executionResult.value = null;
});

const toggleRow = async (contractId) => {
  if (expandedRows.value.has(contractId)) {
    expandedRows.value.delete(contractId);
  } else {
    expandedRows.value.add(contractId);
    if (!histories.value[contractId]) {
      try {
        const res = await $ReadingApiService.getAll('', [], 1, 'reading_date', true, [contractId], null, null, false);
        histories.value[contractId] = res.results;
      } catch (err) {
        console.error(err);
      }
    }
  }
}

const isSubRegionOpen = ref(false);

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const toggleContractRegion = (force) => {
  showContractRegion.value = force !== undefined ? force : !showContractRegion.value;
  if (!showContractRegion.value) {
    isSubRegionOpen.value = false;
    selectedContractId.value = null;
  }
}

const openContractDetail = async (id) => {
  await toggleContractRegion(false);
  selectedContractId.value = id;
  toggleContractRegion(true);
}

const exportToExcel = () => {
  const allContracts = [...contractsNeedsEstimation.value, ...contractsHasRecent.value];
  if (allContracts.length === 0) return;

  const headers = [
    t('common.identification'),
    t('common.holder'),
    t('common.type'),
    t('reading_block.use_type'),
    t('billing_block.last_invoice_date'),
    t('reading_block.last_reading_date'),
    t('reading'),
    t('billing_block.consumption'),
    t('reading_block.penultimate_reading_date'),
    t('reading'),
    t('billing_block.consumption')
  ];

  const rows = allContracts.map(c => [
    c.token,
    c.holder_name,
    c.client_type_name,
    c.use_type_name,
    c.last_invoice_date,
    c.last_reading?.date,
    c.last_reading?.value,
    c.last_reading?.consumption,
    c.penultimate_reading?.date,
    c.penultimate_reading?.value,
    c.penultimate_reading?.consumption
  ]);

  const csvContent = "data:text/csv;charset=utf-8," 
    + [headers.join(','), ...rows.map(e => e.join(','))].join("\n");

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `estimacio_lectures_${new Date().toISOString().split('T')[0]}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

const permissions = ref(null);

const getPermissions = async () => {
  try {
    const data = await $ReadingApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    console.error(err);
  }
}

const getTemplates = async () => {
  try {
    const data = await $ReadingBatchTemplateApiService.getAll('', [], 1, 'name', false);
    templates.value = data.results.map(t => ({
      value: t.id,
      label: t.name || t.token
    }));
  } catch (err) {
    console.error(err);
  }
}

const search = async () => {
  if (selectedTemplates.value.length === 0) {
    toast.warning(t('reading_block.select_template_warning'));
    return;
  }

  is_fetching.value = true;
  contractsHasRecent.value = [];
  contractsNeedsEstimation.value = [];
  selectedContractsHasRecent.value = [];
  selectedContractsNeedsEstimation.value = [];
  
  try {
    const startDate = lastInvoiceDateRange.value?.start_date || null;
    const endDate = lastInvoiceDateRange.value?.end_date || null;

    const data = await $ContractEstimationApiService.getContractsForEstimation(
      selectedTemplates.value.map(t => t.value), 
      startDate, 
      endDate
    );
    
    contractsHasRecent.value = data.has_recent_reading || [];
    contractsNeedsEstimation.value = data.needs_estimation || [];
    
    selectedContractsHasRecent.value = [...contractsHasRecent.value];
    selectedContractsNeedsEstimation.value = [...contractsNeedsEstimation.value];
    if (data.settings?.default_days) {
      estimatedDays.value = data.settings.default_days;
    }
    if (data.settings?.period_choices) {
      periodChoices.value = data.settings.period_choices.map(p => ({
        value: p,
        label: t(`reading_block.estimation_period_${p}`)
      }));
    }
    if (data.settings?.statistic_choices) {
      statisticChoices.value = data.settings.statistic_choices.map(s => ({
        value: s,
        label: t(`reading_block.estimation_statistic_${s}`)
      }));
    }
    if (!selectedPeriod.value && data.settings?.default_period) {
      selectedPeriod.value = data.settings.default_period;
    }
    if (!selectedStatistic.value && data.settings?.default_statistic) {
      selectedStatistic.value = data.settings.default_statistic;
    }

    if (contractsHasRecent.value.length === 0 && contractsNeedsEstimation.value.length === 0) {
      toast.info(t('common.no_records'));
    }

  } catch (err) {
    console.error('Error fetching data for estimation:', err);
    toast.error(t('common.error_fetching_data'));
  } finally {
    is_fetching.value = false;
  }
}

const handleContractSelection = (contract, listName) => {
  const selectedList = listName === 'hasRecent' ? selectedContractsHasRecent : selectedContractsNeedsEstimation;
  const index = selectedList.value.findIndex(c => c.id === contract.id);
  if (index > -1) {
    selectedList.value.splice(index, 1);
  } else {
    selectedList.value.push(contract);
  }
}

const toggleSelectAll = (listName) => {
  if (listName === 'hasRecent') {
    if (selectedContractsHasRecent.value.length === contractsHasRecent.value.length) {
      selectedContractsHasRecent.value = [];
    } else {
      selectedContractsHasRecent.value = [...contractsHasRecent.value];
    }
  } else {
    if (selectedContractsNeedsEstimation.value.length === contractsNeedsEstimation.value.length) {
      selectedContractsNeedsEstimation.value = [];
    } else {
      selectedContractsNeedsEstimation.value = [...contractsNeedsEstimation.value];
    }
  }
}

const totalSelectedCount = computed(() => {
  return selectedContractsHasRecent.value.length + selectedContractsNeedsEstimation.value.length;
});

const totalContractsCount = computed(() => {
  return contractsHasRecent.value.length + contractsNeedsEstimation.value.length;
});

const isAllSelectedHasRecent = computed(() => {
  return contractsHasRecent.value.length > 0 && selectedContractsHasRecent.value.length === contractsHasRecent.value.length;
});

const isAllSelectedNeedsEstimation = computed(() => {
  return contractsNeedsEstimation.value.length > 0 && selectedContractsNeedsEstimation.value.length === contractsNeedsEstimation.value.length;
});

const estimationDetailsByToken = computed(() => {
  const map = {};
  for (const detail of executionResult.value?.details || []) {
    if (detail.token) map[detail.token] = detail;
  }
  return map;
});

const getEstimationResultForContract = (contract) => {
  const detail = estimationDetailsByToken.value[contract.token];
  if (!detail) return null;
  const result = (detail.results || []).find(r => r.status !== 'skipped');
  return result || null;
};

const generateEstimations = async () => {
  if (selectedContractsHasRecent.value.length === 0 && selectedContractsNeedsEstimation.value.length === 0) {
    toast.warning(t('reading_block.no_contracts_selected'));
    return;
  }

  saving.value = true;
  executionResult.value = null;

  try {
    const data = {
      has_recent_reading_ids: selectedContractsHasRecent.value.map(c => c.id),
      needs_estimation_ids: selectedContractsNeedsEstimation.value.map(c => c.id),
      days: estimatedDays.value,
      dry_run: dryRun.value,
      observation: `ESTIMADA_${selectedTemplates.value[0]?.label || ''}_${new Date().toISOString().split('T')[0]}`
    };

    if (selectedPeriod.value) data.period = selectedPeriod.value;
    if (selectedStatistic.value) data.statistic = selectedStatistic.value;

    const result = await $ContractEstimationApiService.createMassiveEstimation(data);
    executionResult.value = result;
    
    if (dryRun.value) {
      toast.info(t('reading_block.dry_run_completed', { processed: result.processed }));
    } else {
      toast.success(t('reading_block.estimation_created_success', { created: result.created }));
      hasExecutedReal.value = true;
    }
    // Keep results visible inline via the comparison column instead of auto-opening the details region.

  } catch (err) {
    console.error(err);
    toast.error(t('common.error_saving_data'));
  } finally {
    saving.value = false;
  }
}

const createBatch = async () => {
  if (!executionResult.value || dryRun.value) return;

  creatingBatch.value = true;
  try {
    const data = {
      template_id: selectedTemplates.value[0]?.value,
      reading_ids: executionResult.value.created_reading_ids || [],
      // The backend should know how to link these
      name: `LOT_ESTIMADES_${selectedTemplates.value[0]?.label || ''}_${new Date().toLocaleDateString()}`
    };

    const result = await $ReadingBatchApiService.create(data);
    toast.success(t('reading_batch_block.batch_created_success'));
    router.push(`/reading/reading-batches?id=${result.id}`);
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_saving_data'));
  } finally {
    creatingBatch.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  await Promise.all([getPermissions(), getTemplates()]);
  await fetchFireUsageTypeTokens();
  loading.value = false;
});

</script>

<template>
  <div id="wrapper" class="text-base p-4">
    <div class="flex justify-between items-center mb-6">
      <div class="flex items-center gap-4">
        <button @click="router.back()" class="p-2 hover:bg-slate-100 rounded-full transition-colors" title="Back">
          <Icon name="fa6-solid:arrow-left" class="text-slate-500" />
        </button>
        <H1>{{ t('reading_block.contract_estimation_title') }}</H1>
      </div>
    </div>

    <!-- Filters Section -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      <div class="lg:col-span-2 bg-white p-6 border border-gray-200 rounded-lg shadow-sm space-y-6">
        <h3 class="text-sm font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
          <Icon name="fa6-solid:filter" class="text-sky-500" />
          {{ t('common.filters') }}
        </h3>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label class="block text-xs font-semibold text-slate-500 uppercase mb-2">
              {{ t('reading_block.reading_batch_template') }}
            </label>
            <v-select 
              v-model="selectedTemplates" 
              :options="templates" 
              class="custom-select"
              multiple
              :placeholder="t('common.select')"
            />
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-semibold text-slate-500 uppercase mb-2">
                {{ t('billing_block.last_invoice_date') }}
              </label>
              
              <div class="relative dropdown-container-local">
                <button @click="isDateDropdownVisible = !isDateDropdownVisible"
                    class="w-full text-left bg-white rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-sky-500/20 px-4 py-2 flex items-center justify-between group hover:border-sky-300 transition-all h-[42px]">
                    <div class="flex items-center gap-2">
                      <Icon name="fa6-solid:calendar-days" class="text-slate-400 group-hover:text-sky-500" />
                      <span v-if="lastInvoiceDateRange && lastInvoiceDateRange.start_date && lastInvoiceDateRange.end_date" class="text-sm font-medium text-slate-700">
                        {{ formatDate(lastInvoiceDateRange.start_date) }} &harr; {{ formatDate(lastInvoiceDateRange.end_date) }}
                      </span>
                      <span v-else class="text-sm text-slate-400">
                        {{ t('billing_block.last_invoice_date') }}
                      </span>
                    </div>
                    <Icon name="fa6-solid:chevron-down" class="text-[10px] text-slate-300 transition-transform" :class="{ 'rotate-180': isDateDropdownVisible }" />
                </button>

                <div v-if="isDateDropdownVisible" class="z-[60] absolute mt-2 bg-white border border-gray-200 rounded-xl shadow-2xl p-2 dropdown-content-local">
                    <DatePicker @date-range-selected="handleDateRangeSelected" />
                </div>
              </div>
            </div>
            <div class="flex items-end">
              <button 
                @click="search" 
                class="button-primary w-full flex items-center justify-center gap-2"
                :disabled="is_fetching"
              >
                <Icon v-if="is_fetching" name="fa6-solid:spinner" class="animate-spin" />
                <Icon v-else name="fa6-solid:magnifying-glass" />
                {{ t('common.search') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Pane: Actions -->
      <div class="space-y-6">
        <div class="bg-sky-50 p-6 rounded-lg border border-sky-100 shadow-sm space-y-6">
          <h3 class="text-sm font-bold text-sky-700 uppercase tracking-wider flex items-center gap-2">
            <Icon name="fa6-solid:gears" />
            {{ t('reading_block.estimation_parameters') }}
          </h3>
          
          <div>
            <label class="block text-xs font-semibold text-slate-500 uppercase mb-2">
              {{ t('reading_block.days_to_estimate') }}
            </label>
            <input 
              type="number" 
              v-model="estimatedDays" 
              class="input w-full bg-white"
              min="1"
            />
          </div>

          <div v-if="periodChoices.length > 0">
            <label class="block text-xs font-semibold text-slate-500 uppercase mb-2">
              {{ t('reading_block.estimation_period') }}
            </label>
            <select v-model="selectedPeriod" class="input w-full bg-white">
              <option v-for="opt in periodChoices" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>

          <div v-if="statisticChoices.length > 0">
            <label class="block text-xs font-semibold text-slate-500 uppercase mb-2">
              {{ t('reading_block.estimation_statistic') }}
            </label>
            <select v-model="selectedStatistic" class="input w-full bg-white">
              <option v-for="opt in statisticChoices" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>

          <div class="flex items-center justify-between p-3 bg-white rounded border border-sky-100">
            <span class="text-xs font-semibold text-slate-500 uppercase">
              {{ t('common.dry_run') }}
            </span>
            <button 
              type="button" 
              @click="dryRun = !dryRun"
              class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none"
              :class="dryRun ? 'bg-sky-500' : 'bg-gray-300'"
            >
              <span 
                class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                :class="dryRun ? 'translate-x-6' : 'translate-x-1'"
              />
            </button>
          </div>

          <div class="pt-4 border-t border-sky-200">
            <div class="flex justify-between items-center mb-4">
              <span class="text-xs font-bold text-slate-500 uppercase">{{ t('common.selected') }}:</span>
              <span class="text-lg font-black text-sky-700">{{ totalSelectedCount }} <small class="font-normal text-slate-400">/ {{ totalContractsCount }}</small></span>
            </div>
            <button 
              @click="generateEstimations" 
              class="button-primary w-full bg-sky-600 hover:bg-sky-700 text-white flex justify-center items-center gap-2 py-3 shadow-md active:translate-y-0.5 transition-all"
              :disabled="saving || totalSelectedCount === 0 || hasExecutedReal"
              :class="{ 'opacity-50 grayscale cursor-not-allowed': hasExecutedReal }"
            >
              <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin" />
              <Icon v-else :name="hasExecutedReal ? 'fa6-solid:check' : 'fa6-solid:bolt'" />
              <span class="font-bold uppercase tracking-wide">
                {{ hasExecutedReal ? t('common.already_executed') : t('reading_block.generate_estimations') }}
              </span>
            </button>

            <!-- Generate Batch Button (only after real execution) -->
            <button 
              v-if="hasExecutedReal"
              @click="createBatch" 
              class="button-default w-full mt-4 bg-white hover:bg-slate-50 text-slate-700 flex justify-center items-center gap-2 py-3 border-2 border-sky-500 shadow-sm transition-all"
              :disabled="creatingBatch"
            >
              <Icon v-if="creatingBatch" name="fa6-solid:spinner" class="animate-spin" />
              <Icon v-else name="fa6-solid:layer-group" class="text-sky-500" />
              <span class="font-bold uppercase tracking-wide">
                {{ t('billing_block.generate_missing_batch') }}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Results Toolbar & Contracts Sections -->
    <div v-if="contractsNeedsEstimation.length > 0 || contractsHasRecent.length > 0" class="md:col-span-2 lg:col-span-3 space-y-8 pb-32">
      
      <div class="flex justify-start px-2">
        <button 
          @click="exportToExcel" 
          class="bg-white hover:bg-green-50 text-green-700 border border-green-200 px-4 py-2 rounded-lg flex items-center gap-2 shadow-sm transition-all"
        >
          <Icon name="fa6-solid:file-excel" />
          <span class="text-xs font-bold uppercase tracking-wider">{{ t('common.export') }}</span>
        </button>
      </div>
      
      <!-- Needs Estimation Section -->
      <div v-if="contractsNeedsEstimation.length > 0" class="space-y-4">
        <h3 class="text-sm font-black text-slate-700 uppercase tracking-widest flex items-center gap-2 px-2">
          <Icon name="fa6-solid:hourglass-start" class="text-amber-500" />
          {{ t('reading_block.needs_estimation') }}
          <span class="bg-amber-100 text-amber-700 text-[10px] px-2 py-0.5 rounded-full">{{ contractsNeedsEstimation.length }}</span>
        </h3>
        <div class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
          <div class="heading grid grid-cols-[40px,40px,130px,1fr,100px,100px,100px,120px,120px,130px] gap-2 p-4 bg-slate-50 border-b font-bold text-[10px] text-slate-500 uppercase tracking-wider items-center">
            <div class="flex justify-center">
              <input type="checkbox" :checked="isAllSelectedNeedsEstimation" @change="toggleSelectAll('needsEstimation')" />
            </div>
            <div></div> <!-- Eye placeholder -->
            <div>{{ t('common.identification') }}</div>
            <div>{{ t('common.holder') }}</div>
            <div>{{ t('common.use') }}</div>
            <div>{{ t('common.type') }}</div>
            <div>{{ t('billing_block.last_invoice_date_short') }}</div>
            <div>{{ t('reading_block.last_reading') }}</div>
            <div>{{ t('reading_block.penultimate_reading') }}</div>
            <div class="text-emerald-600">{{ t('reading_block.new_estimation') }}</div>
          </div>
          <div class="divide-y divide-gray-100">
            <template v-for="contract in contractsNeedsEstimation" :key="contract.id">
              <div 
                class="grid grid-cols-[40px,40px,130px,1fr,100px,100px,100px,120px,120px,130px] gap-2 p-4 items-center hover:bg-slate-50 transition-colors cursor-pointer group"
                :class="{ 'bg-sky-50/20': selectedContractsNeedsEstimation.some(c => c.id === contract.id) }"
                @click="handleContractSelection(contract, 'needsEstimation')"
              >
                <div class="flex justify-center" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedContractsNeedsEstimation.some(c => c.id === contract.id)"
                    @change="handleContractSelection(contract, 'needsEstimation')"
                  />
                </div>
                <div class="flex justify-center" @click.stop>
                   <button @click="toggleRow(contract.id)" class="p-1 hover:bg-sky-100 rounded text-sky-600 transition-colors">
                      <Icon :name="expandedRows.has(contract.id) ? 'fa6-solid:eye-slash' : 'fa6-solid:eye'" />
                   </button>
                </div>
                <div class="font-mono text-xs font-bold text-sky-600 underline" @click.stop="openContractDetail(contract.id)">{{ contract.token }}</div>
                <div class="text-[11px] font-medium text-slate-600 truncate">{{ contract.holder_name }}</div>
                <div class="text-[10px] text-slate-400 uppercase font-bold flex items-center gap-1">
                  {{ contract.use_type_name }}
                  <Icon v-if="fireUsageTypeTokens.includes(contract.use_type_token)" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
                </div>
                <div class="text-[10px] text-slate-400 uppercase">{{ contract.client_type_name }}</div>
                <div class="text-[11px] text-slate-500 font-mono">{{ formatDate(contract.last_invoice_date) }}</div>

                <div class="text-[10px] leading-tight">
                   <div class="font-bold text-slate-700">{{ formatDate(contract.last_reading?.date) }}</div>
                   <div v-if="contract.last_reading?.consumption !== null" class="text-sky-600 font-black">{{ contract.last_reading?.consumption }} <small>m³</small></div>
                </div>

                <div class="text-[10px] leading-tight">
                   <div class="text-slate-400 italic">{{ formatDate(contract.penultimate_reading?.date) }}</div>
                   <div v-if="contract.penultimate_reading?.consumption !== null" class="text-slate-400">{{ contract.penultimate_reading?.consumption }} <small>m³</small></div>
                </div>

                <div class="text-[10px] leading-tight" @click.stop>
                  <div v-if="getEstimationResultForContract(contract)"
                    class="p-1.5 rounded bg-emerald-50 border-2 border-dashed border-emerald-400">
                    <div class="font-bold text-emerald-800">{{ formatDate(getEstimationResultForContract(contract).date) }}</div>
                    <div class="text-emerald-700 font-black"> {{ getEstimationResultForContract(contract).consumption }} <small>m³ ({{ getEstimationResultForContract(contract).val }})</small></div>
                  </div>
                  <span v-else class="text-slate-300 italic">&mdash;</span>
                </div>
              </div>

              <!-- Expandable Row -->
              <div v-if="expandedRows.has(contract.id)" class="bg-slate-50 border-y border-sky-100 px-12 py-4">
                 <div v-if="!histories[contract.id]" class="flex justify-center py-4">
                    <Icon name="fa6-solid:spinner" class="animate-spin text-sky-400" />
                 </div>
                 <div v-else class="space-y-3">
                    <h4 class="text-[10px] font-black text-sky-700 uppercase tracking-widest">{{ t('common.reading_history') }}</h4>
                    <div class="bg-white rounded border border-gray-200 overflow-hidden text-[12px]">
                      <table class="w-full text-left border-collapse">
                        <thead class="bg-gray-50 border-b">
                          <tr>
                            <th class="p-2">{{ t('common.date') }}</th>
                            <th class="p-2">{{ t('reading') }}</th>
                            <th class="p-2">{{ t('billing_block.consumption') }}</th>
                            <th class="p-2">{{ t('billing_block.consumption_days') }}</th>
                            <th class="p-2">{{ t('billing_block.consumption_daily_avg') }}</th>
                            <th class="p-2">{{ t('common.origin') }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="rh in histories[contract.id]" :key="rh.id" class="border-b last:border-0 hover:bg-slate-50">
                            <td class="p-2">{{ formatDate(rh.reading_date) }}</td>
                            <td class="p-2 font-mono font-bold">{{ parseInt(rh.reading_value) }}</td>
                            <td class="p-2 text-sky-600 font-bold">{{ parseInt(rh.calculated_value) }} m³</td>
                            <td class="p-2">{{ rh.consumption_days ?? '-' }}</td>
                            <td class="p-2 text-slate-600">{{ rh.consumption_days ? (parseInt(rh.calculated_value) / rh.consumption_days).toFixed(2) : '-' }} m³</td>
                            <td class="p-2 text-slate-400 italic">{{ rh.origin }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                 </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- Has Recent Reading Section -->
      <div v-if="contractsHasRecent.length > 0" class="space-y-4 opacity-75 grayscale-[0.5] hover:opacity-100 transition-opacity">
        <h3 class="text-sm font-black text-slate-500 uppercase tracking-widest flex items-center gap-2 px-2">
          <Icon name="fa6-solid:circle-check" class="text-green-500" />
          {{ t('reading_block.has_recent_reading') }}
          <span class="bg-gray-100 text-gray-600 text-[10px] px-2 py-0.5 rounded-full">{{ contractsHasRecent.length }}</span>
        </h3>
        <div class="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
          <div class="heading grid grid-cols-[40px,40px,130px,1fr,100px,100px,100px,120px,120px,130px] gap-2 p-4 bg-slate-50 border-b font-bold text-[10px] text-slate-500 uppercase tracking-wider items-center">
            <div class="flex justify-center">
              <input type="checkbox" :checked="isAllSelectedHasRecent" @change="toggleSelectAll('hasRecent')" />
            </div>
            <div></div> <!-- Eye placeholder -->
            <div>{{ t('common.identification') }}</div>
            <div>{{ t('common.holder') }}</div>
            <div>{{ t('common.use') }}</div>
            <div>{{ t('common.type') }}</div>
            <div>{{ t('billing_block.last_invoice_date_short') }}</div>
            <div>{{ t('reading_block.last_reading') }}</div>
            <div>{{ t('reading_block.penultimate_reading') }}</div>
            <div class="text-emerald-600">{{ t('reading_block.new_estimation') }}</div>
          </div>
          <div class="divide-y divide-gray-100">
            <template v-for="contract in contractsHasRecent" :key="contract.id">
              <div 
                class="grid grid-cols-[40px,40px,130px,1fr,100px,100px,100px,120px,120px,130px] gap-2 p-4 items-center hover:bg-slate-50 transition-colors cursor-pointer"
                :class="{ 'bg-sky-50/20': selectedContractsHasRecent.some(c => c.id === contract.id) }"
                @click="handleContractSelection(contract, 'hasRecent')"
              >
                <div class="flex justify-center" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedContractsHasRecent.some(c => c.id === contract.id)"
                    @change="handleContractSelection(contract, 'hasRecent')"
                  />
                </div>
                <div class="flex justify-center" @click.stop>
                   <button @click="toggleRow(contract.id)" class="p-1 hover:bg-sky-100 rounded text-sky-600 transition-colors">
                      <Icon :name="expandedRows.has(contract.id) ? 'fa6-solid:eye-slash' : 'fa6-solid:eye'" />
                   </button>
                </div>
                <div class="font-mono text-xs font-bold text-sky-600 underline" @click.stop="openContractDetail(contract.id)">{{ contract.token }}</div>
                <div class="text-[11px] font-medium text-slate-600 truncate">{{ contract.holder_name }}</div>
                <div class="text-[10px] text-slate-400 uppercase font-bold flex items-center gap-1">
                  {{ contract.use_type_name }}
                  <Icon v-if="fireUsageTypeTokens.includes(contract.use_type_token)" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
                </div>
                <div class="text-[10px] text-slate-400 uppercase">{{ contract.client_type_name }}</div>
                <div class="text-[11px] text-slate-500 font-mono">{{ formatDate(contract.last_invoice_date) }}</div>

                <div class="text-[10px] leading-tight">
                   <div class="font-bold text-slate-700">{{ formatDate(contract.last_reading?.date) }}</div>
                   <div v-if="contract.last_reading?.consumption !== null" class="text-sky-600 font-black">{{ contract.last_reading?.consumption }} <small>m³</small></div>
                </div>

                <div class="text-[10px] leading-tight">
                   <div class="text-slate-400 italic">{{ formatDate(contract.penultimate_reading?.date) }}</div>
                   <div v-if="contract.penultimate_reading?.consumption !== null" class="text-slate-400">{{ contract.penultimate_reading?.consumption }} <small>m³</small></div>
                </div>

                <div class="text-[10px] leading-tight" @click.stop>
                  <div v-if="getEstimationResultForContract(contract)"
                    class="p-1.5 rounded bg-emerald-50 border-2 border-dashed border-emerald-400">
                    <div class="font-bold text-emerald-800">{{ formatDate(getEstimationResultForContract(contract).date) }}</div>
                    <div class="text-emerald-700 font-black">{{ getEstimationResultForContract(contract).val }} <small>m³ ({{ getEstimationResultForContract(contract).consumption }})</small></div>
                  </div>
                  <span v-else class="text-slate-300 italic">&mdash;</span>
                </div>
              </div>

              <!-- Expandable Row -->
              <div v-if="expandedRows.has(contract.id)" class="bg-slate-50 border-y border-sky-100 px-12 py-4">
                 <div v-if="!histories[contract.id]" class="flex justify-center py-4">
                    <Icon name="fa6-solid:spinner" class="animate-spin text-sky-400" />
                 </div>
                 <div v-else class="space-y-3">
                    <h4 class="text-[10px] font-black text-sky-700 uppercase tracking-widest">{{ t('common.reading_history') }}</h4>
                    <div class="bg-white rounded border border-gray-200 overflow-hidden text-[12px]">
                      <table class="w-full text-left border-collapse">
                        <thead class="bg-gray-50 border-b">
                          <tr>
                            <th class="p-2">{{ t('common.date') }}</th>
                            <th class="p-2">{{ t('reading') }}</th>
                            <th class="p-2">{{ t('billing_block.consumption') }}</th>
                            <th class="p-2">{{ t('billing_block.consumption_days') }}</th>
                            <th class="p-2">{{ t('billing_block.consumption_daily_avg') }}</th>
                            <th class="p-2">{{ t('common.origin') }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="rh in histories[contract.id]" :key="rh.id" class="border-b last:border-0 hover:bg-slate-50">
                            <td class="p-2">{{ formatDate(rh.reading_date) }}</td>
                            <td class="p-2 font-mono font-bold">{{ parseInt(rh.reading_value) }}</td>
                            <td class="p-2 text-sky-600 font-bold">{{ parseInt(rh.calculated_value) }} m³</td>
                            <td class="p-2">{{ rh.consumption_days ?? '-' }}</td>
                            <td class="p-2 text-slate-600">{{ rh.consumption_days ? (parseInt(rh.calculated_value) / rh.consumption_days).toFixed(2) : '-' }} m³</td>
                            <td class="p-2 text-slate-400 italic">{{ rh.origin }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                 </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
    
    <div v-else-if="!is_fetching" class="text-center py-20 bg-white border border-dashed border-gray-300 rounded-lg">
      <div class="max-w-xs mx-auto">
        <Icon name="fa6-solid:file-circle-question" class="text-5xl text-slate-200 mb-4" />
        <p class="text-slate-400 font-medium">{{ selectedTemplates.length > 0 ? t('common.no_records') : t('reading_block.select_template_warning') }}</p>
      </div>
    </div>

    <!-- Execution Summary Footer -->
    <Transition name="fade">
      <div v-if="executionResult" class="fixed bottom-6 left-1/2 -translate-x-1/2 z-40">
        <div class="bg-slate-900 text-white px-6 py-3 rounded-full shadow-2xl flex items-center gap-6 border border-slate-700/50 backdrop-blur-md">
          <div class="flex items-center gap-2">
            <Icon :name="dryRun ? 'fa6-solid:flask' : 'fa6-solid:circle-check'" :class="dryRun ? 'text-amber-400' : 'text-green-400'" />
            <span class="text-sm font-bold uppercase tracking-wide">
              {{ dryRun ? t('common.simulation') : t('common.execution') }}
            </span>
          </div>
          <div class="h-4 w-px bg-slate-700"></div>
          <div class="flex gap-4 text-sm">
            <span v-if="executionResult.processed !== undefined" class="font-medium">
              {{ t('common.processed') }}: <span class="text-sky-300">{{ executionResult.processed }}</span>
            </span>
            <span v-if="executionResult.created !== undefined" class="font-medium">
              {{ t('common.created') }}: <span class="text-green-300">{{ executionResult.created }}</span>
            </span>
          </div>
          <button @click="showResultsRegion = true" class="bg-sky-500 hover:bg-sky-400 text-white text-xs font-bold px-3 py-1 rounded transition-colors uppercase tracking-wider">
            {{ t('common.view_details') }}
          </button>
        </div>
      </div>
    </Transition>
  </div>

  <!-- Contract Side Region (Standard Floating Region) -->
  <div role="region" id="contract_region"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-50 shadow-2xl"
    :class="{ 'translate-x-0': showContractRegion, 'translate-x-[2000px]': !showContractRegion, 'w-[95%]': isSubRegionOpen, 'w-[50%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleContractRegion(false)" class="p-2 hover:bg-slate-100 rounded-full transition-colors font-black">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full overflow-y-auto">
      <ContractRegion 
        v-if="selectedContractId" 
        :id="parseInt(selectedContractId)" 
        :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" 
        @changed="search" 
        @close-subregion="toggleContractRegion(false)"
      />
    </div>
  </div>

  <!-- Results Side Region (Fixed) -->
  <div v-if="showResultsRegion" role="region" id="results_region"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/3 z-50 shadow-2xl"
    :class="{ 'translate-x-0': showResultsRegion, 'translate-x-[2000px]': !showResultsRegion }">
    <div id="region_nav" class="mb-3 px-3 flex justify-between items-center border-b border-gray-50 pb-2">
      <button @click="showResultsRegion = false" class="p-2 hover:bg-slate-100 rounded-full transition-colors">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
      <span class="text-xs font-black uppercase text-slate-400 tracking-widest">{{ t('common.details') }}</span>
    </div>
    <div class="px-10 py-6 overflow-y-auto h-[calc(100vh-60px)]">
      <h2 class="text-xl font-black text-slate-800 mb-6 flex items-center gap-2">
        <Icon name="fa6-solid:list-check" class="text-sky-500" />
        {{ t('common.execution_summary') }}
      </h2>
      
      <div v-if="executionResult" class="space-y-6">
        <div class="grid grid-cols-2 gap-4">
          <div class="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span class="block text-[10px] font-black text-slate-400 uppercase mb-1">{{ t('common.processed') }}</span>
            <span class="text-2xl font-black text-slate-700">{{ executionResult.processed || 0 }}</span>
          </div>
          <div class="bg-green-50 p-4 rounded-xl border border-green-100">
            <span class="block text-[10px] font-black text-green-400 uppercase mb-1">{{ t('common.created') }}</span>
            <span class="text-2xl font-black text-green-700">{{ executionResult.created || 0 }}</span>
          </div>
        </div>

        <div v-if="executionResult.details && executionResult.details.length > 0">
           <h3 class="text-xs font-black text-slate-400 uppercase mb-3">{{ t('common.details') }}</h3>
           <div class="space-y-2">
              <div class="space-y-3">
                <div v-for="(detail, index) in executionResult.details" :key="index" class="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
                  <div class="flex justify-between items-start mb-2 border-b border-slate-50 pb-2">
                    <div class="flex flex-col">
                      <span class="text-xs font-black text-sky-700 tracking-tighter">{{ detail.token }}</span>
                      <span class="text-[10px] font-bold text-slate-500 uppercase">{{ detail.holder_name }}</span>
                    </div>
                    <div class="flex items-center gap-1">
                      <span v-if="detail.results?.[0]?.is_intermediate" class="bg-amber-100 text-amber-700 text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-tighter">
                        Intermèdia
                      </span>
                      <span 
                        class="text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-tighter"
                        :class="detail.status === 'error' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'"
                      >
                        {{ detail.status === 'error' ? t('common.error') : (dryRun ? t('common.dry_run') : t('common.created')) }}
                      </span>
                    </div>
                  </div>

                  <div v-if="detail.results && detail.results.length" class="grid grid-cols-1 gap-2">
                    <div v-for="res in detail.results" :key="res.sp_id" class="space-y-2">
                      <div v-if="res.status !== 'skipped'" class="grid grid-cols-2 gap-2 text-[10px]">
                        <div class="p-2 bg-slate-50 rounded border border-slate-100">
                          <div class="text-slate-400 uppercase font-bold mb-1">{{ t('reading_block.last_reading') }}</div>
                          <div class="flex justify-between items-center">
                            <span class="font-medium">{{ formatDate(res.base_date) }}</span>
                            <div class="flex flex-col items-end">
                              <span class="font-black text-slate-700 leading-none">{{ res.base_val }}</span>
                              <span v-if="res.base_consumption !== undefined" class="text-[8px] font-bold text-slate-400 uppercase">{{ res.base_consumption }} m³</span>
                            </div>
                          </div>
                        </div>
                        <div class="p-2 bg-sky-50 rounded border border-sky-100">
                          <div class="text-sky-400 uppercase font-bold mb-1">{{ t('common.estimation') }}</div>
                          <div class="flex justify-between items-center">
                            <span class="font-medium">{{ formatDate(res.date) }}</span>
                            <div class="flex flex-col items-end">
                              <span class="font-black text-sky-700 leading-none">{{ res.val }}</span>
                              <span class="text-[8px] font-bold text-sky-500 uppercase">{{ res.consumption }} m³</span>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div v-else class="text-[10px] text-amber-600 font-bold p-2 bg-amber-50 rounded border border-amber-100">
                         {{ res.msg.includes('reading_block') ? t(res.msg) : res.msg }}
                      </div>
                    </div>
                  </div>
                  <div v-else-if="detail.msg" class="text-[10px] text-amber-600 font-bold p-2 bg-amber-50 rounded border border-amber-100">
                    {{ detail.msg.includes('reading_block') ? t(detail.msg) : detail.msg }}
                  </div>
                </div>
              </div>
           </div>
        </div>

        <div v-if="hasExecutedReal" class="p-4 bg-amber-50 text-amber-700 rounded-xl border border-amber-100 text-xs italic flex items-start gap-2">
          <Icon name="fa6-solid:circle-info" class="mt-0.5" />
          <p>{{ t('reading_block.real_execution_done_info') }}</p>
        </div>
      </div>
    </div>
  </div>

  <!-- Loading Overlay -->
  <div v-if="loading || is_fetching" class="fixed inset-0 bg-slate-900/10 backdrop-blur-sm flex items-center justify-center z-50 transition-all">
    <div class="bg-white p-8 rounded-2xl shadow-2xl flex flex-col items-center gap-4">
      <AppLoading :text="is_fetching ? t('common.fetching_data') : t('common.loading')" />
    </div>
  </div>
</template>

<style scoped>
.custom-select :deep(.vs__dropdown-toggle) {
  @apply border-gray-300 rounded-md py-1.5 px-2 bg-white shadow-sm transition-all focus-within:ring-2 focus-within:ring-sky-500/20 focus-within:border-sky-500;
}

.custom-select :deep(.vs__search::placeholder) {
  @apply text-slate-400 text-sm;
}

.input {
  @apply border border-gray-300 rounded-md px-4 py-2.5 shadow-sm focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 outline-none transition-all text-sm;
}

.custom-datepicker :deep(.dp__input) {
  @apply border-gray-300 rounded-md py-2 px-4 text-sm shadow-sm transition-all focus-within:ring-2 focus-within:ring-sky-500/20 focus-within:border-sky-500;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translate(-50%, 20px);
}

.dropdown-container-local {
    position: relative;
    width: 100%;
}

.dropdown-content-local {
    position: absolute;
    top: 100%;
    left: 0;
    width: auto;
    min-width: 350px;
    background: white;
    box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
    border-radius: 12px;
    margin-top: 8px;
    z-index: 100;
}
</style>
