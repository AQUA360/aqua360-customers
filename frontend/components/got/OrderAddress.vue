<template>
  <div v-if="address">
    <div class="flex items-center gap-2 mb-3">
      <Icon name="fa6-solid:location-dot" class="text-black text-sm" />
      <h3 class="text-sm font-semibold text-gray-900">{{ $t('GOT.address_info') }}</h3>
    </div>
    <div class="space-y-0.5">
      <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
        {{ $t('GOT.full_address') }}
      </label>
      <div class="flex items-start gap-2">
        <Icon name="fa6-solid:map" class="text-gray-400 text-xs mt-0.5 flex-shrink-0" />
        <p class="text-sm text-gray-900 leading-snug">
          {{ address.address_complete || "-" }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  address: {
    type: Object,
    default: null
  }
});
</script>
