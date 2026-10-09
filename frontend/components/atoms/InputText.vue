<script setup>
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';

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
  name: {
    type: String,
    default: ''
  },
  type: {
    type: String,
    default: 'text' // Permet especificar altres tipus d'input com 'email', 'password', etc.
  },
  minLength: {
    type: Number,
    default: null
  },
  showValidation: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue', 'validation-change']);

const { t } = useI18n();

const showPassword = ref(false);

const inputType = computed(() => {
  if (props.type === 'password') {
    return showPassword.value ? 'text' : 'password';
  }
  return props.type;
});

const isValid = computed(() => {
  if (!props.showValidation) return true;
  
  // Required validation
  if (props.required && !props.modelValue) return false;
  
  // Min length validation
  if (props.minLength && props.modelValue.length < props.minLength) return false;
  
  return true;
});

const errorMessage = computed(() => {
  if (!props.showValidation || isValid.value) return '';
  
  if (props.required && !props.modelValue) {
    return t('common.field_required');
  }
  
  if (props.minLength && props.modelValue.length < props.minLength) {
    return t('common.min_length_error', { min: props.minLength });
  }
  
  return '';
});

const handleInput = (event) => {
  emit('update:modelValue', event.target.value);
  emit('validation-change', isValid.value);
};

const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value;
};
</script>

<template>
  <div class="input-group mb-4">
    <label :for="name || label" class="block text-sm font-medium text-gray-700 mb-2">
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>
    <div class="relative">
      <input
        :id="name || label"
        :type="inputType"
        :value="modelValue"
        @input="handleInput"
        :disabled="disabled"
        :placeholder="placeholder"
        :required="required"
        :name="name || label"
        class="input"
        :class="{ 
          'pr-10': type === 'password',
          'border-red-500 focus:border-red-500 focus:ring-red-500': showValidation && !isValid,
        }"
      />
      <button
        v-if="type === 'password'"
        type="button"
        @click="togglePasswordVisibility"
        class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 focus:outline-none"
        :title="showPassword ? t('common.hide_password') : t('common.show') + ' ' + t('common.password')"
      >
        <Icon 
          :name="showPassword ? 'fa6-solid:eye-slash' : 'fa6-solid:eye'" 
          class="h-4 w-4"
        />
      </button>
    </div>
    <p v-if="showValidation && errorMessage" class="mt-1 text-sm text-red-600">
      {{ errorMessage }}
    </p>
  </div>
</template>

<style scoped>
.input-group {
  margin-bottom: 1rem;
}
</style>
