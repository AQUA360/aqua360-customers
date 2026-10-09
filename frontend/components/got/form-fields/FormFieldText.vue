<script setup>
/**
 * Text Field Component for Dynamic Forms
 * Handles 'text' type fields
 */
import { computed } from 'vue';

const props = defineProps({
  field: {
    type: Object,
    required: true
  },
  modelValue: {
    type: String,
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
    
    <textarea
      v-model="value"
      :placeholder="$t('GOT.form_field_text_placeholder')"
      :disabled="disabled"
      rows="3"
      class="w-full px-3 py-2.5 border rounded-lg text-base resize-none transition-all duration-150"
      :class="[
        error 
          ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' 
          : 'border-gray-200/60 focus:border-blue-500 focus:ring-blue-500/20',
        disabled ? 'bg-gray-50 cursor-not-allowed' : ''
      ]"
    ></textarea>
    
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
