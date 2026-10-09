<template>
  <div v-if="completedAt">
    <div class="flex items-center gap-2 mb-3">
      <Icon name="fa6-solid:circle-check" class="text-green-600 text-sm" />
      <h3 class="text-sm font-semibold text-gray-900">{{ $t('GOT.completed_at') }}</h3>
    </div>
    <div class="space-y-0.5">
      <p class="text-sm text-green-600 font-medium">
        {{ new Date(completedAt).toLocaleString() }}
      </p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  completedAt: {
    type: String,
    default: null
  }
});
</script>
