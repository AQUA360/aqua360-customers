<template>
  <div class="px-6 py-5" :class="{ 'border-t border-gray-200/60': hasBorder }">
    <div class="space-y-3">
      <div class="flex items-center gap-2">
        <Icon name="fa6-solid:pen-to-square" class="text-gray-600 text-sm" />
        <h2 class="text-base font-semibold text-gray-900">{{ $t('GOT.new_observation') }}</h2>
      </div>
      
      <textarea
        v-model="observationText"
        :placeholder="$t('GOT.enter_observation')"
        class="w-full px-3 py-2 border border-gray-200/60 rounded-md focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-150 text-sm resize-none"
        rows="4"
      ></textarea>
      
      <div class="flex justify-end">
        <button
          @click="handleSubmit"
          :disabled="loading || !observationText.trim()"
          class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium text-sm shadow-sm transition-all duration-150"
        >
          <Icon 
            :name="loading ? 'fa6-solid:spinner' : 'fa6-solid:plus'" 
            class="text-sm"
            :class="{ 'animate-spin': loading }"
          />
          <span v-if="!loading">{{ $t('GOT.add_observation') }}</span>
          <span v-else>{{ $t('common.saving') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  },
  hasBorder: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue', 'submit']);

const observationText = ref(props.modelValue);

watch(() => props.modelValue, (newValue) => {
  observationText.value = newValue;
});

watch(observationText, (newValue) => {
  emit('update:modelValue', newValue);
});

const handleSubmit = () => {
  emit('submit');
};
</script>
