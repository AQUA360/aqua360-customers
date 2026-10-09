<script setup>
import { ref, onMounted } from 'vue';
import _ from 'lodash';
import { _getAppConfig } from '#app';

const { t } = useI18n();
const { $ExploitationApiService, $ClusterApiService, $ConfiglistApiService, $RouteApiService } = useNuxtApp();

const props = defineProps({
  request: Object
});

const emit = defineEmits(['change-data']);

const loading = ref(true);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const type = ref(null);
const supply_type = ref(null);
const source = ref(null);
const route = ref(null);
const placement = ref(null);

const types = ref([]);
const supply_types = ref([]);
const sources = ref([]);
const routes = ref([]);
const placements = ref([]);
const full_routes = ref([]);
const positions = ref([]);

const editingMeters = ref(false);
const editingProperties = ref(false);
const editingOrder = ref(false);

const selected_meter = ref(null);
const selected_property = ref(null);
const selected_position = ref(null);

const getData = async () => {
  await getConfig()
  loadData();
  loading.value = false;
};

const loadData = async () => {
  if (props.request) {
    if (props.request.meter) {
      selected_meter.value = props.request.meter;
    }
    if (props.request.property) {
      selected_property.value = props.request.property;
    }
    if (props.request.type) {
      type.value = {
        code: props.request.type.id,
        label: props.request.type.name || props.request.type.token
      }
    }
    if (props.request.supply_type) {
      supply_type.value = {
        code: props.request.supply_type.id,
        label: props.request.supply_type.name || props.request.supply_type.token
      }
    }
    if (props.request.source) {
      source.value = {
        code: props.request.source.id,
        label: props.request.source.name || props.request.source.token
      }
    }
    if (props.request.route) {
      route.value = {
        code: props.request.route.id,
        label: props.request.route.name || props.request.route.token
      }
      positions.value = props.request.route.positions;
    }
    if (props.request.route_position) {
      selected_position.value = props.request.route_position;
    }
    if (props.request.placement) {
      placement.value = {
        code: props.request.placement.id,
        label: props.request.placement.name || props.request.placement.token
      }
    }
  }
};

const meterClicked = (item) => {
  if (item.id == selected_meter.value?.id) {
    selected_meter.value = null;
  }
  else {
    selected_meter.value = item;
  }
  setTimeout(() => {
    closeAllRegions();
    emitData();
  }, 200)
};

const propertyClicked = (item) => {
  if (item.id == selected_property.value?.id) {
    selected_property.value = null;
  }
  else {
    selected_property.value = item;
  }
  setTimeout(() => {
    closeAllRegions();
    emitData();
  }, 200)
};

const getConfig = async () => {
  try {

    types.value = [];
    supply_types.value = [];
    sources.value = [];
    placements.value = [];
    let data = [];

    data = await $ConfiglistApiService.getAll('service/supply-point-type');
    data.results?.forEach(type => {
      types.value.push({
        code: type.id,
        label: type.name || type.token
      })
    });

    data = await $ConfiglistApiService.getAll('service/supply-point-supply-type');
    data.results?.forEach(type => {
      supply_types.value.push({
        code: type.id,
        label: type.name || type.token
      })
    });

    data = await $ConfiglistApiService.getAll('service/supply-point-source');
    data.results?.forEach(source => {
      sources.value.push({
        code: source.id,
        label: source.name
      })
    });

    data = await $ConfiglistApiService.getAll('service/supply-point-placement');
    data.results?.forEach(source => {
      placements.value.push({
        code: source.id,
        label: source.name
      })
    });

    data = await $RouteApiService.getData();
    full_routes.value = data.results;
    data.results?.forEach(source => {
      routes.value.push({
        code: source.id,
        label: source.name
      })
    });
  } catch (error) {
    console.error('Error fetching connection statuses:', error);
  }
}

const selectRoute = async (e) => {
  const selected_route = full_routes.value.find(r => r.id == e.id?.code);

  if (selected_route && selected_route.id != props.request.route?.id) {
    positions.value = selected_route.positions;

    if (props.request.route_position) {
      await $RouteApiService.deleteRoutePosition(props.request.route_position.id)
      positions.value = positions.value.filter(p => p.id != props.request.route_position.id)
    }

    let token = '';
    let position = 0;

    positions.value.forEach(p => {
      if (p.position >= position) {
        token = selected_route.token + '/' + (p.position + 1);
        position = p.position + 1;
      }
    });

    const data = {
      name: '',
      token: token,
      notebook: '',
      position: position,
      property_id: selected_property.value?.id,
      route_id: selected_route.id,
      supply_points_ids: [],

      address_postal_code: selected_meter.value?.address_postal_code?.id || null,
      address_city: selected_meter.value?.address_city?.id || null,
      address_street: selected_meter.value?.address_street?.id || null,
      address_street_number: selected_meter.value?.address_street_number?.id || null,
      latitude: selected_meter.value?.latitude || 0,
      longitude: selected_meter.value?.longitude || 0
    }

    let result = await $RouteApiService.createRoutePosition(data)

    if (result) {
      selected_position.value = result;
      positions.value.push(result);
    }
    route.value = e.id;
    emitData();
  }
}

const updateSelected = (e) => {
  if (e.entity == 'type') {
    type.value = e.id;
    emitData();
  }
  else if (e.entity == 'source') {
    source.value = e.id;
    emitData();
  }
  else if (e.entity == 'route') {
    selectRoute(e);
  }
  else if (e.entity == 'placement') {
    placement.value = e.id;
    emitData();
  }
  else if (e.entity == 'supply_type') {
    supply_type.value = e.id;
    emitData();
  }
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const openRegion = (region) => {
  closeAllRegions();

  if (region == 'meter') {
    editingMeters.value = true;
  }
  if (region == 'property') {
    editingProperties.value = true;
  }
  if (region == 'order') {
    editingOrder.value = true;
  }

  showRegion.value = true;
};

const closeAllRegions = () => {
  editingOrder.value = false;
  editingProperties.value = false;
  editingMeters.value = false;
  showRegion.value = false;
};

const emitData = () => {
  emit('change-data', {
    meter_id: selected_meter.value?.id,
    property_id: selected_property.value?.id,
    type_id: type.value?.code,
    supply_type_id: supply_type.value?.code,
    source_id: source.value?.code,
    route_id: route.value?.code,
    position_id: selected_position.value?.id,
    placement_id: placement.value?.code
  });
}

onMounted(() => {
  getData();
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <h2 class="text-xl font-semibold mb-4">
      {{ $t('billing_block.step') }} 2: {{ $t('service_block.supply_data') }}
    </h2>
    <div v-if="loading">
      <div class="border border-gray-300 rounded-b p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>

    <div v-else class="grid grid-cols-2 gap-3">
      <div class="mb-2">
        <div class="flex">
          <label for="type" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('common.type') }}</label>
        </div>
        <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="type"
          @update:modelValue="updateSelected({ entity: 'type', id: $event })" :options="types" />
      </div>
      <div class="mb-2">
        <div class="flex">
          <label for="source" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('service_block.supply_source') }}</label>
        </div>
        <v-select class="block w-full mr-2 required" :disabled="sources.length == 0" :model-value="source"
          @update:modelValue="updateSelected({ entity: 'source', id: $event })" :options="sources" />
      </div>
      <div class="mb-2">
        <div class="flex">
          <label for="supply_type" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('service_block.supply_type') }}</label>
        </div>
        <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="supply_type"
          @update:modelValue="updateSelected({ entity: 'supply_type', id: $event })" :options="supply_types" />
      </div>
      <div class="mb-2">
        <div class="flex">
          <label for="type" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('service_block.placement') }}</label>
        </div>
        <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="placement"
          @update:modelValue="updateSelected({ entity: 'placement', id: $event })" :options="placements" />
      </div>
      <div class="mb-2 col-span-2">
        <div class="field">
          <label for="child_meters" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('meter') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selected_meter }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_meter" class="group grid grid-cols-[1fr,2fr,1fr] divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('common.code') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('address_block.address') }} {{ $t('meter') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.status') }}
            </span>
          </div>
          <div v-if="selected_meter" class="group grid grid-cols-[1fr,2fr,1fr] divide-x text-sm text-center leading-4 ">
            <div class="p-2 text-slate-800">{{ selected_meter.code }}</div>
            <div class="p-2 text-slate-800">{{ $AddressHelper.getAddressString(selected_meter) }}</div>
            <div class="p-2 text-slate-800 relative">
              <AtomsColorBadge :value="selected_meter.status?.name" :color="selected_meter.status?.color" />
              <button
                class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                @click="meterClicked(selected_meter)">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
          </div>
          <div class="footering">
            <button @click="openRegion('meter')" v-if="selected_meter == null"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.select') }} {{ $t('meter') }}</button>
          </div>
        </div>
      </div>
      <div class="mb-2 col-span-2">
        <div class="field">
          <label for="properties" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('property') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selected_property }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_property"
            class="group grid grid-cols-[1fr,2fr,1fr] divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('common.code') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('address_block.address') }} {{ $t('property') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.cadastral') }}
            </span>
          </div>
          <div v-if="selected_property"
            class="group grid grid-cols-[1fr,2fr,1fr] divide-x text-sm text-center leading-4 ">
            <div class="p-2 text-slate-800">{{ selected_property.token }}</div>
            <div class="p-2 text-slate-800">{{ $AddressHelper.getAddressString(selected_property) }}</div>
            <div class="p-2 text-slate-800 relative">
              {{ selected_property.cadastral }}
              <button
                class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                @click="propertyClicked(selected_property)">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
          </div>
          <div class="footering">
            <button @click="openRegion('property')" v-if="selected_property == null"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.select') }} {{ $t('property') }}</button>
          </div>
        </div>
      </div>
      <div class="mb-2">
        <div class="flex">
          <label for="route" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('route') }} {{ $t('common.and') }} {{ $t('common.position') }}
          </label>
        </div>
        <div class="flex">
          <v-select class="block w-full mr-2 required" :disabled="routes.length == 0 || selected_property == null"
            :model-value="route" @update:modelValue="updateSelected({ entity: 'route', id: $event })"
            :options="routes" />
          <button
            class=" h-9 w-32 border-gray-300 mr-1 border rounded text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200"
            @click="openRegion('order')" :disabled="route == null"><Icon name="fa6-solid:text-md" icon="pencil" />
            {{ $t('common.order_action') }} </button>
        </div>
      </div>

      <div class="mb-2" v-if="selected_position">
        <div class="flex">
          <label for="route" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('address_block.address') }} {{ $t('meter') }} </label>
        </div>
        <div class="mt-2">
          <Icon name="fa6-solid:map" class="display-inline mr-2" />{{ $AddressHelper.getAddressString(selected_position)
          }}
        </div>
      </div>
    </div>

  </div>
  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)"
        class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300"><Icon name="fa6-solid:angles-right"
          class="text-slate-500" /></button>
    </div>
    <div class="px-10">
      <MoleculesAddMeters v-if="editingMeters" @item-clicked="meterClicked" :multiple="false"
        :selected_items="[selected_meter]" :all-statuses="true" />
      <MoleculesAddProperties v-if="editingProperties" @item-clicked="propertyClicked" :multiple="false"
        :selected_items="[selected_property]" />
      <MoleculesOrderPositions v-if="editingOrder" :selected_positions="positions"
        :new_position_id="selected_position?.id" :route_id="route.code" :route_name="route.label"
        @item-clicked="propertyClicked" />
    </div>
  </div>
</template>
