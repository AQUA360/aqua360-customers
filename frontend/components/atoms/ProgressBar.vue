<template>
  <div class="px-4">
    <div 
      class="relative w-full bg-gray-200 rounded-full overflow-hidden shadow-inner transition-all duration-700"
      :class="{ 'opacity-0 h-0 my-0': internalProgress >= 100 && !error, 'my-4': (internalProgress < 100 && !error) || error }"
      :style="{ height: internalProgress >= 100 && !error ? '0px' : '32px' }"
    >
      <div 
        class="h-full rounded-l-full transition-all ease-linear duration-500"
        :class="error ? 'bg-red-500' : 'bg-gradient-to-r from-green-500 to-green-300'"
        :style="{ width: internalProgress + '%' }"
      ></div>
      <span 
        class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-sm font-bold text-white"
        :class="{ 'hidden': internalProgress >= 100 && !error }"
      >
        {{ error ? 'Error' : internalProgress + '%' }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

// Props: Accept a `progress` value between 0 and 100
// Adds an `error` boolean prop to toggle error state
const props = defineProps({
  progress: {
    type: Number,
    required: true,
    validator: value => value >= 0 && value <= 100,
  },
  error: {
    type: Boolean,
    default: false,
  },
});

const internalProgress = ref(props.progress || 0);

// Watch the `error` prop and set progress to 100 when it becomes true
watch(
  () => props.error,
  (newValue) => {
    if (newValue) {
      internalProgress.value = 100;
    }
  }
);

// Sync `internalProgress` with `progress` prop unless error is true
watch(
  () => props.progress,
  (newValue) => {
    if (!props.error) {
      internalProgress.value = newValue;
    }
  }
);
</script>
