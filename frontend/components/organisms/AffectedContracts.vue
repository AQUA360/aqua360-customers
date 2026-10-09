<script setup>
import { toRaw, ref, onMounted, watch, defineAsyncComponent } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import _ from 'lodash';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';


const { $ContractApiService } = useNuxtApp();
// Lazy-load SupplyPointDetail to improve performance
const LazyContractDetail = defineAsyncComponent(() =>
  import('../molecules/ContractDetail.vue')
);

const props = defineProps({
  contracts: Object,
  contract_tokens: Array
});

const { t } = useI18n();
const emit = defineEmits(['show-subregion']);

const loading = ref(true);
const contractsData = ref([]);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const SubRegion = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    isSubRegionOpen.value = false;
  }
};

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

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

const closeAllRegions = () => {
  showRegion.value = false;
};

onMounted(() => {
  if(props.contracts && props.contracts.length > 0){
    contractsData.value = props.contracts;
  }
  if(props.contract_tokens && props.contract_tokens.length > 0){
    contractsData.value = props.contract_tokens;
  }
  loading.value = false;
});

watch(() => props.contracts, (newValue) => {
  loading.value = true;
  if(newValue && newValue.length > 0){
    contractsData.value = newValue;
  }
  loading.value = false;
}, { immediate: true });

watch(() => props.contract_tokens, (newValue) => {
  loading.value = true;
  if(newValue && newValue.length > 0){
    contractsData.value = newValue;
  }
  loading.value = false;
}, { immediate: true });

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <!-- Loading State -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>

    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <details v-for="item in contractsData" :key="item.id"
        class="mb-3 border border-gray-300 rounded px-4 pt-2 bg-white my-2">
        <span></span>
        <summary class="text-sm p-2 text-slate-500 hover:bg-slate-200 active:bg-slate-300 cursor-pointer mb-2">
          <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />
          {{ item.token }} - {{ item.holder_token }} {{ item.holder }} 
        </summary>

        <Suspense>
          <template #default>
            <LazyContractDetail :id="item.id" @show-subregion="showDetail" />
          </template>
          <template #fallback>
            <div class="text-center p-4">{{ t('common.loading') }}...</div>
          </template>
        </Suspense>
      </details>

    </div>

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white ml-5 fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3 absolute z-10">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10 mt-10">
        <OrganismsSupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
