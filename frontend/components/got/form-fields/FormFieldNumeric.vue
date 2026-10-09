<script setup>
/**
 * Numeric Field Component for Dynamic Forms
 * Handles 'numeric' type fields
 */
import { computed } from 'vue';

const props = defineProps({
  field: {
    type: Object,
    required: true
  },
  modelValue: {
    type: [String, Number],
    default: ''
  },
  error: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue']);

const value = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
});
</script>

<template>
  <div class="space-y-2">
    <label class="block text-sm font-medium text-gray-700">
      {{ field.name }}
      <span v-if="field.required" class="text-red-500">*</span>
    </label>
    
    <div class="relative">
      <Icon 
        name="fa6-solid:hashtag" 
        class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm" 
      />
      <input
        v-model="value"
        type="number"
        inputmode="numeric"
        :placeholder="$t('GOT.form_field_numeric_placeholder')"
        :disabled="disabled"
        class="w-full pl-10 pr-4 py-2.5 border rounded-lg text-base transition-all duration-150"
        :class="[
          error 
            ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' 
            : 'border-gray-200/60 focus:border-blue-500 focus:ring-blue-500/20',
          disabled ? 'bg-gray-50 cursor-not-allowed' : ''
        ]"
      />
    </div>
    
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-1"
    >
      <p v-if="error" class="text-sm text-red-600 flex items-center gap-1.5">
        <Icon name="fa6-solid:circle-exclamation" class="text-xs" />
        {{ error }}
      </p>
    </Transition>
  </div>
</template>

<style scoped>
/* Hide number input spinners */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
input[type="number"] {
  -moz-appearance: textfield;
  appearance: textfield;
}
</style>
