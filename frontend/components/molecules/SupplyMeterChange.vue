<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import H1Region from '../atoms/H1Region.vue';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';
import MeterDetail from './MeterDetail.vue';
import AddMeters from './AddMeters.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import ReadingDetail from './ReadingDetail.vue';
import { format } from 'date-fns';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();

const { $MeterApiService, $ReadingApiService, $SupplyPointApiService } = useNuxtApp();

const props = defineProps({
  id: Number, // SP
  data: Object,
  meter_id: Number
});

const emit = defineEmits(['save']);

const attemptedSave = ref(false);
const saving = ref(null);

const selectedMeter = ref(null);
const showMeters = ref([])

const previous_reading = ref({});
const new_reading = ref({});
const last_reading_new_meter = ref(null)
const og_reading_value = ref(0);

const showCurrentFull = ref(true);
const showNewFull = ref(true);

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const showRegion = ref(false);

const warnLeakValue = ref(false);

const columnsGridClass = ref('grid-cols-[1fr,120px,120px,120px]');

const changeMeterDate = ref(format(new Date(), 'yyyy-MM-dd').toString());

const createEmptyReading = (is_new) => ({
  reading_date: changeMeterDate.value,
  reading_value: is_new ? last_reading_new_meter.value?.reading_value || 0 : 0,
  calculated_value: 0,
  leak_value: 0,
  is_control: false,
  is_estimated: false,
  is_close: is_new ? false : true,
});

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  toggleRegion(true);
}

const toggleRegion = function (value) {
  showRegion.value = value;
  if (!value) {
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
  }
}

const setMeter = async function (meter) {
  try {
    if (meter.last_reading_id) {
      let response = await $ReadingApiService.getDetail(meter.last_reading_id);
      last_reading_new_meter.value = response;
      if (response && response?.reading_value) {
        new_reading.value.reading_value = parseInt(response.reading_value);
      }
    }
  } catch (error) {
    console.error(error);
    last_reading_new_meter.value = null;
  }
  selectedMeter.value = meter;
  showMeters.value = [meter];
  toggleRegion(false);
}

const getMeterData = async function () {
  try {
    const response = await $MeterApiService.getDetail(props.meter_id);
    if (response && response.last_reading) {
      previous_reading.value.reading_value = response.last_reading.reading_value;
      og_reading_value.value = parseInt(response.last_reading.reading_value);
    }

  } catch (error) {
    console.error(error);
    last_reading_new_meter.value = null;
  }
}

const updateCalculatedValue = async function () {
  previous_reading.value.calculated_value = parseInt(previous_reading.value.reading_value) - og_reading_value.value;
  if (previous_reading.value.calculated_value < 0) {
    previous_reading.value.calculated_value = 0;
  }
  updateLeakValue();
}

const updateLeakValue = function () {
  previous_reading.value.leak_value = parseInt(previous_reading.value.leak_value);
  checkWarningLeakValue();
  if (previous_reading.value.leak_value > previous_reading.value.calculated_value) {
    previous_reading.value.leak_value = previous_reading.value.calculated_value;
  }
  if (previous_reading.value.leak_value < 0) {
    previous_reading.value.leak_value = 0;
  }
}

const checkWarningLeakValue = function () {
  warnLeakValue.value = false;
  if (previous_reading.value.leak_value > previous_reading.value.calculated_value) {
    warnLeakValue.value = true;
  }
}

const saveNewMeter = async function () {
  attemptedSave.value = true;

  if (!isValid()) {
    toast.error(t('common.missing_fields'));
    return;
  }

  const confirmMessage = props.meter_id ? t('confirmation_text_block.confirm_change_meter') : t('confirmation_text_block.confirm_add_meter');
  if (!confirm(confirmMessage)) return;

  saving.value = true;

  try {
    const save_data = {
      supply_point: props.id,
      prev_meter: props.meter_id,
      new_meter: selectedMeter.value.id,
      change_date: changeMeterDate.value,
      previous_reading: previous_reading.value,
      new_reading: new_reading.value,
      origin: t('service_block.meter_change')
    }

    const response = await $SupplyPointApiService.saveMeterChange(save_data);
    console.log("response save");
    console.log(response);
    if (response) {
      console.log("response save success");
      toast.success(t('billing_block.correct_manual_reading'));
      emit('save', selectedMeter.value);
    }
  } catch (error) {
    console.error(error);
  } finally {
    saving.value = false;
  }

  // emit('save', selectedMeter.value);
}

const isValid = function () {
  // if (!previous_reading.value) return false;
  if (!selectedMeter.value) return false;
  return true;
}

onMounted(async () => {
  new_reading.value = createEmptyReading(true);
  if (props.meter_id) {
    previous_reading.value = createEmptyReading(false);
    await getMeterData();
  }
});

</script>

<template>
  <div class="region__content w-full max-h-[calc(100vh-85px)] overflow-y-auto pr-4">

    <H1Region>{{ props.meter_id ? t('service_block.change_sp_meter') : t('service_block.add_sp_meter') }}</H1Region>
    <div class="mt-3 space-y-5">
      <div v-if="meter_id">
        <label class="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.08em]">
          {{ $t('service_block.current_meter') }}
        </label>
        <div class="mt-2 flex items-start justify-between gap-3 rounded-lg bg-sky-50/80 px-3 py-2">
          <MeterDetail class="min-w-0 flex-1" :id="meter_id" :reduced="showCurrentFull" />
          <button @click="showCurrentFull = !showCurrentFull"
            class="shrink-0 h-8 px-2.5 inline-flex items-center gap-1.5 text-xs font-medium text-sky-700 hover:text-sky-800 hover:bg-white/70 rounded-md transition-colors">
            <Icon :name="showCurrentFull ? 'fa6-solid:eye' : 'fa6-solid:eye-slash'" class="text-sm" />
          </button>
        </div>

      </div>

      <div :class="{ 'mt-2': meter_id }">
        <label class="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.08em]">
          {{ $t('service_block.new_meter') }}
        </label>
        <div v-if="!selectedMeter" class="flex items-center mt-2">
          <ButtonSeleccio @click="showDetail('AddMeters', null)">
            {{ $t('common.select') }} {{ $t('meter').toLowerCase() }}
          </ButtonSeleccio>
        </div>

        <div v-else class="mt-2">
          <div class="flex items-start justify-between gap-3 rounded-lg bg-emerald-50/80 px-3 py-2">
            <MeterDetail class="min-w-0 flex-1" :id="selectedMeter?.id" :reduced="showNewFull" />
            <div class="shrink-0 inline-flex items-center gap-1">
              <button @click="showNewFull = !showNewFull"
                class="h-8 px-2.5 inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 hover:text-emerald-800 hover:bg-white/70 rounded-md transition-colors">
                <Icon :name="showNewFull ? 'fa6-solid:eye' : 'fa6-solid:eye-slash'" class="text-sm" />
              </button>
              <button @click="showDetail('AddMeters', null)"
                class="h-8 px-2.5 inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 hover:text-emerald-800 hover:bg-white/70 rounded-md transition-colors">
                <Icon name="fa6-solid:pencil" class="text-sm" />
              </button>
            </div>
          </div>
          <div class="mt-3 rounded-lg bg-emerald-50/60 px-3 py-3">
            <div>
              <div class="pb-1">
                <div class="flex items-center justify-between mb-3">
                  <h4 class="text-xs font-semibold text-slate-600 flex items-center gap-2">
                    <Icon name="fa6-solid:clock" class="w-3 h-3 text-slate-400" />
                    {{ $t('billing_block.last_reading') }}
                  </h4>
                  <div v-if="last_reading_new_meter" class="flex flex-wrap gap-x-5 gap-y-1 opacity-80 text-xs">
                    <div v-if="last_reading_new_meter.is_control"
                      class="flex items-center rounded-full border px-2 py-1 bg-green-100 text-green-800 border-green-400">
                      <span class="text-xs font-semibold">{{ t('billing_block.control_reading') }}</span>
                    </div>
                    <div v-if="last_reading_new_meter.is_estimated"
                      class="flex items-center rounded-full border px-2 py-1 bg-green-100 text-green-800 border-green-400">
                      <span class="text-xs font-semibold">{{ t('billing_block.estimated_reading') }}</span>
                    </div>
                    <div v-if="last_reading_new_meter.is_close"
                      class="flex items-center rounded-full border px-2 py-1 bg-green-100 text-green-800 border-green-400">
                      <span class="text-xs font-semibold">{{ t('billing_block.close_reading') }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="last_reading_new_meter" class="grid grid-cols-2 gap-x-4">
                  <FieldDetail :label="t('common.date')" :value="formatDate(last_reading_new_meter.reading_date)" />
                  <FieldDetail :label="t('reading')" :value="last_reading_new_meter.reading_value" />
                  <FieldDetail :label="t('billing_block.consumption_days')"
                    :value="last_reading_new_meter.consumption_days ? (last_reading_new_meter.consumption_days).toString() : t('common.unregistered')" />
                  <FieldDetail :label="t('billing_block.consumption')">
                    <div class="flex items-center gap-x-1">
                      <span>
                        {{ last_reading_new_meter.calculated_value || t('common.unregistered')
                        }}</span>

                      <span v-if="last_reading_new_meter.estimated_used"
                        class="text-xs font-semibold text-amber-700 flex items-center">
                        (<abbr :title="t('billing_block.estimated_correction')">
                          {{ t('billing_block.estimated_correction_abbr') }}
                        </abbr>:
                        -{{ last_reading_new_meter.estimated_used }} m3)</span>
                    </div>
                  </FieldDetail>
                  <FieldDetail :label="t('billing_block.leak')" :value="last_reading_new_meter.leak_value ?
                    last_reading_new_meter.leak_value + ' m³' : t('common.unregistered')" />
                  <FieldDetail :label="t('common.origin')" :value="last_reading_new_meter.origin" />
                </div>
                <div v-else class="text-sm text-slate-500">
                  {{ t('common.no_records') }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="my-4 border-t border-slate-200 pt-2">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span class="text-xs font-semibold uppercase tracking-[0.08em] text-slate-600">
          {{ t('service_block.meter_change_date') }}
        </span>
        <AtomsInputDate v-model="changeMeterDate"
          :invalid="attemptedSave && (changeMeterDate == null || changeMeterDate == '')" />
      </div>

      <div class="mt-5 grid gap-2 text-[11px] font-semibold text-slate-500 uppercase tracking-[0.06em]"
        :class="[columnsGridClass]">
        <div></div>
        <div class="px-1"><span>{{ t('reading') }}</span></div>
        <div class="px-1"><span>{{ t('billing_block.consumption') }}</span></div>
        <div class="px-1"><span>{{ t('billing_block.leak') }}</span></div>
      </div>
      <div v-if="meter_id" class="mt-2 grid gap-2 rounded-lg border border-slate-200 p-2 items-center"
        :class="[columnsGridClass]">
        <div class="text-xs text-slate-600 tracking-[0.08em] font-semibold uppercase">{{
          $t('service_block.current_meter_reading') }}</div>
        <div><input type="number" v-model="previous_reading.reading_value" class="input"
            @input="updateCalculatedValue" /></div>
        <div><input type="number" v-model="previous_reading.calculated_value" class="input" @input="updateLeakValue" />
        </div>
        <div><input type="number" v-model="previous_reading.leak_value" class="input" @input="updateLeakValue" /></div>
      </div>
      <div class="mt-2 grid gap-2 rounded-lg border border-slate-200 p-2 items-center" :class="[columnsGridClass]">
        <div class="text-xs text-slate-600 tracking-[0.08em] font-semibold uppercase">{{
          $t('service_block.new_meter_reading') }}</div>
        <div><input type="number" v-model="new_reading.reading_value" class="input" /></div>
        <div><input type="number" :disabled="meter_id" v-model="new_reading.calculated_value" class="input" /></div>
        <div><input type="number" :disabled="meter_id" v-model="new_reading.leak_value" class="input" /></div>
      </div>
    </div>

    <div v-if="warnLeakValue"
      class="my-3 bg-red-50/80 rounded-lg px-3 py-2 text-red-700 border border-red-300 text-sm font-medium leading-relaxed flex items-center gap-x-2">
      <Icon name="fa6-solid:circle-info" class="text-red-700 text-lg" />
      {{ t('warning_block.warning_leak_value_too_high') }}
    </div>
    <div
      class="my-3 bg-amber-50/80 rounded-lg px-3 py-2 text-amber-700 border border-amber-300 text-sm font-medium leading-relaxed flex items-center gap-x-2">
      <Icon name="fa6-solid:circle-info" class="text-amber-700 text-lg" />
      {{ t('informative_block.info_readings_change_meter') }}
    </div>

    <div class="sticky bottom-0 flex justify-end gap-3 border-t border-slate-100 bg-white/90 py-3 mt-5">

      <button class="button-primary" :disabled="saving" @click="saveNewMeter">
        {{ saving ? t('common.loading') : t('common.save') }}
      </button>
    </div>

    <div v-if="showRegion" role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 w-[95%] text-base bg-white z-[100] overflow-x-hidden"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion }" :style="{ marginTop: '-5px' }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddMeters v-if="showRegionDetailComponent === 'AddMeters'" :selected_items="showMeters" :multiple="false"
          @item-clicked="setMeter" />
        <ReadingDetail v-if="showRegionDetailComponent === 'ReadingDetail'" :meter_id="regionDetailId"
          :isSubRegion="true" />
      </div>
    </div>

  </div>
</template>
