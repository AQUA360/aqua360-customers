<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import toast from '~/plugins/npm/toast';
import { formatDate } from '~/utils/date';
import AppLoading from '~/components/atoms/AppLoading.vue';

definePageMeta({
  layout: 'got',
  title: 'My Orders',
});

const { t } = useI18n();
const { $gotApi } = useNuxtApp();

const orders = ref([]);
const loading = ref(true);

// Pagination state
const currentPage = useState('got_summary_page', () => 1);
const totalPages = ref(1);
const hasNext = ref(false);
const hasPrevious = ref(false);
const totalOrders = ref(0);
const perPage = 15;

// Lecture users for filtering
const lectureUsers = ref([]);
const selectedLectureUser = useState('got_summary_operator', () => null); // null = my orders, 'unassigned' = unassigned, number = specific user
const loadingUsers = ref(false);

const loadingExploitations = ref(false);
const exploitations = ref([]);
const selectedExploitation = useState('got_summary_exploitation', () => null);

const showPending = useState('got_summary_show_pending', () => true);
const showCompleted = useState('got_summary_show_completed', () => false);
const totalCompletedOrders = ref(0);
const totalPendingOrders = ref(0);

const loadingDoc = ref(false);
const docTaskId = ref(null);

// Load lecture users for filter dropdown
const loadLectureUsers = async () => {
  loadingUsers.value = true;
  try {
    const response = await $gotApi.getLectureUsers();
    if (response.success) {
      lectureUsers.value = response.lecture_users;
    }
  } catch (error) {
    console.error('Error loading lecture users:', error);
  } finally {
    loadingUsers.value = false;
  }
};

const loadOrders = async (page = 1) => {
  try {
    loading.value = true;
    
    // Build filters
    const filters = {};
    if (selectedLectureUser.value === 'unassigned') {
      filters.unassigned = true;
    } else if (selectedLectureUser.value !== null) {
      filters.lectureUserId = selectedLectureUser.value;
    }
    filters.exploitationId = selectedExploitation.value;
    filters.showPending = showPending.value;
    filters.showCompleted = showCompleted.value;
    // If null, API returns current user's orders by default
    
    const response = await $gotApi.getOrdersList(page, perPage, filters);
    
    if (response.success) {
      totalCompletedOrders.value = response.total_completed_orders;
      totalPendingOrders.value = response.total_pending_orders;
      orders.value = response.orders;
      console.log(orders.value);
      currentPage.value = response.page;
      totalPages.value = response.total_pages;
      hasNext.value = response.has_next;
      hasPrevious.value = response.has_previous;
      totalOrders.value = response.total;
    }
  } catch (error) {
    // toast.error('Error loading orders:', error);
    console.log(error);
  } finally {
    loading.value = false;
  }
};

const getDoc = async () => {
  try {
    loadingDoc.value = true;
    // Build filters
    const filters = {};
    if (selectedLectureUser.value === 'unassigned') {
      filters.unassigned = true;
    } else if (selectedLectureUser.value !== null) {
      filters.lectureUserId = selectedLectureUser.value;
    }
    filters.exploitationId = selectedExploitation.value;
    filters.showPending = showPending.value;
    filters.showCompleted = showCompleted.value;
    const response = await $gotApi.getDoc(filters);
    
    //get date of today as ddmmYYYYHHMMSS
    let right_now = new Date().toLocaleDateString('ca-ES', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    if (response) {
      let response_buffer = await response.arrayBuffer();
      downloadFile(response_buffer, `${right_now}.xlsx`);
    }
  } catch (error) {
    // toast.error('Error loading orders:', error);
    console.log(error);
  } finally {
    loadingDoc.value = false;
  }
};

const downloadFile = (buffer, fileName) => {
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
}

const loadExploitations = async () => {
  loadingExploitations.value = true;
  try {
    const response = await $gotApi.getExploitations();
    exploitations.value = response.exploitations;
    
  } catch (error) {
    console.error('Error loading exploitations:', error);
  } finally {
    loadingExploitations.value = false;
  }
};

// Handle filter change
const handleLectureUserChange = (user) => {
  currentPage.value = 1; // Reset to first page
  loadOrders(1);
};

const handleExploitationChange = (exploitationId) => {
  selectedExploitation.value = exploitationId;
  loadOrders(1);
};

const toggleStatusFilter = (status) => {
  if (status === 'pending') {
    showPending.value = !showPending.value;
  } else if (status === 'completed') {
    showCompleted.value = !showCompleted.value;
  }
  loadOrders(1);
};

// Handle page change
const handlePageChange = (page) => {
  loadOrders(page);
  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

const filteredOrders = computed(() => {
  return orders.value;
});

// Count for local filter badges
const pendingCount = computed(() => orders.value.filter(o => !o.is_completed).length);
const completedCount = computed(() => orders.value.filter(o => o.is_completed).length);

onMounted(() => {
  loadExploitations();
  loadLectureUsers();
  loadOrders();
});
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-3 min-w-0">
        <div class="w-10 h-10 rounded-lg bg-black flex items-center justify-center flex-shrink-0">
          <Icon name="fa6-solid:sheet-plastic" class="text-white text-lg" />
        </div>
        <h1 class="text-2xl sm:text-3xl font-bold text-gray-900 truncate">
          {{ t('GOT.summary') }}
        </h1>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center gap-2">
      <button 
        @click="getDoc()"
        :disabled="loading"
        class="px-2.5 py-1.5 bg-white border border-gray-200/60 rounded-md hover:bg-gray-50 transition-all duration-150 flex-shrink-0 gap-x-1.5 flex items-center shadow-sm"
        :title="t('export_csv')"
      >
        <span class="text-xs text-gray-600 uppercase tracking-wide">
          {{ t('export_csv') }}
        </span>
        <Icon :name="loadingDoc || loading ? 'fa6-solid:rotate-right' : 'fa6-solid:download'" class="text-xs text-gray-600" :class="{ 'animate-spin': loadingDoc || loading }" />
      </button>
      
      <button 
        @click="loadOrders(currentPage)"
        :disabled="loading"
        class="px-2.5 py-1.5 bg-white border border-gray-200/60 rounded-md hover:bg-gray-50 transition-all duration-150 flex-shrink-0 gap-x-1.5 flex items-center shadow-sm"
        :title="t('common.load_again')"
      >
        <Icon name="fa6-solid:rotate-right" class="text-xs text-gray-600" :class="{ 'animate-spin': loading }" />
      </button>
      <NuxtLink 
        to="/got/orders"
        class="px-2.5 py-1.5 bg-white border border-gray-200/60 rounded-lg hover:bg-gray-50 transition-all duration-150 flex-shrink-0 gap-x-1.5 flex items-center shadow-sm"
      >
        <Icon name="fa6-solid:list" class="text-sm text-gray-600" />
        <span class="text-xs text-gray-600 uppercase tracking-wide">Anar a les meves ordres</span>
      </NuxtLink>
    </div>

    <!-- Filters -->
    <div class="grid grid-cols-2 gap-3 w-full">
      <GotLectureUserSelect
        v-model="selectedLectureUser"
        :lecture-users="lectureUsers"
        :loading="loadingUsers"
        :showAll="true"
        :placeholder="$t('GOT.filter_by_operator')"
        @change="handleLectureUserChange"
      />
      <GotExploitationSelect
        v-model="selectedExploitation"
        :exploitations="exploitations"
        :loading="loadingExploitations"
        :placeholder="$t('common.exploitation')"
        @change="handleExploitationChange"
      />
    </div>



    <!-- Status Filters -->
    <div class="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      <button
        @click="toggleStatusFilter('pending')"
        class="px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-all duration-150 inline-flex items-center gap-2"
        :class="showPending
          ? 'bg-gray-900 text-white shadow-sm'
          : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200/60'"
      >
        <Icon :name="showPending ? 'fa6-solid:eye' : 'fa6-solid:eye-slash'" class="text-xs" />
        {{ t('GOT.pending_orders') }} <span class="opacity-60 ml-1">{{ totalPendingOrders }}</span>
      </button>
      <button
        @click="toggleStatusFilter('completed')"
        class="px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-all duration-150 inline-flex items-center gap-2"
        :class="showCompleted
          ? 'bg-gray-900 text-white shadow-sm'
          : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200/60'"
      >
        <Icon :name="showCompleted ? 'fa6-solid:eye' : 'fa6-solid:eye-slash'" class="text-xs" />
        {{ t('GOT.completed_orders') }} <span class="opacity-60 ml-1">{{ totalCompletedOrders }}</span>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <AppLoading />
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredOrders.length === 0"
      class="text-center py-20 bg-white/50 rounded-lg border border-gray-200/60">
      <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-4">
        <Icon name="fa6-solid:clipboard" class="text-3xl text-gray-400" />
      </div>
      <p class="text-gray-500 text-sm">{{ t('GOT.no_orders') }}</p>
      <p v-if="selectedLectureUser === 'unassigned'" class="text-gray-400 text-xs mt-1">
        {{ $t('GOT.no_unassigned_orders') }}
      </p>
    </div>

    <!-- Orders List -->
    <div v-else class="bg-white rounded-lg border border-gray-200/60 overflow-hidden">
      <div class="hidden lg:grid lg:grid-cols-[1fr_80px_1fr_80px_80px_1fr_80px] gap-y-4 gap-x-1 px-4 py-3 bg-gray-50/80 border-b border-gray-200/60 text-xs font-semibold text-gray-600 uppercase tracking-wide">
        <div>{{ t('order') }}</div>
        <div>{{ t('common.status') }}</div>
        <div>{{ t('common.type') }}</div>
        <div>{{ t('common.date') }}</div>
        <div>{{ t('common.completion') }}</div>
        <div>{{ t('common.address') }}</div>
        <div class="text-right">{{ t('common.operators') }}</div>
      </div>

      <NuxtLink
        v-for="order in filteredOrders"
        :key="order.id"
        :to="`/got/orders/${order.id}?from=summary`"
        class="group block border-b border-gray-100 last:border-b-0 px-4 py-3 hover:bg-gray-50/70 transition-colors duration-150"
      >
        <!-- Mobile: card-like compact layout -->
        <div class="lg:hidden rounded-md border border-gray-100 bg-white p-3 space-y-2.5">
          <!-- Header -->
          <div class="flex items-start justify-between">
            <div class="flex-1 min-w-0">
              <h3 class="text-base font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">
                <Icon name="fa6-solid:flag" class="text-xs mr-1" :class="{
                  'text-red-500': order?.priority?.color == 'red',
                  'text-green-500': order?.priority?.color == 'green',
                  'text-blue-500': order?.priority?.color == 'blue',
                  'text-yellow-500': order?.priority?.color == 'yellow',
                  'text-gray-400': !order?.priority?.color || !['red', 'green', 'blue', 'yellow'].includes(order?.priority?.color)
                }" />
                #{{ order.token }}
              </h3>
              <p class="text-sm text-gray-500 mt-0.5">
                {{ order.type_name }}
              </p>
              <p class="text-xs text-gray-400 mt-0.5">
                {{ order.reason_name || '⠀' }}
              </p>
            </div>
            <AtomsColorBadge :value="order.status_name" :color="order.status_color" class="ml-2 flex-shrink-0" />
          </div>

          <!-- Details -->
          <div class="space-y-2.5 text-sm">
            <!-- Operators Count & Due Date -->
            <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
              <div class="flex items-center gap-2">
                <Icon name="fa6-solid:users" class="text-gray-400 flex-shrink-0 text-xs" />
                <span class="text-gray-600 text-sm">
                  {{ order.operators?.length || 0 }} {{ $t('GOT.operators_assigned') }}
                </span>
              </div>

              <div v-if="order.dueDateAt" class="flex items-center gap-2">
                <Icon name="fa6-solid:calendar" class="text-gray-400 flex-shrink-0 text-xs" />
                <span class="text-gray-600 text-sm">
                  {{ formatDate(order.dueDateAt) }}
                </span>
              </div>
            </div>

            <!-- Address/Location -->
            <div class="flex items-start gap-2">
              <Icon name="fa6-solid:location-dot" class="text-gray-400 mt-0.5 flex-shrink-0 text-xs" />
              <span class="text-gray-600 line-clamp-2 text-sm">{{ order.address?.address_complete || order.supply_point?.address_complete || order.connection?.address || "-" }}</span>
            </div>

            <!-- Completion Date -->
            <div v-if="order.completed_at" class="flex items-center gap-2 pt-2 border-t border-gray-100">
              <Icon name="fa6-solid:circle-check" class="text-green-600 flex-shrink-0 text-xs" />
              <span class="text-green-600 text-xs font-medium">
                {{ t('common.completed') }}: {{ formatDate(order.completed_at) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Desktop: list row layout -->
        <div class="hidden lg:grid lg:grid-cols-[1fr_80px_1fr_80px_80px_1fr_80px] gap-4 items-center">
          <div class="min-w-0">
            <div class="flex items-center gap-1.5 min-w-0">
              <Icon name="fa6-solid:flag" class="text-xs flex-shrink-0" :class="{
                'text-red-500': order?.priority?.color == 'red',
                'text-green-500': order?.priority?.color == 'green',
                'text-blue-500': order?.priority?.color == 'blue',
                'text-yellow-500': order?.priority?.color == 'yellow',
                'text-gray-400': !order?.priority?.color || !['red', 'green', 'blue', 'yellow'].includes(order?.priority?.color)
              }" />
              <span class="font-semibold text-gray-900 truncate group-hover:text-blue-600 transition-colors">#{{ order.token }}</span>
            </div>
          </div>

          <div>
            <AtomsColorBadge :value="order.status_name" :color="order.status_color" class="w-fit" />
          </div>

          <div class="min-w-0">
            <p class="text-sm text-gray-700 truncate">{{ order.type_name || '-' }}</p>
          </div>

          <div>
            <p class="text-sm text-gray-600">{{ order.dueDateAt ? formatDate(order.dueDateAt) : '-' }}</p>
          </div>

          <div>
            <p class="text-sm text-gray-600">{{ order.completed_at ? formatDate(order.completed_at) : '-' }}</p>
          </div>

          <div class="min-w-0">
            <p class="text-sm text-gray-600 truncate">
              {{ order.address?.address_complete || order.supply_point?.address_complete || order.connection?.address || '-' }}
            </p>
          </div>

          <div>
            <div class="flex items-start justify-end gap-2 text-sm text-gray-700">
              <div v-if="order.operators?.length" class="flex flex-col items-end gap-0.5">
                <span
                v-for="operator in order.operators"
                :key="operator.id || operator.token"
                class="max-w-full truncate text-[10px] leading-tight text-gray-500"
                :title="operator.token"
                >
                {{ operator.token }}
              </span>
            </div>
            <div class="flex items-center gap-1 mt-0.5">
              <Icon name="fa6-solid:users" class="text-xs text-gray-400" />
              <span class="font-medium">{{ order.operators?.length || 0 }}</span>
            </div>
            </div>
          </div>
        </div>
      </NuxtLink>
    </div>

    <!-- Pagination -->
    <GotPagination
      :current-page="currentPage"
      :total-pages="totalPages"
      :has-next="hasNext"
      :has-previous="hasPrevious"
      :total="totalOrders"
      :loading="loading"
      @page-change="handlePageChange"
    />
  </div>
</template>

<style scoped>
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
</style>
