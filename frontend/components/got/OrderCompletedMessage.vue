<template>
  <div class="bg-green-50 border border-green-200/60 rounded-lg p-6 text-center">
    <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-100 mb-3">
      <Icon name="fa6-solid:circle-check" class="text-green-600 text-2xl" />
    </div>
    <p class="text-green-800 font-medium">{{ $t('GOT.order_completed') }}</p>
    
    <!-- Show observations history for completed orders -->
    <div v-if="observations && observations.length > 0" class="mt-6 bg-white rounded-lg border border-gray-200/60 overflow-hidden text-left">
      <GotObservationsList :observations="observations" :expanded="observationsExpanded" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

defineProps({
  observations: {
    type: Array,
    default: () => []
  }
});

const observationsExpanded = ref(false);
</script>
