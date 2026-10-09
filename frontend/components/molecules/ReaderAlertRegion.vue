<script setup>
import { ref, computed } from 'vue';
import AtomsReadingEdit from '~/components/atoms/ReadingEdit.vue';
import Pagination from '~/components/molecules/Pagination.vue';

const props = defineProps({
  batch_id: {
    type: Number,
    default: null
  },
  breakdown: {
    type: Object,
    default: () => ({})
  }
});

const { $ReadingApiService } = useNuxtApp();
const { t } = useI18n();

const selectedAlert = ref(null);
const readings = ref([]);
const loadingReadings = ref(false);
const showingDetailId = ref(0);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const totalAlerts = computed(() => Object.values(props.breakdown).reduce((sum, count) => sum + Number(count || 0), 0));

const loadAlertReadings = async (page = 1) => {
  if (!selectedAlert.value) return;
  loadingReadings.value = true;
  try {
    const result = await $ReadingApiService.getReadingsByBatchMinimal(
      props.batch_id, page, 'reader_alert=' + encodeURIComponent(selectedAlert.value)
    );
    readings.value = result.results || [];
    Object.assign(pagination.value, {
      page: page,
      total: result.count,
      totalPages: Math.ceil((result.count || 0) / pagination.value.perPage),
      previous: result.previous,
      next: result.next
    });
  } finally {
    loadingReadings.value = false;
  }
};

const openAlert = (name) => {
  selectedAlert.value = name;
  showingDetailId.value = 0;
  loadAlertReadings(1);
};

const backToList = () => {
  selectedAlert.value = null;
  readings.value = [];
};

const handlePageChange = (newPage) => {
  loadAlertReadings(newPage);
};

const onShowDetail = (id) => {
  showingDetailId.value = showingDetailId.value === id ? 0 : id;
};

const subRegionEntity = ref('');
const subRegionId = ref(0);
const showSubRegion = ref(false);

const openRegion = (e) => {
  subRegionEntity.value = e.entity;
  subRegionId.value = e.id;
  showSubRegion.value = true;
};

const closeSubRegion = () => {
  showSubRegion.value = false;
};
</script>

<template>
  <div class="relative h-full">
    <div v-if="!selectedAlert">
      <h2 class="text-xl font-semibold mb-2">{{ t('billing_block.reader_alerts') }}</h2>
      <p class="text-sm text-slate-500 mb-4">
        {{ t('common.total') }}: <span class="font-bold">{{ totalAlerts }}</span>
      </p>
      <ul class="divide-y divide-gray-100 border border-gray-200 rounded-md bg-white">
        <li v-for="(count, name) in breakdown" :key="name"
          class="flex justify-between items-center p-3 cursor-pointer hover:bg-slate-50"
          @click="openAlert(name)">
          <span class="font-medium">{{ name }}</span>
          <span class="inline-flex items-center gap-2">
            <span class="inline-flex items-center bg-red-100 text-red-700 text-sm rounded-full px-2 py-1">{{ count }}</span>
            <Icon name="fa6-solid:chevron-right" class="text-slate-400" />
          </span>
        </li>
      </ul>
    </div>

    <div v-else>
      <button type="button" class="mb-3 text-sky-600 hover:underline flex items-center gap-1" @click="backToList">
        <Icon name="fa6-solid:arrow-left" /> {{ t('common.previous') }}
      </button>
      <h2 class="text-lg font-semibold mb-4">{{ selectedAlert }}</h2>
      <div v-if="loadingReadings" class="text-center py-4">{{ t('common.loading') }}...</div>
      <div v-else-if="readings.length === 0" class="text-center py-8 text-sm text-slate-400">{{ t('common.no_records') }}</div>
      <div v-else>
        <div v-for="reading in readings" :key="reading.id">
          <AtomsReadingEdit :reading="reading" :showDetail="showingDetailId == reading.id"
            @show-edit="onShowDetail" @open-region="openRegion" :allowChange="false" />
        </div>
        <Pagination v-if="readings.length > 0" :pagination="pagination" @update:page="handlePageChange" />
      </div>
    </div>

    <!-- Sub-region: contract/person/supply_point detail, stacked over this region -->
    <div role="region"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[45%] z-50 shadow"
      :class="{ 'translate-x-0': showSubRegion, 'translate-x-[2000px]': !showSubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <OrganismsContractRegion v-if="subRegionEntity === 'contract'" :id="subRegionId" :isSubRegion="true" />
        <OrganismsPersonRegion v-if="subRegionEntity === 'person'" :id="subRegionId" :isSubRegion="true" />
        <OrganismsSupplyPointRegion v-if="subRegionEntity === 'supply_point'" :id="subRegionId" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
