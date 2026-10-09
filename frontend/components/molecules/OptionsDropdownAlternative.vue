<script setup>
import { ref, computed } from 'vue';
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
    default: 'gray-50'
  }
});

const isDropdownVisible = ref(false);
const startDropdownVisible = ref(false);

const positionClasses = computed(() => {
  return props.position === 'right' ? 'items-end right-0' : 'items-start left-0';
});

const toggleDropdown = () => {
  if (isDropdownVisible.value) {
    startDropdownVisible.value = false;
    setTimeout(() => {
      isDropdownVisible.value = false;
    }, 200);
  } else {
    isDropdownVisible.value = true;
    startDropdownVisible.value = true;
  }
};

const handleClickOutside = (event) => {
  startDropdownVisible.value = false;
  setTimeout(() => {
    isDropdownVisible.value = false;
  }, 200);
};
</script>

<template>
  <div :class="['absolute top-0 flex flex-col z-20', positionClasses]">
    <button :id="'dropdown' + id + 'Button'" :data-dropdown-toggle="'dropdown' + id" type="button"
      @click="toggleDropdown" @blur="handleClickOutside"
      class="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-700 bg-white rounded-lg hover:bg-gray-50 focus:ring-1 focus:ring-blue-200 focus:outline-none border border-gray-200 shadow-sm transition-all duration-200 ease-in-out hover:shadow-md">
      <span class="mr-2">{{ $t('common.options') }}</span>
      <svg class="w-4 h-4 transition-transform duration-200 ease-in-out" :class="{ 'rotate-90': isDropdownVisible }"
        aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 16 3">
        <path
          d="M2 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm6.041 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM14 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z" />
      </svg>
    </button>
    <div ref="dropdownMenu" :id="'dropdown' + id"
      class="mt-1 transition-all duration-200 ease-in-out transform origin-top" :class="{
        'opacity-100 scale-100': startDropdownVisible,
        'opacity-0 scale-95': !startDropdownVisible,
        'hidden': !isDropdownVisible,
        'z-10 bg-white rounded-lg shadow-lg border border-gray-200': true
      }">
      <ul class="py-1 text-sm text-gray-700" :aria-labelledby="'dropdown' + id + 'Button'">
        <slot>
          <li>
            <button
              class="block w-full text-left px-4 py-2 hover:bg-gray-50 transition-colors duration-150 ease-in-out">
              Option
            </button>
          </li>
        </slot>
      </ul>
    </div>
  </div>
</template>