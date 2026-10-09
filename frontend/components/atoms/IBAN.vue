<script setup>
import { ref, computed } from 'vue';
import { hideIban, formatIban } from '~/utils/iban';

const props = defineProps({
  value: {
    type: String,
    required: true
  },
  hide: {
    type: Boolean,
    default: true
  }
});

const isHidden = ref(props.hide);

const displayValue = computed(() => {
  return isHidden.value ? hideIban(props.value) : formatIban(props.value);
});

const toggleVisibility = () => {
  isHidden.value = !isHidden.value;
};
</script>

<template>
  <div class="flex items-center gap-2 group whitespace-nowrap">
    <span class="text-black-900 truncate font-mono">{{ displayValue }}</span>
    <button 
      type="button"
      @click="toggleVisibility" 
      class="text-slate-400 hover:text-sky-500 transition-colors p-1 rounded-full hover:bg-slate-100 flex items-center justify-center h-6 w-6"
      :title="isHidden ? $t('common.show_iban') : $t('common.hide_iban')"
    >
      <Icon :name="isHidden ? 'fa6-solid:eye' : 'fa6-solid:eye-slash'" class="text-xs" />
    </button>
  </div>
</template>

<style scoped>
.truncate {
  max-width: 100%;
}
</style>