<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import _ from 'lodash';
import SupplyPointDetail from '~/components/molecules/SupplyPointDetail.vue';
import ConnectionDetail from '../molecules/ConnectionDetail.vue';
import { useToast } from 'vue-toastification';
import ContractDetail from '../molecules/ContractDetail.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const props = defineProps({
  id: Number,
  order: {
    type: Object,
    required: false
  },
  incident_id: {
    type: Number,
    required: false
  },
  contract_id: {
    type: Number,
    required: false
  }
});

const config = useRuntimeConfig();
const externalGot = String(config.public.externalGot).toLowerCase() === 'true';

const originalToken = ref('')

const selected_order = ref(null);

const { t } = useI18n();
const { $OrderApiService, $ObservationApiService } = useNuxtApp();
const { $OperatorApiService } = useNuxtApp();
const { $OrderTypeApiService } = useNuxtApp();
const { $ConfiglistApiService } = useNuxtApp();
const { $OrderPriorityApiService } = useNuxtApp();
const { $PropertyApiService } = useNuxtApp();
const { $SupplyPointApiService } = useNuxtApp();
const { $ConnectionApiService } = useNuxtApp();

const pendingObservations = ref([]);

const { $ContractApiService } = useNuxtApp();
const toast = useToast();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);


const item = ref(null);
const token = ref(null);

const selectedOperators = ref([])
const selectedType = ref(null)
const selectedReason = ref(null)
const selectedStatus = ref(null)
const selectedSupplyPoint = ref(null)
const selectedConnection = ref(null)
const selectedAddress = ref(null)
const selectedContract = ref(null)
const linkedContract = ref(null) // contracte derivat de contract_id (incidència/contracte d'origen), per reutilitzar dades en canviar de radiobutton

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingSupplyPoints = ref(false);
const editingConnection = ref(false);
const editingAddress = ref(false);
const editingContract = ref(false);

const operators = ref([])
const order_type = ref([])
const order_reason = ref([])  

const orderStatuses = ref([]);
const orderStatus = ref(null);

const priorities = ref([]);
const selectedPriority = ref(null);
const dueDate = ref(null);
const description = ref('');

// Geolocation fields
const latitude = ref(null);
const longitude = ref(null);
const updatePropertyGeolocation = ref(true);
const updateConnectionGeolocation = ref(true);

const descriptionLength = computed(() => description.value.length);

const hasCoordinates = computed(() =>
  !isNaN(parseFloat(latitude.value)) && !isNaN(parseFloat(longitude.value))
);

const updateDescription = (val) => {
  description.value = val.substring(0, 700);
};

const locationTypeRadio = ref('SP');

// Suppress the locationTypeRadio watch when restoring state from loaded order data
const suppressLocationWatch = ref(false);

watch(locationTypeRadio, (newVal, oldVal) => {
  if (suppressLocationWatch.value || newVal === oldVal) return;
  // No esborrem les seleccions dels altres tipus en canviar de radiobutton, es mantenen
  // per si l'usuari torna a seleccionar-los. Només s'omplen valors si falten.
  if (newVal === 'CON' && !selectedContract.value && linkedContract.value) {
    selectedContract.value = linkedContract.value;
    if (!selectedSupplyPoint.value) {
      selectedSupplyPoint.value = linkedContract.value.supply_point_default ?? null;
    }
  } else if (newVal === 'SP' && !selectedSupplyPoint.value && linkedContract.value) {
    selectedSupplyPoint.value = linkedContract.value.supply_point_default ?? null;
  }
}, { flush: 'sync' });

const loadFromDetail = async (data) => {
  selected_order.value = data.connection;
}

const emit = defineEmits(['changed']);

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll(entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

const getData = async () => {
  loading.value = true;

  try {
    await fetchConfigData('order/order-status', orderStatuses);
    await getPriorities();
  } 
  catch (error) {
    console.error('Error loading draft:', error);
  }

  if (props.id) {
    item.value = await $OrderApiService.getDetail(props.id);
    token.value = item.value.token;
    originalToken.value = token.value
    selectedOperators.value = [];
    item.value.operators.forEach(operator => {
      // Build label with token, name, and surname
      let labelParts = [];
      if (operator.token) labelParts.push(operator.token);
      if (operator.name) labelParts.push(operator.name);
      if (operator.surname) labelParts.push(operator.surname);
      
      selectedOperators.value.push({
        code: operator.id,
        label: labelParts.join(' - ')
      });
    });
    selectedType.value = [];
    selectedType.value.push({
      code: item.value.type.id,
      label: item.value.type.name
    });
    selectedStatus.value = [];
    selectedStatus.value.push({
      code: item.value.status.id,
      label: item.value.status.name
    });
    if (item.value.reason) {
      selectedReason.value = {
        code: item.value.reason.id,
        label: item.value.reason.name
      };
    }
    selectedSupplyPoint.value = null;
    selectedSupplyPoint.value = item.value.supply_point;

    selectedConnection.value = null;
    selectedConnection.value = item.value.connection;

    selectedAddress.value = null;
    selectedAddress.value = item.value.address;

    selectedContract.value = null;
    selectedContract.value = item.value.contract;

    // Restore locationTypeRadio — priority: contract > supply_point > connection > address
    // Use suppressLocationWatch to avoid clearing the refs we just assigned above
    suppressLocationWatch.value = true;
    if (item.value.contract) {
      locationTypeRadio.value = 'CON';
    } else if (item.value.supply_point) {
      locationTypeRadio.value = 'SP';
    } else if (item.value.connection) {
      locationTypeRadio.value = 'C';
    } else if (item.value.address) {
      locationTypeRadio.value = 'A';
    } else if (item.value.latitude && item.value.longitude) {
      locationTypeRadio.value = 'G';
    } else {
      locationTypeRadio.value = 'SP';
    }
    suppressLocationWatch.value = false;

    orderStatus.value = item.value.status;

    // Set priority if exists
    if (item.value.priority) {
      selectedPriority.value = {
        code: item.value.priority.id,
        label: item.value.priority.name,
        color: item.value.priority.color
      };
    }

    // Set due date if exists
    if (item.value.dueDateAt) {
      dueDate.value = item.value.dueDateAt;
    }

    // Set description if exists
    if (item.value.description) {
      description.value = item.value.description;
    }

    // Set coordinates if exists
    if (item.value.latitude) {
      latitude.value = parseFloat(item.value.latitude);
    }
    if (item.value.longitude) {
      longitude.value = parseFloat(item.value.longitude);
    }

  } 
  else {
    item.value = {};
    description.value = '';
    const defaultStatus = orderStatuses.value.find(s => s.is_default == true);
    if (defaultStatus) {
      selectedStatus.value = {
        label: defaultStatus.name,
        code: defaultStatus.id
      };
    }

    if (props.contract_id) {
      try {
        // Es vincula l'ordre al punt de subministrament del contracte, no al contracte,
        // per evitar exposar dades sensibles del contracte des d'aquests fluxos.
        // Es guarda el contracte per si l'usuari canvia manualment el radiobutton a "Contracte".
        const fullContract = await $ContractApiService.getDetail(props.contract_id);
        linkedContract.value = fullContract;
        selectedSupplyPoint.value = fullContract.supply_point_default ?? null;
        suppressLocationWatch.value = true;
        locationTypeRadio.value = 'SP';
        suppressLocationWatch.value = false;
      } catch (err) {
        console.error('Error fetching contract detail:', err);
      }
    }
  }

  getTypes();
  if (selectedType.value) {
    let typeId = selectedType.value[0].code
    getReasons(typeId)
  }
  getStatuses();
  getOperators();
  loading.value = false;
}

const newAddress = (new_address) => {
  selectedAddress.value = new_address;
  closeAllRegions();
}

const editAddress = (selAd) => {
  if (selAd) {
    selectedAddress.value = selAd;
    openRegion('addresses');
  }
  else {
    selectedAddress.value = null;
  }
}

const deleteAddress = () => {
  selectedAddress.value = null;
};

const deleteSupplyPoint = () => {
  selectedSupplyPoint.value = null;
};

const deleteConnection = () => {
  selectedConnection.value = null;
};

const getTypes = async () => {
  const response = await $OrderTypeApiService.getAll();
  order_type.value = [];

  response.results.forEach(function (item) {
    order_type.value.push({
      label: item.name,
      code: item.id
    })
  })
}

const getReasons = async (typeId) => {
  let reasons = await getOrderTypeReasons(typeId);
  order_reason.value = reasons;
}

const getOrderTypeReasons = async (typeId) => {
  const response = await $OrderTypeApiService.getDetail(typeId);
  let order_type_reasons = [];
  response.reasons.forEach(function (item) {
    order_type_reasons.push({
      label: item.name,
      code: item.id
    })
  })
  return order_type_reasons
}

const getStatuses = async () => {
  const response = await $ConfiglistApiService.getAll('order/order-status');
  orderStatuses.value = [];

  response.results.forEach(function (item) {
    orderStatuses.value.push({
      label: item.name,
      code: item.id
    })
  })
}

const getOperators = async () => {
  const response = await $OperatorApiService.getAll();
  operators.value = [];
  response.results.forEach(function (item) {
    // Build label with token, name, and surname
    let labelParts = [];
    if (item.token) labelParts.push(item.token);
    if (item.name) labelParts.push(item.name);
    if (item.surname) labelParts.push(item.surname);
    
    operators.value.push({
      label: labelParts.join(' - '),
      code: item.id
    })
  })
}

const getPriorities = async () => {
  try {
    const response = await $OrderPriorityApiService.getAll();
    priorities.value = [];
    response.results.forEach(function (item) {
      priorities.value.push({
        label: item.name,
        code: item.id,
        color: item.color
      })
    })
  } catch (error) {
    console.error('Error fetching priorities:', error);
  }
}

const addPendingObservation = (text) => {
  if (text?.trim()) {
    pendingObservations.value.push(text);
  }
}

const removePendingObservation = (index) => {
  pendingObservations.value.splice(index, 1);
}

const save = async () => {
  attemptedSave.value = true;
  if (isValid()) {
    saving.value = true;

    // Handle both array (when editing) and object (when creating) formats
    const typeCode = Array.isArray(selectedType.value) ? selectedType.value[0]?.code : selectedType.value?.code;
    const statusCode = Array.isArray(selectedStatus.value) ? selectedStatus.value[0]?.code : selectedStatus.value?.code;

    const selectedOptions = {
      id: props.id,
      token: token.value,
      operators: selectedOperators.value.map(operator => operator.code),
      type: typeCode,
      reason: selectedReason.value ? selectedReason.value.code : null,
      status: statusCode
    };
    
    // Add optional fields
    if (selectedPriority.value) {
      selectedOptions.priority = selectedPriority.value.code;
    }
    if (dueDate.value) {
      selectedOptions.dueDateAt = dueDate.value;
    }
    // Always include description, send null if empty
    selectedOptions.description = description.value || null;
    
    // Add coordinates if set - format to max 6 decimal places (9 total digits max for backend)
    selectedOptions.latitude = latitude.value ? parseFloat(latitude.value).toFixed(6) : null;
    selectedOptions.longitude = longitude.value ? parseFloat(longitude.value).toFixed(6) : null;
    
    if (props.incident_id) {
      selectedOptions.incident = props.incident_id;
    }
    if (locationTypeRadio.value == 'SP') {
      selectedOptions.supply_point = selectedSupplyPoint.value ? selectedSupplyPoint.value.id : null;
      selectedOptions.connection = null;
      selectedOptions.address = null;
      selectedOptions.contract = null;
    }
    else if (locationTypeRadio.value == 'C') {
      selectedOptions.connection = selectedConnection.value ? selectedConnection.value.id : null;
      selectedOptions.supply_point = null;
      selectedOptions.address = null;
      selectedOptions.contract = null;
    }
    else if (locationTypeRadio.value == 'A') {
      selectedOptions.address = selectedAddress.value;
      selectedOptions.supply_point = null;
      selectedOptions.connection = null;
      selectedOptions.contract = null;
    }
    else if (locationTypeRadio.value == 'CON') {
      selectedOptions.contract = selectedContract.value ? selectedContract.value.id : null;
      selectedOptions.supply_point = selectedContract.value?.supply_point_default?.id ?? null;
      selectedOptions.connection = null;
      selectedOptions.address = null;
    }
    else if (locationTypeRadio.value == 'G') {
      // Ubicació només per coordenades: no es vincula l'ordre a cap entitat
      selectedOptions.supply_point = null;
      selectedOptions.connection = null;
      selectedOptions.address = null;
      selectedOptions.contract = null;
    }
    try {
      item.value = await $OrderApiService.save(selectedOptions);
      
      // Save pending observations if any (for new orders)
      if (pendingObservations.value.length > 0 && item.value?.id) {
        for (const obs of pendingObservations.value) {
          try {
            await $ObservationApiService.postObservation({
              observation: obs,
              order: item.value.id
            }, 'order', 'order');
          } catch (obsError) {
            console.error('Error saving observation:', obsError);
          }
        }
      }
      if (updatePropertyGeolocation.value && 
          locationTypeRadio.value == 'SP' && 
          selectedSupplyPoint.value && 
          (latitude.value || longitude.value)) {
        try {
          // Fetch supply point detail to get property id
          const spDetail = await $SupplyPointApiService.getDetail(selectedSupplyPoint.value.id);
          if (spDetail?.property?.id) {
            await $PropertyApiService.save({
              id: spDetail.property.id,
              latitude: latitude.value ? parseFloat(latitude.value).toFixed(6) : null,
              longitude: longitude.value ? parseFloat(longitude.value).toFixed(6) : null
            });
          }
        } catch (propertyError) {
          console.error('Error updating property geolocation:', propertyError);
        }
      }
      
      // Update connection geolocation if checkbox is checked and connection is selected
      if (updateConnectionGeolocation.value && 
          locationTypeRadio.value == 'C' && 
          selectedConnection.value && 
          (latitude.value || longitude.value)) {
        try {
          await $ConnectionApiService.save({
            id: selectedConnection.value.id,
            latitude: latitude.value ? parseFloat(latitude.value).toFixed(6) : null,
            longitude: longitude.value ? parseFloat(longitude.value).toFixed(6) : null
          });
        } catch (connectionError) {
          console.error('Error updating connection geolocation:', connectionError);
        }
      }
      
      if (props.incident_id) {
        emit('changed');
      } else {
        return navigateTo('/order/orders/')
      }
    } finally {
      saving.value = false;
    }
  }
}

const deleteItem = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    try {
      await $OrderApiService.deleteItem(props.id);
      return navigateTo('/order/orders/')
    } finally {
      saving.value = false;
    }
  }
}

const isValid = () => {
  // Handle both array (when editing) and object (when creating) formats
  const typeCode = Array.isArray(selectedType.value) ? selectedType.value[0]?.code : selectedType.value?.code;
  const statusCode = Array.isArray(selectedStatus.value) ? selectedStatus.value[0]?.code : selectedStatus.value?.code;
  
  if (locationTypeRadio.value == 'G' && !hasCoordinates.value) {
    return false;
  }

  return typeCode != null && typeCode > 0 && statusCode != null && statusCode > 0;
}

onMounted(() => {
  getData()
  if (props.order) {
    loadFromDetail();
  }
});

const supplyPointClicked = (supplyPoint) => {
  selectedSupplyPoint.value = supplyPoint;
  
  // Fill geolocation if not set and available in supply point property
  if (!latitude.value && !longitude.value) {
    let hasCoords = false;
    if (supplyPoint?.property?.latitude) {
      latitude.value = parseFloat(supplyPoint.property.latitude);
      hasCoords = true;
    }
    if (supplyPoint?.property?.longitude) {
      longitude.value = parseFloat(supplyPoint.property.longitude);
      hasCoords = true;
    }
    
    // Deactivate update checkbox if filled by default
    if (hasCoords) {
      updatePropertyGeolocation.value = false;
    }
  }
  
  closeAllRegions();
}

const connectionClicked = (connection) => {
  selectedConnection.value = connection;
  
  // Fill geolocation if not set and available in connection
  if (!latitude.value && !longitude.value) {
    let hasCoords = false;
    if (connection?.latitude) {
      latitude.value = parseFloat(connection.latitude);
      hasCoords = true;
    }
    if (connection?.longitude) {
      longitude.value = parseFloat(connection.longitude);
      hasCoords = true;
    }
    
    // Deactivate update checkbox if filled by default
    if (hasCoords) {
      updateConnectionGeolocation.value = false;
    }
  }
  
  closeAllRegions();
}


const contractClicked = async (contract) => {
  try {
    const fullContract = await $ContractApiService.getDetail(contract.id);
    selectedContract.value = fullContract;
    selectedSupplyPoint.value = fullContract.supply_point_default ?? null;
  } catch (err) {
    console.error('Error fetching contract detail:', err);
    selectedContract.value = contract;
    selectedSupplyPoint.value = null;
  }
  closeAllRegions();
}

const deleteContract = () => {
  selectedContract.value = null;
  selectedSupplyPoint.value = null;
};

const openRegion = (region) => {
  closeAllRegions();

  if (region == 'supply_points') {
    editingSupplyPoints.value = true;
  } else if (region == 'connections') {
    editingConnection.value = true;
  } else if (region == "addresses") {
    editingAddress.value = true;
  } else if (region == 'contracts') {
    editingContract.value = true;
  }
  showRegion.value = true;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const closeAllRegions = () => {
  // tanquem tots els components
  editingSupplyPoints.value = false;
  editingConnection.value = false;
  editingAddress.value = false;
  editingContract.value = false;
  // tanquem region
  showRegion.value = false;
};



const updateSelect = async (event, entity) => {
  switch (entity) {
    case 'operators':
      selectedOperators.value = event;
      break;
    case 'order_type':
      selectedType.value = event;
      selectedReason.value = null;
      if (selectedType) {
        order_reason.value = await getOrderTypeReasons(selectedType.value.code);
      }
      break;
    case 'order_status':
      selectedStatus.value = event;
      break;
    case 'order_reason':
      selectedReason.value = event;
      break;
    case 'priority':
      selectedPriority.value = event;
      break;
  }
}

const onIdLostFocus = async () => {
  if (token.value != null && token.value != '' && token.value != originalToken.value) { 
    try {
      let order = await $OrderApiService.getOrderByToken(token.value);
      if (order) {
        toast.warning(t("warning_block.warning_already_exists"), {
            position: 'top-right',
            timeout: 2000,
            autoClose: false,
            hideProgressBar: true,
            closeOnClick: true,
            pauseOnHover: false,
            icon: true,
            rtl: false,
            draggable: true,
            progress: undefined,
            theme: 'light',
        });
        if (props.id) {
          token.value = originalToken.value
        } else {
          token.value = ''
        }
      }
    } catch (error) {
      console.log('error', error)
    }
  }
}
</script>

<template>
  <div class="wrapper text-base max-w-full">

    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="rounded p-2 md:p-4 bg-white">

      <!-- First 6 fields in 2 columns layout -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <!-- Column 1 -->
        <div class="space-y-4">
          <!-- Status -->
          <div v-if="!externalGot">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.status') }}</label>
            <v-select class="block w-full required" :model-value="selectedStatus"
              @update:modelValue="updateSelect($event, 'order_status')" :options="orderStatuses" />
          </div>

          <!-- Type -->
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.type') }}</label>
            <v-select class="block w-full required" :model-value="selectedType"
              @update:modelValue="updateSelect($event, 'order_type')" :options="order_type" 
              :class="{ 'invalid': attemptedSave && (!selectedType) }"/>
          </div>

          <!-- Reason -->
          <div v-if="selectedType">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('order_block.reason') }}</label>
            <v-select class="block w-full required" :model-value="selectedReason" 
              @update:modelValue="updateSelect($event, 'order_reason')" :options="order_reason"
              :class="{ 'invalid': attemptedSave && (!selectedReason) }"/>
          </div>
        </div>

        <!-- Column 2 -->
        <div class="space-y-4">
          <!-- Operators -->
          <div v-if="!externalGot">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.operators') }}</label>
            <v-select multiple class="block w-full required" :model-value="selectedOperators"
              @update:modelValue="updateSelect($event, 'operators')" :options="operators" />
          </div>

          <!-- Priority -->
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.priority') }}</label>
            <v-select class="block w-full" :model-value="selectedPriority"
              @update:modelValue="updateSelect($event, 'priority')" :options="priorities">
              <template #option="option">
                <AtomsColorBadge :value="option.label" :color="option.color" />
              </template>
              <template #selected-option="option">
                <AtomsColorBadge :value="option.label" :color="option.color" />
              </template>
            </v-select>
          </div>

          <!-- Scheduled Date -->
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('order_block.scheduled_date') }}</label>
            <AtomsInputDate v-model="dueDate" :placeholder="t('order_block.scheduled_date')" />
          </div>
        </div>
      </div>

      <!-- Description field -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">
          {{ t('order_block.description') }}
          <span class="text-slate-400 text-sm">({{ t('common.optional') }})</span>
        </label>
        <textarea 
          v-model="description" 
          @input="updateDescription(description)"
          :placeholder="t('order_block.description_placeholder')"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent resize-y min-h-[100px]"
          maxlength="700">
        </textarea>
        <div class="text-right text-xs mt-1" :class="descriptionLength >= 700 ? 'text-red-500' : 'text-slate-400'">
          {{ descriptionLength }} / 700
        </div>
      </div>

      <!-- Observations field -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">
          {{ t('common.observations') }}
        </label>
        
        <div v-if="!props.id">
          <!-- Component for adding notes before order exists -->
          <AtomsInputTextarea @update:text="addPendingObservation" :autosave="true" />
          
          <!-- Show list of pending observations -->
          <div v-if="pendingObservations.length > 0" class="mt-2 space-y-2">
            <div v-for="(obs, index) in pendingObservations" :key="index" 
                 class="p-2 bg-slate-50 border border-slate-200 rounded-md flex justify-between items-start group">
              <p class="text-sm text-gray-700 whitespace-pre-wrap flex-1">{{ obs }}</p>
              <button @click="removePendingObservation(index)" 
                      class="text-slate-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                <Icon name="fa6-solid:xmark" />
              </button>
            </div>
          </div>
        </div>
        <div v-else>
           <MoleculesObservationList 
            parent_entity="order" 
            :id="props.id" 
            module="order" />
        </div>
      </div>

      <!-- Location section -->
      <div v-if="selectedType" class="row">
        <label class="block text-sm font-medium text-slate-500 mb-2">
          {{ t('address_block.location') }}
          <span v-if="props.contract_id" class="text-slate-400 text-sm">
            ({{ t('common.optional') }})
          </span>
        </label>
        <div class="flex flex-col md:flex-row items-start md:items-center gap-2 md:gap-4 mb-2">
          <label class="flex items-center gap-2">
            <input type="radio" v-model="locationTypeRadio" value="SP" /> {{ t('supply_point') }}
          </label>
          <label class="flex items-center gap-2">
            <input type="radio" v-model="locationTypeRadio" value="A" /> {{ t('address_block.address') }}
          </label>
          <label class="flex items-center gap-2">
            <input type="radio" v-model="locationTypeRadio" value="C" /> {{ t('connection') }}
          </label>
          <label class="flex items-center gap-2">
            <input type="radio" v-model="locationTypeRadio" value="CON" /> {{ t('contract') }}
          </label>
          <label class="flex items-center gap-2">
            <input type="radio" v-model="locationTypeRadio" value="G" /> {{ t('order_block.only_coordinates') }}
          </label>
        </div>
      </div>

      <div v-if="selectedType && locationTypeRadio == 'A'" class="row grid grid-cols-1 md:grid-cols-2 gap-3">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.address') }}</label>
          <div :class="{ 'mt-1': selectedAddress == null }" class="text-gray-900 divide-y rounded shadow">
            <div v-if="selectedAddress" class="text-slate-500 p-2 w-full mb-2 flex flex-col md:grid md:grid-cols-[1fr,30px,30px] gap-2 md:gap-0">
              <span class="flex-1">{{ selectedAddress.address_complete }} - {{ selectedAddress.postal_code }}, {{ selectedAddress.city?.name
                }}</span>
              <div class="flex gap-2 md:contents">
                <button @click="editAddress(selectedAddress)" class="px-2 py-1 hover:bg-slate-200 rounded">
                  <Icon name="fa6-solid:pencil" />
                </button>
                <button @click="deleteAddress()" class="px-2 py-1 hover:bg-slate-200 rounded">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering" v-if="selectedAddress == null">
              <button @click="openRegion('addresses')"
                class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ t('address_block.address') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="selectedType && locationTypeRadio == 'SP'" class="mb-2 col-span-2">
        <div class="field">
          <label for="Supply_points" class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('supply_point') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selectedSupplyPoint == null }" class="text-gray-900 border rounded">
          <div v-if="selectedSupplyPoint" class="group grid divide-x text-sm leading-4 ">
            <div>
              <SupplyPointDetail :id="selectedSupplyPoint.id" :isSubRegion="true"  />
            </div>
          </div>
          <div v-if="selectedSupplyPoint" class="flex justify-end p-2 border-t">
            <button @click="deleteSupplyPoint()" class="px-2 py-1 hover:bg-slate-200 rounded text-slate-500" :title="$t('common.clear')">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
          <div class="footering" v-if="selectedSupplyPoint == null">
            <button @click="openRegion('supply_points')"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ t('supply_point') }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="selectedType && locationTypeRadio == 'C'" class="mb-2 col-span-2">
        <div class="field">
          <label for="Connections" class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('connection') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selectedConnection == null }" class="text-gray-900 border rounded">
          <div v-if="selectedConnection" class="group grid divide-x text-sm text-center leading-4 ">
            <div>
              <ConnectionDetail :id="selectedConnection.id" :data="selectedConnection" />
            </div>
          </div>
          <div v-if="selectedConnection" class="flex justify-end p-2 border-t">
            <button @click="deleteConnection()" class="px-2 py-1 hover:bg-slate-200 rounded text-slate-500" :title="$t('common.clear')">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
          <div class="footering" v-if="selectedConnection == null">
            <button @click="openRegion('connections')"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ t('connection') }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="selectedType && locationTypeRadio == 'CON'" class="mb-2 col-span-2">
        <div class="field">
          <label for="Contracts" class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('contract') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selectedContract == null }" class="text-gray-900 border rounded">
          <div v-if="selectedContract" class="group grid divide-x text-sm leading-4">
            <div>
              <ContractDetail :id="selectedContract.id" :reducedDetail="true" :isSubRegion="true" :showPayment="false" :showCommunication="false" />
            </div>
          </div>
          <div v-if="selectedContract" class="flex justify-end p-2 border-t">
            <button @click="deleteContract()" class="px-2 py-1 hover:bg-slate-200 rounded text-slate-500" :title="$t('common.clear')">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
          <div class="footering" v-if="selectedContract == null">
            <button @click="openRegion('contracts')"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ t('contract') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Geolocation Section -->
      <div v-if="selectedType" class="mb-4 mt-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">
          {{ t('service_block.geolocation') }}
          <span v-if="locationTypeRadio != 'G'" class="text-slate-400 text-sm">({{ t('common.optional') }})</span>
        </label>
        <p v-if="locationTypeRadio == 'G'" class="text-xs text-slate-400 mb-2">
          {{ t('order_block.only_coordinates_hint') }}
        </p>
        <AtomsInputGeolocation 
          v-model:model-latitude="latitude" 
          v-model:model-longitude="longitude" 
        />
        <p v-if="attemptedSave && locationTypeRadio == 'G' && !hasCoordinates" class="text-sm text-red-500 mt-2">
          {{ t('order_block.only_coordinates_required') }}
        </p>
        
        <!-- Checkbox to update property geolocation -->
        <div v-if="locationTypeRadio == 'SP' && selectedSupplyPoint" class="mt-3">
          <label class="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <input 
              type="checkbox" 
              v-model="updatePropertyGeolocation"
              class="w-4 h-4 text-sky-500 border-gray-300 rounded focus:ring-sky-500"
            />
            {{ t('order_block.update_property_geolocation') }}
          </label>
          <p class="text-xs text-slate-400 mt-1 ml-6">
            {{ t('order_block.update_property_geolocation_hint') }}
          </p>
        </div>
        
        <!-- Checkbox to update connection geolocation -->
        <div v-if="locationTypeRadio == 'C' && selectedConnection" class="mt-3">
          <label class="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <input 
              type="checkbox" 
              v-model="updateConnectionGeolocation"
              class="w-4 h-4 text-sky-500 border-gray-300 rounded focus:ring-sky-500"
            />
            {{ t('order_block.update_connection_geolocation') }}
          </label>
          <p class="text-xs text-slate-400 mt-1 ml-6">
            {{ t('order_block.update_connection_geolocation_hint') }}
          </p>
        </div>
      </div>

      <hr class="mb-2 col-span-1 md:col-span-2" />
      <div class="col-span-1 md:col-span-2 flex flex-col-reverse md:flex-row-reverse gap-2 md:gap-0 mt-4">
        <button v-if="id != null" @click="deleteItem" :disabled="saving" class="button-default md:mx-5">
          &nbsp; {{ $t('common.delete') }}
        </button>
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->
    </div>

    <!-- Overlay for mobile -->
    <div v-if="showRegion" 
      class="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden transition-opacity duration-500"
      @click="toggleRegion(false)">
    </div>

    <div role="region" id="right_page"
      class="fixed h-full top-0 transition-all duration-500 ease py-2 text-base bg-white z-50 overflow-y-auto"
      :class="{ 
        'left-0 md:right-0 md:left-auto': true,
        'border-l-0 md:border-l md:border-gray-100': true,
        'translate-x-0': showRegion, 
        '-translate-x-full md:translate-x-[2000px]': !showRegion, 
        'w-screen max-w-full md:w-[95%]': isSubRegionOpen, 
        'w-screen max-w-full md:w-1/2': !isSubRegionOpen 
      }"
      style="max-width: 100vw;">
      <div id="region_nav" class="mb-3 px-3 md:px-3 flex items-center justify-end border-b border-gray-200 pb-2">
        <button @click="toggleRegion(false)" class="px-3 py-2 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded-md flex items-center gap-2">
          <Icon name="fa6-solid:xmark" class="text-slate-500 md:hidden text-xl" />
          <Icon name="fa6-solid:angles-right" class="text-slate-500 hidden md:block" />
          <span class="md:hidden font-medium">{{ $t('common.close') }}</span>
        </button>
      </div>
      <div class="px-4 md:px-10">
        <MoleculesAddSupplyPoints v-if="editingSupplyPoints" :show="editingSupplyPoints"
          :selected_items="selectedSupplyPoint ? [selectedSupplyPoint] : []" @item-clicked="supplyPointClicked" :multiple="false" />
        <MoleculesAddConnections v-if="editingConnection" :show="editingConnection"
          :selected_items="selectedConnection ? [selectedConnection] : []" @item-clicked="connectionClicked" :multiple="false" />
        <MoleculesAddAddress :selectedAddress="selectedAddress" @new-address="newAddress" v-if="editingAddress"
          :isSubRegion="true" :onlyExploitation="true" />
        <MoleculesAddContracts v-if="editingContract" :show="editingContract"
          :selected_items="selectedContract ? [selectedContract] : []" @item-clicked="contractClicked" :multiple="false" />
      </div>
    </div>
  </div>
</template>
