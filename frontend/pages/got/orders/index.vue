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
const filter = useState('got_orders_filter', () => 'pending'); // all, pending, completed

// Pagination state
const currentPage = useState('got_orders_page', () => 1);
const totalPages = ref(1);
const hasNext = ref(false);
const hasPrevious = ref(false);
const totalOrders = ref(0);
const perPage = 7;

const loadingExploitations = ref(false);
const exploitations = ref([]);
const selectedExploitation = useState('got_orders_exploitation', () => null);

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

const loadOrders = async (page = 1) => {
  try {
    loading.value = true;
    
    // Build filters
    const filters = {};
    filters.exploitationId = selectedExploitation.value;

    const response = await $gotApi.getOrders(page, perPage, filters);

    if (response.success) {
      orders.value = response.orders;
      currentPage.value = response.page;
      totalPages.value = response.total_pages;
      hasNext.value = response.has_next;
      hasPrevious.value = response.has_previous;
      totalOrders.value = response.total;
    }
  } catch (error) {
    toast.error('Error loading orders:', error);
  } finally {
    loading.value = false;
  }
};

// Handle filter change
const handleExploitationChange = (exploitationId) => {
  selectedExploitation.value = exploitationId;
  currentPage.value = 1; // Reset to first page
  loadOrders(1);
};

// Handle page change
const handlePageChange = (page) => {
  loadOrders(page);
  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

const filteredOrders = computed(() => {
  if (filter.value === 'pending') {
    return orders.value.filter(o => !o.is_completed);
  } else if (filter.value === 'completed') {
    return orders.value.filter(o => o.is_completed);
  }
  return orders.value;
});

// Count for local filter badges
const pendingCount = computed(() => orders.value.filter(o => !o.is_completed).length);
const completedCount = computed(() => orders.value.filter(o => o.is_completed).length);

onMounted(() => {
  loadExploitations();
  loadOrders();
});
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-3 min-w-0">
        <div class="w-10 h-10 rounded-lg bg-black flex items-center justify-center flex-shrink-0">
          <Icon name="fa6-solid:list" class="text-white text-lg" />
        </div>
        <h1 class="text-2xl sm:text-3xl font-bold text-gray-900 truncate">
          {{ t('GOT.my_orders') }}
        </h1>
      </div>

      <button 
        @click="loadOrders(currentPage)"
        :disabled="loading"
        class="p-2.5 bg-white border border-gray-200/60 rounded-lg hover:bg-gray-50 transition-all duration-150 flex-shrink-0"
        :title="t('common.load_again')"
      >
        <Icon name="fa6-solid:rotate-right" class="text-sm text-gray-600" :class="{ 'animate-spin': loading }" />
      </button>
    </div>

    <!-- Exploitation Filter -->
    <div class="w-full">
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
      <button @click="filter = 'all'"
        class="px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-all duration-150" :class="filter === 'all'
          ? 'bg-gray-900 text-white shadow-sm'
          : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200/60'">
        {{ t('common.all') }} <span class="opacity-60 ml-1">{{ orders.length }}</span>
      </button>
      <button @click="filter = 'pending'"
        class="px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-all duration-150" :class="filter === 'pending'
          ? 'bg-gray-900 text-white shadow-sm'
          : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200/60'">
        {{ t('GOT.pending_orders') }} <span class="opacity-60 ml-1">{{ pendingCount }}</span>
      </button>
      <button @click="filter = 'completed'"
        class="px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-all duration-150" :class="filter === 'completed'
          ? 'bg-gray-900 text-white shadow-sm'
          : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200/60'">
        {{ t('GOT.completed_orders') }} <span class="opacity-60 ml-1">{{ completedCount }}</span>
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

    <!-- Orders Grid -->
    <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <NuxtLink v-for="order in filteredOrders" :key="order.id" :to="`/got/orders/${order.id}?from=orders`"
        class="group block bg-white rounded-lg border border-gray-200/60 hover:shadow-md hover:border-gray-300 transition-all duration-200 p-5">
        <!-- Header -->
        <div class="flex items-start justify-between mb-4">
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
            <span class="text-gray-600 line-clamp-2 text-sm">{{order.address?.address_complete || order.supply_point?.address_complete || order.connection?.address ||  "-" }}</span>
          </div>

          <!-- Completion Date -->
          <div v-if="order.completed_at" class="flex items-center gap-2 pt-2 border-t border-gray-100">
            <Icon name="fa6-solid:circle-check" class="text-green-600 flex-shrink-0 text-xs" />
            <span class="text-green-600 text-xs font-medium">
              {{ t('common.completed') }}: {{ formatDate(order.completed_at) }}
            </span>
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
