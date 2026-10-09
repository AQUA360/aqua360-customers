<script setup>
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

// Definició de les propietats que el component rep
const props = defineProps({
  modelValue: {
    type: String, // Format 'YYYY-MM-DDTHH:MM'
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
  invalid: {
    type: Boolean,
    default: false
  },
  startDate: {
    type: String,
    default: null
  },
  min: {
    type: String,
    default: ''
  },
  max: {
    type: String,
    default: ''
  }
});

// Definició dels esdeveniments que el component pot emetre
const emit = defineEmits(['update:modelValue', 'date-interval-error']);

// Funció per manejar l'entrada de l'usuari
const onInput = (event) => {
  emit('update:modelValue', event.target.value);
};

const onBlur = (event) => {
  const val = event.target.value;
  if (props.startDate && val && val < props.startDate) {
    emit('update:modelValue', props.startDate);
    emit('date-interval-error', t('warning_block.date_warning'));
  }
};
</script>

<template>
  <div class="input-group mb-4">
    <label :for="`datetime-${label}`" class="block text-sm font-medium text-gray-700">
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>
    <input
      :id="`datetime-${label}`"
      type="datetime-local"
      :value="modelValue"
      @input="onInput"
      @blur="onBlur"
      :disabled="disabled"
      :placeholder="placeholder"
      :required="required"
      :min="min || startDate"
      :max="max"
      :class="{ 'ring-[1px] ring-red-400': invalid }"
      class="input"
    />
  </div>
</template>
