<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';
import H1 from '~/components/atoms/H1.vue';

const { t } = useI18n();
const { $ReadingBatchApiService } = useNuxtApp();

const props = defineProps({
  batchId: {
    type: Number,
    required: true
  },
  title: {
    type: String,
    default: 'no_route_supply_points_count'
  }
});

const emit = defineEmits(['openRegion']);

const items = ref([]);
const loading = ref(false);
const pagination = ref({
  page: 1,
  next: null
});

const loadData = async (page = 1) => {
  loading.value = true;
  try {
    const result = await $ReadingBatchApiService.getNoRouteSupplyPoints(props.batchId, page);
    if (page === 1) {
      items.value = result;
    } else {
      items.value.push(...result);
    }
    pagination.value.page = page;
    pagination.value.next = result.next;
  } catch (err) {
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const onScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollTop + clientHeight >= scrollHeight - 20 && !loading.value && pagination.value.next) {
    loadData(pagination.value.page + 1);
  }
};

const openSupplyPointRegion = (id) => {
  emit('openRegion', { entity: 'supply_point', id });
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="flex flex-col h-full">
    <H1>{{ t(title) }}</H1>
    <div class="grid gap-2 grid-cols-[1.5fr,2fr,1fr,1.5fr] px-4 divide-x divide-gray-200 border-b border-gray-400 items-end">
      <span class="p-3 font-bold">{{ t('supply_point') }}</span>
      <span class="p-3 font-bold">{{ t('common.address') }}</span>
      <span class="p-3 font-bold">{{ t('common.status') }}</span>
      <span class="p-3 font-bold">{{ t('common.roles.HOLDER') }}</span>
    </div>
    <div class="overflow-y-auto flex-grow pb-10" @scroll="onScroll">
      <div v-for="sp in items" :key="sp.id"
        class="grid grid-cols-[1.5fr,2fr,1fr,1.5fr] py-2 px-4 divide-x divide-gray-200 border-b border-gray-100 items-center hover:bg-slate-50 transition-colors">
        <div class="p-3">
          <a href="#" class="text-sky-600 font-bold hover:underline" @click.prevent="openSupplyPointRegion(sp.id)">
            {{ sp.token }}
          </a>
        </div>
        <div class="p-3 truncate" :title="sp.address_complete">{{ sp.address_complete }}</div>
        <div class="p-3">
          <AtomsColorBadge :color="sp.status_color" :value="sp.status_name" />
        </div>
        <div class="p-3 truncate">
          <span v-if="sp.contracts && sp.contracts.length > 0">{{ sp.contracts[0].holder }}</span>
          <span v-else class="text-slate-400">-</span>
        </div>
      </div>
      <div v-if="loading" class="text-center py-4 flex items-center justify-center">
        <AppLoading :text="$t('common.loading')" :size="40" />
      </div>
    </div>
  </div>
</template>
