<script setup>

// Definició de les propietats que el component rep
const props = defineProps({
  modelValue: {
    type: String, // Format 'HH:MM'
    default: ''
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
    type: String,
    default: ''
  },
  max: {
    type: String,
    default: ''
  },
  invalid: {
    type: Boolean,
    default: false
  }
});

// Definició dels esdeveniments que el component pot emetre
const emit = defineEmits(['update:modelValue']);

// Funció per manejar l'entrada de l'usuari
const onInput = (event) => {
  emit('update:modelValue', event.target.value);
};
</script>

<template>
  <div class="input-group mb-4">
    <label :for="`time-${label}`" class="block text-sm font-medium text-slate-600 mb-2">
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>
    <input
      :id="`time-${label}`"
      type="time"
      :value="modelValue"
      @input="onInput"
      :disabled="disabled"
      :placeholder="placeholder"
      :required="required"
      :min="min"
      :max="max"
      :class="{ 'ring-[1px] ring-red-400': invalid }"
      class="input"
    />
  </div>
</template>
