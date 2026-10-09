<script setup>
const props = defineProps({
  amount: Number,
});

const formatted = computed(() => {
  if (!props.amount && props.amount !== 0) return '0';
  return new Intl.NumberFormat('ca-ES', { style: 'currency', currency: 'EUR' }).format(props.amount);
});
</script>

<template>
  <span class="text-xs font-medium" :class="props.amount ? 'text-red-600' : 'text-gray-400'">
    {{ formatted }}
  </span>
</template>