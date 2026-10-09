<template>
  <div class="transition-all duration-300 border-b" :class="{ 'rounded-lg shadow-lg pb-2 my-3': props.showDetail }">
    <div
      class="grid pt-1 pb-1 gap-2 px-4 divide-gray-200 transition-all rounded-t-lg duration-300 ease-in-out flex items-center"
      :class="{
        'mb-1 pb-2 pt-2 bg-slate-200': props.showDetail,
        'grid-cols-[1.8fr,1.8fr,2fr,1fr,1.2fr,1fr,0.8fr,1fr,1fr]': !props.readerAlert && !props.remoteAlert,
        'grid-cols-[1.8fr,1.8fr,1fr,100px,120px,1fr,1fr,1fr,1.5fr,1fr,1fr]': props.readerAlert || props.remoteAlert
      }">
      <div class="p-3 flex items-center gap-1">
        <div v-if="supply.contracts && supply.contracts.length > 0" class="flex items-center gap-1">
          <a href="#" class="text-sky-600 font-bold hover:underline" @click.prevent="openRegion('contract', supply.contracts[0].id)">
            {{ supply.contracts[0].token }}
          </a>
          <Icon v-if="isFireContract(supply.contracts[0]) || isFireContract(supply)" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
          <div class="text-xs text-slate-500">
            <AtomsDate :date="supply.contracts[0].registration_date || supply.contracts[0].created_at" />
          </div>
        </div>
        <span v-else>-</span>
      </div>
      <div class="p-3 truncate">
        <span>{{ supply.contracts && supply.contracts.length > 0 ? supply.contracts[0].holder : '-' }}</span>
      </div>
      <div class="p-3 pt-2 truncate grid grid-rows-2">
        <abbr :title="supply.address_complete" class="truncate">
          <span>{{ supply.address_complete }}</span>
        </abbr>
        <div class="flex items-center gap-2">
          <AtomsColorBadge :color="supply.supply_status_color" :value="supply.supply_status_name" />
          <span v-if="supply.usage_type_name" class="text-xs font-semibold text-slate-500">
            ({{ supply.usage_type_name }})
          </span>
        </div>
      </div>
      <div class="p-3">
        <span>{{ props.readerAlert || props.remoteAlert ? supply.last_previous_reading_value : supply.last_reading_value }}</span>
      </div>
      <div class="p-3">
        <input :disabled="disableAll || props.disableAll || props.remoteAlert" type="date" v-model="reading_date" class="input"/>
      </div>
      <div class="p-3">
        <input :disabled="disableAll || props.disableAll" type="text" class="input" v-model="reading_value" 
        :class="{ 'border-red-500': !reading_value }" />
      </div>
      <div class="p-3">
        <input :disabled="disableAll || props.disableAll" type="text" class="input" v-model="leak_value" />
      </div>
      <div class="p-3">
        <span>{{ calculated_value ?? '-' }}</span>
      </div>
      <div v-if="props.readerAlert" class="p-3">
        <span>{{ translateReaderAlert(supply.last_reader_alert) }}</span>
      </div>
      <div v-if="props.remoteAlert" class="p-3">
        <!-- <span>{{ selected_remote_alert.label }}</span> -->
        <v-select class="block w-full mr-2 required"
          :disabled="props.remoteAlert.length == 0 || disableAll || props.disableAll" :model-value="selected_remote_alert"
          @update:modelValue="updateSelected({ entity: 'remote_alert', id: $event })" :options="props.remoteAlert"></v-select>
      </div>
      <div v-if="props.readerAlert || props.remoteAlert"  class="p-3">
        <template v-if="props.supply.photo">
          <button :title="t('common.view')"
            class="w-8 h-8 mx-1 bg-sky-500 text-white rounded-full flex items-center justify-center enabled:hover:bg-sky-300 transition-all duration-200"
            @click="openPhotoModal">
            <Icon name="fa6-solid:eye" />
          </button>
        </template>
        <span v-else> - </span>
      </div>
      <div class="ml-3 flex">
        <button v-if="!props.remoteAlert" :title="t('billing_block.estimate')" 
          :disabled="disableAll || props.disableAll || (props.readerAlert && reading_value)"
          class="w-8 h-8 mx-1 bg-yellow-500 text-white rounded-full flex items-center justify-center enabled:hover:bg-yellow-300 transition-all duration-200 disabled:opacity-30"
          @click="estimate">
          <Icon name="fa6-solid:calculator" />
        </button>
        <button v-if="!props.remoteAlert" :title="`${t('common.generate')} ${t('common.work_order')}`" 
          :disabled="disableAll || props.disableAll || (props.readerAlert && reading_value)"
          class="w-8 h-8 mx-1 bg-orange-400 text-white rounded-full flex items-center justify-center enabled:hover:bg-orange-200 transition-all duration-200 disabled:opacity-30"
          @click="createOrderReadMeter">
          <Icon name="fa6-solid:screwdriver-wrench" />
        </button>
        <button :title="t('common.save')" :disabled="disableAll || props.disableAll"
          class="w-8 h-8 mx-1 bg-sky-500 text-white rounded-full flex items-center justify-center enabled:hover:bg-sky-300 transition-all duration-200 disabled:opacity-30"
          @click="save">
          <Icon name="fa6-solid:floppy-disk" />
        </button>
      </div>
    </div>
  </div>
  
  <!-- Photo modal -->
  <div v-if="showPhotoModal" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/60" @click="closePhotoModal"></div>
    <div class="relative bg-white rounded-lg shadow-lg max-w-3xl w-[90vw] max-h-[90vh] p-2">
      <button :title="t('common.close')" class="absolute top-2 right-2 w-8 h-8 bg-slate-600 text-white rounded-full flex items-center justify-center hover:bg-slate-500" @click="closePhotoModal">
        <Icon name="fa6-solid:xmark" />
      </button>
      <img :src="photoSrc" alt="Photo" class="block max-h-[80vh] w-auto object-contain mx-auto" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { format } from 'date-fns';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const { $ReadingApiService, $ReadingBatchApiService, $ConfiglistApiService, $ConfigProjectApiService, $OrderApiService } = useNuxtApp();

const props = defineProps({
  supply: {
    type: Object,
    required: true
  },
  showDetail: {
    type: Boolean,
    default: false
  },
  batch_id: {
    type: Number,
    required: true
  },
  orderTypeReadMeter: {
    type: Object,
    required: true
  },
  orderStatuses: {
    type: Array,
    required: true
  },
  readingDate: {
    type: String,
    required: false
  },
  disableAll: {
    type: Boolean,
    default: false
  },
  readerAlert: {
    type: Boolean,
    default: false
  },
  remoteAlert: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['refresh', 'openRegion']);
const toast = useToast();
const supply = ref(props.supply);
const disableAll = ref(false);

const translateReaderAlert = (alert) => {
  if (!alert) return '-';
  const key = `billing_block.${alert}`;
  const translated = t(key);
  return translated !== key ? translated : alert;
};

const openRegion = (entity, id) => {
  emit('openRegion', { entity, id });
}

const showPhotoModal = ref(false);
const openPhotoModal = () => {
  showPhotoModal.value = true;
}
const closePhotoModal = () => {
  showPhotoModal.value = false;
}

const photoSrc = computed(() => {
  const photo = props.supply?.photo;
  if (!photo) return '';
  if (typeof photo !== 'string') return '';
  if (photo.startsWith('data:') || photo.startsWith('http')) return photo;
  return `data:image/jpeg;base64,${photo}`;
});

const reading_value = ref(0);
const reading_date = ref(null);
const leak_value = ref(null);
const calculated_value = ref(null);
const selected_remote_alert = ref(null);
const orderTypes = ref([]);
const orderTypeReadMeter = ref(null);
const orderStatuses = ref([]);

const createOrderReadMeter = async () => {
  const defaultOrderStatus = orderStatuses.value.find(s => s.is_default == true);
  // creem un order del tipus lectura, si cal després l'usuari l'eliminarà
  const order_data = {
    token: format(new Date(), 'yyyyMMddHHmmss'),
    supply_point: supply.value.id,
    type: orderTypeReadMeter.value.id,
    status: defaultOrderStatus.id || orderStatuses.value[0].id,
    requested_at: format(new Date(), 'yyyy-MM-dd HH:mm:ss')
  }

  if (confirm(t("confirmation_text_block.confirm_gen_order_reading_check"))) {
    const order_saved = await $OrderApiService.save(order_data);
    disableAll.value = true;
    toast.success(t('common.correct_creation'));
  }
}

const save = async () => {
  if (confirm(t("confirmation_text_block.confirm_manual_reading"))) {
    const data = {
      supply_id: props.supply.id,
      supply_point: supply.value.id,
      meter: supply.value.meter_id,
      reading_value: reading_value.value,
      leak_value: leak_value.value,
      batch: props.batch_id,
      reading_date: reading_date.value ? reading_date.value : format(new Date(), 'yyyy-MM-dd'),
      remote_alert: selected_remote_alert?.value?.value || null,
      origin: 'manual',
      contract: supply.value.contracts[0].id,
      add_to_all: true,
      is_control: false,
      is_estimated: false,
    }

    try {
        const response_check = await $ReadingApiService.checkAllowSave(data);
        if (!response_check.allow) {
            toast.warning(t('warning_block.warning_reading_too_close_to_last'),{timeout: 6500});
            return;
        }
    } catch (error) {
        console.error(error);
        return;
    }

    const response = await $ReadingApiService.save(data);

    disableAll.value = true;
    toast.success(t('common.correct_creation'));
    emit('refresh');
  }
}

const estimate = async () => {
  if (confirm(t('confirmation_text_block.confirm_estimate_reading'))) {

    const response = await $ReadingBatchApiService.estimateReadings(props.batch_id, { supply_points: [supply.value.id], reading_date: reading_date.value || props.readingDate });
    
    if (response && response.readings && response.readings.length > 0) {
      reading_value.value = response.readings[0].reading_value;
      leak_value.value = response.readings[0].leak_value;
      reading_date.value = response.readings[0].reading_date;
      calculated_value.value = response.readings[0].calculated_value;
      disableAll.value = true;
      toast.success(t('billing_block.correct_estimate'));
      emit('refresh');
    }
    if (response && (!response.readings || response.readings.length == 0)) {
      toast.warning(t('warning_block.warning_error_estimate'));
    }
  }
}

const updateSelected = (event) => {
  selected_remote_alert.value = event.id;
}

const alertNote = ref('');

const { fetchFireUsageTypeTokens, isFireContract } = useFireUsageTypeTokens();

onMounted(async () => {
  orderTypeReadMeter.value = props.orderTypeReadMeter;
  orderStatuses.value = props.orderStatuses;
  if (props.readerAlert || props.remoteAlert) {
    reading_value.value = props.supply.last_reading_value;
    reading_date.value = props.supply.last_reading_date || null;
    leak_value.value = props.supply.last_leak_value || null;
    if (props.remoteAlert && props.supply.last_remote_alert_object) {
      selected_remote_alert.value = props.remoteAlert.find(item => item.value == props.supply?.last_remote_alert_object?.id);
    }
  }
  await fetchFireUsageTypeTokens();
});

</script>
