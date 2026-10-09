<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="show"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        @click.self="$emit('close')"
      >
        <div class="bg-white rounded-lg p-6 max-w-md w-full shadow-2xl">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center flex-shrink-0">
              <Icon name="fa6-solid:circle-check" class="text-green-600 text-lg" />
            </div>
            <h3 class="text-lg font-semibold text-gray-900">{{ $t('GOT.finalize_order') }}</h3>
          </div>
          <p class="text-gray-600 mb-6 text-sm">{{ $t('GOT.confirm_finalize') }}</p>
          
          <div class="flex gap-3">
            <button
              @click="$emit('close')"
              :disabled="loading"
              class="flex-1 px-4 py-2 border border-gray-200/60 rounded-md hover:bg-gray-50 font-medium text-sm transition-all duration-150 disabled:opacity-50"
            >
              {{ $t('common.cancel') }}
            </button>
            <button
              @click="$emit('confirm')"
              :disabled="loading"
              class="flex-1 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 font-medium text-sm transition-all duration-150"
            >
              <span v-if="!loading">{{ $t('common.confirm') }}</span>
              <span v-else class="flex items-center justify-center gap-2">
                <Icon name="fa6-solid:spinner" class="animate-spin" />
              </span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
defineProps({
  show: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
});

defineEmits(['close', 'confirm']);
</script>
