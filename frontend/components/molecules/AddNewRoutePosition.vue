<script setup>
import { ref, watch, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';
import Pagination from '~/components/molecules/Pagination.vue';

const { t } = useI18n();
const { $SupplyPointApiService, $MeterApiService, $AddressHelper, $RouteApiService } = useNuxtApp();

const emit = defineEmits(['position_changed', 'show-subregion']);
const props = defineProps({
  isSubRegionOpen: Boolean,
  selectedOptions: {
    type: Object,
    required: false,
  },
  routeToken: {
    type: String,
    required: true,
  },
  numPositions: {
    type: Number,
    required: false,
  },
  selected_properties: {
    type: Array,
    required: false,
    default: () => []
  },
  selected_supply_points: {
    type: Array,
    required: false,
    default: () => []
  },
  editingPosition: {
    type: Object,
    required: false,
    default: null
  },
  selectedOptions: {
    type: Array,
    required: false,
    default: () => []
  },
  routeId: {
    type: Number,
    required: false,
    default: null
  },
  insertAfterPosition: {
    type: Number,
    required: false,
    default: null
  }
});
const openSubRegion = ref(props.isSubRegionOpen);
const addingProperty = ref(false);

const loadingSupplies = ref(false);

const selected_properties = ref([])
const selected_supply_points = ref([])

const currentPage = ref(1);
const perPage = ref(10);

const pagination = computed(() => {
  const total = selected_supply_points.value.length;
  const totalPages = Math.ceil(total / perPage.value);
  return {
    page: currentPage.value,
    perPage: perPage.value,
    total: total,
    totalPages: totalPages,
    previous: currentPage.value > 1 ? currentPage.value - 1 : null,
    next: currentPage.value < totalPages ? currentPage.value + 1 : null,
    isFiltered: false
  };
});

const paginatedSupplyPoints = computed(() => {
  const start = (currentPage.value - 1) * perPage.value;
  const end = start + perPage.value;
  return selected_supply_points.value.slice(start, end);
});

const handlePageChange = (newPage) => {
  currentPage.value = newPage;
};

const name = ref('');
const token = ref('');
const position = ref(0);
const notebook = ref('');
const reader_observation = ref('');
const meter = ref(null);
const lastPosition = ref(0);
// null: no comprovat / valor invàlid, 'checking', 'free' o 'occupied'
const positionStatus = ref(null);
let positionCheckToken = 0;

const fetchOccupiedPositions = async () => {
  if (!props.routeId) return;
  try {
    const response = await $RouteApiService.getOccupiedPositions(props.routeId);
    if (response) {
      lastPosition.value = response.last_position || 0;
    }
  } catch (error) {
    console.error('Error loading occupied positions:', error);
  }
};

const checkPositionStatus = async (pos) => {
  const requestId = ++positionCheckToken;

  if (pos === null || pos === '' || Number.isNaN(Number(pos)) || Number(pos) < 1 || !props.routeId) {
    positionStatus.value = null;
    return;
  }

  const currentPosition = props.editingPosition?.position ? Number(props.editingPosition.position) : null;
  if (currentPosition !== null && Number(pos) === currentPosition) {
    positionStatus.value = 'free';
    return;
  }

  positionStatus.value = 'checking';
  const occupied = await $RouteApiService.checkPositionOccupied(props.routeId, Number(pos));
  if (requestId !== positionCheckToken) return; // a newer check superseded this one
  positionStatus.value = occupied ? 'occupied' : 'free';
};

const debouncedCheckPositionStatus = debounce(checkPositionStatus, 300);

watch(position, (newValue) => {
  debouncedCheckPositionStatus(newValue);
});

const fetchSupplyPoints = async () => {
  if (loadingSupplies.value) return;
  loadingSupplies.value = true;
  try {
    if (selected_properties.value.length === 0) {
      selected_supply_points.value = [];
      currentPage.value = 1;
      positionChanged();
      return;
    }

    // Fetch full supply point details for each property via the API
    const promises = selected_properties.value.map(p => $SupplyPointApiService.getByProperty(p.id));
    const results = await Promise.all(promises);
    let allSupplies = [];
    results.forEach(res => {
      if (res.results && res.results.length > 0) {
        allSupplies = allSupplies.concat(res.results);
      }
    });

    const propertyIds = selected_properties.value.map(p => p.id).map(id => Number(id));
    const existingMap = new Map(selected_supply_points.value.map(s => [s.id, s]));

    // Reconcile: Keep existing points (with their local overrides) 
    // and add new points from fetch
    allSupplies.forEach(newSp => {
      if (!existingMap.has(newSp.id)) {
        existingMap.set(newSp.id, newSp);
      }
      // If it exists, we keep the existing one because it might have a local property_id override
    });

    // Filter: only keep points that belong (locally or via backend) to one of the selected properties
    const finalSupplies = Array.from(existingMap.values()).filter(sp => {
      const propId = getPropertyId(sp);
      return !propId || propertyIds.includes(Number(propId));
    });

    // Update local state
    selected_supply_points.value = finalSupplies;
    currentPage.value = 1;
    getMeter();
    positionChanged();

  } catch (error) {
    console.error(error);
  } finally {
    loadingSupplies.value = false;
  }
};

const deleteProperty = (prop) => {
  const index = selected_properties.value.findIndex(p => p.id === prop.id);
  if (index !== -1) {
    selected_properties.value.splice(index, 1);
  }
  fetchSupplyPoints();
  positionChanged();
}
const deleteSupplyPoint = (supply_point) => {
  const index = selected_supply_points.value.findIndex(s => s.id === supply_point.id);
  if (index !== -1) {
    selected_supply_points.value.splice(index, 1);
  }
  const maxPage = Math.ceil(selected_supply_points.value.length / perPage.value) || 1;
  if (currentPage.value > maxPage) {
    currentPage.value = maxPage;
  }
  positionChanged();
}

const updateSupplyPointProperty = (item, event) => {
  const newPropertyId = Number(event.target.value) || null;
  
  // Update the item safely in local state
  item.property_id = newPropertyId;
  
  if (typeof item.property === 'object' && item.property !== null) {
      item.property.id = newPropertyId;
  } else {
      item.property = newPropertyId;
  }
  
  // Force a new array to trigger parent watchers
  selected_supply_points.value = [...selected_supply_points.value];
  positionChanged();
}

const getPropertyId = (item) => {
  if (!item) return null;
  // prioritize property_id as per new backend structure
  const val = item.property_id || (item.property?.id || item.property);
  return val ? Number(val) : null;
}

const getMeter = async () => {

  let id = null;

  if (selected_supply_points.value?.length > 0) {
    id = selected_supply_points.value[0].meter_id;
    if(!id) return;
    try {
      const data = await $MeterApiService.getDetail(id);
      meter.value = data;
      setAddressValues();

    }
    catch (error) {
      console.error(error);
    }
  }

}

const setAddressValues = () => {
  positionChanged()
}

const generateToken = (pos) => {
  if (props.routeToken == null) return '';
  const num = pos ? Number(pos) : 1;
  return `${props.routeToken}_${num}`;
};

const positionChanged = () => {
  emit('position_changed', getPosition());
}

// Only regenerate the token when the route order changes and we are creating a new record
const positionOrderChanged = () => {
  if (!props.editingPosition) {
    token.value = generateToken(position.value);
  }
  positionChanged();
}

const getPosition = () => {
  return {
    name: name.value,
    token: token.value,
    notebook: notebook.value,
    reader_observation: reader_observation.value,
    position: position.value,
    selected_supply_points: selected_supply_points.value,
    selected_properties: selected_properties.value,

    address_postal_code: meter.value?.address_postal_code?.id || null,
    address_city: meter.value?.address_city?.id || null,
    address_street: meter.value?.address_street?.id || null,
    address_street_number: meter.value?.address_street_number?.id || null,
    latitude: meter.value?.latitude || 0,
    longitude: meter.value?.longitude || 0
  }
}

const openRegion = (region) => {
  switch (region) {
    case 'property':
      addingProperty.value = true;
      break;
    default:
      null;
      break;
  }
  showSubRegion(region)
}

const showSubRegion = function (region) {
  openSubRegion.value = true;
  emit('show-subregion', region);
}

watch(() => props.isSubRegionOpen, (newValue) => {
  openSubRegion.value = newValue;
});

watch(() => props.selected_properties, (newValue) => {
  const oldIds = selected_properties.value.map(p => p.id).sort().join(',');
  const newIds = (newValue || []).map(p => p.id).sort().join(',');
  
  if (oldIds !== newIds) {
    selected_properties.value = [...newValue];
    // Only fetch if IDs changed
    fetchSupplyPoints();
  }
}, { deep: true });

watch(() => props.selected_supply_points, (newValue) => {
  const oldIds = selected_supply_points.value.map(s => s.id).sort().join(',');
  const newIds = (newValue || []).map(s => s.id).sort().join(',');
  
  if (oldIds !== newIds) {
    selected_supply_points.value = [...(newValue || [])];
    getMeter();
    positionChanged();
  }
}, { deep: true, immediate: true });

const loadData = async () => {
  if (props.editingPosition) {
    name.value = props.editingPosition.name || '';
    token.value = props.editingPosition.token || '';
    position.value = props.editingPosition.position || 0;
    notebook.value = props.editingPosition.notebook || '';
    reader_observation.value = props.editingPosition.reader_observation || '';

    // Reset before loading
    selected_supply_points.value = [];
    currentPage.value = 1;

    if (props.editingPosition.selected_properties) {
      // Case A: Newly created position (not yet saved), objects stored in memory
      selected_properties.value = [...props.editingPosition.selected_properties];
      selected_supply_points.value = [...(props.editingPosition.selected_supply_points || [])];
      currentPage.value = 1;
      if (selected_properties.value.length > 0) {
        await fetchSupplyPoints();
      }
    } else if (
      props.editingPosition.properties &&
      props.editingPosition.properties.length > 0 &&
      typeof props.editingPosition.properties[0] === 'object'
    ) {
      // Case B: Saved position already loaded from list with full property objects
      selected_properties.value = [...props.editingPosition.properties];
      await fetchSupplyPoints();
    } else if (props.editingPosition.id) {
      // Case C: Saved position, but properties are missing or are just strings — fetch from backend
      const detail = await $RouteApiService.getRoutePosition(props.editingPosition.id);
      if (detail.properties && detail.properties.length > 0 && typeof detail.properties[0] === 'object') {
        selected_properties.value = [...detail.properties];
      } else {
        selected_properties.value = [];
      }
      if (selected_properties.value.length > 0) {
        await fetchSupplyPoints();
      }
    } else {
      selected_properties.value = [];
    }
  } else {
    // New position
    name.value = '';
    notebook.value = '';
    reader_observation.value = '';
    selected_properties.value = [];
    selected_supply_points.value = [];
    currentPage.value = 1;
    
    if (props.insertAfterPosition !== null) {
      position.value = props.insertAfterPosition + 1;
    } else {
      position.value = (lastPosition.value || 0) + 1;
    }
    token.value = generateToken(position.value);
  }

  // Keep parent always synced with loaded values
  positionChanged();
};

watch(() => props.editingPosition?.id, (newId, oldId) => {
  // ONLY reload data if the ID actually changed (meaning we switched record)
  // This prevents data loss when opening/closing subregions or other minor prop changes
  if (newId !== oldId) {
    loadData();
  }
});

// Quan es canvia de ruta des de la pròpia regió (veure el botó "Ruta" més avall),
// recol·loquem la posició a la nova ruta (la primera lliure disponible) i
// regenerem l'Ident. perquè reflecteixi la nova ruta, tant si és una posició
// nova com si s'està editant una ja existent.
watch(() => props.routeId, async (newId, oldId) => {
  if (newId === oldId) return;
  await fetchOccupiedPositions();
  position.value = (lastPosition.value || 0) + 1;
  token.value = generateToken(position.value);
  positionChanged();
});

// Re-initialize the insertion position if insertAfterPosition arrives after the initial
// mount (race condition when the parent sets insertAfterIndex after opening the region)
watch(() => props.insertAfterPosition, (insertAfter) => {
  if (props.editingPosition) return;
  if (insertAfter === null) return;
  position.value = insertAfter + 1;
  token.value = generateToken(position.value);
  positionChanged();
});

onMounted(async () => {
  await fetchOccupiedPositions();
  await loadData();
});

</script>

<template>
  <div>
    <div class="row grid grid-cols-2 gap-3">
      <div class="mb-2 col-span-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('route') }}</label>
        <div class="flex items-center gap-2">
          <input type="text" :value="props.routeToken" class="input flex-1" disabled />
          <button @click="openRegion('route')" type="button"
            class="button-default h-11 w-11 flex items-center justify-center"
            :title="t('common.modify')">
            <Icon name="fa6-solid:pencil" />
          </button>
        </div>
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.code') }} *</label>
        <input 
          required 
          :readonly="props.editingPosition != null" 
          :disabled="props.editingPosition != null" 
          type="text" 
          v-model="token" 
          class="input" 
          :class="{ 'bg-slate-100': props.editingPosition != null }"
          @change="positionChanged()"
        />
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.route_order') }} *</label>
        <input type="number" min="1" step="1" v-model.number="position" @change="positionOrderChanged()" class="input required" />
        <p v-if="positionStatus === 'free'" class="mt-1 text-sm text-green-600">{{ t('service_block.position_free') }}</p>
        <p v-else-if="positionStatus === 'occupied'" class="mt-1 text-sm text-red-600">{{ t('service_block.position_occupied') }}</p>
        <p v-else-if="positionStatus === 'checking'" class="mt-1 text-sm text-slate-400">{{ t('common.loading') }}...</p>
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
        <input type="text" v-model="name" class="input" @change="positionChanged()" />
      </div>
      <div class="mb-2 col-span-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.notebook') }}</label>
        <input type="text" v-model="notebook" class="input" @change="positionChanged()" />
      </div>
      <div class="mb-2 col-span-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.reader_observation') }}</label>
        <input type="text" v-model="reader_observation" class="input" @change="positionChanged()" />
      </div>

      <div class="mb-2 col-span-2">
        <div class="field">
          <div class="flex">
            <label for="properties" class="pt-2 text-slate-500 mb-2">{{ $t('property') }}</label>
          </div>
        </div>
        <div :class="{ 'mt-1': selected_properties.length > 0 }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_properties.length > 0" class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('common.code') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.address') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.cadastral') }}
            </span>
          </div>
          <div v-for="prop in selected_properties" :key="prop.id" class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
            <div class="p-2 text-slate-800">{{ prop.token }}</div>
            <div class="p-2 text-slate-800 relative">
              {{ prop.name }}
            </div>
            <div class="p-2 text-slate-800 relative">
              {{ prop.cadastral }}
              <button
                class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                @click="deleteProperty(prop)">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
          </div>
          <div class="footering">
            <button @click="openRegion('property')"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" />
              {{ selected_properties.length > 0 ? $t('common.select') + ' ' + $t('property').toLowerCase() : $t('common.select') + ' ' + $t('property').toLowerCase() }}
            </button>
          </div>
        </div>
      </div>
      <div class="mb-2 col-span-2">
        <div class="field">
          <div class="flex">
            <label for="properties" class="pt-2 text-slate-500 mb-2">{{ $t('common.supply_points') }}</label>
          </div>
        </div>
        <div :class="{ 'mt-1': selected_supply_points.length == 0 }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_supply_points.length > 0"
            class="group grid grid-cols-[1fr,0.5fr,2.5fr,1.5fr] divide-x text-sm text-center leading-4">
            <span class="p-1 text-slate-400">
              {{ t('common.code') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.status') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('address_block.address') }}
            </span>
            <span v-if="selected_properties.length > 0" class="p-1 text-slate-400">
              {{ t('property') }}
            </span>
          </div>
          <div v-for="item in paginatedSupplyPoints" :key="item.id"
            class="group grid grid-cols-[1fr,0.5fr,2.5fr,1.5fr] divide-x text-sm text-center items-center">
            <div class="p-2 text-slate-800">{{ item.token }}</div>
            <div class="p-2 text-slate-800 relative">
              <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
              <button
                class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                @click="deleteSupplyPoint(item)">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
            <div class="p-2 text-slate-800 relative">
              {{ item.address_complete }}
            </div>
            <div v-if="selected_properties.length > 0" class="p-2 text-slate-800 relative">
               <select :value="selected_properties.some(p => p.id === getPropertyId(item)) ? getPropertyId(item) : ''" @change="updateSupplyPointProperty(item, $event)" class="w-full text-xs border border-gray-200 rounded p-1">
                 <option value="">{{ t('common.select') }}...</option>
                 <option v-for="prop in selected_properties" :key="prop.id" :value="prop.id">
                   {{ prop.cadastral || prop.token || prop.name }}
                 </option>
               </select>
            </div>
          </div>
          <div v-if="selected_supply_points.length > perPage" class="p-2 border-t">
            <Pagination :pagination="pagination" @update:page="handlePageChange" />
          </div>
          <div class="footering">
            <button @click="openRegion('supply_point')" :disabled="selected_properties.length === 0 || loadingSupplies"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b disabled:bg-slate-100 enabled:hover:bg-slate-200 text-left enabled:active:bg-slate-300"><Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('service_block.select_supply_point') }}</button>
          </div>
        </div>
        <div class="mb-2 col-span-2" v-if="meter">
          <div class="field">
            <div class="flex">
              <label for="properties" class="pt-2 text-slate-500 mb-2">{{ $t('service_block.route_address') }}</label>
            </div>

            <div class="ml-2 text-slate-800">
              <span> {{ $AddressHelper.getAddressString(meter) }}</span> <br>
              <span> <Icon name="fa6-solid:map" class="display-inline mr-2" /> {{ meter.latitude ?? 0 }}, {{ meter.longitude ?? 0 }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

</template>
