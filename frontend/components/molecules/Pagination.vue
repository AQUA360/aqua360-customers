<template>
  <div class="flex justify-between items-center p-1">
    <div class="font-semibold">
      <span v-if="pagination.isFiltered">{{ $t('common.total_filtered') }}: {{ pagination.total }}</span>
      <span v-else>{{ $t('common.total') }}: {{ pagination.total }}</span>
    </div>
    <div class="flex justify-between gap-3 items-center mt-2">
      <button @click="changePage(pagination.page - 1)" :disabled="pagination.page === 1"
        :class="{ 'hover:bg-slate-100 rounded text-sky-500': pagination.page !== 1, 'opacity-20': pagination.page === 1 }"
        class="px-2 py-1">
        <Icon name="fa6-solid:angle-left" class="" />
      </button>
      <button v-if="showFirstPageButton" @click="changePage(1)" :disabled="pagination.page === 1"
        :class="{ 'hover:bg-slate-100 rounded text-sky-500': pagination.page !== 1, 'opacity-50': pagination.page === 1 }"
        class="px-2 py-1">
        1
      </button>
      <div v-if="shouldShowLeftEllipsis" class="mx-2">...</div>
      <div class="flex gap-3">
        <button v-for="page in visiblePages" @click="changePage(page)"
          :class="{ 'font-bold': page === pagination.page, 'hover:bg-slate-100 rounded text-sky-500': page !== pagination.page }"
          class="px-2 py-1">
          {{ page }}
        </button>
      </div>
      <div v-if="shouldShowRightEllipsis" class="mx-2">...</div>
      <button v-if="showLastPageButton" @click="changePage(pagination.totalPages)"
        :disabled="pagination.page === pagination.totalPages"
        :class="{ 'hover:bg-slate-100 rounded text-sky-500': pagination.page !== pagination.totalPages, 'opacity-50': pagination.page === pagination.totalPages }"
        class="px-2 py-1">
        {{ pagination.totalPages }}
      </button>
      <button @click="changePage(pagination.page + 1)" :disabled="pagination.page === pagination.totalPages"
        :class="{ 'hover:bg-slate-100 rounded text-sky-500': pagination.page !== pagination.totalPages, 'opacity-20': pagination.page === pagination.totalPages }"
        class="px-2 py-1">
        <Icon name="fa6-solid:angle-right" class="" />
      </button>
    </div>
    <div>
      {{ $t('common.showing') }} {{ start }} {{ $t('common.to') }} {{ end }}
    </div>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue';

const props = defineProps({
  pagination: {
    type: Object,
    required: true,
    default: () => ({
      page: 1,
      perPage: 50,
      total: 0,
      totalPages: 0,
      previous: null,
      next: null,
      isFiltered: false
    })
  }
});

const emit = defineEmits(['update:page']);

const changePage = (newPage) => {
  emit('update:page', newPage);
};

const start = computed(() => {
  return (props.pagination.page - 1) * props.pagination.perPage + 1;
});

const end = computed(() => {
  return Math.min(props.pagination.page * props.pagination.perPage, props.pagination.total);
});

const visiblePages = computed(() => {
  const totalPages = props.pagination.totalPages;
  const currentPage = props.pagination.page;
  const pages = [];

  if (totalPages <= 5) {
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i);
    }
  } else {
    if (currentPage <= 3) {
      for (let i = 1; i <= 5; i++) {
        pages.push(i);
      }
    } else if (currentPage >= totalPages - 2) {
      for (let i = totalPages - 4; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      for (let i = currentPage - 2; i <= currentPage + 2; i++) {
        pages.push(i);
      }
    }
  }

  return pages;
});

const shouldShowLeftEllipsis = computed(() => {
  return props.pagination.totalPages > 5 && props.pagination.page > 3;
});

const shouldShowRightEllipsis = computed(() => {
  return props.pagination.totalPages > 5 && props.pagination.page < props.pagination.totalPages - 2;
});

const showFirstPageButton = computed(() => {
  return props.pagination.totalPages > 5 && !visiblePages.value.includes(1);
});

const showLastPageButton = computed(() => {
  return props.pagination.totalPages > 5 && !visiblePages.value.includes(props.pagination.totalPages);
});

watch(() => props.pagination, (newVal) => {
  // console.log("Pagination updated:", newVal);
}, { deep: true });
</script>
