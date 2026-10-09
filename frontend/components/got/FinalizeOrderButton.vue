<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="opacity-0 translate-y-8 scale-90"
    enter-to-class="opacity-100 translate-y-0 scale-100"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="opacity-100 translate-y-0 scale-100"
    leave-to-class="opacity-0 translate-y-8 scale-90"
  >
    <button
      v-if="show"
      @click="$emit('click')"
      class="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 lg:bottom-8 lg:right-8 inline-flex items-center justify-center gap-2.5 min-w-[56px] min-h-[56px] sm:min-w-0 sm:min-h-0 px-3 sm:px-5 py-3 bg-green-600 text-white rounded-full hover:bg-green-700 active:bg-green-800 font-medium text-sm shadow-lg hover:shadow-xl active:scale-95 transition-all duration-150 z-50 group"
    >
      <Icon name="fa6-solid:circle-check" class="text-lg sm:text-lg group-hover:scale-110 transition-transform" />
      <span class="hidden sm:inline whitespace-nowrap">{{ $t('GOT.finalize_order') }}</span>
    </button>
  </Transition>
</template>

<script setup>
defineProps({
  show: {
    type: Boolean,
    default: false
  }
});

defineEmits(['click']);
</script>
