<script setup>
import { ref, watch, onMounted } from 'vue';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';
import SelectInvoiceCategory from './SelectInvoiceCategory.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const { $ReadingApiService, $ExploitationApiService, $BillingApiService, $ConfigProjectApiService, $BillingBatchApiService } = useNuxtApp();

const props = defineProps({
  // When both are null, allow selection between contract/person
  object_id: Number,
  service: Object,
  persons: Array,
  // Two-way bound selectedCustom object from parent
  selectedCustom: Object,
  companies: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits([
  'update:selectedCustom',
  'select-contract',
  'select-person',
  'clear-selected',
  'update:readingHasInvoice',
  'select-exploitation'
]);

const showCustomInvoice = ref(true);

// Local mirror for two-way binding
const localSelectedCustom = ref(props.selectedCustom || null);
watch(() => props.selectedCustom, (val) => {
  localSelectedCustom.value = val;
}, { deep: true });
watch(localSelectedCustom, (val) => {
  emit('update:selectedCustom', val);
}, { deep: true });

// Title handling
const title = ref('');
const updateTitle = () => {
  if (!localSelectedCustom.value) return;
  localSelectedCustom.value.title = title.value;
};

// Custom invoice type / readings
const customInvoiceTypes = ref([]);
const selectedCustomInvoiceType = ref(null);
const readings = ref([]);
const selectedReading = ref(null);
const loadingReadings = ref(false);
const generalInvoice = ref(false);
const selectedExploitation = ref(null);
const exploitations = ref([]);
const loadingExploitations = ref(false);
const billingBatches = ref([]);
const loadingBillingBatches = ref(false);
const selectedBillingBatch = ref(null);
const selectedCategoryId = ref(null);
const selectedCompanyId = ref(null);
const hasInvoiceCategories = ref(true);
const useMultipleCompanies = ref(false);

const onCategoriesLoaded = ({ options }) => {
  hasInvoiceCategories.value = !!options?.length;
};

const getCustomInvoiceType = () => {
  customInvoiceTypes.value = [];
  customInvoiceTypes.value.push({ value: 'custom', label: t('common.custom')});
  
  if (localSelectedCustom.value?.entity === 'contract') {
    customInvoiceTypes.value.push({ value: 'reading', label: t('readings') });
  }
};

const getExploitations = async () => {
  loadingExploitations.value = true;
  try {
    const response = await $ExploitationApiService.getData();
    exploitations.value = response.results.map(exploitation => ({
      value: exploitation.id,
      label: exploitation.name
    }));
  } catch (error) {
    console.log(error);
  } finally {
    loadingExploitations.value = false;
  }
};

const getReadings = async () => {
  loadingReadings.value = true;
  try {
    const response = await $ReadingApiService.getAll(
      '', [], 1, 'id', false,
      localSelectedCustom.value?.entity === 'contract' ? [localSelectedCustom.value.id] : [],
      null, null, false
    );

    const groupedReadings = response.results.reduce((acc, reading) => {
      const date = reading.reading_date;
      if (reading.is_control) return acc;
      if (!acc[date]) {
        acc[date] = { has_invoice: reading.invoice != null, ids: [reading.id]};
      } else {
        acc[date].ids.push(reading.id);
      }
      return acc;
    }, {});
    readings.value = Object.entries(groupedReadings).map(([date, total]) => ({
      value: date,
      label: `${date}`,
      has_invoice: total.has_invoice,
      ids: total.ids
    }));
  } catch (error) {
    console.log(error);
  } finally {
    loadingReadings.value = false;
  }
};

const getBillingBatches = async () => {
  loadingBillingBatches.value = true;
  try {
    const processedToken = await $ConfigProjectApiService.get('billing_batch_processed');
    
    // Fetch Billings (Facturacions)
    const billingResponse = await $BillingApiService.getAll('', [processedToken], 1, 'created_at', true);
    const billings = billingResponse.results.map(b => ({
      value: b.id,
      label: `${b.name} (${b.token}) [${t('billing')}]`,
      type: 'billing'
    }));

    // Fetch BillingBatches (Lots)
    const batchResponse = await $BillingBatchApiService.getAll('', [processedToken], 1, 'created_at', true);
    const batches = batchResponse.results.map(b => ({
      value: b.id,
      label: `${b.name} (${b.token}) [${t('billingbatch')}]`,
      type: 'billing_batch'
    }));

    billingBatches.value = [...billings, ...batches];
  } catch (error) {
    console.log(error);
  } finally {
    loadingBillingBatches.value = false;
  }
};

const updateSelect = async (event, field) => {
  switch (field) {
    case 'custom_invoice_type':
      selectedCustomInvoiceType.value = event;
      if (localSelectedCustom.value) {
        localSelectedCustom.value.type = event?.value;
        if (event?.value != 'reading') {
          localSelectedCustom.value.billing_batch_id = null;
          localSelectedCustom.value.billing_id = null;
          selectedBillingBatch.value = null;
        }
      }
      if (event?.value != 'reading') generalInvoice.value = false;
      selectedReading.value = null;
      emit('update:readingHasInvoice', false);
      if (event?.value === 'reading') {
        await getReadings();
      }
      break;
    case 'reading':
      selectedReading.value = event;
      if (localSelectedCustom.value) {
        localSelectedCustom.value.readings = event?.ids;
        localSelectedCustom.value.reading_date = event?.value;
      }
      emit('update:readingHasInvoice', true);
      break;
    case 'exploitation':
      selectedExploitation.value = event;
      console.log("selectedExploitation.value", selectedExploitation.value)
      emit('select-exploitation', event.value);
      break;
    case 'billing_batch':
      selectedBillingBatch.value = event;
      if (localSelectedCustom.value) {
        if (event?.type === 'billing') {
          localSelectedCustom.value.billing_id = event?.value;
          localSelectedCustom.value.billing_batch_id = null;
        } else if (event?.type === 'billing_batch') {
          localSelectedCustom.value.billing_batch_id = event?.value;
          localSelectedCustom.value.billing_id = null;
        } else {
          localSelectedCustom.value.billing_id = null;
          localSelectedCustom.value.billing_batch_id = null;
        }
      }
      break;
  }
};

const updateGeneralInvoice = () => {
  localSelectedCustom.value.is_general = generalInvoice.value;
}

const updateCategory = () => {
  if (!localSelectedCustom.value) return;
  localSelectedCustom.value.category = selectedCategoryId.value;
}

const updateCompany = () => {
  if (!localSelectedCustom.value) return;
  localSelectedCustom.value.company = selectedCompanyId.value;
}

onMounted(async () => {
  // Mirror existing behavior: show info box initially
  showCustomInvoice.value = true;
  getCustomInvoiceType();
  getExploitations();
  getBillingBatches();
  try {
    const multi = await $ConfigProjectApiService.get('use_multiple_companies');
    useMultipleCompanies.value = multi === true || multi === 'True' || multi === 'true';
  } catch {
    useMultipleCompanies.value = false;
  }
});

watch(() =>props.selectedCustom, () => {
  getCustomInvoiceType();
}, { deep: true, immediate: true });

</script>

<template>
  <fieldset class="w-[95%] mb-4 rounded-lg p-1 mx-5">
    <div v-if="showCustomInvoice" class="flex items-center gap-2 p-2 rounded border border-sky-500 mb-4 text-sky-500">
      <span>
        {{ $t('informative_block.info_individual_invoice') }}
      </span>
      <button @click="showCustomInvoice = false" class="text-sky-500 hover:text-sky-600 transition-all duration-300 flex mb-auto">
        <Icon name="fa6-solid:xmark" class="h-5 w-5" />
      </button>
    </div>

    <div v-if="!object_id" class="grid grid-cols-2 gap-3">
      <div class="space-y-1">
        <ButtonSeleccio v-if="!localSelectedCustom || localSelectedCustom?.entity !== 'contract'" :disabled="localSelectedCustom?.entity === 'person'" :small="true"
          @click="emit('select-contract')">
          {{ $t('common.select') }} {{ $t('contract') }}
        </ButtonSeleccio>
        <div v-if="localSelectedCustom && localSelectedCustom?.entity === 'contract'"
          class="px-4 text-sky-500 rounded w-full text-left border py-2 border-sky-400 relative group">
          {{ localSelectedCustom.label }}
          <button @click="emit('clear-selected')"
            class="absolute right-2 top-1/2 -translate-y-1/2 p-2 opacity-0 group-hover:opacity-100 transition-all duration-300">
            <Icon name="fa6-solid:xmark" class="text-red-500" />
          </button>
        </div>
      </div>
      <div class="space-y-1">
        <ButtonSeleccio v-if="!localSelectedCustom || localSelectedCustom?.entity !== 'person'" :disabled="localSelectedCustom?.entity === 'contract'" :small="true"
          @click="emit('select-person')">
          {{ $t('common.select') }} {{ $t('person') }}
        </ButtonSeleccio>
        <div v-if="localSelectedCustom && localSelectedCustom?.entity === 'person'"
          class="px-4 text-sky-500 rounded w-full text-left border py-2 border-sky-400 relative group">
          {{ localSelectedCustom.label }}
          <button @click="emit('clear-selected')"
            class="absolute right-2 top-1/2 -translate-y-1/2 p-2 opacity-0 group-hover:opacity-100 transition-all duration-300">
            <Icon name="fa6-solid:xmark" class="text-red-500" />
          </button>
        </div>
      </div>
    </div>
    <div v-else>
      <div class="px-4 text-sky-500 rounded w-full text-left border py-2 border-sky-400 relative group flex justify-between items-center">
        {{ localSelectedCustom?.label }}
        <span class="text-xs font-bold uppercase tracking-wide">
          {{ localSelectedCustom?.entity ? $t(localSelectedCustom.entity) : '-' }}
        </span>
      </div>
    </div>

    <div class="mt-2 grid grid-cols-2 gap-2 items-center">
      <input type="text" v-model="title" class="input" :placeholder="$t('common.title')" @change="updateTitle" />
      
      <div>
        <!-- <div v-if="localSelectedCustom?.general_invoice" class="flex items-center gap-2" :class="{ 'opacity-60': selectedCustomInvoiceType?.value != 'reading' }">
          <input type="checkbox" :disabled="selectedCustomInvoiceType?.value != 'reading'" v-model="generalInvoice" @change="updateGeneralInvoice" />
          <abbr :title="$t('informative_block.info_make_general_invoice')">
            <Icon name="fa6-solid:circle-info" class="text-slate-500" />
          </abbr>
          <label class="block text-xs font-medium text-slate-600 uppercase">
            {{ $t('billing_block.general_invoice') }}
          </label>
        </div> -->
      </div>
      <div>
        <label class="block text-xs font-medium text-slate-600 uppercase">
          {{ $t('common.type') }}
        </label>
        <v-select class="block w-full mr-1 required" :model-value="selectedCustomInvoiceType" :disabled="!localSelectedCustom?.id"
          :options="customInvoiceTypes" @update:modelValue="updateSelect($event, 'custom_invoice_type')">
          <template #no-options="{ search, searching, loading }">
            {{ $t('common.no_options') }}
          </template>
        </v-select>
      </div>
      <div v-if="hasInvoiceCategories">
        <label class="block text-xs font-medium text-slate-600 uppercase">
          {{ $t('billing_block.category') }}
        </label>
        <SelectInvoiceCategory v-model="selectedCategoryId" :model-as-number="true"
          select-class="w-full text-sm border border-gray-300 rounded p-2" @change="updateCategory" @loaded="onCategoriesLoaded" />
      </div>
      <div v-if="useMultipleCompanies && companies && companies.length > 1">
        <label class="block text-xs font-medium text-slate-600 uppercase">
          {{ $t('company') }}
        </label>
        <select v-model.number="selectedCompanyId" class="input" @change="updateCompany">
          <option :value="null">-- {{ $t('common.select') }} --</option>
          <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </div>
      <div v-if="selectedCustomInvoiceType?.value == 'reading'">
        <label class="block text-xs font-medium text-slate-600 uppercase">
          {{ $t('billing_block.reading_date') }}
        </label>
        <v-select class="block w-full mr-1 required" :model-value="selectedReading" :loading="loadingReadings"
        :options="readings" @update:modelValue="updateSelect($event, 'reading')">
          <template #no-options="{ search, searching, loading }">
            {{ $t('common.no_options') }}
          </template>
        </v-select>
      </div>
      <div v-if="localSelectedCustom?.entity === 'person'">
        <label class="block text-xs font-medium text-slate-600 uppercase">
          {{ $t('exploitation') }}
        </label>
        <v-select class="block w-full mr-1 required" :model-value="selectedExploitation" :loading="loadingExploitations"
          :options="exploitations" @update:modelValue="updateSelect($event, 'exploitation')">
          <template #no-options="{ search, searching, loading }">
            {{ $t('common.no_options') }}
          </template>
        </v-select>
      </div>
      <div v-if="selectedCustomInvoiceType?.value == 'reading'">
        <label class="block text-xs font-medium text-slate-600 uppercase">
          {{ $t('billingbatch') }}
        </label>
        <v-select class="block w-full mr-1" :model-value="selectedBillingBatch" :loading="loadingBillingBatches"
          :options="billingBatches" @update:modelValue="updateSelect($event, 'billing_batch')">
          <template #no-options="{ search, searching, loading }">
            {{ $t('common.no_options') }}
          </template>
        </v-select>
      </div>
    </div>

    <!-- <div v-if="selectedReading?.has_invoice" class="bg-red-50 text-red-500 border border-red-500 rounded-lg px-4 py-2 my-2">
      <div class="space-y-1">
        <span class="font-bold">{{ $t('informative_block.info_existing_invoice_reading') }}</span>
      </div>
    </div> -->
  </fieldset>
</template> 