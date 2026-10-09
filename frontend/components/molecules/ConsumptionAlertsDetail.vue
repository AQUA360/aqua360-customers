<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import ContractRegion from '~/components/organisms/ContractRegion.vue';

const { t } = useI18n();
const { $ConsumptionManagementApiService } = useNuxtApp();

const props = defineProps({
  billingId: { type: Number, required: true },
});

const items = ref([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const hasMore = ref(false);

const showSubRegion = ref(false);
const selectedContractId = ref(null);

const TYPE_COLORS = {
  fire_hydrant:         { bg: 'bg-red-100',    text: 'text-red-700',    border: 'border-red-300' },
  inactive_consumption: { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-300' },
  duplicate_readings:   { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-300' },
};

const loadData = async (p = 1) => {
  loading.value = true;
  try {
    const res = await $ConsumptionManagementApiService.getAll('', null, p, null, false, 'history', props.billingId);
    if (p === 1) {
      items.value = res.results;
    } else {
      items.value = [...items.value, ...res.results];
    }
    total.value = res.count;
    hasMore.value = !!res.next;
    page.value = p;
  } catch (e) {
    console.error('Error loading consumption alerts:', e);
  } finally {
    loading.value = false;
  }
};

const loadMore = async () => {
  if (loading.value || !hasMore.value) return;
  await loadData(page.value + 1);
};

const openContract = (contractId) => {
  selectedContractId.value = contractId;
  showSubRegion.value = true;
};

const onScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollTop + clientHeight >= scrollHeight - 20) {
    loadMore();
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="mb-4 flex items-center gap-3">
      <h2 class="text-xl font-semibold text-slate-800">{{ t('consumption_management.title') }}</h2>
      <span v-if="total > 0" class="inline-flex items-center justify-center rounded-full bg-amber-200 px-2.5 py-0.5 text-sm font-bold text-amber-800">
        {{ total }}
      </span>
    </div>

    <div v-if="loading && items.length === 0" class="flex items-center gap-2 text-slate-400 text-sm py-6">
      <Icon name="fa6-solid:spinner" class="animate-spin" />
      <span>{{ t('common.loading') }}...</span>
    </div>

    <div v-else-if="items.length === 0" class="py-8 text-center text-slate-400 text-sm">
      {{ t('common.no_records') }}
    </div>

    <div v-else class="flex flex-col flex-1 min-h-0">
      <div class="grid grid-cols-[180px,1fr,1fr,1fr,120px,120px] gap-2 px-3 pb-2 border-b border-gray-300 text-xs font-semibold text-slate-500 uppercase tracking-wide">
        <span>{{ t('consumption_management.type') }}</span>
        <span>{{ t('contract') }}</span>
        <span>{{ t('common.holder') }}</span>
        <span>{{ t('supply_point') }}</span>
        <span>{{ t('consumption_management.consumption') }}</span>
        <span>{{ t('consumption_management.reading_date') }}</span>
      </div>

      <div class="flex-1 overflow-y-auto" @scroll="onScroll">
        <div v-for="item in items" :key="item.id"
          class="grid grid-cols-[180px,1fr,1fr,1fr,120px,120px] gap-2 px-3 py-2 border-b border-slate-100 items-center hover:bg-slate-50 text-sm">

          <span>
            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border"
              :class="[
                TYPE_COLORS[item.type]?.bg    ?? 'bg-slate-100',
                TYPE_COLORS[item.type]?.text  ?? 'text-slate-700',
                TYPE_COLORS[item.type]?.border ?? 'border-slate-300',
              ]">
              {{ item.type_display }}
            </span>
          </span>

          <span>
            <button class="group flex justify-between w-full items-center text-sky-500 font-mono text-left text-sm"
              @click="openContract(item.contract_id)">
              {{ item.contract_token }}
              <Icon name="fa6-solid:eye" class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200" />
            </button>
          </span>

          <span class="truncate text-slate-700" :title="item.holder_name">{{ item.holder_name }}</span>

          <span class="text-xs text-slate-500 truncate" :title="item.supply_point_address">{{ item.supply_point_address }}</span>

          <span class="text-slate-600">
            <template v-if="item.readings_in_period !== null">
              {{ item.readings_in_period }} {{ t('consumption_management.readings') }}
            </template>
            <template v-else-if="item.consumption !== null">
              {{ item.consumption }} {{ item.consumption_unit }}
            </template>
            <template v-else>—</template>
          </span>

          <span class="text-xs text-slate-500">
            <template v-if="item.period_start && item.period_end">
              {{ formatDate(item.period_start) }} – {{ formatDate(item.period_end) }}
            </template>
            <template v-else-if="item.reading_date">
              {{ formatDate(item.reading_date) }}
            </template>
            <template v-else>—</template>
          </span>
        </div>

        <div v-if="loading && items.length > 0" class="text-center py-4 text-slate-400 text-sm">
          {{ t('common.loading') }}...
        </div>
      </div>
    </div>

    <div role="region"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[75%] z-40 shadow"
      :class="{ 'translate-x-0': showSubRegion, 'translate-x-[2000px]': !showSubRegion }">
      <div class="mb-3 px-3">
        <button @click="showSubRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10 overflow-y-auto h-full">
        <ContractRegion v-if="showSubRegion && selectedContractId" :id="selectedContractId" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
