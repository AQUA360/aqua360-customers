<script setup>
import { computed } from 'vue';

const props = defineProps({
  currentPage: {
    type: Number,
    default: 1
  },
  totalPages: {
    type: Number,
    default: 1
  },
  hasNext: {
    type: Boolean,
    default: false
  },
  hasPrevious: {
    type: Boolean,
    default: false
  },
  total: {
    type: Number,
    default: 0
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['page-change']);

// Generate page numbers to show
const visiblePages = computed(() => {
  const pages = [];
  const current = props.currentPage;
  const total = props.totalPages;
  
  if (total <= 5) {
    // Show all pages if 5 or less
    for (let i = 1; i <= total; i++) {
      pages.push(i);
    }
  } else {
    // Always show first page
    pages.push(1);
    
    if (current > 3) {
      pages.push('...');
    }
    
    // Show pages around current
    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    
    for (let i = start; i <= end; i++) {
      if (!pages.includes(i)) {
        pages.push(i);
      }
    }
    
    if (current < total - 2) {
      pages.push('...');
    }
    
    // Always show last page
    if (!pages.includes(total)) {
      pages.push(total);
    }
  }
  
  return pages;
});

const goToPage = (page) => {
  if (page === '...' || page === props.currentPage || props.loading) return;
  emit('page-change', page);
};

const goToPrevious = () => {
  if (props.hasPrevious && !props.loading) {
    emit('page-change', props.currentPage - 1);
  }
};

const goToNext = () => {
  if (props.hasNext && !props.loading) {
    emit('page-change', props.currentPage + 1);
  }
};
</script>

<template>
  <div v-if="totalPages > 1" class="flex flex-col sm:flex-row items-center justify-between gap-4 py-4">
    <!-- Mobile: Simple prev/next -->
    <div class="flex sm:hidden items-center justify-between w-full">
      <button
        @click="goToPrevious"
        :disabled="!hasPrevious || loading"
        class="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200/60 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-all text-sm font-medium"
      >
        <Icon name="fa6-solid:chevron-left" class="text-xs" />
        {{ $t('GOT.previous') }}
      </button>
      
      <span class="text-sm text-gray-600">
        {{ currentPage }} / {{ totalPages }}
      </span>
      
      <button
        @click="goToNext"
        :disabled="!hasNext || loading"
        class="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200/60 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-all text-sm font-medium"
      >
        {{ $t('GOT.next') }}
        <Icon name="fa6-solid:chevron-right" class="text-xs" />
      </button>
    </div>

    <!-- Desktop: Full pagination -->
    <div class="hidden sm:flex items-center gap-1">
      <!-- Previous Button -->
      <button
        @click="goToPrevious"
        :disabled="!hasPrevious || loading"
        class="p-2 rounded-lg border border-gray-200/60 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        <Icon name="fa6-solid:chevron-left" class="text-sm text-gray-600" />
      </button>

      <!-- Page Numbers -->
      <template v-for="page in visiblePages" :key="page">
        <span v-if="page === '...'" class="px-2 text-gray-400">...</span>
        <button
          v-else
          @click="goToPage(page)"
          :disabled="loading"
          class="min-w-[36px] h-9 px-3 rounded-lg text-sm font-medium transition-all"
          :class="page === currentPage 
            ? 'bg-gray-900 text-white' 
            : 'bg-white border border-gray-200/60 text-gray-700 hover:bg-gray-50'"
        >
          {{ page }}
        </button>
      </template>

      <!-- Next Button -->
      <button
        @click="goToNext"
        :disabled="!hasNext || loading"
        class="p-2 rounded-lg border border-gray-200/60 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        <Icon name="fa6-solid:chevron-right" class="text-sm text-gray-600" />
      </button>
    </div>

    <!-- Total count -->
    <div class="hidden sm:block text-sm text-gray-500">
      {{ $t('GOT.total_orders', { count: total }) }}
    </div>
  </div>
</template>
