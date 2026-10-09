<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  orderId: {
    type: [Number, String],
    required: true
  },
  currentOperators: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['close', 'updated']);

const { t } = useI18n();
const { $gotApi } = useNuxtApp();
const toast = useToast();

const searchQuery = ref('');
const lectureUsers = ref([]);
const selectedUserIds = ref([]);
const loading = ref(false);
const saving = ref(false);
const assigningToMe = ref(false);

// Get current user
const currentUser = computed(() => {
  return lectureUsers.value.find(u => u.is_current_user);
});

// Check if current user is assigned
const isCurrentUserAssigned = computed(() => {
  if (!currentUser.value) return false;
  return selectedUserIds.value.includes(currentUser.value.id);
});

// Filter users based on search
const filteredUsers = computed(() => {
  const query = searchQuery.value.toLowerCase().trim();
  
  let users = lectureUsers.value.filter(user => {
    if (!query) return true;
    return (
      user.full_name?.toLowerCase().includes(query) ||
      user.username?.toLowerCase().includes(query) ||
      user.operator_token?.toLowerCase().includes(query)
    );
  });

  // Sort: selected first, then current user, then alphabetically
  users.sort((a, b) => {
    const aSelected = selectedUserIds.value.includes(a.id);
    const bSelected = selectedUserIds.value.includes(b.id);
    
    if (aSelected && !bSelected) return -1;
    if (!aSelected && bSelected) return 1;
    if (a.is_current_user && !b.is_current_user) return -1;
    if (!a.is_current_user && b.is_current_user) return 1;
    return a.full_name.localeCompare(b.full_name);
  });

  return users;
});

// Load lecture users
const loadLectureUsers = async () => {
  loading.value = true;
  try {
    const response = await $gotApi.getLectureUsers();
    if (response.success) {
      lectureUsers.value = response.lecture_users;
    }
  } catch (error) {
    console.error('Error loading lecture users:', error);
  } finally {
    loading.value = false;
  }
};

// Initialize selected users from current operators
const initializeSelection = () => {
  // Map current operators to lecture user IDs
  selectedUserIds.value = props.currentOperators
    .map(op => {
      const user = lectureUsers.value.find(u => u.operator_id === op.id || u.operator_token === op.token);
      return user?.id;
    })
    .filter(id => id !== undefined);
};

// Toggle user selection
const toggleUser = (userId) => {
  const index = selectedUserIds.value.indexOf(userId);
  if (index === -1) {
    selectedUserIds.value.push(userId);
  } else {
    selectedUserIds.value.splice(index, 1);
  }
};

// Quick assign to me
const assignToMe = async () => {
  if (!currentUser.value) return;
  
  assigningToMe.value = true;
  try {
    const response = await $gotApi.assignLectureUser(props.orderId, 'assign');
    if (response.success) {
      toast.success(t('GOT.assigned_to_me_success'));
      emit('updated', response.assigned_operators);
      emit('close');
    }
  } catch (error) {
    toast.error(t('GOT.assign_error'));
  } finally {
    assigningToMe.value = false;
  }
};

// Remove from me
const removeFromMe = async () => {
  if (!currentUser.value) return;
  
  assigningToMe.value = true;
  try {
    const response = await $gotApi.assignLectureUser(props.orderId, 'deassign');
    if (response.success) {
      toast.success(t('GOT.removed_from_me_success'));
      emit('updated', response.assigned_operators);
      emit('close');
    }
  } catch (error) {
    toast.error(t('GOT.assign_error'));
  } finally {
    assigningToMe.value = false;
  }
};

// Save changes
const saveChanges = async () => {
  saving.value = true;
  try {
    const response = await $gotApi.assignLectureUser(
      props.orderId, 
      'set', 
      null, 
      selectedUserIds.value
    );
    if (response.success) {
      toast.success(t('GOT.operators_updated'));
      emit('updated', response.assigned_operators);
      emit('close');
    }
  } catch (error) {
    toast.error(t('GOT.assign_error'));
  } finally {
    saving.value = false;
  }
};

// Watch for modal open
watch(() => props.show, async (newVal) => {
  if (newVal) {
    searchQuery.value = '';
    await loadLectureUsers();
    initializeSelection();
  }
});

// Get initials for avatar
const getInitials = (name) => {
  if (!name) return '?';
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
};

// Get color for avatar based on name
const getAvatarColor = (name) => {
  const colors = [
    'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-pink-500',
    'bg-indigo-500', 'bg-teal-500', 'bg-orange-500', 'bg-cyan-500'
  ];
  const index = name ? name.charCodeAt(0) % colors.length : 0;
  return colors[index];
};
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="show"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center z-50 p-0 sm:p-4"
        @click.self="$emit('close')"
      >
        <Transition
          enter-active-class="transition-all duration-300 ease-out"
          enter-from-class="opacity-0 translate-y-full sm:translate-y-0 sm:scale-95"
          enter-to-class="opacity-100 translate-y-0 sm:scale-100"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 translate-y-0 sm:scale-100"
          leave-to-class="opacity-0 translate-y-full sm:translate-y-0 sm:scale-95"
        >
          <div 
            v-if="show"
            class="bg-white w-full sm:max-w-md sm:rounded-xl rounded-t-2xl shadow-2xl max-h-[85vh] sm:max-h-[600px] flex flex-col overflow-hidden"
          >
            <!-- Header -->
            <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-gray-900 flex items-center justify-center">
                  <Icon name="fa6-solid:user-plus" class="text-white text-sm" />
                </div>
                <div>
                  <h2 class="text-base font-semibold text-gray-900">{{ $t('GOT.assign_operators') }}</h2>
                  <p class="text-xs text-gray-500">{{ $t('GOT.select_operators_for_order') }}</p>
                </div>
              </div>
              <button
                @click="$emit('close')"
                class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <Icon name="fa6-solid:xmark" class="text-gray-500" />
              </button>
            </div>

            <!-- Quick Actions -->
            <div class="px-4 py-3 border-b border-gray-100 flex-shrink-0">
              <button
                v-if="!isCurrentUserAssigned"
                @click="assignToMe"
                :disabled="assigningToMe || !currentUser"
                class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 transition-all font-medium text-sm"
              >
                <Icon 
                  :name="assigningToMe ? 'fa6-solid:spinner' : 'fa6-solid:hand-pointer'" 
                  :class="{ 'animate-spin': assigningToMe }"
                />
                {{ $t('GOT.assign_to_me') }}
              </button>
              <button
                v-else
                @click="removeFromMe"
                :disabled="assigningToMe"
                class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 disabled:opacity-50 transition-all font-medium text-sm"
              >
                <Icon 
                  :name="assigningToMe ? 'fa6-solid:spinner' : 'fa6-solid:user-minus'" 
                  :class="{ 'animate-spin': assigningToMe }"
                />
                {{ $t('GOT.remove_from_me') }}
              </button>
            </div>

            <!-- Search -->
            <div class="px-4 py-3 border-b border-gray-100 flex-shrink-0">
              <div class="relative">
                <Icon name="fa6-solid:magnifying-glass" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm" />
                <input
                  v-model="searchQuery"
                  type="text"
                  :placeholder="$t('GOT.search_operator')"
                  class="w-full pl-10 pr-4 py-2.5 bg-gray-50 border-0 rounded-lg text-sm focus:ring-2 focus:ring-blue-500/20 focus:bg-white transition-all"
                />
              </div>
            </div>

            <!-- Selected Users Pills -->
            <div v-if="selectedUserIds.length > 0" class="px-4 py-2 border-b border-gray-100 flex-shrink-0">
              <div class="flex flex-wrap gap-1.5">
                <span
                  v-for="userId in selectedUserIds"
                  :key="userId"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-medium"
                >
                  {{ lectureUsers.find(u => u.id === userId)?.full_name || 'Unknown' }}
                  <button
                    @click="toggleUser(userId)"
                    class="p-0.5 hover:bg-blue-100 rounded-full transition-colors"
                  >
                    <Icon name="fa6-solid:xmark" class="text-xs" />
                  </button>
                </span>
              </div>
            </div>

            <!-- Loading -->
            <div v-if="loading" class="flex-1 flex items-center justify-center py-12">
              <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-gray-300" />
            </div>

            <!-- Users List -->
            <div v-else class="flex-1 overflow-y-auto">
              <div v-if="filteredUsers.length === 0" class="py-12 text-center">
                <Icon name="fa6-solid:user-slash" class="text-3xl text-gray-300 mb-2" />
                <p class="text-sm text-gray-500">{{ $t('GOT.no_operators_found') }}</p>
              </div>

              <div v-else class="py-2">
                <button
                  v-for="user in filteredUsers"
                  :key="user.id"
                  @click="toggleUser(user.id)"
                  class="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors"
                  :class="{ 'bg-blue-50/50': selectedUserIds.includes(user.id) }"
                >
                  <!-- Avatar -->
                  <div 
                    class="w-10 h-10 rounded-full flex items-center justify-center text-white font-medium text-sm flex-shrink-0"
                    :class="getAvatarColor(user.full_name)"
                  >
                    {{ getInitials(user.full_name) }}
                  </div>

                  <!-- User Info -->
                  <div class="flex-1 min-w-0 text-left">
                    <div class="flex items-center gap-2">
                      <p class="text-sm font-medium text-gray-900 truncate">{{ user.full_name }}</p>
                      <span 
                        v-if="user.is_current_user" 
                        class="px-1.5 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 rounded"
                      >
                        {{ $t('GOT.you') }}
                      </span>
                    </div>
                    <p class="text-xs text-gray-500 truncate">
                      {{ user.operator_token }} · @{{ user.username }}
                    </p>
                  </div>

                  <!-- Checkbox -->
                  <div 
                    class="w-5 h-5 rounded border-2 flex items-center justify-center transition-all flex-shrink-0"
                    :class="selectedUserIds.includes(user.id) 
                      ? 'bg-blue-600 border-blue-600' 
                      : 'border-gray-300 hover:border-gray-400'"
                  >
                    <Icon 
                      v-if="selectedUserIds.includes(user.id)" 
                      name="fa6-solid:check" 
                      class="text-white text-xs" 
                    />
                  </div>
                </button>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-4 py-3 border-t border-gray-100 flex gap-3 flex-shrink-0 bg-gray-50/50">
              <button
                @click="$emit('close')"
                class="flex-1 px-4 py-2.5 border border-gray-200 rounded-lg hover:bg-gray-100 font-medium text-sm transition-colors"
              >
                {{ $t('common.cancel') }}
              </button>
              <button
                @click="saveChanges"
                :disabled="saving"
                class="flex-1 px-4 py-2.5 bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:bg-gray-400 font-medium text-sm transition-colors flex items-center justify-center gap-2"
              >
                <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin" />
                <span v-if="!saving">{{ $t('common.save') }}</span>
                <span v-else>{{ $t('common.saving') }}</span>
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Smooth scrollbar */
.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}
.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}
.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
