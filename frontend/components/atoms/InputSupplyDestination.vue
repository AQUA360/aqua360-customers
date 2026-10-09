<script setup>
import { ref, watch, onMounted } from 'vue';

const props = defineProps({
  value: {
    type: Object,
    default: () => ({}),
  },
  destination: {
    type: String,
    default: ''
  }
});
const { t } = useI18n();
const emit = defineEmits(['change']);
const emitChange = () => {
  emit('change', {
    floor: floor.value,
    door: door.value,
    stair: stair.value,
    building: building.value,
    address_extra: address_extra.value,
  });
};

const floor = ref('');
const door = ref('');
const stair = ref('');
const building = ref('');
const address_extra = ref('');

const setDestination = () => {
  // If we have the address object in props.value, prioritize its fields as they are already separate
  if (props.value && (props.value.floor != null || props.value.door != null || props.value.stair != null || props.value.building != null || props.value.address_extra != null)) {
    floor.value = props.value.floor || '';
    door.value = props.value.door || '';
    stair.value = props.value.stair || '';
    building.value = props.value.building || '';
    address_extra.value = props.value.address_extra || '';
  }
  else if (props.destination) {
    const parts = props.destination.split('-');
    floor.value = parts[0] || '';
    door.value = parts[1] || '';
    stair.value = parts[2] || '';
    building.value = parts[3] || '';
  }
};

onMounted(() => {
  setDestination();
});

watch( () => props.value, () => {
    setDestination();
  },
  { deep: true }
);

watch( () => props.destination, () => {
    if (!props.value || (!props.value.floor && !props.value.door && !props.value.stair && !props.value.building)) {
      setDestination();
    }
  }
);


</script>

<template>
  <div class="grid grid-cols-5 divide-x border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400">
    <input v-no-dash @input="emitChange" :placeholder="t('address_block.floor')" v-model="floor" class="bg-transparent focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm p-2 rounded-l-md placeholder-slate-200" type="text"/>
    <input v-no-dash @input="emitChange" :placeholder="t('address_block.door')" v-model="door" class="bg-transparent focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm p-2 placeholder-slate-200" type="text"/>
    <input v-no-dash @input="emitChange" :placeholder="t('address_block.stair')" v-model="stair" class="bg-transparent focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm p-2 placeholder-slate-200" type="text"/>
    <input v-no-dash @input="emitChange" :placeholder="t('address_block.building')" v-model="building" class="bg-transparent focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm p-2 placeholder-slate-200" type="text"/>
    <input @input="emitChange" :placeholder="t('address_block.address_extra')" v-model="address_extra" class="bg-transparent focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm p-2 rounded-r-md placeholder-slate-200" type="text"/>
  </div>
</template>
