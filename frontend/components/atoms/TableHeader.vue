<template>
  <span 
    class="p-1 flex items-center gap-1 min-w-0" 
    @click="handleSort"
    :class="{'cursor-pointer': sortable, 'cursor-default text-slate-400': !sortable, 'text-black': isActive, 'text-slate-400': !isActive }">
    <span class="truncate">{{ label }}</span>
    <Icon
      v-if="sortable"
      :name="icon"
      :class="{'text-black': isActive, 'text-slate-400': !isActive}"
      class="shrink-0"
    />
  </span>
</template>

<script setup>
  import { computed } from 'vue';

  const props = defineProps({
    label: {
        type: String,
        required: true
    },
    sortKey: {
        type: String,
        default: ''
    },
    currentSortBy: {
        type: String,
        default: ''
    },
    sortDesc: {
        type: Boolean,
        default: false
    },
    sortable: {
        type: Boolean,
        default: true
    }
  });

  const emit = defineEmits(['sort']);

  const isActive = computed(() => props.sortKey === props.currentSortBy);
  const icon = computed(() => {
    if (props.sortKey !== props.currentSortBy) {
        return 'fa6-solid:sort';
    }
    return props.sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down';
  });

  const handleSort = () => {
    emit('sort', props.sortKey);
  };
</script>
  