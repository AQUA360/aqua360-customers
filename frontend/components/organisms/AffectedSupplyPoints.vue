<script setup>
import { toRaw, ref, onMounted, watch, defineAsyncComponent } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import _ from 'lodash';
import FieldDetail from '~/components/atoms/FieldDetail.vue';

import MeterRegion from '~/components/organisms/MeterRegion.vue';
import ClusterRegion from '~/components/organisms/ClusterRegion.vue';
import ConnectionRegion from '~/components/organisms/ConnectionRegion.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import RouteRegion from '~/components/organisms/RouteRegion.vue';
import SupplyPointRemoval from '~/components/organisms/SupplyPointRemoval.vue';

// Lazy-load SupplyPointDetail to improve performance
const LazySupplyPointDetail = defineAsyncComponent(() =>
  import('../molecules/SupplyPointDetail.vue')
);

const props = defineProps({
  supply_points: Object
});

const { t } = useI18n();
const emit = defineEmits(['show-subregion']);

const loading = ref(true);
const supplyPoints = ref([]);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showAffectedSP = ref(false);
const SubRegion = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const closeSubRegion = () => {
  SubRegion.value = false;
  emit('show-subregion', false);
};

const showSubRegion = () => {
  SubRegion.value = true;
  emit('show-subregion', true);
};

const showDetail = (res) => {
  showRegionDetailComponent.value = res.component;
  regionDetailId.value = res.id;
  showSubRegion();
};

onMounted(() => {
  supplyPoints.value = props.supply_points;
  loading.value = false;
});

watch(() => props.supply_points, (newValue) => {
  loading.value = true;
  supplyPoints.value = newValue;
  loading.value = false;
}, { immediate: true });

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <!-- Loading State -->
    <div v-if="loading">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>

    <!-- Supply Points List -->
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <details v-for="item in supplyPoints" :key="item.id"
        class="mb-3 border border-gray-300 rounded px-4 pt-2 bg-white my-2">
        <summary class="text-sm p-2 text-slate-500 hover:bg-slate-200 active:bg-slate-300 cursor-pointer mb-2">
          <Icon name="fa6-solid:street-view" class="display-inline mr-2" />
          {{ item.token + ' - ' + item.address_complete }}
        </summary>

        <!-- Lazy Load SupplyPointDetail -->
        <Suspense>
          <template #default>
            <LazySupplyPointDetail :id="item.id" @show-detail="showDetail" />
          </template>
          <template #fallback>
            <div class="text-center p-4">{{ $t('common.loading') }}...</div>
          </template>
        </Suspense>
      </details>
    </div>

    <!-- SubRegion -->
    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white ml-5 fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3 absolute z-10">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10 mt-10">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ClusterRegion v-if="showRegionDetailComponent === 'ClusterRegion'" :id="regionDetailId" :isSubRegion="true" />
        <RouteRegion v-if="showRegionDetailComponent === 'RouteRegion'" :id="regionDetailId" :isSubRegion="true" />
        <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId" :isSubRegion="true" />
        <ConnectionRegion v-if="showRegionDetailComponent === 'ConnectionRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <SupplyPointRemoval v-if="showRegionDetailComponent === 'SupplyPointRemoval'" :id="regionDetailId"
          @save-success="removalSave" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
