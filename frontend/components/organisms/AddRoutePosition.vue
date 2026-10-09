<script setup>
import { ref, watch, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import debounce from 'lodash.debounce';

const { t } = useI18n();
const toast = useToast();
const { $RouteApiService, $SupplyPointApiService } = useNuxtApp();

const emit = defineEmits(['selected', 'created', 'show-subregion', 'preview-position']);
const props = defineProps({
  route_id: Number,
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
  editingPosition: {
    type: Object,
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
const editingSupplyPoints = ref(false);
const changingRoute = ref(false);

// Ruta seleccionada per aquesta posició: normalment és la del props.route_id,
// però es pot canviar des de la pròpia regió (veure openRegion('route')).
const selectedRouteId = ref(props.route_id);
const selectedRouteToken = ref(props.routeToken);

const selected_positions = ref([])
const selected_supply_points = ref([])
const selected_properties = ref([])

const isEditing = computed(() => props.editingPosition !== null);

const positionData = ref(null); 

const positionChanged = (position) => {
  positionData.value = position;
  if (position) {
    if (position.selected_supply_points) {
      const currentIds = selected_supply_points.value.map(s => s.id).sort().join(',');
      const newIds = position.selected_supply_points.map(s => s.id).sort().join(',');
      if (currentIds !== newIds) {
        selected_supply_points.value = [...position.selected_supply_points];
      }
    }
    if (position.selected_properties) {
      const currentIds = selected_properties.value.map(p => p.id).sort().join(',');
      const newIds = position.selected_properties.map(p => p.id).sort().join(',');
      if (currentIds !== newIds) {
        selected_properties.value = [...position.selected_properties];
      }
    }
    if (position.position) {
      emit('preview-position', position.position);
    }
  }
  // Re-emit updated position data to ensure the parent is always in sync
  positionData.value = {
    ...positionData.value,
    selected_supply_points: selected_supply_points.value,
    selected_properties: selected_properties.value
  };
};

const newPropertyClicked = (property) => {
  const index = selected_properties.value.findIndex(p => p.id === property.id);
  if (index > -1) {
    selected_properties.value = selected_properties.value.filter(p => p.id !== property.id);
  } else {
    selected_properties.value = [...selected_properties.value, property];
  }
}

const supplyPointClicked = (supplyPoint) => {
  if (selected_supply_points.value) {
    const ids = selected_supply_points.value.map(s => s.id);

    const index = ids.indexOf(supplyPoint.id);
    if (index > -1) {
      selected_supply_points.value = selected_supply_points.value.filter(s => s.id !== supplyPoint.id);
    }
    else {
      selected_supply_points.value = [...selected_supply_points.value, supplyPoint];
    }
  }
}

const openRegion = (region) => {
  // Clear any existing sub-region flags first, but don't close the whole subregion
  addingProperty.value = false;
  editingSupplyPoints.value = false;
  changingRoute.value = false;

  switch (region) {
    case 'property':
      addingProperty.value = true;
      break;
    case 'supply_point':
      editingSupplyPoints.value = true;
      break;
    case 'route':
      changingRoute.value = true;
      break;
  }

  if (!openSubRegion.value) {
    showSubRegion();
  }
}

const onRouteChanged = (route) => {
  if (!route) return;
  selectedRouteId.value = route.id;
  selectedRouteToken.value = route.token;
  closeSubRegion();
}

const positionClicked = (position) => {
  const index = selected_positions.value.findIndex(sp => sp.id == position.id);
  if (index == -1) {
    selected_positions.value.push(position);
  }
  else {
    selected_positions.value.splice(index, 1)
  }

  console.log(selected_positions.value);
};

const closeSubRegion = function () {
  openSubRegion.value = false;
  addingProperty.value = false;
  editingSupplyPoints.value = false;
  changingRoute.value = false;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  openSubRegion.value = true;
  emit('show-subregion', true);
}

watch(() => props.selectedOptions, (newValue) => {
  selected_positions.value = newValue;
});

watch(() => props.editingPosition, (newValue) => {
  // Reset parent local state when the editing record changes or is closed/reopened
  positionData.value = null; // Reset position data to ensure fresh start
  // Cancel·lem qualsevol canvi de ruta pendent d'una sessió d'edició anterior
  selectedRouteId.value = props.route_id;
  selectedRouteToken.value = props.routeToken;
  if (newValue) {
    // If it's an existing position, try to extract already loaded objects if available
    // or let the child fetch them. But we need to sync parent state for subregions.
    selected_supply_points.value = [...(newValue.selected_supply_points || newValue.supply_points || [])];
    selected_properties.value = [...(newValue.selected_properties || newValue.properties || [])];
  } else {
    selected_supply_points.value = [];
    selected_properties.value = [];
  }
}, { immediate: true, deep: true });

watch(() => props.isSubRegionOpen, (newValue) => {
  openSubRegion.value = newValue;
});

watch(() => props.route_id, (newValue) => {
  selectedRouteId.value = newValue;
});

watch(() => props.routeToken, (newValue) => {
  selectedRouteToken.value = newValue;
});

const save = async () => {

  // Check if points are assigned to a property (Task: All supply points must be assigned)
    if (positionData.value?.selected_supply_points?.length > 0) {
      const anyUnassigned = positionData.value.selected_supply_points.some(sp => {
        const propId = sp.property_id || (sp.property?.id || sp.property);
        return !propId;
      });
      
      if (anyUnassigned) {
        alert(t('common.assign') + ' ' + t('property').toLowerCase() + ' a tots els ' + t('common.supply_points').toLowerCase());
        return;
      }
    }

    // create new position and return it
    
    let response = null;

    const data = {
      name: positionData.value.name,
      token: positionData.value.token,
      notebook: positionData.value.notebook,
      reader_observation: positionData.value.reader_observation,
      position: positionData.value.position,
      supply_points_ids: positionData.value.selected_supply_points?.map(sp => sp.id),
      property_ids: positionData.value.selected_properties?.map(sp => sp.id) || [],
      route_id: selectedRouteId.value || 0,

      address_postal_code: positionData.value.address_postal_code,
      address_city: positionData.value.address_city,
      address_street: positionData.value.address_street,
      address_street_number: positionData.value.address_street_number,
      latitude: positionData.value.latitude,
      longitude: positionData.value.longitude
    }

    // Check for duplicate token within current route positions (Task 1).
    // Instead of blocking the request (which used to make it impossible to insert
    // a position between two occupied slots, e.g. between 100 and 101), an
    // incremental numeric suffix is appended to the token until it's unique
    // (10_00101 -> 10_001011 -> 10_001012...), and the user is only notified.
    // Nota: props.selectedOptions correspon a la ruta original — si l'usuari ha
    // canviat de ruta des d'aquesta mateixa regió, aquesta llista ja no aplica
    // (el backend ja gestiona el desplaçament en cadena a la ruta de destí).
    const routeChanged = selectedRouteId.value !== props.route_id;
    if (!routeChanged) {
      const otherTokens = new Set(
        props.selectedOptions
          .filter(p => !isEditing.value || p.id !== props.editingPosition?.id)
          .map(p => p.token)
      );
      if (otherTokens.has(data.token)) {
        const baseToken = data.token;
        let suffix = 1;
        while (otherTokens.has(`${baseToken}${suffix}`)) {
          suffix++;
        }
        data.token = `${baseToken}${suffix}`;
        toast.warning(t('service_block.duplicate_token_auto_renamed', { token: data.token }));
      }
    }

    try {
      if (isEditing.value) {
        response = await $RouteApiService.updateRoutePosition({ ...data, id: props.editingPosition.id });
      } else {
        response = await $RouteApiService.createRoutePosition(data);
      }

      // After saving the route position, update all selected supply point properties on the backend in bulk
      if (positionData.value.selected_supply_points) {
        const bulkDataMap = new Map();
        for (const sp of positionData.value.selected_supply_points) {
          const propId = sp.property_id || (sp.property?.id || sp.property);
          if (propId) {
            if (!bulkDataMap.has(propId)) {
              bulkDataMap.set(propId, []);
            }
            bulkDataMap.get(propId).push(sp.id);
          }
        }

        if (bulkDataMap.size > 0) {
          const bulkPayload = Array.from(bulkDataMap.entries()).map(([property_id, supply_points]) => ({
            property_id: Number(property_id),
            supply_points
          }));

          try {
            await $SupplyPointApiService.bulkUpdateProperty(bulkPayload);
          } catch (bulkError) {
            console.error('Failed to bulk update supply point properties:', bulkError);
          }
        }
      }

      // The backend response contains 'properties' as full objects.
      // Build the display labels for the RouteEdit table.
      if (response.properties && response.properties.length > 0 && typeof response.properties[0] === 'object') {
        // Backend already returned full objects — extract display labels
        response._properties_display = response.properties.map(p =>
          p.name || p.address_complete ||
          [p.address_street?.name, p.address_street_number?.name, p.address_city?.name].filter(Boolean).join(' ') ||
          p.token
        );
      } else if (positionData.value.selected_properties) {
        // Fallback: build from local selected properties
        response.properties = positionData.value.selected_properties;
        response._properties_display = positionData.value.selected_properties.map(p =>
          p.name || p.address_complete || p.city || p.token
        );
      }

      // Store full selected objects in response so the edit panel can reuse them without re-fetching
      response.selected_properties = positionData.value.selected_properties;
      response.selected_supply_points = positionData.value.selected_supply_points;
      response.name = positionData.value.name;

      emit('created', response);
    }
    catch (error) {
      console.error(error);
    }

};

onMounted(() => {
  selected_positions.value = [...props.selectedOptions];
});

</script>

<template>
  <div class="region__content h-full" :class="{ 'grid grid-cols-2 gap-4': openSubRegion }">
    <div class="h-full overflow-y-auto pb-24 pr-2" :class="{ 'pr-5': openSubRegion }">
      <h2 class="text-xl font-semibold mb-4">{{ t('common.select') }} {{ t('service_block.route_position') }}</h2>

      <div>
        <MoleculesAddNewRoutePosition @show-subregion="openRegion" @position_changed="positionChanged"
          :selectedOptions="props.selectedOptions"
          :selected_properties="selected_properties" :selected_supply_points="selected_supply_points"
          :isSubRegionOpen="props.isSubRegionOpen" :routeToken="selectedRouteToken" :numPositions="props.numPositions"
          :editingPosition="props.editingPosition" :routeId="selectedRouteId"
          :insertAfterPosition="props.insertAfterPosition" />
      </div>

      <button @click="save" :disabled="!positionData?.selected_properties || positionData.selected_properties.length === 0" class="button-primary">
        {{ isEditing ? t('common.save') : `${t('common.assign')} ${t('common.position')}` }}</button>
    </div>
    <div v-if="openSubRegion" role="region" id="subregion"
      class="h-[calc(100%+45px)] border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden"
      style="margin-top: -45px;">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-hidden pr-2 flex flex-col">
        <MoleculesAddSupplyPoints v-if="editingSupplyPoints" :show="editingSupplyPoints"
          :selected_items="selected_supply_points" @item-clicked="supplyPointClicked" :noProperty="true"
          :multiple="true" />
        <MoleculesAddProperties v-if="addingProperty" :selected_items="selected_properties"
          @item-clicked="newPropertyClicked" :multiple="true" :fitContainer="true" />
        <MoleculesAddRoute v-if="changingRoute" :selected_items="[]" @item-clicked="onRouteChanged" />
      </div>
    </div>
  </div>
</template>
