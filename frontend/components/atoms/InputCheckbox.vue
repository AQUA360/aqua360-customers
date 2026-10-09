<script setup>
import { useI18n } from 'vue-i18n';

// Definició de les propietats que el component rep
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  label: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  required: {
    type: Boolean,
    default: false
  },
  name: {
    type: String,
    default: ''
  }
});

// Definició dels esdeveniments que el component pot emetre
const emit = defineEmits(['update:modelValue']);

// Gestió de les traduccions
const { t } = useI18n();

// Funció per manejar els canvis en el checkbox
const handleChange = (event) => {
  emit('update:modelValue', event.target.checked);
};
</script>

<template>
  <div class="flex items-center mb-4">
    <input
      :id="name || label"
      type="checkbox"
      :checked="modelValue"
      @change="handleChange"
      :disabled="disabled"
      :required="required"
      class="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
    />
    <label
      :for="name || label"
      class="ml-2 block text-sm text-gray-900"
    >
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>
  </div>
</template>
