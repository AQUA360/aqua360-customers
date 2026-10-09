<template>
  <div v-if="observations && observations.length > 0">
    <button
      @click="isExpanded = !isExpanded"
      class="w-full px-6 py-4 border-b border-gray-200/60 bg-gray-50/50 flex items-center justify-between hover:bg-gray-50 transition-colors"
    >
      <div class="flex items-center gap-2">
        <Icon name="fa6-solid:clock-rotate-left" class="text-gray-600 text-sm" />
        <h2 class="text-base font-semibold text-gray-900">{{ $t('GOT.observations_history') }}</h2>
        <span class="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
          {{ observations.length }}
        </span>
      </div>
      <Icon 
        name="fa6-solid:chevron-down" 
        class="text-gray-400 text-sm transition-transform duration-200"
        :class="{ 'rotate-180': isExpanded }"
      />
    </button>
    
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 max-h-0"
      enter-to-class="opacity-100 max-h-[600px]"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 max-h-[600px]"
      leave-to-class="opacity-0 max-h-0"
    >
      <div v-show="isExpanded" class="overflow-hidden">
        <div class="px-6 py-5 space-y-3 max-h-[500px] overflow-y-auto">
          <details
            v-for="(obs, index) in reversedObservations" 
            :key="obs.id"
            open
            class="group bg-gray-50/70 rounded-lg border border-gray-200/60 overflow-hidden"
          >
            <summary class="px-4 py-3 cursor-pointer list-none flex items-center justify-between hover:bg-gray-100/70 transition-colors">
              <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                  <span class="text-xs font-medium text-gray-600">
                    {{ observations.length - index }}
                  </span>
                </div>
                <div class="flex items-center gap-2 min-w-0">
                  <Icon name="fa6-solid:clock" class="text-gray-400 text-xs flex-shrink-0" />
                  <span class="text-xs text-gray-500 truncate">
                    {{ new Date(obs.created_at).toLocaleString() }}
                  </span>
                </div>
                <span v-if="obs.has_user" class="text-xs text-blue-600 font-medium truncate ml-auto">
                  Admin
                </span>
              </div>
              <Icon 
                name="fa6-solid:chevron-down" 
                class="text-gray-400 text-xs ml-2 flex-shrink-0 transition-transform duration-200 group-open:rotate-180"
              />
            </summary>
            <div class="px-4 pb-3 pt-1">
              <div v-if="obs.has_user" class="flex items-center gap-1.5 mb-2">
                <Icon name="fa6-solid:shield-halved" class="text-blue-500 text-xs" />
                <span class="text-xs font-semibold text-blue-600">Admin:</span>
              </div>
              <p class="text-sm text-gray-700 leading-relaxed">
                {{ obs.observation || $t('common.no_observation') }}
              </p>
            </div>
          </details>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  observations: {
    type: Array,
    default: () => []
  },
  expanded: {
    type: Boolean,
    default: false
  }
});

const isExpanded = ref(props.expanded);

const reversedObservations = computed(() => {
  return props.observations.slice().reverse();
});
</script>
