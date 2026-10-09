<template>
  <NuxtLink 
    :to="`/got/orders/${order.id}`"
    class="group block bg-white rounded-lg border border-gray-200/60 hover:shadow-md hover:border-gray-300 transition-all duration-200 p-5"
  >
    <!-- Header -->
    <div class="flex items-start justify-between mb-4">
      <div class="flex-1 min-w-0">
        <h3 class="text-base font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">
          <Icon 
            name="fa6-solid:flag" 
            class="text-xs mr-2" 
            :class="priorityIconClass"
          />
          #{{ order.token }}
        </h3>
        <p class="text-sm text-gray-500 mt-0.5">
          {{ order.type_name }}
        </p>
        <p v-if="order.reason_name" class="text-xs text-gray-400 mt-0.5">
          {{ order.reason_name }}
        </p>
      </div>
      <AtomsColorBadge 
        :value="order.status_name" 
        :color="order.status_color" 
        class="ml-2 flex-shrink-0" 
      />
    </div>

    <!-- Details -->
    <div class="space-y-2.5 text-sm">
      <!-- Due Date -->
      <div v-if="order.dueDateAt" class="flex items-center gap-2">
        <Icon name="fa6-solid:calendar" class="text-gray-400 flex-shrink-0 text-xs" />
        <span class="text-gray-600 text-sm">
          {{ formatDate(order.dueDateAt) }}
        </span>
      </div>

      <!-- Address/Location -->
      <div class="flex items-start gap-2">
        <Icon name="fa6-solid:location-dot" class="text-gray-400 mt-0.5 flex-shrink-0 text-xs" />
        <span class="text-gray-600 line-clamp-2 text-sm">
          {{ order.address || order.supply_point?.address_complete || "-" }}
        </span>
      </div>

      <!-- Completion Date -->
      <div v-if="order.completed_at" class="flex items-center gap-2 pt-2 border-t border-gray-100">
        <Icon name="fa6-solid:circle-check" class="text-green-600 flex-shrink-0 text-xs" />
        <span class="text-green-600 text-xs font-medium">
          {{ $t('common.completed') }}: {{ formatDate(order.completed_at) }}
        </span>
      </div>
    </div>
  </NuxtLink>
</template>

<script setup>
import { computed } from 'vue';
import { formatDate } from '~/utils/date';

const props = defineProps({
  order: {
    type: Object,
    required: true
  }
});

const priorityIconClass = computed(() => {
  const color = props.order?.priority?.color;
  return {
    'text-red-500': color === 'red',
    'text-green-500': color === 'green',
    'text-blue-500': color === 'blue',
    'text-yellow-500': color === 'yellow',
    'text-gray-400': !color || !['red', 'green', 'blue', 'yellow'].includes(color)
  };
});
</script>
