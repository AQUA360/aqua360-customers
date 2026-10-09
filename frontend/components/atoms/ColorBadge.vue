<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { AppColors } from '~/utils/config';

const { t, te } = useI18n();

const props = defineProps({
  value: String,
  color: {
    type: String,
    default: 'gray'
  },
});

const colorClass = ref()

const setColor = () => {
  const color = AppColors.find(c => c.code === props.color);
  colorClass.value = color ? color.class : 'badge-gray';
}

const capitalize = (str) => str ? str.charAt(0).toUpperCase() + str.slice(1) : str;

const translatedValue = computed(() => {
  if (!props.value) return '';

  const blockKey = `billing_block.${props.value}`;
  if (te(blockKey)) return capitalize(t(blockKey));
  if (te(props.value)) return capitalize(t(props.value));

  return capitalize(props.value);
});

onMounted(() => {
  setColor();
})

watch(() => props.color, () => {
  setColor();
})

</script>


<template>
  <span :class="colorClass" class="inline-block rounded px-2 py-0.5 text-sm cursor-default w-fit"> {{ translatedValue }}</span>
</template>