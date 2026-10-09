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
      class="fixed bottom-20 right-4 sm:bottom-24 sm:right-6 lg:bottom-24 lg:right-8 inline-flex items-center justify-center gap-2.5 min-w-[56px] min-h-[56px] sm:min-w-0 sm:min-h-0 px-3 sm:px-5 py-3 bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-full hover:from-blue-700 hover:to-purple-700 active:scale-95 font-medium text-sm shadow-lg hover:shadow-xl transition-all duration-150 z-40 group"
    >
      <Icon name="fa6-solid:file-circle-plus" class="text-lg sm:text-lg group-hover:scale-110 transition-transform" />
      <span class="hidden sm:inline whitespace-nowrap">{{ $t('GOT.add_report') }}</span>
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
