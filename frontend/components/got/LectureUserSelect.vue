<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';

const props = defineProps({
  modelValue: {
    type: [Number, String, null],
    default: null
  },
  lectureUsers: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  placeholder: {
    type: String,
    default: ''
  },
  showAll: false
});

const emit = defineEmits(['update:modelValue', 'change']);

const isOpen = ref(false);
const searchQuery = ref('');
const dropdownRef = ref(null);
const inputRef = ref(null);

const selectedUser = computed(() => {
  if (props.modelValue === 'unassigned') {
    return { id: 'unassigned', full_name: 'Sin asignar', is_unassigned: true };
  }
  if (props.modelValue === null || props.modelValue === 'all') {
    return null;
  }
  return props.lectureUsers.find(u => u.id === props.modelValue) || null;
});

const filteredUsers = computed(() => {
  const query = searchQuery.value.toLowerCase().trim();
  
  let users = props.lectureUsers.filter(user => {
    if (!query) return true;
    return (
      user.full_name?.toLowerCase().includes(query) ||
      user.username?.toLowerCase().includes(query) ||
      user.operator_token?.toLowerCase().includes(query)
    );
  });

  // Sort to show current user first
  users.sort((a, b) => {
    if (a.is_current_user && !b.is_current_user) return -1;
    if (!a.is_current_user && b.is_current_user) return 1;
    return 0;
  });

  return users;
});

const selectUser = (user) => {
  emit('update:modelValue', user?.id || null);
  emit('change', user);
  isOpen.value = false;
  searchQuery.value = '';
};

const selectUnassigned = () => {
  emit('update:modelValue', 'unassigned');
  emit('change', { id: 'unassigned', is_unassigned: true });
  isOpen.value = false;
  searchQuery.value = '';
};

const clearSelection = () => {
  emit('update:modelValue', null);
  emit('change', null);
  searchQuery.value = '';
};

const toggleDropdown = () => {
  isOpen.value = !isOpen.value;
  if (isOpen.value) {
    setTimeout(() => {
      inputRef.value?.focus();
    }, 50);
  }
};

// Close dropdown when clicking outside
const handleClickOutside = (event) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target)) {
    isOpen.value = false;
    searchQuery.value = '';
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <div ref="dropdownRef" class="relative">
    <!-- Trigger Button -->
    <button
      type="button"
      @click="toggleDropdown"
      class="w-full flex items-center gap-2 px-3 py-2 bg-white border border-gray-200/60 rounded-lg hover:bg-gray-50 transition-all duration-150 text-left"
      :class="{ 'ring-2 ring-blue-500/20 border-blue-500': isOpen }"
    >
      <Icon name="fa6-solid:user" class="text-gray-400 text-sm flex-shrink-0" />
      
      <span v-if="selectedUser" class="flex-1 truncate text-sm font-medium text-gray-900">
        <span v-if="selectedUser.is_current_user" class="text-blue-600">{{ $t('GOT.me') }} · </span>
        {{ selectedUser.full_name }}
      </span>
      <span v-else class="flex-1 truncate text-sm text-gray-500">
        {{ placeholder || $t('GOT.filter_by_operator') }}
      </span>

      <div class="flex items-center gap-1 flex-shrink-0">
        <button
          v-if="selectedUser"
          type="button"
          @click.stop="clearSelection"
          class="p-1 hover:bg-gray-200 rounded transition-colors"
        >
          <Icon name="fa6-solid:xmark" class="text-gray-400 text-xs" />
        </button>
        <Icon 
          name="fa6-solid:chevron-down" 
          class="text-gray-400 text-xs transition-transform duration-200"
          :class="{ 'rotate-180': isOpen }"
        />
      </div>
    </button>

    <!-- Dropdown -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 scale-95 -translate-y-2"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-2"
    >
      <div
        v-if="isOpen"
        class="absolute z-50 mt-1 w-full min-w-[280px] bg-white border border-gray-200/60 rounded-lg shadow-lg overflow-hidden"
      >
        <!-- Search Input -->
        <div class="p-2 border-b border-gray-100">
          <div class="relative">
            <Icon name="fa6-solid:magnifying-glass" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm" />
            <input
              ref="inputRef"
              v-model="searchQuery"
              type="text"
              :placeholder="$t('GOT.search_operator')"
              class="w-full pl-9 pr-3 py-2 bg-gray-50 border-0 rounded-md text-sm focus:ring-2 focus:ring-blue-500/20 focus:bg-white transition-all"
            />
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="loading" class="px-3 py-8 text-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-gray-400 text-xl" />
        </div>

        <!-- Options List -->
        <div v-else class="max-h-[280px] overflow-y-auto">
          <!-- All Orders Option -->
          <button
            type="button"
            @click="selectUser(null)"
            class="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 transition-colors text-left"
            :class="{ 'bg-blue-50': !selectedUser }"
          >
            <div class="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
              <Icon name="fa6-solid:users" class="text-gray-500 text-sm" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-900">{{ props.showAll ? $t('GOT.all_orders') :  $t('GOT.my_assigned_orders') }}</p>
              <p class="text-xs text-gray-500">{{ props.showAll ? $t('GOT.show_all_orders') :  $t('GOT.show_my_orders') }}</p>
            </div>
            <Icon v-if="!selectedUser" name="fa6-solid:check" class="text-blue-600 text-sm flex-shrink-0" />
          </button>

          <!-- Unassigned Option -->
          <button
            type="button"
            @click="selectUnassigned"
            class="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 transition-colors text-left border-b border-gray-100"
            :class="{ 'bg-blue-50': selectedUser?.is_unassigned }"
          >
            <div class="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center flex-shrink-0">
              <Icon name="fa6-solid:user-slash" class="text-orange-600 text-sm" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-900">{{ $t('GOT.unassigned_orders') }}</p>
              <p class="text-xs text-gray-500">{{ $t('GOT.orders_without_operator') }}</p>
            </div>
            <Icon v-if="selectedUser?.is_unassigned" name="fa6-solid:check" class="text-blue-600 text-sm flex-shrink-0" />
          </button>

          <!-- Lecture Users -->
          <div v-if="filteredUsers.length > 0" class="py-1">
            <p class="px-3 py-1.5 text-xs font-medium text-gray-500 uppercase tracking-wide">
              {{ $t('GOT.operators') }}
            </p>
            <button
              v-for="user in filteredUsers"
              :key="user.id"
              type="button"
              @click="selectUser(user)"
              class="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 transition-colors text-left"
              :class="{ 'bg-blue-50': selectedUser?.id === user.id }"
            >
              <div 
                class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                :class="user.is_current_user ? 'bg-blue-100' : 'bg-gray-100'"
              >
                <Icon 
                  name="fa6-solid:user" 
                  class="text-sm"
                  :class="user.is_current_user ? 'text-blue-600' : 'text-gray-500'"
                />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <p class="text-sm font-medium text-gray-900 truncate">{{ user.full_name }}</p>
                  <span 
                    v-if="user.is_current_user" 
                    class="px-1.5 py-0.5 text-[10px] font-medium bg-blue-100 text-blue-700 rounded"
                  >
                    {{ $t('GOT.you') }}
                  </span>
                </div>
                <p class="text-xs text-gray-500 truncate">{{ user.operator_token }} · @{{ user.username }}</p>
              </div>
              <Icon v-if="selectedUser?.id === user.id" name="fa6-solid:check" class="text-blue-600 text-sm flex-shrink-0" />
            </button>
          </div>

          <!-- No Results -->
          <div v-else-if="searchQuery" class="px-3 py-8 text-center">
            <Icon name="fa6-solid:user-slash" class="text-gray-300 text-2xl mb-2" />
            <p class="text-sm text-gray-500">{{ $t('GOT.no_operators_found') }}</p>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Custom scrollbar */
.max-h-\[280px\]::-webkit-scrollbar {
  width: 6px;
}
.max-h-\[280px\]::-webkit-scrollbar-track {
  background: transparent;
}
.max-h-\[280px\]::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}
.max-h-\[280px\]::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
