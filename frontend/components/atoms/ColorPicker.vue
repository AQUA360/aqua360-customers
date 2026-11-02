<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue';
import { AppColors } from '~/utils/config';
const { $apiService } = useNuxtApp();

const props = defineProps({
  id: Number,
  entity: String,
  code: {
    type: String,
    default: 'gray'
  },
  // Camp del model que s'actualitza (color de fons o de text).
  property: {
    type: String,
    default: 'color'
  },
  colors: {
    type: Array,
    default: null
  },
  position: {
    type: String,
    default: 'left'
  }
});

const emit = defineEmits(['changed']);

const shownColor = ref(null)
const isDropdownVisible = ref(false);
const startDropdownVisible = ref(false);
const triggerRef = ref(null);
const dropdownPosition = ref({ top: 0, left: 0 });
const dropdownWidth = 168;

const palette = computed(() => props.colors || AppColors);

const positionClasses = computed(() => {
  return props.position === 'right' ? 'items-end right-0' : 'items-start left-0';
});

const resolveShownColor = (code) => {
  const color = palette.value.find(c => c.code === code);
  shownColor.value = color ? color.class : 'badge-gray';
};

const updateDropdownPosition = () => {
  if (triggerRef.value) {
    const rect = triggerRef.value.getBoundingClientRect();
    dropdownPosition.value = {
      top: rect.bottom + 4,
      left: props.position === 'right' ? rect.right - dropdownWidth : rect.left
    };
  }
};

const toggleDropdown = () => {
  if (isDropdownVisible.value === true) {
    startDropdownVisible.value = false;
    setTimeout(() => {
      isDropdownVisible.value = false;
    }, 200)
  }
  else {
    updateDropdownPosition();
    isDropdownVisible.value = true;
    startDropdownVisible.value = true;
  }
};

const dropdownMenuRef = ref(null);

const handleClickOutside = (event) => {
  if (!isDropdownVisible.value) return;
  const trigger = triggerRef.value;
  const menu = dropdownMenuRef.value;
  if (trigger && trigger.contains(event.target)) return;
  if (menu && menu.contains(event.target)) return;
  startDropdownVisible.value = false;
  setTimeout(() => {
    isDropdownVisible.value = false;
  }, 200);
};

const colorSelected = async (color) => {
  shownColor.value = color.class;
  startDropdownVisible.value = false;
  setTimeout(() => {
    isDropdownVisible.value = false;
  }, 200);
  try {
    await $apiService.updateValue(props.entity, props.property, props.id, color.code);
    emit('changed', { property: props.property, code: color.code });
  } catch (err) {
    console.error(err);
  }
};

watch(isDropdownVisible, (visible) => {
  if (visible) {
    nextTick(() => {
      document.addEventListener('click', handleClickOutside);
    });
  } else {
    document.removeEventListener('click', handleClickOutside);
  }
});

watch(() => [props.code, palette.value], () => {
  resolveShownColor(props.code);
}, { immediate: true });

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

</script>

<template>
  <div>
    <div class="relative" ref="triggerRef">
      <div :class="['absolute color-picker flex flex-col', positionClasses]">
        <button :id="'dropdown' + id + property + 'Button'" :data-dropdown-toggle="'dropdown' + id + property"
          type="button" @click="toggleDropdown"
          class="inline-flex items-center p-2 rounded-sm hover:opacity-80 focus:ring-4 focus:outline-none focus:ring-gray-50"
          :class="shownColor">
        </button>
      </div>
    </div>
    <Teleport to="body">
      <div v-show="isDropdownVisible" ref="dropdownMenuRef" :id="'dropdown' + id + property"
        class="fixed z-50 bg-white rounded shadow border border-gray-200 transition-all duration-100 p-2"
        :class="{ 'opacity-100': startDropdownVisible, 'opacity-0': !startDropdownVisible }"
        :style="{ top: dropdownPosition.top + 'px', left: dropdownPosition.left + 'px', width: dropdownWidth + 'px' }"
        @mousedown.prevent>
        <div class="grid grid-cols-6 gap-1.5">
          <button v-for="color in palette" :key="color.code" type="button" @click="colorSelected(color)"
            :class="color.class" :title="color.code"
            class="block w-5 h-5 rounded-sm flex-shrink-0 hover:ring-2 hover:ring-slate-300" />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style lang="css">
.color-picker {
  top: -7px;
}
</style>
