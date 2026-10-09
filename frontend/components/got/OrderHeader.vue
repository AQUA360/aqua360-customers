<template>
  <div>
    <div class="flex items-center gap-3">
      <div 
        class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
        :class="priorityColorClass"
      >
        <Icon name="fa6-solid:flag" class="text-white text-lg" />
      </div>
      <div>
        <h1 class="text-3xl font-bold text-gray-900">
          {{ $t('GOT.order_detail') }}
        </h1>
        <p v-if="order" class="text-sm text-gray-500 mt-0.5">
          #{{ order.token }}
        </p>
        <div v-if="order" class="flex items-center gap-4 mt-1">
          <div v-if="order.status" class="flex items-center gap-2">
            <span 
              class="w-2 h-2 rounded-full" 
              :class="statusColorClass" 
            ></span>
            <p class="text-xs text-gray-600">
              {{ order.status_name || order.status?.name || '-' }}
            </p>
          </div>
          <div v-if="order.dueDateAt" class="flex items-center gap-2">
            <Icon name="fa6-solid:calendar" class="text-gray-400 text-xs" />
            <p class="text-xs text-gray-600">
              {{ formatDate(order.dueDateAt) }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { formatDate } from '~/utils/date';

const props = defineProps({
  order: {
    type: Object,
    default: null
  }
});

defineEmits(['back']);

const priorityColorClass = computed(() => {
  const color = props.order?.priority?.color;
  return {
    'bg-gradient-to-br from-red-500 to-rose-500': color === 'red',
    'bg-gradient-to-br from-green-500 to-emerald-500': color === 'green',
    'bg-gradient-to-br from-blue-500 to-cyan-500': color === 'blue',
    'bg-gradient-to-br from-yellow-400 to-amber-400': color === 'yellow',
    'bg-gradient-to-br from-gray-400 to-gray-500': !color || !['red', 'green', 'blue', 'yellow'].includes(color)
  };
});

const statusColorClass = computed(() => {
  const color = props.order?.status?.color;
  return {
    'bg-gradient-to-br from-red-500 to-rose-500': color === 'red',
    'bg-gradient-to-br from-green-500 to-emerald-500': color === 'green',
    'bg-gradient-to-br from-blue-500 to-cyan-500': color === 'blue',
    'bg-gradient-to-br from-yellow-400 to-amber-400': color === 'yellow',
    'bg-gradient-to-br from-gray-400 to-gray-500': !color || !['red', 'green', 'blue', 'yellow'].includes(color)
  };
});
</script>
