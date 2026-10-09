<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <Icon name="fa6-solid:users" class="text-gray-900 text-sm" />
        <h3 class="text-sm font-semibold text-gray-900">{{ $t('GOT.operators') }}</h3>
      </div>
      
      <!-- Edit button (only if editable and not completed) -->
      <button
        v-if="editable"
        @click="$emit('edit')"
        class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-all"
      >
        <Icon name="fa6-solid:pen" class="text-[10px]" />
        {{ $t('GOT.edit') }}
      </button>
    </div>

    <!-- Empty state with assign to me button -->
    <div v-if="!operators || operators.length === 0" class="space-y-3">
      <p class="text-sm text-gray-500 italic">{{ $t('GOT.no_operators_assigned') }}</p>
      
      <!-- Quick assign to me button -->
      <button
        v-if="editable"
        @click="$emit('assign-to-me')"
        :disabled="assigningToMe"
        class="inline-flex items-center gap-2 px-3 py-2 bg-blue-50 text-blue-700 border border-blue-200/60 rounded-lg hover:bg-blue-100 transition-all text-sm font-medium"
      >
        <Icon 
          :name="assigningToMe ? 'fa6-solid:spinner' : 'fa6-solid:hand-pointer'" 
          :class="{ 'animate-spin': assigningToMe }"
          class="text-sm"
        />
        {{ $t('GOT.assign_to_me') }}
      </button>
    </div>

    <!-- Operators list -->
    <div v-else class="space-y-2">
      <div class="flex flex-wrap gap-2">
        <span 
          v-for="operator in operators" 
          :key="operator.id"
          class="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium border border-blue-200/60"
        >
          <div class="w-5 h-5 rounded-full bg-blue-200 flex items-center justify-center flex-shrink-0">
            <Icon name="fa6-solid:user" class="text-[10px] text-blue-700" />
          </div>
          <span class="truncate max-w-[150px]">{{ operator.name }} {{ operator.surname }}</span>
        </span>
      </div>

      <!-- Quick assign to me button (if not already assigned) -->
      <button
        v-if="editable && !isCurrentUserAssigned"
        @click="$emit('assign-to-me')"
        :disabled="assigningToMe"
        class="inline-flex items-center gap-2 px-3 py-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-all text-xs font-medium"
      >
        <Icon 
          :name="assigningToMe ? 'fa6-solid:spinner' : 'fa6-solid:plus'" 
          :class="{ 'animate-spin': assigningToMe }"
          class="text-xs"
        />
        {{ $t('GOT.add_me_to_order') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  operators: {
    type: Array,
    default: () => []
  },
  editable: {
    type: Boolean,
    default: false
  },
  currentOperatorId: {
    type: [Number, String],
    default: null
  },
  assigningToMe: {
    type: Boolean,
    default: false
  }
});

defineEmits(['edit', 'assign-to-me']);

const isCurrentUserAssigned = computed(() => {
  if (!props.currentOperatorId || !props.operators) return false;
  return props.operators.some(op => op.id === props.currentOperatorId);
});
</script>
