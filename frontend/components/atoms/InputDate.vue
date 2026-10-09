<script setup>
import { useI18n } from 'vue-i18n';
import { computed } from 'vue';

const { t } = useI18n();

// Define the props and logic as before
const props = defineProps({
  modelValue: {
    type: String,
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
  inputId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue', 'date-interval-error']);

const fallbackId = useId();
const resolvedInputId = computed(() => {
  if (props.inputId) return props.inputId;
  if (props.label) return `date-${props.label}`;
  return fallbackId;
});

const onInput = (event) => {
  emit('update:modelValue', event.target.value);
};

const onBlur = (event) => {
  let val = event.target.value;
  if (props.startDate && val && val != '' && val < props.startDate) {
    emit('update:modelValue', props.startDate);
    emit('date-interval-error', t('warning_block.date_warning'))
  }
}
</script>

<template>
  <div class="input-group mb-4">
    <label v-if="label" :for="resolvedInputId" class="block text-sm font-medium text-slate-600 mb-2">
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>
    <input
      :id="resolvedInputId"
      type="date"
      :value="modelValue"
      @input="onInput"
      @blur="onBlur"
      :disabled="disabled"
      :placeholder="placeholder"
      :required="required"
      :class="{ 'ring-[1px] ring-red-400': invalid }"
      class="input"
      :min="startDate || null"
    />
  </div>
</template>

<style scoped>
/* Ús compacte (p. ex. al costat d'un AtomsColorBadge dins una fila de FieldDetail): elimina el
   marge inferior per defecte i redueix el padding vertical de l'input al mateix que fa servir
   ColorBadge (py-0.5), perquè el camp de data quedi a la mateixa alçada que un valor normal. */
.compact-date {
  margin-bottom: 0;
}
.compact-date input[type="date"] {
  padding-top: 0.125rem;
  padding-bottom: 0.125rem;
}
.no-border input[type="date"] {
  border: none;
  outline: none;
  box-shadow: none;
}
</style>
