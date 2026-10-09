<script setup>
import { formatDate } from '~/utils/date';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
const { t } = useI18n();

const props = defineProps({
  contract_ids: {
    type: Array,
    default: []
  },
  supply_point_id: {
    type: Number,
    default: null
  },
  meter_id: {
    type: Number,
    default: null
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  // Mostra una columna per triar una lectura existent com a lectura inicial (alta de contracte)
  selectableAsInitial: {
    type: Boolean,
    default: false
  },
  selectingDisabled: {
    type: Boolean,
    default: false
  }
});

const { $ReadingApiService } = useNuxtApp();

const data = ref([]);
const SubRegion = ref(props.isSubRegion);
const loading = ref(false);

// Photo modal state
const showPhotoModal = ref(false);
const modalPhoto = ref('');
const openPhotoModal = (photo) => {
  modalPhoto.value = photo || '';
  showPhotoModal.value = true;
}
const closePhotoModal = () => {
  showPhotoModal.value = false;
  modalPhoto.value = '';
}

const showControlReadings = ref(false);

const photoSrc = computed(() => {
  const photo = modalPhoto.value;
  if (!photo || typeof photo !== 'string') return '';
  if (photo.startsWith('data:') || photo.startsWith('http')) return photo;
  return `data:image/jpeg;base64,${photo}`;
});

// A reading copied to other contracts sharing the meter (copied_from) is shown
// as a single row: copies are folded into their original when both are listed
const getOriginalId = (reading) => reading.copied_from?.id ?? reading.copied_from;

const rows = computed(() => {
  const listedIds = new Set(data.value.map(reading => reading.id));
  const copiesByOriginal = {};
  for (const reading of data.value) {
    const originalId = getOriginalId(reading);
    if (originalId && listedIds.has(originalId)) {
      (copiesByOriginal[originalId] ||= []).push(reading);
    }
  }
  return data.value
    .filter(reading => !(getOriginalId(reading) && listedIds.has(getOriginalId(reading))))
    .map(reading => ({ ...reading, copies: copiesByOriginal[reading.id] || [] }));
});

const copiesTooltip = (element) => t('billing_block.reading_copies_tooltip', {
  count: element.copies.length,
  contracts: element.copies.map(copy => copy.contract?.token || '-').join(', ')
});

const getData = async (load = true) => {
  loading.value = load;
  try {
    const response = await $ReadingApiService.getAll('', [], 1, null, false, props.contract_ids, props.supply_point_id, props.meter_id, showControlReadings.value? null : false);
    data.value = []
    data.value = response.results;
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const deleteReading = async (id) => {
  if (!confirm(`${t('confirmation_text_block.confirm_delete')}`)) return;
  try {
    await $ReadingApiService.doDelete(id);
    data.value = data.value.filter(reading => reading.id !== id);
  } catch (error) {
    console.error(error)
  }
}

const emit = defineEmits(['show-detail', 'select-initial']);


// Lectures posteriors a `reading`: si es tria una lectura antiga com a inicial, totes les
// posteriors passaran a ser del contracte nou (s'avisa abans i en triar-la)
const readingTime = (reading) => reading?.reading_date ? new Date(reading.reading_date).getTime() : null;
const isNewerThan = (reading, reference) => {
  const a = readingTime(reading);
  const b = readingTime(reference);
  if (a == null || b == null || reading.id === reference.id) return false;
  return a > b || (a === b && reading.id > reference.id);
};
// Mateix criteri que el backend en finalitzar l'alta (move_newer_readings_to_contract):
// ni inicials ni de tancament, i només les pendents de facturar
const movesWithInitial = (reading) => reading.reading_value != null && !reading.is_initial && !reading.is_close && !reading.is_billed;
// Com a inicial només es pot triar la darrera lectura facturada o una de posterior: les
// anteriors ja tenen el consum facturat al contracte anterior i se solaparien els períodes.
// Si es tria una lectura facturada, el backend en duplica el valor (request-reading/).
const lastBilledReading = computed(() => data.value
  .filter(reading => reading.is_billed && !reading.is_control && reading.reading_value != null)
  .reduce((last, reading) => (last == null || isNewerThan(reading, last) ? reading : last), null));
const canSelectAsInitial = (reading) => reading.reading_value != null && !reading.is_initial && !reading.is_control
  && (lastBilledReading.value == null || reading.id === lastBilledReading.value.id || isNewerThan(reading, lastBilledReading.value));

const newerReadingsThan = (reference) => rows.value.filter(reading =>
  movesWithInitial(reading) && isNewerThan(reading, reference));

const hoveredReading = ref(null);
const onRowEnter = (reading) => {
  if (props.selectableAsInitial && canSelectAsInitial(reading)) hoveredReading.value = reading;
};
const willMoveToNewContract = (reading) => props.selectableAsInitial && hoveredReading.value != null
  && movesWithInitial(reading) && isNewerThan(reading, hoveredReading.value);

const selectRow = (reading) => {
  if (!props.selectableAsInitial || props.selectingDisabled || !canSelectAsInitial(reading)) return;
  emit('select-initial', reading, newerReadingsThan(reading));
};

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

onMounted(async () => {
  await getData();
});

watch(() => props.contract_ids, async () => {
  await getData();
});

watch(() => showControlReadings.value, async () => {
  await getData(false);
});

</script>

<template>
  <div v-if="loading">
    <div class="flex justify-center items-center mt-5">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>
  <div v-else>
    <div v-if="data.length == 0" class="">
      <div class="footering text-slate-500 p-2">
        {{ t('common.no_data_found') }}
      </div>
    </div>
    <div v-else :class="{ 'overflow-x-auto': selectableAsInitial }">
      <p v-if="selectableAsInitial" class="flex items-center gap-2 text-sm text-slate-600 mb-1">
        <Icon name="fa6-solid:hand-pointer" class="text-emerald-600" />
        {{ t('contract_block.choose_existing_reading_hint') }}
      </p>
      <p v-if="selectableAsInitial" class="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5 mb-1">
        <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500 mt-0.5 shrink-0" />
        {{ t('contract_block.older_initial_reading_info') }}
      </p>
      <p v-if="selectableAsInitial && lastBilledReading" class="flex items-start gap-2 text-sm text-slate-600 mb-1">
        <Icon name="fa6-solid:circle-info" class="text-sky-500 mt-0.5 shrink-0" />
        {{ t('contract_block.initial_reading_billed_limit_info', {
          date: lastBilledReading.reading_date ? formatDate(lastBilledReading.reading_date) : '-',
        }) }}
      </p>
      <table class="min-w-full text-sm text-slate-800 mt-2">
        <thead>
          <tr class="bg-gray-100 border-b text-left">
            <!-- <th class="p-2"></th> -->
            <th v-if="selectableAsInitial" class="p-2 w-8"></th>
            <th class="p-2">{{ t('common.date') }}</th>
            <th class="p-2">{{ t('invoice') }}</th>
            <th class="p-2">{{ t('reading') }}</th>
            <th class="p-2">{{ t('billing_block.reading_batch') }}</th>
            <th class="p-2">{{ t('common.origin') }}</th>
            <th class="p-2">{{ t('meter') }}</th>
            <th v-if="!contract_ids || contract_ids.length == 0" class="p-2">{{ t('contract') }}</th>
            <th class="p-2">{{ t('billing_block.consumption') }}</th>
            <th class="p-2">{{ t('billing_block.estimated') }}</th>
            <th class="py-2 px-1">
              <button type="button" @click="showControlReadings = !showControlReadings"
                :aria-pressed="showControlReadings"
                class="inline-flex items-center justify-center gap-1 whitespace-nowrap rounded-md border px-2 py-1 text-xs font-semibold transition-all"
                :class="showControlReadings
                  ? 'border-sky-600 bg-sky-500 text-white hover:bg-sky-600'
                  : 'border-slate-300 bg-white text-slate-700 hover:border-sky-400 hover:bg-sky-50 hover:text-sky-700'">
                <Icon :name="showControlReadings ? 'fa6-solid:eye' : 'fa6-solid:eye-slash'" />
                {{ t('billing_block.short_control_reading') }}
              </button>
            </th>
            <!-- <th class="p-2">{{ t('billing_block.short_control_reading') }}</th> -->
            <th class="p-2">{{ t('common.photo') || 'Photo' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="element in rows" :key="element.id" class="border-b"
            :class="{
              'bg-red-50': element.is_close,
              'bg-green-50': element.is_initial,
              'cursor-pointer hover:bg-emerald-50': selectableAsInitial && canSelectAsInitial(element) && !selectingDisabled,
              'opacity-50': selectableAsInitial && !canSelectAsInitial(element),
              '!bg-amber-50': willMoveToNewContract(element)
               }"
            :title="selectableAsInitial
              ? (canSelectAsInitial(element) ? t('contract_block.mark_as_initial_short')
                : (lastBilledReading && !element.is_initial && !element.is_control ? t('contract_block.initial_reading_before_billed') : null))
              : null"
            @mouseenter="onRowEnter(element)" @mouseleave="hoveredReading = null"
            @click="selectRow(element)">
            <td v-if="selectableAsInitial" class="p-2 text-center">
              <Icon v-if="willMoveToNewContract(element)" name="fa6-solid:arrow-right-to-bracket" class="text-amber-500"
                :title="t('contract_block.moves_to_new_contract')" />
              <Icon v-else-if="canSelectAsInitial(element)" name="fa6-regular:circle" class="text-slate-400" />
            </td>
            <!-- <td class="p-2">
              <button v-if="index == 0 && !element.invoice" @click="deleteReading(element.id)"
                class="text-red-500 hover:text-red-700">
                <Icon name="fa6-solid:trash" />
              </button>
            </td> -->
            <td class="p-2">
              {{ element.reading_date ? formatDate(element.reading_date) : '-' }}
            </td>
            <td class="p-2">
              <button v-if="!isSubRegion && element.invoice"
                class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
                @click="showDetail('InvoiceRegion', element.invoice.id)">{{ element.invoice.serie_final }} </button>
              <span v-else>{{ element.invoice ? element.invoice.serie_final : '-' }}</span>
            </td>
            <td class="p-2">
              <div class="flex items-center gap-1">
                <span>{{ element.reading_value ? parseInt(element.reading_value) : '-' }}</span>
                <Icon v-if="element.is_fire" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
                <span v-if="element.copies.length > 0" :title="copiesTooltip(element)"
                  class="inline-flex items-center gap-0.5 rounded-full bg-sky-100 px-1.5 py-0.5 text-xs font-semibold text-sky-700 whitespace-nowrap cursor-help">
                  <Icon name="fa6-solid:copy" class="text-[10px]" />
                  {{ element.copies.length }}
                </span>
              </div>
            </td>
            <td class="p-2">{{ element.batch ? element.batch.name : '-' }}</td>
            <td class="p-2">{{ element.origin ? element.origin : '-' }}</td>
            <td v-if="!isSubRegion && element.meter && !meter_id" class="p-2">
              <button class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
                @click="showDetail('MeterRegion', element.meter.id)">{{ element.meter.code }}</button>
            </td>
            <td v-else class="p-2">{{ element.meter ? element.meter.code : '-' }}</td>
            <td v-if="!isSubRegion && (!contract_ids || contract_ids.length == 0)" class="p-2">
              <button class="text-sky-600 underline cursor-pointer hover:text-sky-400 mx-1"
                @click="showDetail('ContractRegion', element.contract.id)">{{ element.contract.token }}</button>
            </td>
            <td v-else-if="!contract_ids || contract_ids.length == 0" class="p-2">{{ element.contract ?
              element.contract.token : '-' }}</td>
            <td class="p-2 min-w-[80px]">
              <div>
                <span>
                  {{ element.calculated_value ? parseInt(element.calculated_value) : '-' }}
                </span>
                <abbr :title="t('billing_block.estimated_correction')" v-if="element.estimated_used && element.estimated_used > 0"
                  class="text-yellow-600 font-semibold">
                  - {{ parseInt(element.estimated_used) }}
                </abbr>
                m3
              </div>
              <div v-if="(element.leak_value && element.leak_value > 0)" class="text-xs font-bold">
                <p class="text-red-600">
                  {{ t('billing_block.leak') }}: {{ element.leak_value ? parseInt(element.leak_value) + ' m3' : '-' }}
                </p>
                <p class="text-green-600">
                  {{ t('common.real') }}: {{ element.real_consumption ? (parseInt(element.real_consumption) - parseInt(element.leak_value || 0)) + ' m3' : '-'
                  }}
                </p>
              </div>
            </td>
            <td class="p-2" v-if="element.is_estimated">
              <Icon name="fa6-solid:check" v-show="element.is_estimated" class="text-xl text-green-600" />
            </td>
            <td class="p-2" v-else>
              -
            </td>
            <td class="p-2" v-if="element.is_control">
              <Icon name="fa6-solid:check" v-show="element.is_control" class="text-xl text-green-600" />
            </td>
            <td class="p-2" v-else>
              <!-- <Icon v-show="!element.is_control" name="fa6-solid:xmark" class="text-xl text-red-600" /> -->
              -
            </td>
            <td class="p-2">
              <button v-if="element.photo" :title="t('common.view')"
                class="w-8 h-8 mx-1 bg-sky-500 text-white rounded-full flex items-center justify-center enabled:hover:bg-sky-300 transition-all duration-200"
                @click.stop="openPhotoModal(element.photo)">
                <Icon name="fa6-solid:eye" />
              </button>
              <span v-else>-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Photo modal -->
  <div v-if="showPhotoModal" class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="absolute inset-0 bg-black/60" @click="closePhotoModal"></div>
    <div class="relative bg-white rounded-lg shadow-lg max-w-3xl w-[90vw] max-h-[90vh] p-2">
      <button :title="t('common.close')"
        class="absolute top-2 right-2 w-8 h-8 bg-slate-600 text-white rounded-full flex items-center justify-center hover:bg-slate-500"
        @click="closePhotoModal">
        <Icon name="fa6-solid:xmark" />
      </button>
      <img :src="photoSrc" alt="Photo" class="block max-h-[80vh] w-auto object-contain mx-auto" />
    </div>
  </div>

</template>