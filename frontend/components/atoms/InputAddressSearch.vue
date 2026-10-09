<script setup>
import { ref, watch, onMounted } from 'vue';

const props = defineProps({
  value: {
    type: String,
    default: ''
  }
});

const { t } = useI18n();
const emit = defineEmits(['change']);

const street = ref('');
const number = ref('');
const numbersuffix = ref('');
const numberrange = ref('');
const numberrangesuffix = ref('');
const floor = ref('');
const door = ref('');
const stair = ref('');
const building = ref('');

const buildConcatString = () => {
  const parts = [
    street.value,
    number.value,
    numbersuffix.value,
    numberrange.value,
    numberrangesuffix.value,
    floor.value,
    door.value,
    stair.value,
    building.value
  ].map(p => (p || '').trim());
  const joined = parts.join('%');
  return parts.every(p => p === '') ? '' : joined;
};

const emitChange = () => {
  emit('change', buildConcatString());
};

const setFromValue = () => {
  if (props.value) {
    const parts = props.value.split('%');
    street.value = parts[0] ?? '';
    number.value = parts[1] ?? '';
    numbersuffix.value = parts[2] ?? '';
    numberrange.value = parts[3] ?? '';
    numberrangesuffix.value = parts[4] ?? '';
    floor.value = parts[5] ?? '';
    door.value = parts[6] ?? '';
    stair.value = parts[7] ?? '';
    building.value = parts[8] ?? '';
  }
};

onMounted(() => {
  setFromValue();
});

watch(() => props.value, () => {
  setFromValue();
}, { immediate: true });
</script>

<template>
  <div class="flex flex-wrap items-center gap-1">
    <input
      v-no-dash
      v-model="street"
      type="text"
      :placeholder="t('address_block.street')"
      class="border border-gray-300 rounded-md bg-white p-2 shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm placeholder-slate-400 min-w-[100px]"
      @input="emitChange"
    />
    <!-- Bubble 1: number + numbersuffix -->
    <div class="grid grid-cols-2 divide-x border border-gray-300 bg-white rounded-md shadow-sm focus-within:ring-1 focus-within:ring-indigo-500 focus-within:border-indigo-500 sm:text-sm">
      <input
        v-no-dash
        v-model="number"
        type="text"
        :placeholder="'Num.'"
        class="bg-transparent focus:outline-none focus:ring-0 p-2 rounded-l-md placeholder-slate-400 w-10"
        @input="emitChange"
      />
      <input
        v-no-dash
        v-model="numbersuffix"
        type="text"
        :placeholder="'Suf.'"
        class="bg-transparent focus:outline-none focus:ring-0 p-2 rounded-r-md placeholder-slate-400 w-10"
        @input="emitChange"
      />
    </div>
    <span class="text-slate-400 font-medium">–</span>
    <!-- Bubble 2: numberrange + numberrangesuffix -->
    <div class="grid grid-cols-2 divide-x border border-gray-300 bg-white rounded-md shadow-sm focus-within:ring-1 focus-within:ring-indigo-500 focus-within:border-indigo-500 sm:text-sm">
      <input
        v-no-dash
        v-model="numberrange"
        type="text"
        :placeholder="'Núm. fin'"
        class="bg-transparent focus:outline-none focus:ring-0 p-2 rounded-l-md placeholder-slate-400 w-10"
        @input="emitChange"
      />
      <input
        v-no-dash
        v-model="numberrangesuffix"
        type="text"
        :placeholder="'Suf. fin'"
        class="bg-transparent focus:outline-none focus:ring-0 p-2 rounded-r-md placeholder-slate-400 w-10"
        @input="emitChange"
      />
    </div>
    <!-- Bubble: floor, door, stair, building -->
    <div class="grid grid-cols-4 divide-x border border-gray-300 bg-white rounded-md shadow-sm focus-within:ring-1 focus-within:ring-indigo-500 focus-within:border-indigo-500 sm:text-sm">
      <input
        v-no-dash
        v-model="floor"
        type="text"
        :placeholder="t('address_block.floor')"
        class="bg-transparent focus:outline-none focus:ring-0 p-2 rounded-l-md placeholder-slate-400 w-12"
        @input="emitChange"
      />
      <input
        v-no-dash
        v-model="door"
        type="text"
        :placeholder="t('address_block.door')"
        class="bg-transparent focus:outline-none focus:ring-0 p-2 placeholder-slate-400 w-12"
        @input="emitChange"
      />
      <input
        v-no-dash
        v-model="stair"
        type="text"
        :placeholder="t('address_block.stair')"
        class="bg-transparent focus:outline-none focus:ring-0 p-2 placeholder-slate-400 w-12"
        @input="emitChange"
      />
      <input
        v-no-dash
        v-model="building"
        type="text"
        :placeholder="t('address_block.building')"
        class="bg-transparent focus:outline-none focus:ring-0 p-2 rounded-r-md placeholder-slate-400 w-12"
        @input="emitChange"
      />
    </div>
  </div>
</template>
