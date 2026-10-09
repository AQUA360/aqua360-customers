<script setup>
import { ref, computed, onUnmounted } from 'vue';
const { $apiService } = useNuxtApp();

const props = defineProps({
  id: String,
  position: {
    type: String,
    default: 'right'
  },
  bg: {
    type: String,
    default: 'white'
  },
  bgHover: {
    type: String,
    default: 'gray-100'
  }
});

const isDropdownVisible = ref(false);
const startDropdownVisible = ref(false);
const dropdownWrapper = ref(null);

const positionClasses = computed(() => {
  return props.position === 'right' ? 'items-end right-0' : 'items-start left-0';
});

const closeDropdown = () => {
  startDropdownVisible.value = false;
  setTimeout(() => {
    isDropdownVisible.value = false;
  }, 200);
  removeClickOutsideListener();
};

let clickOutsideListener = null;

const addClickOutsideListener = () => {
  removeClickOutsideListener();
  clickOutsideListener = (event) => {
    if (!dropdownWrapper.value || dropdownWrapper.value.contains(event.target)) return;
    closeDropdown();
  };
  document.addEventListener('mousedown', clickOutsideListener);
};

const removeClickOutsideListener = () => {
  if (clickOutsideListener) {
    document.removeEventListener('mousedown', clickOutsideListener);
    clickOutsideListener = null;
  }
};

const toggleDropdown = () => {
  if (isDropdownVisible.value == true) {
    closeDropdown();
  }
  else {
    isDropdownVisible.value = true;
    startDropdownVisible.value = true;
    addClickOutsideListener();
  }
};

onUnmounted(() => {
  removeClickOutsideListener();
});

provide('closeOptionsDropdown', closeDropdown);
</script>


<template>
  <div ref="dropdownWrapper" :class="['absolute top-0 z-20 flex flex-col', positionClasses]">
    <button :id="'dropdown' + id + 'Button'" :data-dropdown-toggle="'dropdown' + id" type="button"
      @click="toggleDropdown"
      :class="'inline-flex items-center px-2 py-1 text-sm font-medium text-center text-gray-500 bg-'+props.bg+' rounded-lg hover:bg-'+props.bgHover+' focus:ring-4 focus:outline-none focus:ring-gray-50'">
      <svg class="w-4 h-4" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 3">
        <path
          d="M2 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm6.041 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM14 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z" />
      </svg>
    </button>
    <div ref="dropdownMenu" :id="'dropdown' + id" class="transition-all duration-200"
      :class="{ 'opacity-100' :startDropdownVisible,'hidden': !isDropdownVisible, 'z-10 opacity-0 bg-white rounded divide-y divide-gray-100 shadow border border-gray-200': true }">
      <ul class="py-1 text-sm text-gray-700 max-h-[70vh] overflow-y-auto options-dropdown-scroll" :aria-labelledby="'dropdown' + id + 'Button'">
        <slot>
          <li>
            <button class="block py-2 px-4 hover:bg-gray-100">Option</button>
          </li>
        </slot>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.options-dropdown-scroll::-webkit-scrollbar {
  width: 4px;
}

.options-dropdown-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.options-dropdown-scroll::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 2px;
}

.options-dropdown-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}
</style>