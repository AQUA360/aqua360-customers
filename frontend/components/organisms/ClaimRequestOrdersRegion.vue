<script setup>
import { useToast } from 'vue-toastification';
import { formatDate } from '~/utils/date';
import OrderRegion from './OrderRegion.vue';
import ContractRegion from './ContractRegion.vue';

const props = defineProps({
  request: Object,
  orderType: String,
  isSubRegionOpen: Boolean
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close', 'show-subregion']);
const { $ClaimRequestApiService } = useNuxtApp();

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const loading = ref(false);
const orders = ref([]);

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = async function (component, id) {
  await closeSubRegion()
  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  showSubRegion();
}

// Carregar les ordres associades a la reclamació
const loadOrders = async () => {
  loading.value = true;
  try {
    const response = await $ClaimRequestApiService.getClaimRequestOrders(props.request.id, props.orderType);
    orders.value = response.results || [];
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// Carregar les ordres al iniciar
onMounted(async () => {
  await loadOrders();
});
</script>

<template>
  <div class="region__content">
    <div class="h-full flex flex-col transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-lg font-semibold">{{ $t('work_orders') }}</h3>
        <!-- <button @click="$emit('close')" class="text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button> -->
      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="loading" class="flex justify-center items-center h-full">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl" />
        </div>
        <div v-else>
          <div v-if="orders.length === 0" class="text-gray-500 text-center py-4">
            {{ $t('common.no_data_found') }}
          </div>
          <div v-else class="ml-4 mt-4">
            <div class="grid grid-cols-6 gap-3 border-b text-slate-500 py-1">
              <div>{{ $t('common.identification') }}</div>
              <div>{{ $t('common.type') }}</div>
              <div>{{ $t('common.date') }}</div>
              <div>{{ $t('common.status') }}</div>
              <div>{{ $t('contract') }}</div>
              <div>{{ $t('contract_block.holder') }}</div>
            </div>
            <div v-for="order in orders" :key="order.id" class="grid grid-cols-6 gap-3 py-1">
              <div>
                <button class="text-sky-500 hover:text-sky-700 w-full" @click="showDetail('OrderRegion', order.id)">
                  <span class="truncate block">
                    {{ order.token }}
                  </span>
                </button>
              </div>
              <div>{{ order.type.name }}</div>
              <div>{{ formatDate(order.created_at) }}</div>
              <div>
                <AtomsColorBadge :value="order.status?.name || order.status?.token" :color="order.status?.color" />
              </div>
              <div>
                <button class="text-sky-500 hover:text-sky-700" @click="showDetail('ContractRegion', order.contract?.id)">
                  <span class="truncate">
                    {{ order.contract?.token || '-' }}
                  </span>
                </button>
              </div>
              <div>{{ order.contract?.holder_token || '-' }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 py-2 text-base bg-white transition-all duration-500 ease fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <OrderRegion v-if="showRegionDetailComponent === 'OrderRegion'" :id="regionDetailId" :isSubRegion="true" />

      </div>
    </div>
  </div>
</template>