<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

defineProps({
  show: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['close', 'confirm']);

// Literals compartits amb el catàleg exposat pel GET /contract-estimation/
const PERIOD_CHOICES = ['last_reading', 'last_year', 'same_period_previous_year', 'historic'];
const STATISTIC_CHOICES = ['mean', 'median'];
const selectedPeriod = ref(null);
const selectedStatistic = ref(null);

const handleConfirm = () => {
  const params = {};
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
    <div class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-40 flex items-center justify-center" @click="handleClose"></div>

    <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4 my-auto relative pointer-events-auto">
        <button @click="handleClose" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>

        <div class="mb-6">
          <h3 class="text-xl font-bold text-slate-800 mb-2">
            {{ t('billing_block.estimate') }}
          </h3>
          <p class="text-slate-500 text-sm">
            {{ t('confirmation_text_block.confirm_estimate_reading') }}
          </p>
        </div>

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

        <div class="flex justify-end gap-3">
          <button @click="handleClose" class="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-100 rounded-lg transition-colors">
            {{ t('common.cancel') }}
          </button>
          <button @click="handleConfirm" :disabled="loading" class="button-primary flex items-center gap-2">
            <Icon v-if="loading" name="fa6-solid:spinner" class="animate-spin" />
            {{ t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
