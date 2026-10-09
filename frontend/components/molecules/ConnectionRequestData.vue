<script setup>
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import OrderTypeDetail from './OrderTypeDetail.vue';
import { format } from 'date-fns';

import { useToast } from 'vue-toastification';

const { $ConfiglistApiService, $DMAApiService, $TankApiService, $OrderApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  request: Object,
  hideOrder: Boolean
});

const emit = defineEmits(['change-data','current-order','show-detail']);

const loading = ref(true);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingTank = ref(false);

const selectedPerson = ref(null);

const latitude = ref(0)
const longitude = ref(0)

const blueprintUploaded = ref(null);

const connectionTypes = ref([]);
const connectionInstallationTypes = ref([]);
const connectionUseTypes = ref([]);
const connectionValveTypes = ref([]);
const connectionMaterials = ref([]);
const connectionDiameters = ref([]);
const connectionDMAs = ref([]);
const supplyTypes = ref([]);

const connectionRequestStatuses = ref([]);

const tanks = ref([]);
const tankId = ref(null);

const selectedConnectionType = ref(null);
const selectedConnectionInstallationType = ref(null);
const selectedConnectionUseType = ref(null);
const selectedConnectionValveType = ref(null);
const selectedConnectionMaterial = ref(null);
const selectedConnectionDiameter = ref(null);
const selectedConnectionDMA = ref(null);
const selectedConnectionTank = ref(null);
const selectedConnectionCodeGis = ref(null);
const selectedConnectionFlowRate = ref(0);
const selectedSupplyType = ref(null);

const closedOrderStatus = ref();

const order = ref(null);
const orderStatuses = ref([]);
const orderTypes = ref([]);
const orderTypeLandInspection = ref(null);
const landInspectionToken = ref('land_inspection');

const closeAllRegions = () => {
  // tanquem tots els components
  editingTank.value = false;

  // tanquem region
  showRegion.value = false;
};

const updateSelect = (ev, entity) => {
  switch (entity) {
    case 'connection-type':
      selectedConnectionType.value = ev;
      break;
    case 'connection-use-type':
      selectedConnectionUseType.value = ev;
      break;
    case 'connection-valve-type':
      selectedConnectionValveType.value = ev;
      break;
    case 'connection-material':
      selectedConnectionMaterial.value = ev;
      break;
    case 'connection-diameter':
      selectedConnectionDiameter.value = ev;
      break;
    case 'connection-request-status':
      selectedConnectionStatus.value = ev;
      break;
    case 'connection-dma':
      selectedConnectionDMA.value = ev;
      break;
    case 'connection-tank':
      selectedConnectionTank.value = ev;
      break;
    case 'connection-installation-type':
      selectedConnectionInstallationType.value = ev;
      break;
    case 'supply-type':
      selectedSupplyType.value = ev;
      break;
  }

  emitChange()

};

const emitChange = () => {
  let data = {
    code_gis: selectedConnectionCodeGis.value || null,
    flow_rate: selectedConnectionFlowRate.value || null,
    dma: selectedConnectionDMA.value?.code || null,
    type: selectedConnectionType.value?.code || null,
    installation_type: selectedConnectionInstallationType.value?.code || null,
    use_type: selectedConnectionUseType.value?.code || null,
    valve_type: selectedConnectionValveType.value?.code || null,
    diameter: selectedConnectionDiameter.value?.code || null,
    material: selectedConnectionMaterial.value?.code || null,
    tank: selectedConnectionTank.value?.code || null,
    supply_type: selectedSupplyType.value?.code || null
  }
  emit('change-data', data);
}

const editTank = (edit = false) => {
  closeAllRegions();
  if (edit) {
    tankId.value = selectedConnectionTank.value?.code;
  }
  else {
    tankId.value = null;
  }
  editingTank.value = true;
  showRegion.value = true;
};

const showDetail = (component, id) => {
  emit('show-detail', component, id);
}

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll('service/' + entity);
    targetArray.value = [];

    if (data.results) {
      data.results.forEach(data => {
        targetArray.value.push({
          label: data.name || data.token,
          code: data.id
        })
      });
    }
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

const fetchSelectData = async ($api, targetArray) => {
  try {
    const data = await $api.getAll();

    targetArray.value = [];

    if (data.results) {
      data.results.forEach(data => {
        targetArray.value.push({
          label: data.name || data.token,
          code: data.id
        })
      });
    }
  } catch (error) {
    console.error(`Error fetchSelectData ${entity}:`, error);
  }
}

const fetchTank = (tank) => {
  // hem d'actualitzar el select de tanks

  let newTank = {
    code: tank.id,
    label: tank.name || tank.token
  }

  tanks.value.push(newTank);
  selectedConnectionTank.value = newTank;
  closeAllRegions();
}

const loadData = async (getAll = true) => {
  if (getAll) {
    try {
      loading.value = true
      await fetchConfigData('connection-type', connectionTypes);
      await fetchConfigData('connection-installation-type', connectionInstallationTypes);
      await fetchConfigData('connection-use-type', connectionUseTypes);
      await fetchConfigData('connection-valve-type', connectionValveTypes);
      await fetchConfigData('connection-material', connectionMaterials);
      await fetchConfigData('connection-diameter', connectionDiameters);
      await fetchConfigData('connection-request-status', connectionRequestStatuses);
      await fetchConfigData('supply-point-supply-type', supplyTypes);
      await fetchSelectData($DMAApiService, connectionDMAs);
      await fetchSelectData($TankApiService, tanks);

      const order_types = await $ConfiglistApiService.getAll('order/order-type');
      orderTypes.value = order_types.results;
      const order_type_token = await $ConfigProjectApiService.get('order_type_land_inspection_token');
      if (order_type_token) landInspectionToken.value = order_type_token;
      orderTypeLandInspection.value = order_types.results.find(item => item.token == landInspectionToken.value);
      if (!orderTypeLandInspection.value) {
        // Fallback: try to find by name if token fails
        orderTypeLandInspection.value = order_types.results.find(item => {
          const n = (item.name || '').toLowerCase();
          return n.includes('inspecció') && n.includes('pressupost');
        });
      }
      const order_statuses = await $ConfiglistApiService.getAll('order/order-status');
      orderStatuses.value = order_statuses.results;
      const closed_order_status = await $ConfigProjectApiService.get('order_status_completed_token');
      closedOrderStatus.value = orderStatuses.value.find(item => item.token == closed_order_status);
    } catch (error) {
      console.error("Error loading draft:", error);
    } finally {
      loading.value = false;
    }
  }
  if (props.request) {
    if (props.request.person) {
      selectedPerson.value = props.request.person;
    }
    latitude.value = props.request.latitude;
    longitude.value = props.request.longitude;
    blueprintUploaded.value = props.request.blueprint;
    
    selectedConnectionCodeGis.value = props.request.code_gis;
    selectedConnectionFlowRate.value = props.request.flow_rate;
    selectedConnectionDMA.value = props.request.dma ? { code: props.request.dma.id, label: props.request.dma.name || props.request.dma.token } : null;
    selectedConnectionType.value = props.request.type ? { code: props.request.type.id, label: props.request.type.name || props.request.type.token } : null;
    selectedConnectionInstallationType.value = props.request.installation_type ? { code: props.request.installation_type.id, label: props.request.installation_type.name || props.request.installation_type.token } : null;
    selectedConnectionUseType.value = props.request.use_type ? { code: props.request.use_type.id, label: props.request.use_type.name || props.request.use_type.token } : null;
    selectedConnectionValveType.value = props.request.valve_type ? { code: props.request.valve_type.id, label: props.request.valve_type.name || props.request.valve_type.token } : null;
    selectedConnectionDiameter.value = props.request.diameter ? { code: props.request.diameter.id, label: props.request.diameter.name || props.request.diameter.token } : null;
    selectedConnectionMaterial.value = props.request.material ? { code: props.request.material.id, label: props.request.material.name || props.request.material.token } : null;
    selectedConnectionTank.value = props.request.tank ? { code: props.request.tank.id, label: props.request.tank.name || props.request.tank.token } : null;
    selectedSupplyType.value = props.request.supply_type ? { code: props.request.supply_type.id, label: props.request.supply_type.name || props.request.supply_type.token } : null;
    if (!props.hideOrder) getOrder();
  }
  emitChange();
  loading.value = false;
};

const getOrder = async () => {
  console.log('getOrder', props.request.id);
  try {
    const order_response = await $OrderApiService.getFilterConnectionRequest(props.request.id);
    
    // Filter by ID if we have the type resolved, otherwise by token
    if (orderTypeLandInspection.value) {
      order.value = order_response.find(item => item.type?.id == orderTypeLandInspection.value.id);
    } else {
      order.value = order_response.find(item => item.type?.token == landInspectionToken.value);
    }

    if (order.value) {
      const res = {
        order: order.value,
        warning: order.value.status?.id != closedOrderStatus.value?.id
      }

      emit('current-order', res);
    }
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false;
  }
}

const generateWorkOrder = async () => {
  try {
    const order_saved = await createOrderLandInspection();
    if (order_saved) {
      order.value = order_saved;
    } else {
      await getOrder();
    }
    emitChange()
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  }
};

const createOrderLandInspection = async () => {
  if (!orderTypeLandInspection.value) {
    toast.error(t('warning_block.warning_order_type_not_found') + ': ' + landInspectionToken.value);
    return;
  }

  const defaultOrderStatus = orderStatuses.value.find(s => s.is_default == true);
  const statusId = defaultOrderStatus?.id || orderStatuses.value[0]?.id;

  if (!statusId) {
    toast.error(t('warning_block.warning_order_status_not_found'));
    return;
  }

  const description = `${t("address_block.location")}: ${props.request.address_complete || ''}\n` +
    `${t("connection")}:\n` +
    `- ${t("common.type")}: ${props.request.type?.name || ''}\n` +
    `- ${t("common.usage_type")}: ${props.request.use_type?.name || ''}\n` +
    `- ${t("service_block.material")}: ${props.request.material?.name || ''}\n` +
    `- ${t("service_block.diameter")}: ${props.request.diameter?.name || ''}\n` +
    `- ${t("service_block.valve_type")}: ${props.request.valve_type?.name || ''}\n` +
    `- ${t("service_block.installation_type")}: ${props.request.installation_type?.name || ''}`;

  const order_data = {
    token: format(new Date(), 'yyyyMMddHHmmss'),
    connection_request: props.request.id,
    type: orderTypeLandInspection.value.id,
    status: statusId,
    requested_at: format(new Date(), 'yyyy-MM-dd HH:mm:ss'),
    latitude: props.request.latitude,
    longitude: props.request.longitude,
    description: description
  }

  const order_saved = await $OrderApiService.save(order_data);
  return order_saved;
}

const clickDeleteOrder = async (id) => {
  if (id && confirm(t('confirmation_text_block.confirm_deactivate'))) {
    try {
      await $OrderApiService.deleteItem(id);
      order.value = null;
      emit('current-order', { order: null, warning: false });
      emitChange();
      toast.success(t('common.deleted_successfully'));
    } catch (error) {
      console.error('Error deleting order:', error);
      toast.error(t('common.error_delete'));
    }
  }
}

onMounted(() => {
  loadData();
});

watch(() => props.request, (newVal) => {
  // console.log('watch props.request', newVal);
  loadData(false)
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <h2 class="text-xl font-semibold mb-4"><span v-if="!hideOrder">{{ $t('billing_block.step') }} 2: </span>{{ $t('service_block.connection_data') }}</h2>

    <div class="row grid grid-cols-4 gap-3">

      <div class="field mb-4">
        <label for="dma" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.dma') }}</label>
        <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedConnectionDMA" :disabled="loading"
          @update:modelValue="updateSelect($event, 'connection-dma')" :options="connectionDMAs" />
      </div>

      <div class="mb-4">
        <label for="connection-type" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('common.type') }}</label>
        <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedConnectionType" :disabled="loading"
          @update:modelValue="updateSelect($event, 'connection-type')" :options="connectionTypes" />
      </div>

      <div class="mb-4">
        <label for="supply-type" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.supply_type') }}</label>
        <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedSupplyType" :disabled="loading"
          @update:modelValue="updateSelect($event, 'supply-type')" :options="supplyTypes" />
      </div>

      <div class="field mb-4">
        <label for="connection-use-type" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('common.usage_type')
        }}</label>
        <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedConnectionUseType" :disabled="loading"
          @update:modelValue="updateSelect($event, 'connection-use-type')" :options="connectionUseTypes" />
      </div>

      <div class="field mb-4" v-if="!request || (request && (request.installation_type == null || request.installation_type == undefined)) || (request && (!request.supply_points || request.supply_points.length == 0))">
        <label for="connection-installation-type" class="block text-sm font-medium text-gray-700 mb-2">
          {{ $t(`service_block.installation_type`) }}</label>
        <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedConnectionInstallationType"
          :disabled="loading" @update:modelValue="updateSelect($event, 'connection-installation-type')"
          :options="connectionInstallationTypes" />
      </div>

      <div class="field mb-4">
        <label for="tank" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.tank') }} {{ $t('common.and') }} {{ $t('service_block.volume') }}</label>

        <div class="flex">
          <v-select id="tank" :loading="loading" class="block w-full required" :model-value="selectedConnectionTank" :disabled="loading"
            @update:modelValue="updateSelect($event, 'connection-tank')" :options="tanks" />
          <button
            class="w-9 h-9 border-gray-300 border border-r-0 text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200 flex items-center justify-center"
            :disabled="selectedConnectionTank == null || loading" @click="editTank(true)">
            <Icon name="fa6-solid:pencil" class="text-md" />
          </button>
          <button :disabled="loading"
            class="w-9 h-9 border-gray-300 border rounded-r disabled:bg-slate-200 disabled:text-slate-400  enabled:hover:bg-slate-200 transition-all duration-200 flex items-center justify-center"
            @click="editTank(false)">
            <Icon name="fa6-solid:plus" class="text-md text-slate-600" />
          </button>
        </div>
      </div>

      <div class="mb-4">
        <label for="connection-diameter" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.diameter')
        }}</label>
        <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedConnectionDiameter" :disabled="loading"
          @update:modelValue="updateSelect($event, 'connection-diameter')" :options="connectionDiameters" />
      </div>

      <div class="mb-4">
        <label for="flow_rate" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.flow_rate')
        }}</label>
        <div class="flex items-stretch">
          <input type="text" v-model="selectedConnectionFlowRate" v-numeric-only @change="emitChange"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-l-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
          <span
            class="px-3 bg-slate-200 rounded-r leading-8 border-gray-300 border-y border-r whitespace-nowrap">l/s</span>
        </div>
      </div>

      <div class="mb-4">
        <label for="connection-material" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.material')
        }}</label>
        <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedConnectionMaterial" :disabled="loading"
          @update:modelValue="updateSelect($event, 'connection-material')" :options="connectionMaterials" />
      </div>

      <div class="mb-4">
        <label for="connection-valve-type" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.valve_type')
        }}</label>
        <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedConnectionValveType" :disabled="loading"
          @update:modelValue="updateSelect($event, 'connection-valve-type')" :options="connectionValveTypes" />
      </div>

      <div v-if="!hideOrder" class="field mb-4">
        <label for="code_gis" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.gis_code') }}</label>
        <input type="text" v-model="selectedConnectionCodeGis" @change="emitChange"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>

    </div><!-- end row -->
    <!-- <hr class="my-2"> -->
    <div v-if="!hideOrder">
      <label for="order_land_inspection" class="block text-sm font-medium text-gray-700 mb-2">
        {{ t('order') }}: {{ $t('order_block.terrain_inspection') }}</label>
      <ButtonOutline v-if="!order" @click="generateWorkOrder">
        {{ $t('common.generate') }} {{ $t('common.work_order') }}
      </ButtonOutline>
      <div v-else class="flex items-center justify-between max-w-xl bg-green-100 pt-1 px-2 mb-1">
        <OrderTypeDetail :data="order.type" :order="order" @show-detail="showDetail('OrderRegion', order.id)" />
        <div class="flex items-center">
          <button @click="clickDeleteOrder(order.id)" class="text-slate-500">
            <Icon name="fa6-solid:trash" />
          </button>
        </div>
      </div>
    </div>
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <OrganismsTankEdit :id="tankId" v-if="editingTank" @saved="fetchTank" />
      </div>
    </div>
  </div>
</template>
<style>
#tank.v-select .vs__dropdown-toggle {
  border-radius: 0.375rem 0 0 0.375rem;
  padding-bottom: 0;
  border-right: none;
}

#tank.v-select .vs__actions {
  border-radius: 0 0.375rem 0.375rem 0;
}
</style>