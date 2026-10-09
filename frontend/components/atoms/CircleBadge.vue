<script setup>
import { AppColors } from '~/utils/config';

const props = defineProps({
  icon: {
    type: String,
    default: 'fa6-solid:circle'
  },
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

onMounted(() => {
  setColor();
})

watch(() => props.color, () => {
  setColor();
})

</script>


<template>
  <Icon :name="icon" :class="colorClass" />
</template>