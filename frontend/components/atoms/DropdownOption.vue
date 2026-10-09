<script setup>
import { useI18n } from 'vue-i18n';

// Defineix les props que acceptarà aquest component
const props = defineProps({
  name: String,
  title: String,
  disabled: {
    type: Boolean,
    default: false
  },
});

// Defineix els esdeveniments que aquest component pot emetre
const emit = defineEmits(['click']);

const closeOptionsDropdown = inject('closeOptionsDropdown', null);

// Funció per gestionar el clic, que emetrà l'esdeveniment 'clicked'
const handleClick = () => {
  emit('click');
  closeOptionsDropdown?.();
}
</script>

<template>
  <li>
    <button @click="handleClick" :disabled="disabled" :class="{ 'cursor-auto opacity-50': disabled, 'hover:bg-gray-100': !disabled }"
            class="block w-full text-start py-2 px-4 whitespace-nowrap"
            :title="title ? title : name">
      <slot>{{ name }}</slot>
    </button>
  </li>
</template>
