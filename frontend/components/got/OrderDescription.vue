<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
  description: {
    type: String,
    default: ''
  }
});

const { t } = useI18n();

const isExpanded = ref(false);
const isSticky = ref(false);
const descriptionRef = ref(null);

const calculateLength = (str) => {
  let length = 0;
  for (let i = 0; i < str.length; i++) {
    if (str[i]==='\n'){
      length += 50; // consider new lines as longer
    } else {
      length += 1;
    }
  }
  return length;
}

const truncate = (str, maxLength) => {
  if (calculateLength(str) <= maxLength) return str;
  let truncated = '';
  let length = 0;
  for (let i = 0; i < str.length; i++) {
    if (str[i]==='\n'){
      length += 50;
    } else {
      length += 1;
    }
    if (length > maxLength) break;
    truncated += str[i];
  }
  return truncated + '...';
};

const shouldTruncate = computed(() => {
  return props.description && calculateLength(props.description) > 100;
});

const displayText = computed(() => {
  if (!props.description) return '';
  if (isExpanded.value || !shouldTruncate.value) {
    return props.description;
  }
  return truncate(props.description, 100);
});

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value;
};

const handleScroll = () => {
  if (!descriptionRef.value) return;
  
  const rect = descriptionRef.value.getBoundingClientRect();
  // When the description reaches the top of the viewport
  isSticky.value = rect.top <= 0;
};

onMounted(() => {
  window.addEventListener('scroll', handleScroll);
});

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll);
});
</script>

<template>
  <div 
    v-if="description"
    ref="descriptionRef"
    class="sticky top-16 z-20 transition-all duration-300 ease-in-out bg-white border-b border-gray-200/60"
    :class="{
      'shadow-md': isSticky
    }"
  >
    <div 
      class="px-4 py-3"
      :class="{
        'bg-white': isSticky,
        'bg-gray-50/30': !isSticky
      }"
    >
      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <Icon name="fa6-solid:file-lines" class="text-gray-600 text-sm flex-shrink-0" />
            <h3 class="text-sm font-semibold text-gray-900">{{ t('order_block.description') }}</h3>
          </div>
          <button
            v-if="shouldTruncate"
            @click="toggleExpand"
            class="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 text-sky-600 hover:text-sky-700 hover:bg-sky-50 rounded-md text-xs font-medium transition-all duration-200"
          >
            <Icon 
              :name="isExpanded ? 'fa6-solid:chevron-up' : 'fa6-solid:chevron-down'" 
              class="text-[10px]"
            />
            <span>{{ isExpanded ? t('common.show_less') : t('common.show_more') }}</span>
          </button>
        </div>
        <p 
          class="text-sm text-gray-700 whitespace-pre-wrap break-words transition-all duration-300 w-full"
          :class="{
            'max-h-[200px] overflow-y-auto': isExpanded,
          }"
        >
          {{ displayText }}
        </p>
      </div>
    </div>
  </div>
</template>
