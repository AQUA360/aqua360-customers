<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';

const { t } = useI18n();

const props = defineProps({
  in_invoice: Object,
  initialReason: {
    type: String,
    default: 'other'
  },
  selectedHolder: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['update:redoOption', 'need-leak-value', 'close-region', 'open-person-search']);

const { $ReadingApiService } = useNuxtApp();

const redoReason = ref(props.initialReason);
const redoLeakConsum = ref({});

const loadingReadings = ref(false);
const invoiceReadings = ref([]);
const currentReadings = ref([]);
const activeReadings = ref([]);

const goToModifyReading = () => {
  const url = new URL(`/contract/contracts/${props.in_invoice.contract.id}/reading-change`, window.location.origin);
  window.open(url.toString(), '_blank');
  emit('close-region');
}

const getContractReadings = async () => {
  loadingReadings.value = true;
  try {
    if (props.in_invoice && props.in_invoice.contract) {
      const response = await $ReadingApiService.getAll(
        '', [], 1, null, false,
        [props.in_invoice.contract.id],
        null, null, false
      );
      currentReadings.value = response.results.filter(r => r.invoice == null);
    }
  } catch (error) {
    console.error(error);
  } finally {
    loadingReadings.value = false;
  }
}
watch(() => props.in_invoice, (val) => {
  if (val && val.readings?.length > 0) {
    invoiceReadings.value = val.readings;
    invoiceReadings.value?.forEach((reading) => {
      redoLeakConsum.value[reading.id] = reading.calculated_value;
    });
    getContractReadings();
  }
}, { immediate: true, deep: true });

watch(redoReason, () => {
  if (props.in_invoice && props.in_invoice.readings?.length > 0) {
    invoiceReadings.value = props.in_invoice.readings;
    invoiceReadings.value.forEach(reading => {
      redoLeakConsum.value[reading.id] = reading.calculated_value;
    });
    getContractReadings();
  }
});

const getRedoOption = () => {
  return {
    reason: redoReason.value,
    leak_consum: redoLeakConsum.value
  };
};

const getCurrentReadingForOgId = (ogId) => {
  return currentReadings.value.find(r => r.original_reading?.id == ogId);
};

watch([redoReason, redoLeakConsum], () => {
  emit('update:redoOption', getRedoOption());
});

onMounted(() => {
  if (props.in_invoice && props.in_invoice.readings?.length > 0) {
    invoiceReadings.value = props.in_invoice.readings;
    invoiceReadings.value.forEach(reading => {
      redoLeakConsum.value[reading.id] = reading.calculated_value;
    });
    getContractReadings();
    emit('update:redoOption', getRedoOption());
  }
});
</script>

<template>
  <fieldset class="w-[95%] mb-4 border border-gray-300 rounded-lg p-4 mx-5">
    <legend class="font-medium text-gray-700 px-3">
      {{ $t('billing_block.select_redo_reason') }}</legend>
    <label v-if="in_invoice && in_invoice.readings?.length > 0" class="mr-4">
      <input type="radio" v-model="redoReason" value="leak" />
      {{ t('billing_block.leak') }} / {{ t('billing_block.wrong_reading') }}
    </label>
    <!-- <label v-if="in_invoice" class="mr-4">
      <input type="radio" v-model="redoReason" value="reading" />
      {{ t('billing_block.wrong_reading') }}
    </label> -->
    <label class="mr-4">
      <input type="radio" v-model="redoReason" value="holder" />
      {{ t('billing_block.holder_change') }}
    </label>
    <label class="mr-4">
      <input type="radio" v-model="redoReason" value="other" />
      {{ t('common.other') }}
    </label>
    <div v-if="redoReason == 'leak' || redoReason == 'reading'" class="mt-2 max-w-3xl">
      <div v-for="reading in in_invoice.readings" :key="reading.id"
        class="rounded-md border border-slate-200 bg-white p-3 mb-2 last:mb-0">
        <template
          v-if="getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id : reading.id) &&
            getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id : reading.id)?.id != reading.id">
          <div class="mb-2 flex items-center text-slate-500 text-xs gap-x-2">
            <div class="uppercase tracking-wide">
              {{ t('meter') }}
            </div>
            <div class="text-slate-900 font-semibold uppercase tracking-wide">
              {{ getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id :
                reading.id)?.meter_code ||
                reading.meter_code }}
            </div>
          </div>

          <div class="grid gap-2 grid-cols-2">
            <div class="rounded-md border border-slate-200 p-2.5 grid gap-2 grid-cols-[80px,1fr]">
              <div class="space-y-1">
                <div class="text-xs font-semibold uppercase tracking-wide text-green-700">
                  {{ t('common.current') }}
                </div>
                <div class="flex items-center gap-2"
                  v-if="getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id : reading.id)?.reading_date != reading.reading_date">
                  <span class="text-slate-800 text-sm font-semibold">
                    {{ formatDate(getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id :
                      reading.id)?.reading_date || '-') }}
                  </span>
                </div>
              </div>
              <div class="space-y-1">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-slate-500 text-sm">{{ t('billing_block.consumption') }}</span>
                  <span class="text-slate-800 text-sm font-semibold">
                    <span v-if="getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id :
                      reading.id)?.leak_value" class="text-red-500">
                      - {{ Math.round(getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id :
                        reading.id)?.leak_value) }}
                      </span>
                    {{ Math.round(getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id :
                      reading.id)?.calculated_value || 0) }} m3
                  </span>
                </div>
                <div class="flex items-center justify-between gap-2">
                  <span class="text-slate-500 text-sm">{{ t('reading') }}</span>
                  <span class="text-slate-800 text-sm font-semibold">
                    {{ Math.round(getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id :
                      reading.id)?.reading_value || 0) }}
                  </span>
                </div>

              </div>
            </div>
            <div class="rounded-md border border-slate-200 p-2.5 grid gap-2 grid-cols-[80px,1fr]">
              <div class="space-y-1">
                <div class="text-xs font-semibold uppercase tracking-wide text-red-700">
                  {{ t('common.previous') }}
                </div>
                <div class="flex items-center gap-2"
                  v-if="getCurrentReadingForOgId(reading.original_reading ? reading.original_reading.id : reading.id)?.reading_date != reading.reading_date">
                  <span class="text-slate-800 text-sm font-semibold line-through">
                    {{ formatDate(reading.reading_date) }}
                  </span>
                </div>
              </div>
              <div class="space-y-1">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-slate-500 text-sm">{{ t('billing_block.consumption') }}</span>
                  <span class="text-slate-800 text-sm font-semibold line-through">
                    <span v-if="reading.leak_value" class="text-red-500">
                      - {{ Math.round(reading.leak_value)}} 
                    </span>
                    {{ Math.round(reading.calculated_value) }} m3
                  </span>
                </div>
                <div class="flex items-center justify-between gap-2">
                  <span class="text-slate-500 text-sm">{{ t('reading') }}</span>
                  <span class="text-slate-800 text-sm font-semibold line-through">
                    {{ Math.round(reading.reading_value) }}
                  </span>
                </div>

              </div>
            </div>
          </div>
        </template>
        <div v-else
          class="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-3 py-2">
          <span class="text-slate-600 text-sm">
            {{ t('informative_block.info_no_matching_reading') }}
          </span>
          <button class="button-primary whitespace-nowrap" @click="goToModifyReading()">
            {{ t('common.modify') }} {{ t('readings') }}
          </button>
        </div>
      </div>
    </div>
    <div v-if="redoReason == 'holder'" class="mt-2 max-w-xl">
      <div v-if="selectedHolder" class="bg-green-100 p-4 rounded relative group">
        <p class="font-semibold">
          {{ selectedHolder.full_name || `${selectedHolder.name || ''} ${selectedHolder.surname || ''}`.trim() }}<br />
          <span class="text-sm text-gray-500">{{ selectedHolder.token }}</span>
        </p>
        <button type="button" @click="emit('open-person-search')"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
          <Icon name="fa6-solid:pencil" />
        </button>
      </div>
      <ButtonSeleccio v-else @click="emit('open-person-search')">
        {{ $t('common.select') }} {{ t('common.or') }} {{ t('common.add') }} {{ t('contract_block.new_holder') }}
      </ButtonSeleccio>
    </div>
  </fieldset>
</template>