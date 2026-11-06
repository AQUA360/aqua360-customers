<script setup>
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import SendBatchRegion from '~/components/organisms/SendBatchRegion.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';
import { useConfigStore } from '~/stores/useConfigStore';
import { storeToRefs } from 'pinia';

const { t } = useI18n();
const toast = useToast();
const configStore = useConfigStore();
const { sendBatchEnabled } = storeToRefs(configStore);
const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    regionComponent.value = null;
    detail.value = null;
    selectedItemId.value = null;
  }
};

const statusColors = {
  0: 'yellow',
  1: 'sky',
  2: 'green',
  pending: 'yellow',
  processing: 'sky',
  done: 'green',
  finalized: 'green',
};

const itemCount = (item) =>
  item.items_count
  ?? ((item.invoices_count || 0) + (item.payments_count || 0) + (item.commitment_deposits_count || 0));

const truncateToken = (token, max = 22) => {
  if (!token) return '-';
  if (token.length <= max) return token;
  return `${token.slice(0, max - 1)}…`;
};

const route = useRoute();
const { $SendBatchApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref(null);
const sortDesc = ref(false);
const regionComponent = ref(null);
const permissions = ref(null);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false,
});

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $SendBatchApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
};

const getData = async (searchQuery = '', page = 1, sort = null, desc = false) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $SendBatchApiService.getAllBatches(searchQuery, page, sort, desc);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '',
    });

    nextTick(() => {
      const activeInput = document.getElementById('searchInput');
      if (activeInput) {
        activeInput.focus();
      }
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const debouncedGetData = debounce((query, sort, desc) => {
  getData(query, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, sortBy.value, sortDesc.value);
};

const refresh = () => {
  debouncedGetData(searchInput.value, sortBy.value, sortDesc.value);
};

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, newPage, sortBy.value, sortDesc.value);
};

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, pagination.value.page, sortBy.value, sortDesc.value);
};

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

const showDetail = async (id, component) => {
  await toggleRegion(false);
  regionComponent.value = component;
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
};

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail' || route?.query?.id) {
    showDetail(route.query.id, 'SendBatchRegion');
  }
};

onMounted(async () => {
  await configStore.fetchSendBatchEnabled();
  if (!sendBatchEnabled.value) {
    toast.error(t('send_batch_block.not_enabled'));
    pending.value = false;
    return navigateTo('/');
  }
  await getPermissions();
  if (permissions.value?.can_view) {
    await getData();
    checkRouteQuery();
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
});

watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

watch(() => route.query, () => {
  checkRouteQuery();
}, { immediate: true });
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('send_batch_block.batches') }}</H1>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <DataTable
      grid-template="200px,140px,110px,100px,100px,70px,140px,130px"
      :pending="pending"
      :error="error"
      :is-empty="permissions?.can_view && items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('send_batch_block.type')" sortKey="batch_type__name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('send_batch_block.billing')" sortKey="billing__token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('send_batch_block.sent_at')" sortKey="sent_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('send_batch_block.finished_at')" sortKey="finished_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('send_batch_block.items')" :sortable="false" />
        <TableHeader :label="$t('send_batch_block.summary')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status__token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <template v-if="permissions?.can_view">
          <div
            v-for="item in items"
            :key="item.id"
            class="gap-3 text-base border-b items-center bg-white"
            :style="gridStyle"
            :class="{
              'bg-yellow-50': item.id === selectedItemId,
              'bg-red-50': item.send_error && item.id !== selectedItemId,
            }">
            <span class="min-w-0 p-1">
              <button
                class="group flex w-full items-center gap-1 text-sky-500 text-left"
                @click="showDetail(item.id, 'SendBatchRegion');">
                <abbr :title="item.token" class="no-underline truncate font-mono text-sm">
                  {{ truncateToken(item.token) }}
                </abbr>
                <Icon
                  name="fa6-solid:eye"
                  class="shrink-0 opacity-0 group-hover:opacity-100 text-slate-500 transition-opacity duration-200 ease-in-out" />
              </button>
              <div v-if="item.related_batch_token" class="mt-0.5 flex items-center gap-1 text-xs text-slate-500">
                <Icon name="fa6-solid:rotate" class="text-[10px]" />
                <span>{{ $t('send_batch_block.resend') }}:</span>
                <abbr :title="item.related_batch_token" class="no-underline font-mono">
                  {{ truncateToken(item.related_batch_token, 16) }}
                </abbr>
              </div>
              <div
                v-else-if="item.send_error"
                class="mt-0.5 text-xs text-red-600 truncate"
                :title="item.send_error">
                {{ item.send_error }}
              </div>
            </span>
            <span class="p-1 min-w-0">
              <div class="truncate" :title="item.batch_type?.name || item.batch_type?.token">
                {{ item.batch_type?.name || item.batch_type?.token || '-' }}
              </div>
              <div
                v-if="item.batch_type?.provider"
                class="text-xs text-slate-500 uppercase tracking-wide">
                {{ item.batch_type.provider.name || item.batch_type.provider.token }}
              </div>
            </span>
            <span class="p-1 font-mono text-sm truncate" :title="item.billing_token || ''">
              {{ item.billing_token || '-' }}
            </span>
            <span class="p-1 text-sm">
              <template v-if="item.sent_at">{{ formatDate(item.sent_at) }}</template>
              <span v-else class="text-slate-400">{{ $t('send_batch_block.not_sent') }}</span>
            </span>
            <span class="p-1 text-sm">
              {{ item.finished_at ? formatDate(item.finished_at) : '-' }}
            </span>
            <span class="p-1">{{ itemCount(item) }}</span>
            <span class="p-1 text-xs flex flex-wrap gap-x-2 gap-y-0.5">
              <span class="text-green-700">
                {{ $t('send_batch_block.summary_short_ok') }} {{ item.ok_count ?? item.summary?.ok ?? 0 }}
              </span>
              <span :class="(item.error_count || 0) > 0 ? 'text-red-600 font-medium' : 'text-slate-500'">
                {{ $t('send_batch_block.summary_short_error') }} {{ item.error_count || 0 }}
              </span>
              <span class="text-slate-500">
                {{ $t('send_batch_block.summary_short_pending') }} {{ item.pending_count ?? item.summary?.pending ?? 0 }}
              </span>
            </span>
            <span class="p-1 flex flex-col items-start gap-1">
              <AtomsColorBadge
                v-if="item.status"
                :value="item.status.name || t(`send_batch_block.status.${item.status.token}`)"
                :color="item.status.color || statusColors[item.status.token]" />
              <span v-else class="text-slate-400 text-sm">-</span>
              <span
                v-if="item.instant_status_code"
                class="text-xs"
                :class="item.instant_status_code >= 400 ? 'text-red-600' : 'text-slate-400'">
                HTTP {{ item.instant_status_code }}
              </span>
            </span>
          </div>
        </template>
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div>

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden"
    :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div v-if="regionComponent" class="px-10">
      <SendBatchRegion v-if="regionComponent === 'SendBatchRegion'" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="refresh" @close-subregion="toggleRegion(false)" />
    </div>
  </div>
</template>
