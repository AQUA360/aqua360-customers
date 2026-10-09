<script setup>
import { ref, computed, onMounted } from 'vue';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import AccountingReferenceCard from '~/components/molecules/AccountingReferenceCard.vue';
import AccountingConceptsRegion from '~/components/molecules/AccountingConceptsRegion.vue';
import AccountingCostCentersRegion from '~/components/molecules/AccountingCostCentersRegion.vue';
import AccountingPricingsBox from '~/components/organisms/AccountingPricingsBox.vue';
import EditAccountingPricing from '~/components/organisms/EditAccountingPricing.vue';
import { checkPermission } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const {
  $PriceRateApiService,
  $ExploitationApiService,
  $AccountingConceptApiService,
} = useNuxtApp();

const objectPermissions = ref(null);
const initializing = ref(true);
const conceptsLoading = ref(false);

const accountingConcepts = ref([]);
const accountingValues = ref([
  { token: 'invoice', name: t('invoice') },
  { token: 'lineitem', name: t('pricing_block.line_items') },
  { token: 'payment', name: t('payments') },
]);

const exploitations = ref([]);
const activeExploitationTab = ref(null);

const pricingsBox = ref(null);
const regionComponent = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const showRegion = ref(false);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    regionComponent.value = null;
    selectedItemId.value = null;
  }
};

const openReferenceRegion = (component, id = null) => {
  regionComponent.value = component;
  selectedItemId.value = id;
  isSubRegionOpen.value = false;
  toggleRegion(true);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

const showExploitation = computed(() => exploitations.value.length > 1);

const setActiveExploitation = (exploitationId) => {
  if (String(activeExploitationTab.value) === String(exploitationId)) return;
  activeExploitationTab.value = exploitationId;
};

const loadExploitations = async () => {
  const response = await $ExploitationApiService.getData();
  exploitations.value = Array.isArray(response.results) ? response.results : [];
  try {
    const exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      const filtered = exploitations.value.filter(
        (exploitation) => String(exploitation.id) === String(exploitation_id),
      );
      if (filtered.length) exploitations.value = filtered;
    }
  } catch (error) {
    console.error(error);
  }
  if (exploitations.value.length) {
    activeExploitationTab.value = exploitations.value[0].id;
  }
};

const refreshConcepts = async () => {
  conceptsLoading.value = true;
  try {
    const response = await $AccountingConceptApiService.getAll();
    accountingConcepts.value = Array.isArray(response) ? response : (response?.results ?? []);
  } catch (error) {
    console.error(error);
    accountingConcepts.value = [];
  } finally {
    conceptsLoading.value = false;
  }
};

const refreshPricings = () => {
  pricingsBox.value?.refresh?.();
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($PriceRateApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  try {
    await Promise.all([loadExploitations(), refreshConcepts()]);
  } catch (error) {
    console.error(error);
  } finally {
    initializing.value = false;
  }
});
</script>

<template>
  <div id="wrapper" class="text-base pb-8">
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <H1 class="!mb-0">{{ $t('pricing_block.accounting') }}</H1>
      <NuxtLink to="/settings/" class="text-sm text-sky-500 underline hover:no-underline">
        {{ t('common.settings') }}
      </NuxtLink>
    </div>

    <AppLoading v-if="initializing" :text="t('common.loading')" />

    <template v-else>
      <div class="w-full">
        <AtomsTabs v-if="showExploitation">
          <li v-for="exploitation in exploitations" :key="exploitation.id">
            <a :href="`#tab_exploitation_${exploitation.id}`" @click.prevent="setActiveExploitation(exploitation.id)"
              :class="{
                'text-sky-600 border-sky-600': String(activeExploitationTab) === String(exploitation.id),
                'hover:text-gray-600 hover:border-gray-300': String(activeExploitationTab) !== String(exploitation.id),
              }">
              <div class="relative inline-flex items-center">
                <Icon name="fa6-solid:house-flag" class="display-inline mr-2" />
                {{ exploitation.token }}
              </div>
            </a>
          </li>
        </AtomsTabs>

        <div class="mb-3 flex flex-wrap justify-around gap-4 max-w-xl" :class="showExploitation ? 'mt-3' : ''">
          <AccountingReferenceCard index="01" icon="fa6-solid:tags" accent="#0d9488" accent-soft="#99f6e4"
            :title="t('pricing_block.accounting_concepts')"
            :description="t('pricing_block.accounting_concepts_description')" :loading="conceptsLoading"
            @check="openReferenceRegion('AccountingConcepts')" />

          <AccountingReferenceCard index="02" icon="fa6-solid:building" accent="#0369a1" accent-soft="#7dd3fc"
            :title="t('pricing_block.accounting_cost_centers')"
            :description="t('pricing_block.accounting_cost_centers_description')"
            @check="openReferenceRegion('AccountingCostCenters')" />
        </div>

        <AccountingPricingsBox ref="pricingsBox" :categories="accountingValues"
          :active-exploitation="activeExploitationTab" :show-exploitation="showExploitation"
          @create="openReferenceRegion('EditAccountingPricing', null)"
          @edit="(id) => openReferenceRegion('EditAccountingPricing', id)" />
      </div>
    </template>
  </div>

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 z-10 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden"
    :class="{
      'translate-x-0': showRegion,
      'translate-x-[2000px]': !showRegion,
      'w-[95%]': isSubRegionOpen,
      'w-[55%]': !isSubRegionOpen,
    }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full overflow-y-auto">
      <AccountingConceptsRegion v-if="regionComponent === 'AccountingConcepts'" :items="accountingConcepts"
        :categories="accountingValues" @show-subregion="handleSubRegionEvent" @close="toggleRegion(false)"
        @changed="refreshConcepts" />
      <AccountingCostCentersRegion v-if="regionComponent === 'AccountingCostCenters'" @close="toggleRegion(false)" />
      <EditAccountingPricing v-if="regionComponent === 'EditAccountingPricing'" :id="selectedItemId"
        @close="toggleRegion(false)" @changed="refreshPricings" />
    </div>
  </div>
</template>
