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

const positionClasses = computed(() => {
  return props.position === 'right' ? 'items-end right-0' : 'items-start left-0';
});

const updateDropdownPosition = () => {
  if (triggerRef.value) {
    const rect = triggerRef.value.getBoundingClientRect();
    dropdownPosition.value = {
      top: rect.bottom + 4,
      left: props.position === 'right' ? rect.right - 200 : rect.left
    };
  }
};

const toggleDropdown = () => {
  if (isDropdownVisible.value === true) {
    startDropdownVisible.value = false;
    setTimeout(()=> {
      isDropdownVisible.value = false;
    },200)
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
    await $apiService.updateValue(props.entity, 'color', props.id, color.code);
    emit('changed');
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

onMounted(() => {
  const color = AppColors.find(c => c.code === props.code);
  shownColor.value = color ? color.class : 'badge-gray'; // Default to gray if code not found
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

</script>

<template>
  <div>
    <div class="relative" ref="triggerRef">
      <div :class="['absolute color-picker flex flex-col', positionClasses]">
        <button :id="'dropdown' + id + 'Button'" :data-dropdown-toggle="'dropdown' + id" type="button"
          @click="toggleDropdown"
          class="inline-flex items-center p-2 rounded-sm hover:opacity-80 focus:ring-4 focus:outline-none focus:ring-gray-50"
          :class="shownColor">
        </button>
      </div>
    </div>
    <Teleport to="body">
      <div
        v-show="isDropdownVisible"
        ref="dropdownMenuRef"
        :id="'dropdown' + id"
        class="fixed z-50 bg-white rounded divide-y divide-gray-100 shadow border border-gray-200 transition-all duration-100 p-1"
        :class="{ 'opacity-100': startDropdownVisible, 'opacity-0': !startDropdownVisible }"
        :style="{ top: dropdownPosition.top + 'px', left: dropdownPosition.left + 'px' }"
        @mousedown.prevent
      >
        <ul class="list-none p-1">
          <li v-for="color in AppColors" :key="color.code">
            <button @click="colorSelected(color)" :class="color.class" class="block w-4 h-4 mb-1 rounded-sm flex-shrink-0">
            </button>
          </li>
        </ul>
      </div>
    </Teleport>
  </div>
</template>

<style lang="css">
  .color-picker {
    top: -7px;
  }
</style>