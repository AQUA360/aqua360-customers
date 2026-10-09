<script setup>
import { useI18n } from 'vue-i18n';

// Definició de les propietats que el component rep
const props = defineProps({
  modelValue: {
    type: Number,
    default: null
  },
  label: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  placeholder: {
    type: String,
    default: ''
  },
  required: {
    type: Boolean,
    default: false
  },
  min: {
    type: Number,
    default: null
  },
  max: {
    type: Number,
    default: null
  },
  step: {
    type: Number,
    default: 1
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

// Funció per manejar l'entrada de l'usuari
const handleInput = (event) => {
  const value = event.target.value === '' ? null : Number(event.target.value);
  emit('update:modelValue', value);
};
</script>

<template>
  <div class="input-group mb-4">
    <label :for="name || label" class="block text-sm font-medium text-gray-700 mb-2">
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>
    <input
      :id="name || label"
      type="number"
      :value="modelValue !== null ? modelValue : ''"
      @input="handleInput"
      :disabled="disabled"
      :placeholder="placeholder"
      :required="required"
      :min="min"
      :max="max"
      :step="step"
      class="input"
    />
  </div>
</template>
