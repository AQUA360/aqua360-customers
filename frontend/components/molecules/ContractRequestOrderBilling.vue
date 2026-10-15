<script setup>
// components/molecules/ContractRequestOrderBilling.vue
import { ref, onMounted, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { format } from 'date-fns';
import { useToast } from 'vue-toastification';

import OrderEdit from '~/components/organisms/OrderEdit.vue'; // Assegura't que aquest component està importat
import OrderTypeDetail from '~/components/molecules/OrderTypeDetail.vue';
import { formatMoneyWithCurrency } from '~/utils/money';
import PriceRateSelectMultiple from '~/components/organisms/PriceRateSelectMultiple.vue';
import OrderRegion from '../organisms/OrderRegion.vue';
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import WorkOrderTypeSelectorModal from '~/components/molecules/WorkOrderTypeSelectorModal.vue';

const {
  $OrderTypeApiService,
  $BailTypeApiService,
  $PriceRateApiService,
  $ConfigProjectApiService,
  $ConfiglistApiService,
  $OrderApiService
} = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const { reasonId, resolved, getReasonId } = useOrderReasonId('order_reason_contract_activation');

const props = defineProps({
  request: {
    type: Object,
    required: false
  }
});

const emit = defineEmits(['change', 'show-subregion', 'refresh']);

const showRegion = ref(false);
const showRegionComponent = ref(null);
const regionDetailId = ref(null);
const isSubRegionOpen = ref(false);

const optionsBudgedLineItems = ref([
  { id: 1, token: 'alta', name: 'Alta de contracte', import: 100 }
  // Afegeix més conceptes segons sigui necessari
]);

const optionsBails = ref([]);

const allPriceRates = ref([]);
const priceRates = ref([]);
const priceRateSelectedItems = ref([]);

const selectedBudgetLineItem = ref([]);
const selectedBails = ref([]);

const isLoadingOrders = ref(false);
const loading = ref(true);

const origin_contract_token = ref(null)
const origin_reading_token = ref(null)
const origin_supply_token = ref(null)

// Definició de l'array per a orders (si no està definit)
const orderTypes = ref([]);
const orderStatuses = ref([]);
const order_types = ref([]); // Assegura't que existeix
const orders = ref([]);
const savingOrder = ref(false);
const workOrderSelectorOpen = ref(false);

const openAddOrderType = () => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddOrderType';
};

const openEditPriceRates = () => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'EditPriceRates';
}

const toggleRegion = (value) => {
  showRegion.value = value;
  if (!value) {
    closeAllRegions();
    regionDetailId.value = null;
    showRegionComponent.value = null;
  }
};

const showDetail = (component, id) => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = component;
  regionDetailId.value = id;
}

const closeAllRegions = () => {
  // Tanquem tots els components
  showRegionComponent.value = null;
  regionDetailId.value = null;
  // Tanquem region
  showRegion.value = false;
};

const emitChange = () => {
  let data = {
    line_items: selectedBudgetLineItem.value.length > 0 ? selectedBudgetLineItem.value : null,
    order_types: order_types.value.length > 0 ? order_types.value : "",
    registration_price_rates_ids: priceRateSelectedItems.value || null
  };

  emit('change', data);
};

const loadBailTypes = async () => {
  const response = await $BailTypeApiService.getAll();
  optionsBails.value = response.results;
};

const loadPriceRates = async () => {
  const dataResponse = await $PriceRateApiService.getAll();
  allPriceRates.value = dataResponse.results
}

const loadOrderTypes = async () => {
  const response = await $OrderTypeApiService.getAll();
  orderTypes.value = response.results;
}

const loadOrderStatuses = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('order/order-status');
    orderStatuses.value = response.results;
  } catch (error) {
    console.error('Error loading order statuses:', error);
  }
}

const loadData = async () => {
  loading.value = true;
  if (props.request) {
    // Assigna les dades del request si estan disponibles
    try {
      origin_contract_token.value = await $ConfigProjectApiService.get('origin_contract_token');
    } catch (error) {
      console.warn("ConfigProject 'origin_contract_token' not found", error);
    }
    try {
      origin_reading_token.value = await $ConfigProjectApiService.get('origin_reading_token');
    } catch (error) {
      console.warn("ConfigProject 'origin_reading_token' not found", error);
    }
    try {
      origin_supply_token.value = await $ConfigProjectApiService.get('origin_supply_token');
    } catch (error) {
      console.warn("ConfigProject 'origin_supply_token' not found", error);
    }
    await loadOrderTypes();
    await loadOrderStatuses();
    await loadBailTypes();
    await loadPriceRates();
    orders.value = props.request?.orders ? props.request.orders : [];
    syncOrderTypesFromOrders();

    // per defecte, haurien de sortir totes les opcions seleccionades
    selectedBudgetLineItem.value = optionsBudgedLineItems.value;
    selectedBails.value = props.request.bail_types || optionsBails.value;
    priceRates.value = props.request.registration_price_rates || [];
    priceRateSelectedItems.value = props.request.registration_price_rates.map(v => v.id) || [];
    // Afegeix més carregaments de dades si cal
    loading.value = false;
  }
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const orderUpdate = async () => {
  try {
    for (let order of orders.value) {
      let response = await $OrderApiService.getDetail(order.id);
      if (response) {
        orders.value = orders.value.map(o => o.id == order.id ? response : o);
      }
    }
  } catch (error) {
    console.error(error);
    toast.error(t('common.error_load'));
  } finally {
    loading.value = false;
  }
  console.log("orders.value");
  console.log(orders.value);
}

const syncOrderTypesFromOrders = () => {
  order_types.value = orders.value
    .filter(order => order.type?.id != null)
    .map(order => ({ label: order.type.name, value: order.type.id }));
};

const excludedOrderTypeIds = computed(() =>
  orders.value.map(order => order.type?.id).filter(id => id != null)
);

const linkedOrderTypes = computed(() => {
  if (!resolved.value || reasonId.value == null) return null;
  return orderTypes.value.filter(orderType =>
    orderType.reasons?.some(reason => reason.id == reasonId.value)
  );
});

const availableOrderTypes = computed(() =>
  linkedOrderTypes.value?.length ? linkedOrderTypes.value : []
);

const showAllTypesWarning = computed(() =>
  resolved.value
  && reasonId.value != null
  && !(linkedOrderTypes.value && linkedOrderTypes.value.length)
);

const openWorkOrderSelector = async () => {
  await getReasonId();
  workOrderSelectorOpen.value = true;
};

const createWorkOrder = async (orderType) => {
  const defaultOrderStatus = orderStatuses.value.find(s => s.is_default == true);
  const statusId = defaultOrderStatus?.id || orderStatuses.value?.[0]?.id;

  if (!orderType?.id || !statusId) {
    toast.error(t('warning_block.warning_order_type_not_found'));
    return null;
  }

  const reason_id = reasonId.value ?? await getReasonId();
  if (!reason_id) {
    toast.error(t('warning_block.warning_order_reason_not_found'));
    return null;
  }

  const order_data = {
    token: format(new Date(), 'yyyyMMddHHmmss'),
    contract_request: props.request.id,
    supply_point: props.request.supply_point_default?.id,
    type: orderType.id,
    status: statusId,
    requested_at: format(new Date(), 'yyyy-MM-dd HH:mm:ss'),
    reason: reason_id,
  };

  const order_saved = await $OrderApiService.save(order_data);
  return order_saved;
}

const onWorkOrderSelected = async (orderType) => {
  workOrderSelectorOpen.value = false;
  if (savingOrder.value) return;
  savingOrder.value = true;
  try {
    const order_saved = await createWorkOrder(orderType);
    if (order_saved) {
      orders.value.push(order_saved);
      syncOrderTypesFromOrders();
    }
  } catch (err) {
    console.error('Error creating order:', err?.data || err?.response?.data || err);
    toast.error(t('common.error'));
  } finally {
    savingOrder.value = false;
  }
}

const clickDeleteOrder = async (id) => {
  if (id) {
    try {
      let response = await $OrderApiService.deleteItem(id);
      if (response) {
        orders.value = orders.value.filter(order => order.id != id);
        syncOrderTypesFromOrders();
      }
    } catch (error) {
      console.error(error);
    }
  }
}

onMounted(() => {

  loadData();
});

// Observa canvis en la sol·licitud per recarregar les dades si cal
watch(() => props.request, (newVal) => {
  loadData();
});


watch(priceRateSelectedItems, async (newItems, oldItems) => {
  if (!loading.value) {
    priceRates.value = [];

    newItems.forEach(id => {
      const item = allPriceRates.value.find(pr => pr.id == id);
      if (item) {
        priceRates.value.push(item);
      }
    });
  }
  emitChange();
});

watch(order_types, () => {
  emitChange();
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <!-- Títol del Component -->
    <h2 class="text-xl font-semibold mb-4">{{ t('common.orders') }} {{ t('common.and') }} {{ t('billing') }}</h2>

    <!-- Orders -->
    <div class="mb-4 max-w-xl">
      <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon name="fa6-solid:asterisk" class="text-lg text-slate-600" />
        <span>{{ $t('order_block.orders_to_execute') }}</span>
        <abbr :title="t('informative_block.info_remaning_order_types')" class="flex items-center">
          <Icon name="fa6-solid:circle-info" class="text-slate-500" />
        </abbr>
      </label>

      <div v-if="orders.length > 0" class="mb-3">
        <div v-for="order in orders" :key="order.id"
          class="flex items-center justify-between max-w-xl bg-green-100 pt-1 px-2 mb-1">
          <MoleculesOrderTypeDetail :data="order.type" :order="order"
            @show-detail="showDetail" />
          <div class="text-slate-500 hover:text-red-500">
            <button @click="clickDeleteOrder(order.id)">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
        </div>
      </div>

      <ButtonOutline :disabled="savingOrder || loading" @click="openWorkOrderSelector">
        <Icon v-if="savingOrder" name="fa6-solid:spinner" class="animate-spin mr-2" />
        {{ $t('common.generate') }} {{ $t('common.work_order') }}
      </ButtonOutline>
    </div>

    <!-- /end Orders -->

    <!-- Pressupost -->
    <div class="mb-4 max-w-xl">

      <div class="mb-4 col-span-3">
        <label for="priceRate" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="priceRates.length != 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="priceRates.length == 0" name="fa6-solid:asterisk" class="text-lg text-pink-600" />
          <span>{{ $t('common.price_rates') }} {{ t('contracting') }} ({{ priceRates.length }})</span>
        </label>

        <div id="price_rate_templates" class="mb-3">
          <div class="pl-3 pr-3">
            <div class="mb-2 grid grid-cols-2 gap-3">
              <div v-for="item in priceRates" class="mb-1">
                <Icon name="fa6-solid:cube" class="text-slate-500" /> &nbsp;<span class="font-semibold">{{
                  item.product?.name || t('pricing_block.no_product') }}</span> - {{ item.name }}
              </div>
            </div>
            <button name="" class="button-default-xs" @click="showDetail('EditPriceRates', null)">
              <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
              {{ $t('common.modify') }} {{ t('common.products') }}/{{ t('common.price_rates') }}
            </button>
          </div>
        </div>
      </div>


    </div>
    <!-- /end Pressupost -->

    <!-- Regió lateral per formularis -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-1/2': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3 flex justify-start">
        <button @click="showRegion = false"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded" aria-label="Tancar formulari">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- Components per afegir informació -->

        <!-- <OrderEdit v-if="showRegionComponent == 'AddOrderType'" :contract_request="props.request"
          @selected-item="onOrderTypeSelected" @order-saved="onOrderSaved" /> -->
        <PriceRateSelectMultiple v-if="showRegionComponent === 'EditPriceRates'" v-model="priceRateSelectedItems"
          :filter="[origin_contract_token]" :exploitation_id="props.request?.type?.exploitation" />
        <OrderRegion v-if="showRegionComponent === 'OrderRegion'" :id="regionDetailId"
          @show-subregion="handleSubRegionEvent" @changed="orderUpdate" />
      </div>
    </div>
    <!-- /end Regió lateral per formularis -->

    <WorkOrderTypeSelectorModal v-model:open="workOrderSelectorOpen" :order-types="availableOrderTypes"
      :excluded-type-ids="excludedOrderTypeIds"
      :warning="showAllTypesWarning ? t('order_block.viewing_all_order_types_warning') : null"
      @select="onWorkOrderSelected" />
  </div>
</template>

<style scoped>
/* Estils addicionals per al component */
</style>
