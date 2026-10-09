<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: String,
    required: true
  }
});

const emit = defineEmits(['saved']);

const currentValue = ref(props.value);

watch(() => props.value, (newValue) => {
  currentValue.value = newValue;
});

const saveTextarea = () => {
  emit('saved', currentValue.value);
};

const handleTextareaUpdate = (newText) => {
  currentValue.value = newText;
};
</script>

<template>
  <div class="mt-4">
    <label class="block text-sm font-medium text-slate-500 mb-2">{{ label }}</label>
    <AtomsInputTextarea :autosave="false" @update:text="handleTextareaUpdate" :text="currentValue"
      :placeholder="'common.write_here'"></AtomsInputTextarea>
    <button @click="saveTextarea" class="button-primary">{{ $t('common.save') }}</button>
  </div>
</template>

<style scoped>
/* Add your styles here */
</style>