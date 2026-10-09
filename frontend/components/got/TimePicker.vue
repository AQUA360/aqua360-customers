<template>
  <div class="space-y-1">
    <!-- Inline layout: Label + Selects -->
    <div class="flex items-center gap-3">
      <label v-if="label" class="text-sm font-medium text-gray-700 min-w-[80px]">
        {{ label }}
        <span v-if="required" class="text-red-500">*</span>
      </label>
      
      <div class="flex items-center gap-1.5">
        <!-- Hours Select -->
        <select
          v-model="hours"
          @change="updateTime"
          :disabled="disabled"
          class="w-16 px-2 py-1.5 border rounded-md text-sm text-center font-medium transition-all duration-150 appearance-none"
          :class="[
            errorMessage 
              ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' 
              : 'border-gray-200 focus:border-blue-500 focus:ring-blue-500/20',
            disabled ? 'bg-gray-50 cursor-not-allowed text-gray-400' : 'bg-white cursor-pointer',
            !hasValue ? 'text-gray-400' : 'text-gray-900'
          ]"
        >
          <option value="" class="text-gray-400">--</option>
          <option v-for="h in 24" :key="h-1" :value="String(h-1).padStart(2, '0')">
            {{ String(h-1).padStart(2, '0') }}
          </option>
        </select>

        <!-- Separator -->
        <span class="text-base font-medium text-gray-400">:</span>

        <!-- Minutes Select -->
        <select
          v-model="minutes"
          @change="updateTime"
          :disabled="disabled"
          class="w-16 px-2 py-1.5 border rounded-md text-sm text-center font-medium transition-all duration-150 appearance-none"
          :class="[
            errorMessage 
              ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' 
              : 'border-gray-200 focus:border-blue-500 focus:ring-blue-500/20',
            disabled ? 'bg-gray-50 cursor-not-allowed text-gray-400' : 'bg-white cursor-pointer',
            !hasValue ? 'text-gray-400' : 'text-gray-900'
          ]"
        >
          <option value="" class="text-gray-400">--</option>
          <option v-for="m in 60" :key="m-1" :value="String(m-1).padStart(2, '0')">
            {{ String(m-1).padStart(2, '0') }}
          </option>
        </select>
      </div>
    </div>
    
    <!-- Error Message -->
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-1"
    >
      <p v-if="errorMessage" class="text-xs text-red-600 flex items-center gap-1 ml-[92px]">
        <Icon name="fa6-solid:circle-exclamation" class="text-[10px]" />
        {{ errorMessage }}
      </p>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  label: {
    type: String,
    default: ''
  },
  required: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  minTime: {
    type: String,
    default: null
  },
  maxTime: {
    type: String,
    default: null
  }
});

const emit = defineEmits(['update:modelValue', 'blur']);

const hours = ref('');
const minutes = ref('');
const touched = ref(false);

// Check if time has a value
const hasValue = computed(() => hours.value !== '' && minutes.value !== '');

// Initialize from modelValue
onMounted(() => {
  if (props.modelValue) {
    const [h, m] = props.modelValue.split(':');
    hours.value = h || '';
    minutes.value = m || '';
  }
});

// Watch for external changes
watch(() => props.modelValue, (newVal) => {
  if (!newVal) {
    hours.value = '';
    minutes.value = '';
  } else if (newVal !== `${hours.value}:${minutes.value}`) {
    const [h, m] = newVal.split(':');
    hours.value = h || '';
    minutes.value = m || '';
  }
});

// Update time when selects change
const updateTime = () => {
  // If both are empty, emit empty string
  if (hours.value === '' && minutes.value === '') {
    emit('update:modelValue', '');
  } 
  // If both have values, emit the full time
  else if (hours.value !== '' && minutes.value !== '') {
    emit('update:modelValue', `${hours.value}:${minutes.value}`);
  }
  // Otherwise, partial selection - don't emit yet
  touched.value = true;
};

// Validation
const errorMessage = computed(() => {
  if (props.error) return props.error;
  if (!touched.value) return '';
  
  const currentTime = hasValue.value ? `${hours.value}:${minutes.value}` : '';
  
  if (props.required && !currentTime) {
    return 'Time is required';
  }
  
  if (currentTime && props.minTime && currentTime < props.minTime) {
    return `Must be after ${props.minTime}`;
  }
  
  if (currentTime && props.maxTime && currentTime > props.maxTime) {
    return `Must be before ${props.maxTime}`;
  }
  
  return '';
});

// Public method to trigger validation
const validate = () => {
  touched.value = true;
  return !errorMessage.value;
};

// Clear the time
const clear = () => {
  hours.value = '';
  minutes.value = '';
  emit('update:modelValue', '');
};

// Expose methods
defineExpose({
  validate,
  clear,
  hasValue
});
</script>

<style scoped>
/* Style the select dropdowns */
select {
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-position: right 0.25rem center;
  background-repeat: no-repeat;
  background-size: 1em 1em;
  padding-right: 1.5rem;
}

select:focus {
  outline: none;
}
</style>
