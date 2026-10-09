<template>
  <div class="transition-all duration-300 border-b" :class="{ 'rounded-lg shadow-lg pb-2 my-3': props.showDetail }">
    <div
      class="grid pt-1 pb-1 grid-cols-[24px,1.2fr,1fr,1fr,1fr,1fr,1fr,1fr,1fr,1fr,2fr,80px,40px,100px] gap-2 px-4 divide-gray-200 transition-all rounded-t-lg duration-300 ease-in-out"
      :class="{ 'mb-1 pb-2 pt-2 bg-slate-200': props.showDetail, 'bg-slate-100': excluded, 'bg-amber-50': selected }">
      <div class="flex items-center justify-center">
        <input type="checkbox" :checked="selected" @change="emit('toggle-select', reading.id)"
          class="w-4 h-4 rounded border-slate-300 accent-amber-500 cursor-pointer" />
      </div>
      <div class="p-3 truncate flex items-center gap-1">
        <span>{{ reading.contract }}</span>
        <Icon v-if="reading.is_fire" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
      </div>
      <div class="p-3 min-w-0">
        <span class="block truncate" :title="reading.origin">{{ reading.origin }}</span>
      </div>
      <div class="p-3">
        <span class="text-red-500 font-bold">
          {{ reading.previous_leak ? reading.previous_leak : '-' }}</span>
      </div>
      <div class="p-3">
        <span>{{ reading.read1 }}</span>
      </div>
      <div :class="{ 
        'p-3 flex items-center': changing_reading,
        'pt-1': !changing_reading
        }">
        <input v-if="!changing_reading" :disabled="excluded || (reading.is_estimated && reading.is_fire)" v-numeric-only type="text" class="input" v-model="reading.read2" />
        <span v-else class="text-slate-500">{{ reading.read2 }}</span>
      </div>
      <div class="pt-1">
        <input :disabled="excluded" v-numeric-only type="text" class="input" v-model="reading.leak_value" />
      </div>
      <div v-if="!changing_reading" class="p-3 pr-0">
        <div class="flex items-center">
          <button v-if="!(reading.is_estimated && reading.is_fire)" @click="changing_reading = true"
          class="text-slate-400 mr-1 flex items-center justify-center">
            <Icon name="fa6-solid:pencil" />
          </button>
          <span>{{ reading.calculated_value }}</span>
          <div class="text-sm">
            <p v-if="(reading.read2 - reading.read1 != reading.calculated_value) && (reading.read2 - reading.read1 != 0)"
              class="text-orange-600 font-semibold ml-4">{{ reading.read2 - reading.read1 }}</p>
            <p v-if="reading.leak_value && reading.leak_value != 0"
              class="text-blue-600 font-semibold ml-4">-{{ reading.leak_value }}</p>
          </div>
        </div>
        <div v-if="reading.estimated_used">
          <span class="text-sky-600 font-semibold">- {{ parseInt(reading.estimated_used) }} {{ t('billing_block.estimated_correction_short') }}</span>
        </div>
        <!-- 
        <span v-if="(reading.read2 - reading.read1 != reading.calculated_value) || (reading.leak_value && reading.leak_value != 0)" class="text-orange-600 font-semibold ml-4">
          {{ !reading.leak_value || reading.leak_value <= 0? reading.read2 - reading.read1 : reading.read2 - reading.read1 -reading.leak_value }}</span>
         -->
      </div>
      <div v-else class="pt-1 flex items-center grid grid-cols-[1fr,15px]">
        <input :disabled="excluded || (reading.is_estimated && reading.is_fire)" v-numeric-only type="text" class="input" v-model="reading.calculated_value" @input="handleManualConsumption(reading, true)" @focus="handleManualConsumption(reading, true)" />
        <button
          class="w-5 h-5 text-slate-400 hover:text-slate-600 flex items-center justify-center"
          @click="handleManualConsumption(reading, false)">
          <Icon name="fa6-solid:rotate-left" />
        </button>
        <!-- 
        <span v-if="(reading.read2 - reading.read1 != reading.calculated_value) || (reading.leak_value && reading.leak_value != 0)" class="text-orange-600 font-semibold ml-4">
          {{ !reading.leak_value || reading.leak_value <= 0? reading.read2 - reading.read1 : reading.read2 - reading.read1 -reading.leak_value }}</span>
         -->
      </div>
      <div class="p-3">
        <div v-if="reading.meter_is_general">
          <Icon name="fa6-solid:check" class="text-l text-green-500" />
        </div>
        <div v-else class="text-slate-400">
          -
        </div>
      </div>
      <div class="p-3">
        <div v-if="reading.is_estimated">
          <Icon name="fa6-solid:check" class="text-l text-green-500" />
        </div>
        <div v-else class="text-slate-400">
          -
        </div>
      </div>
      <div class="pt-1">
        <input :disabled="excluded" v-model="alertNote" class="input" />
      </div>
      <div class="pt-3 flex justify-center text-xs font-mono text-slate-500 italic">
        <span v-if="duration !== null">{{ duration }} <small>{{ t('common.days_abbr') }}</small></span>
        <span v-else>-</span>
      </div>
      <div class="pt-2 flex justify-center">
        <Icon v-if="hasWarning" name="fa6-solid:calendar-day" class="text-orange-500 w-5 h-5" :title="t('warning_block.warning_date_range')" />
      </div>
      <div class="pt-1 flex gap-x-1">
        <button :disabled="reading.in_communication_process" :title="t('common.send_individual_communication')"
          class="w-8 h-8 bg-amber-500 text-white rounded-full flex items-center justify-center enabled:hover:bg-amber-600 transition-all duration-200 disabled:opacity-30"
          @click="addToCommunicationProcess">
          <Icon name="fa6-solid:message" />
        </button>
        <button :disabled="excluded || !isDirty" :title="t('common.save')"
          class="w-8 h-8 bg-sky-500 text-white rounded-full flex items-center justify-center enabled:hover:bg-sky-600 transition-all duration-200 disabled:opacity-30"
          @click="save">
          <Icon name="fa6-solid:floppy-disk" />
        </button>
        <button :disabled="excluded" :title="props.showDetail ? t('common.hide_detail') : t('common.show_detail')"
          class="w-8 h-8 bg-sky-400 text-white rounded-full flex items-center justify-center enabled:hover:bg-sky-500 transition-all duration-200 disabled:opacity-30"
          @click="toggleDetail">
          <Icon v-show="!props.showDetail" name="fa6-solid:eye" />
          <Icon v-show="props.showDetail" name="fa6-solid:eye-slash" />
        </button>
      </div>
    </div>
    <ReadingListDetail @exclude="onExcluded" @open-region="openRegion" :show="props.showDetail" :reading="reading" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import ReadingListDetail from '../molecules/ReadingListDetail.vue';
import { getReadingDuration, hasDateRangeWarning } from '~/utils/stats';
import { useToast } from 'vue-toastification';
const { t } = useI18n();
const { $ReadingApiService } = useNuxtApp();

const props = defineProps({
  reading: {
    type: Object,
    required: true
  },
  showDetail: {
    type: Boolean,
    default: false
  },
  allowChange: {
    type: Boolean,
    default: false
  },
  medianDuration: {
    type: Number,
    default: 0
  },
  selected: {
    type: Boolean,
    default: false
  }
});

const toast = useToast();

const emit = defineEmits(['show-edit', 'open-region', 'toggle-select']);

const reading = ref(props.reading);
const excluded = ref(false);
const changing_reading = ref(false)

const duration = computed(() => getReadingDuration(reading.value));
const hasWarning = computed(() => {
  if (props.medianDuration === 0 || duration.value === null) return false;
  return hasDateRangeWarning(duration.value, props.medianDuration);
});
const translateAlertNote = (note) => {
  if (!note) return '';
  const key = `billing_block.${note}`;
  const translated = t(key);
  return translated !== key ? translated : note;
};

const alertNote = ref(translateAlertNote(props.reading.alert_notes));

const initialValues = ref({
  read2: reading.value.read2,
  leak_value: reading.value.leak_value,
  calculated_value: reading.value.calculated_value,
  alert_notes: alertNote.value,
  is_manual: changing_reading.value
});

const isDirty = computed(() => {
  return reading.value.read2 != initialValues.value.read2 ||
         reading.value.leak_value != initialValues.value.leak_value ||
         reading.value.calculated_value != initialValues.value.calculated_value ||
         alertNote.value != initialValues.value.alert_notes ||
         changing_reading.value != initialValues.value.is_manual;
});

const handleManualConsumption = (reading, changed) => {
  if (changed && !reading.previous_consumption_value) {
    reading.previous_consumption_value = reading.calculated_value;
  } else if (!changed){
    if (reading.previous_consumption_value) {
      reading.calculated_value = reading.previous_consumption_value;
      reading.previous_consumption_value = null;
    }
    changing_reading.value = false;
  }
}

const save = async () => {
  if (!isDirty.value) return;

  if (confirm(t("confirmation_text_block.confirm_modify"))) {
    const data = {
      id: reading.value.id,
      reading_value: reading.value.read2,
      calculated_value: !changing_reading.value ? reading.value.read2 - reading.value.read1 : reading.value.calculated_value,
      leak_value: reading.value.leak_value,
      alert_notes: alertNote.value
    }

    const response = await $ReadingApiService.save(data);
    if (response) {
      reading.value.calculated_value = response.calculated_value;
      reading.value.previous_consumption_value = null;
      changing_reading.value = false;
      
      // Update initial values to current state after successful save
      initialValues.value = {
        read2: reading.value.read2,
        leak_value: reading.value.leak_value,
        calculated_value: reading.value.calculated_value,
        alert_notes: alertNote.value,
        is_manual: false // Resets to false as per existing logic
      };
    }
  }
}

const addToCommunicationProcess = async () => {

  try{
    const response = await $ReadingApiService.addReadingToCommunicationProcess(reading.value.id);
    if (response){
      reading.value.in_communication_process = true;
      toast.success(t('informative_block.info_reading_added_to_communication_process'));
    }
  } catch (error) {
    console.error(error);
  }

}

const toggleDetail = () => {
  emit('show-edit', props.showDetail ? 0 : reading.value.id);
}
const openRegion = (e) => {
  emit('open-region', e);
}

const onExcluded = () => {
  emit('show-edit', 0);
  excluded.value = true;
}


onMounted(() => {
  console.log("reading", reading.value);
});

</script>
