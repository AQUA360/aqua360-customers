<script setup>
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';

const { t } = useI18n();
const emits = defineEmits(['update:nozzle','open-edit', 'delete', 'add-supply-point', 'edit-supply-point', 'show-supply-point-region', 'show-meter-region']);

const props = defineProps({
  nozzle: {
    type: Object,
    required: true,
  },
  position: {
    type: Number,
    required: false,
  },
  statuses: {
    type: Array,
    required: false,
  },
  types: {
    type: Array,
    required: false,
  },
  diameters: {
    type: Array,
    required: false,
  },
  defaultValues: {
    type: Boolean,
    required: false,
  },
  showDelete: {
    type: Boolean,
    required: false,
  }
});

const meterCode = computed(() => {
  const sp = props.nozzle.supplyPoint;
  return sp?.meter_code || sp?.meter?.code || null;
});

const meterId = computed(() => {
  const sp = props.nozzle.supplyPoint;
  return sp?.meter_id || sp?.meter?.id || null;
});

const nozzleDestination = ref(null);
const nozzleDestinationObject = ref(null);
const nozzleStatus = ref(null);
const nozzleType = ref(null);
const nozzleDiameter = ref(null);
const nozzleCol = ref(null);
const nozzleRow = ref(null);

const destinationObject = ref(null);

const updateProps = () => {
  nozzleDestination.value = props.nozzle.destination || null;
  destinationObject.value = props.nozzle.supplyPoint? props.nozzle.supplyPoint.address || null : null;
  nozzleStatus.value = props.nozzle.status?.id || (props.statuses.length > 0 ? props.statuses[0].id : null);
  nozzleType.value = props.nozzle.type?.id || (props.types.length > 0 ? props.types[0].id : null);
  nozzleDiameter.value = props.nozzle.diameter || null;
  nozzleCol.value = props.nozzle.col || null;
  nozzleRow.value = props.nozzle.row || null;
};

const updateDestination = (destination) => {
  nozzleDestinationObject.value = destination;
  nozzleDestination.value = destination.floor;
  if (destination.door) {
    nozzleDestination.value += '-' + destination.door;
  }
  if (destination.stair) {
    nozzleDestination.value += '-' + destination.stair;
  }
  if (destination.building) {
    nozzleDestination.value += '-' + destination.building;
  }

  emitUpdate('destination');

};

const handleClickEdit = () => {
  emits('open-edit',props.nozzle);
};

const handleClickDelete = () => {
  emits('delete',props.nozzle);
};

const emitUpdate = (field) => {
  emits('update:nozzle', {
    ...props.nozzle,
    destination: nozzleDestination.value,
    destinationObject: nozzleDestinationObject.value,
    status: nozzleStatus.value,
    type: nozzleType.value,
    diameter: nozzleDiameter.value,
    col: nozzleCol.value,
    row: nozzleRow.value,
    field: field
  });
};


// Update the values when props.nozzle changes
watch(
  () => props.nozzle,
  (nozzle) => {
    if (nozzle) {
      updateProps()
    }
  },
  { immediate: true, deep: true }
);

// Add individual watchers for each property
watch(() => props.nozzle?.status?.id, (newVal) => {
  if (newVal !== undefined) {
    nozzleStatus.value = newVal;
  }
});

watch(() => props.nozzle?.type?.id, (newVal) => {
  if (newVal !== undefined) {
    nozzleType.value = newVal;
  }
});

watch(() => props.nozzle?.diameter, (newVal) => {
  if (newVal !== undefined) {
    nozzleDiameter.value = newVal;
  }
});

watch(() => props.nozzle?.destination, (newVal) => {
  if (newVal !== undefined) {
    nozzleDestination.value = newVal;
  }
});
</script>

<template>
  <div class="grid gap-2 items-center" :class="{ 'grid-cols-[3fr,1fr,75px,75px,1fr,1fr,2fr]': !props.defaultValues, 'grid-cols-[3fr,1fr,75px,75px,1fr,2fr]': props.defaultValues }">
    <!-- <div v-if="!props.defaultValues">
      {{ nozzle.position }}.
    </div> -->
    <div>
      <AtomsInputSupplyDestination :destination="nozzle.destination" :value="destinationObject" @change="updateDestination"/>
    </div>
    <div>
      <select v-model="nozzleType" @change="emitUpdate('type')"
        class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
        <option v-for="t in types" :key="t.id" :value="t.id">{{ t.name }}</option>
      </select>
    </div>
    <div>
      <input v-no-dash @change="emitUpdate('nozzle-col')" v-model="nozzleCol" type="text" 
        class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm placeholder-slate-200"/>
    </div>
    <div>
      <input v-no-dash @change="emitUpdate('nozzle-row')" v-model="nozzleRow" type="text" 
        class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm placeholder-slate-200"/>
    </div>
    <div>
      <select v-model="nozzleDiameter" @change="emitUpdate('diameter')"
        class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
        <option v-for="t in diameters" :key="t.name" :value="t.name">{{ t.name }}</option>
      </select>
    </div>
    <div>
      <select v-model="nozzleStatus" @change="emitUpdate('status')"
        class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
        <option v-for="status in statuses" :key="status.id" :value="status.id">{{ status.name }}</option>
      </select>
    </div>
    <div class="relative h-full flex items-center justify-between gap-2" v-if="!props.defaultValues">
      <div class="flex items-center gap-2">
        <div v-if="props.nozzle.supplyPoint?.id" class="flex flex-col">
          <div class="flex items-center gap-1">
            <button type="button" @click="emits('show-supply-point-region', props.nozzle)"
              class="text-sky-500 underline hover:no-underline" :title="t('common.show_detail')">
              {{ props.nozzle.supplyPoint?.token }}
            </button>
            <AtomsRedirectButton :id="props.nozzle.supplyPoint?.id" :path="'/service/supplypoints/'" />
            <button type="button" @click="emits('edit-supply-point', props.nozzle)" class="text-sky-600 hover:text-sky-800 p-1 flex items-center" :title="t('common.edit')">
              <Icon name="fa6-solid:pencil" class="w-4 h-4" />
            </button>
          </div>
          <span class="text-xs text-slate-500 flex items-center gap-1">
            {{ t('meter') }}:
            <template v-if="meterCode && meterId">
              <button type="button" @click="emits('show-meter-region', props.nozzle)"
                class="text-sky-500 underline hover:no-underline" :title="t('common.show_detail')">
                {{ meterCode }}
              </button>
              <AtomsRedirectButton :id="meterId" :path="'/service/meters/'" />
            </template>
            <template v-else>{{ meterCode || '-' }}</template>
          </span>
        </div>
        <div v-else class="flex items-center gap-2">
          <span class="text-slate-400">-</span>
          <button type="button" @click="emits('add-supply-point', props.nozzle)" class="text-emerald-600 hover:text-emerald-800 p-1 flex items-center" :title="t('common.add')">
            <Icon name="fa6-solid:plus" class="w-4 h-4" />
          </button>
        </div>
      </div>
      <button v-if="props.showDelete" type="button" @click="handleClickDelete" class="text-rose-600 hover:text-rose-800 p-1 flex items-center" :title="t('common.delete')">
        <Icon name="fa6-solid:trash" class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>
