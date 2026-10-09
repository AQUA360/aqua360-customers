<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const route = useRoute();
const { $SupplyPointApiService, $ConfiglistApiService, $ConnectionApiService } = useNuxtApp();
const emits = defineEmits(['saved']);
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  id: {
    type: String,
    default: null,
    required: false
  },
  supply_point: {
    type: Object,
    required: false,
  }
});
const selected_connection = ref(null);
const selected_property = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingConnection = ref(false);
const editingProperties = ref(false);

const token = ref(null);

const type = ref(null);
const supply_type = ref(null);
const source = ref(null);
const placement = ref(null);

const spCadastral = ref('');

const types = ref([]);
const supply_types = ref([]);
const sources = ref([]);
const placements = ref([]);

const loadFromDetail = async (data) => {
  token.value = data.token;
  spCadastral.value = data.cadastral;
  selected_connection.value = data.connection;

  type.value = data.type
    ? (types.value.find(t => t.code === data.type.id || t.label === data.type.name) ?? null)
    : null;

  source.value = data.source
    ? (sources.value.find(s => s.code === data.source.id || s.label === data.source.name) ?? null)
    : null;

  supply_type.value = data.supply_type
    ? (supply_types.value.find(s => s.code === data.supply_type.id || s.label === data.supply_type.name) ?? null)
    : null;

  placement.value = data.placement
    ? (placements.value.find(p => p.code === data.placement) ?? null)
    : null;
}

const getSelectData = async (entity, targetArray, targetValue) => {
  let data = await $ConfiglistApiService.getAll('service/' + entity);
  data.results?.forEach(item => {
    targetArray.value.push({
      code: item.id,
      label: item.name || item.token
    })
  });
  if (targetArray.value.length > 0) {
    targetValue.value = targetArray.value[0];
  }
}

const connectionClicked = (connection) => {
  if (connection != selected_connection.value) {
    selected_connection.value = connection;
  }
  else {
    selected_connection.value = null;
  }
  setTimeout(() => {
    closeAllRegions();
  }, 200)
}

const updateSelected = (e) => {
  if (e.entity == 'type') {
    type.value = e.id;
  }
  else if (e.entity == 'source') {
    source.value = e.id;
  }
  else if (e.entity == 'placement') {
    placement.value = e.id;
  }
  else if (e.entity == 'supply_type') {
    supply_type.value = e.id;
  }
}

// Funció per guardar el supplypoint
const saveSupplyPoint = async () => {
  
  const address = {
    street: {
      ...selected_connection.value.address_street,
      street_id: selected_connection.value.address_street.id,
      type_name: selected_connection.value.address_street.type.name,
    },
    street_number: {
      ...selected_connection.value.address_street_number,
      street_number_id: selected_connection.value.address_street_number?.id,
    },
    city: selected_connection.value.address_city.id,
    province: selected_connection.value.address_city.province.id,
    country: selected_connection.value.address_city.province.country.id,
    postal_code: selected_connection.value.address_postal_code?.code
  }
  if(selected_connection.value.address_street.type_name.length==0) {
    address.street.type_name = '-';
  }
  if(selected_property.value) {
    address.property_cadastral = selected_property.value;
  }
  const data = {
    id: props.supply_point?.id || null,
    connection_id: selected_connection.value?.id,
    cadastral: spCadastral.value,
    token: clusterToken.value,
    type: type.value.code,
    source: source.value?.code,
    placement_id: placement.value?.code,
    supply_type: supply_type.value.code,
    address_data: address,
    property_id: selected_property?.value?.id,
    property_cadastral: spCadastral?.value,
    is_active: true
  };

  try {
    const response = await $SupplyPointApiService.save(data);

    return navigateTo('/service/supplypoints/')

  } catch (error) {
    console.error(error);
  }
};

const deleteSupplyPoint = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    await $SupplyPointApiService.deleteCluster(props.supply_point.id);
    return navigateTo('/service/supplypoints/')
  }
}

const propertyClicked = (item) => {
  if (item.id == selected_property.value?.id) {
    selected_property.value = null;
  }
  else {
    selected_property.value = item;
  }
  setTimeout(() => {
    closeAllRegions();
    /* emitData(); */
  }, 200)
};

const openRegion = (region) => {
  closeAllRegions();

  if (region == 'connection') {
    editingConnection.value = true;
  }
  if (region == 'property') {
    editingProperties.value = true;
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
  editingConnection.value = false;

  // tanquem region
  showRegion.value = false;
};

const getConnection = async (id) => {
  const connection = await $ConnectionApiService.getDetail(id);
  selected_connection.value = connection;
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($SupplyPointApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  await getSelectData('supply-point-type', types, type);
  await getSelectData('supply-point-supply-type', supply_types, supply_type);
  await getSelectData('supply-point-source', sources, source);
  await getSelectData('supply-point-placement', placements, placement);
  // Si tenim un cluster, carreguem les dades
  if (props.supply_point) {
    loadFromDetail(props.supply_point);
  }
  else {
    token.value = _.random(100000, 999999)
  }
  if (route.query.connection) {
    await getConnection(route.query.connection)
  }
});

</script>

<template>
  <div v-if="objectPermissions?.can_change">
    <div class="form">
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label for="clusterToken" class="block text-sm font-medium text-gray-700">{{ t('common.identification') }}</label>
          <input v-model="token" type="text" id="clusterToken" name="clusterToken"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
        </div>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label for="spCadastral" class="block text-sm font-medium text-gray-700">{{ t('common.cadastral')
            }}</label>
          <input v-model="spCadastral" type="text" id="spCadastral" name="spCadastral"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
        </div>
      </div>
      <div class="mb-2 col-span-2">
        <div class="field">
          <label for="connection" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('Escomesa') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selected_connection == null }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_connection != null"
            class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('common.code') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('address_block.address') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('exploitation') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.status') }}
            </span>
          </div>
          <div v-if="selected_connection != null"
            class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
            <div class="p-2 text-slate-800">{{ selected_connection.token }}</div>
            <div class="p-2 text-slate-800">
              {{ selected_connection.address_complete }}
            </div>
            <div class="p-2 text-slate-800">
              {{ selected_connection.exploitation?.name || selected_connection.exploitation?.token }}
            </div>
            <div class="p-2 text-slate-800 relative">
              <AtomsColorBadge :value="selected_connection.status?.name" :color="selected_connection.status?.color" />
            </div>
          </div>
          <div class="footering" v-if="selected_connection == null">
            <button @click="openRegion('connection')"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ $t('connection') }}
            </button>
          </div>
        </div>
      </div>

      <div>
        <div class="grid grid-cols-4  gap-2">
          <div class="mb-2">
            <div class="flex">
              <label for="type" class="block text-sm text-slate-500 my-1 ml-1">
                {{ $t('common.type') }}</label>
            </div>
            <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="type"
              @update:modelValue="updateSelected({ entity: 'type', id: $event })" :options="types" />
          </div>
          <div class="mb-2">
            <div class="flex">
              <label for="source" class="block text-sm text-slate-500 my-1 ml-1">
                {{ $t('service_block.supply_source') }}</label>
            </div>
            <v-select class="block w-full mr-2 required" :disabled="sources.length == 0" :model-value="source"
              @update:modelValue="updateSelected({ entity: 'source', id: $event })" :options="sources" />
          </div>
          <div class="mb-2">
            <div class="flex">
              <label for="supply_type" class="block text-sm text-slate-500 my-1 ml-1">
                {{ $t('service_block.supply_type') }}</label>
            </div>
            <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="supply_type"
              @update:modelValue="updateSelected({ entity: 'supply_type', id: $event })" :options="supply_types" />
          </div>
          <div class="mb-2">
            <div class="flex">
              <label for="type" class="block text-sm text-slate-500 my-1 ml-1">
                {{ $t('service_block.placement') }}</label>
            </div>
            <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="placement"
              @update:modelValue="updateSelected({ entity: 'placement', id: $event })" :options="placements" />
          </div>
        </div>
      </div>

      <!-- <div class="mb-2 col-span-2">
        <div class="field">
          <label for="properties" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('Finca') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selected_property }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_property"
            class="group grid grid-cols-[1fr,2fr,1fr] divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('Codi') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('Adreça de la finca') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('Cadastre') }}
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
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('Seleccionar finca') }}
            </button>
          </div>
        </div>
      </div> -->

    </div>
    <hr class="mb-3" />

    <div class="col-span-3 flex flex-row-reverse mt-4">
      <button v-if="props.supply_point != null" @click="deleteSupplyPoint" class="button-default mx-5">
        &nbsp; {{ $t('common.delete') }}
      </button>
      <button @click="saveSupplyPoint" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
          t('common.save') }}
      </button>
    </div>

  </div>
  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="px-10">
      <MoleculesAddConnections v-if="editingConnection" :selected_items="[selected_connection]"
        @item-clicked="connectionClicked" :multiple="false" />
      <MoleculesAddProperties v-if="editingProperties" @item-clicked="propertyClicked" :multiple="false"
        :selected_items="[selected_property]" />
    </div>
  </div>
</template>