<script setup>
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import InputDate from '~/components/atoms/InputDate.vue';
import InputNumber from '~/components/atoms/InputNumber.vue';

const { t } = useI18n();

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  defaultReadingDate: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['close', 'confirm']);

// Valors: 'default', 'specific_date', 'days_from_last'
const estimationType = ref('default');
const readingDate = ref(props.defaultReadingDate);
const daysFromLast = ref(30);

// Literals compartits amb el catàleg exposat pel GET /contract-estimation/
const PERIOD_CHOICES = ['last_reading', 'last_year', 'same_period_previous_year', 'historic'];
const STATISTIC_CHOICES = ['mean', 'median'];
const selectedPeriod = ref(null);
const selectedStatistic = ref(null);

const isFormValid = computed(() => {
  if (estimationType.value === 'specific_date') return !!readingDate.value;
  if (estimationType.value === 'days_from_last') return daysFromLast.value !== null && daysFromLast.value >= 0;
  return true; // L'opció per defecte sempre és vàlida
});

const handleConfirm = () => {
  if (!isFormValid.value) return;

  const params = {};

  if (estimationType.value === 'default') {
    params.estimation_type = null; // Com fins ara
    params.reading_date = props.defaultReadingDate;
  } else if (estimationType.value === 'specific_date') {
    params.estimation_type = 'specific_date';
    params.reading_date = readingDate.value;
  } else {
    params.estimation_type = 'days_from_last';
    params.days_from_last = daysFromLast.value;
  }

  if (selectedPeriod.value) params.period = selectedPeriod.value;
  if (selectedStatistic.value) params.statistic = selectedStatistic.value;

  emit('confirm', params);
};

const handleClose = () => {
  emit('close');
};
</script>

<template>
  <div v-if="show">
    <!-- Modal Backdrop -->
    <div class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-40 flex items-center justify-center" @click="handleClose">
    </div>

    <!-- Modal Content -->
    <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative pointer-events-auto">
        <button @click="handleClose" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>

        <div class="mb-6">
          <h3 class="text-xl font-bold text-slate-800 mb-2">
            {{ t('billing_block.estimate_readings') }}
          </h3>
          <p class="text-slate-500 text-sm">
            {{ t('confirmation_text_block.confirm_estimate_readings_description') }}
          </p>
        </div>

        <div class="space-y-3 mb-8">
          <!-- Option: Default (As before) -->
          <div 
            @click="estimationType = 'default'"
            class="flex items-center gap-3 p-3 rounded-lg border border-slate-200 cursor-pointer transition-all hover:bg-slate-50"
            :class="{ 'bg-slate-100 border-slate-400': estimationType === 'default' }"
          >
            <Icon name="fa6-solid:angles-right" :class="estimationType === 'default' ? 'text-slate-600' : 'text-slate-400'" />
            <div class="flex-grow">
              <span class="block font-medium" :class="estimationType === 'default' ? 'text-slate-900 italic' : 'text-slate-700'">{{ t('default') }}</span>
              <span class="block text-xs text-slate-500">{{ t('billing_block.default_estimation_description') }}</span>
            </div>
          </div>

          <!-- Option: Specific Date -->
          <div 
            @click="estimationType = 'specific_date'"
            class="flex items-center gap-3 p-3 rounded-lg border border-slate-200 cursor-pointer transition-all hover:bg-slate-50"
            :class="{ 'bg-slate-100 border-slate-400': estimationType === 'specific_date' }"
          >
            <Icon name="fa6-solid:angles-right" :class="estimationType === 'specific_date' ? 'text-slate-600' : 'text-slate-400'" />
            <div class="flex-grow">
              <span class="block font-medium" :class="estimationType === 'specific_date' ? 'text-slate-900 italic' : 'text-slate-700'">{{ t('billing_block.specific_date_for_all') }}</span>
              <span class="block text-xs text-slate-500">{{ t('billing_block.specific_date_description') }}</span>
            </div>
          </div>

          <!-- Option: Days From Last -->
          <div 
            @click="estimationType = 'days_from_last'"
            class="flex items-center gap-3 p-3 rounded-lg border border-slate-200 cursor-pointer transition-all hover:bg-slate-50"
            :class="{ 'bg-slate-100 border-slate-400': estimationType === 'days_from_last' }"
          >
            <Icon name="fa6-solid:angles-right" :class="estimationType === 'days_from_last' ? 'text-slate-600' : 'text-slate-400'" />
            <div class="flex-grow">
              <span class="block font-medium" :class="estimationType === 'days_from_last' ? 'text-slate-900 italic' : 'text-slate-700'">{{ t('billing_block.days_from_last_reading') }}</span>
              <span class="block text-xs text-slate-500">{{ t('billing_block.days_from_last_description') }}</span>
            </div>
          </div>
        </div>

        <!-- Dynamic Inputs -->
        <div v-if="estimationType !== 'default'" class="mb-8 p-4 bg-slate-50 rounded-lg animate-fadeIn">
          <div v-if="estimationType === 'specific_date'">
            <AtomsInputDate :label="t('billing_block.estimation_date')" v-model="readingDate" :required="true" class="!mb-0" />
          </div>
          <div v-else-if="estimationType === 'days_from_last'">
            <AtomsInputNumber :label="t('billing_block.days_to_calculate')" v-model="daysFromLast" :required="true" :min="0" class="!mb-0" />
          </div>
        </div>

        <!-- Reference period / statistic (optional) -->
        <div class="grid grid-cols-2 gap-3 mb-8">
          <div>
            <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">
              {{ t('reading_block.estimation_period') }}
            </label>
            <select v-model="selectedPeriod" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm bg-white">
              <option :value="null">{{ t('default') }}</option>
              <option v-for="p in PERIOD_CHOICES" :key="p" :value="p">{{ t(`reading_block.estimation_period_${p}`) }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-500 uppercase mb-1">
              {{ t('reading_block.estimation_statistic') }}
            </label>
            <select v-model="selectedStatistic" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm bg-white">
              <option :value="null">{{ t('default') }}</option>
              <option v-for="s in STATISTIC_CHOICES" :key="s" :value="s">{{ t(`reading_block.estimation_statistic_${s}`) }}</option>
            </select>
          </div>
        </div>

        <!-- Footer -->
        <div class="flex justify-end gap-3">
          <button 
            @click="handleClose" 
            class="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-100 rounded-lg transition-colors"
          >
            {{ t('common.cancel') }}
          </button>
          <button 
            @click="handleConfirm" 
            :disabled="!isFormValid || loading"
            class="button-primary flex items-center gap-2"
          >
            <Icon v-if="loading" name="fa6-solid:spinner" class="animate-spin" />
            {{ t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fadeIn {
  animation: fadeIn 0.2s ease-out forwards;
}
</style>
