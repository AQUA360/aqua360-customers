<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import ClusterEdit from './ClusterEdit.vue';
import ConnectionEdit from './ConnectionEdit.vue';

const { t } = useI18n();
const route = useRoute();
const { $SupplyPointApiService, $ConfiglistApiService, $ConnectionApiService, $AddressHelper, $ClusterApiService } = useNuxtApp();
const emits = defineEmits(['saved']);

const props = defineProps({
  id: {
    type: String,
    default: null,
    required: false
  },
  supply_point: {
    type: Object,
    required: false,
  },
  destination: {
    type: Object,
    required: false,
    default: null,
  }
});
const selected_address = ref(null);
const selected_connection = ref(null);
const selected_property = ref(null);
const selected_cluster = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingAddress = ref(false);
const editingConnection = ref(false);
const creatingConnection = ref(false);
const editingProperties = ref(false);
const editingCluster = ref(false);
const creatingCluster = ref(false);

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
  if (!data) return;
  token.value = data.token;
  spCadastral.value = data.cadastral || data.property_cadastral || '';
  selected_connection.value = data.connection;
  selected_cluster.value = data?.cluster_nozzle?.id ? data.cluster_nozzle.cluster : null;
  selected_address.value = data.address;
  selected_property.value = data.property;

  type.value = data.type
    ? (types.value.find(t => t.code === data.type.id || t.label === data.type.name || t.code === data.type) ?? null)
    : null;

  source.value = data.source
    ? (sources.value.find(s => s.code === data.source.id || s.label === data.source.name || s.code === data.source) ?? null)
    : null;

  supply_type.value = data.supply_type
    ? (supply_types.value.find(s => s.code === data.supply_type.id || s.label === data.supply_type.name || s.code === data.supply_type) ?? null)
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
  if (connection.id != selected_connection.value?.id) {
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

const newAddress = (address) => {
  selected_address.value = address;
  closeAllRegions();
}

// Funció per guardar el supplypoint
const saveSupplyPoint = async () => {
  console.log("selected_connection");
  console.log(selected_connection.value);
  console.log("selected_property");
  console.log(selected_property.value);
  console.log("selected_address");
  console.log(selected_address.value);
  
  // Validar camps obligatoris
  if (!selected_connection.value) {
    alert(t('common.connection') + ' ' + t('common.required'));
    return;
  }
  if (!selected_property.value) {
    alert(t('property') + ' ' + t('common.required'));
    return;
  }
  if (!selected_address.value) {
    alert(t('address_block.address') + ' ' + t('common.required'));
    return;
  }

  // Construir l'adreça sempre des de selected_address (obligatori), afegint-hi el
  // pis/porta/escala/edifici de la boquilla (ClusterNozzle) que ha obert aquest formulari,
  // amb el mateix criteri de fallback que ClusterEdit.vue al desar la bateria.
  const address = {
    building: props.destination?.building || selected_address.value?.building || null,
    door: props.destination?.door || selected_address.value?.door || null,
    stair: props.destination?.stair || selected_address.value?.stair || null,
    floor: props.destination?.floor || selected_address.value?.floor || null,
    address_extra: props.destination?.address_extra || selected_address.value?.address_extra || null,
    street: {
      ...selected_address.value.street,
      street_id: selected_address.value.street.id,
      type_name: selected_address.value.street.type.name,
    },
    street_number: {
      ...selected_address.value.street_number,
      street_number_id: selected_address.value.street_number?.id,
    },
    city: selected_address.value?.city?.id,
    province: selected_address.value?.city?.province?.id,
    country: selected_address.value?.city?.province?.country?.id,
    postal_code: selected_address.value?.postal_code
  };

  if (selected_address.value.street.type_name.length == 0) {
    address.street.type_name = '-';
  }



  // Afegir dades de la finca a l'adreça
  address.property_cadastral = selected_property.value.cadastral;

  const data = {
    connection_id: selected_connection.value.id,
    token: token.value,
    type: type.value.code,
    source: source.value.code,
    placement_id: placement.value.code,
    supply_type: supply_type.value.code,
    address: address,
    property_id: selected_property.value.id,
    property_cadastral: spCadastral.value,
    is_active: true,
    cluster_id: selected_cluster.value?.id
  };

  try {
    const response = await $SupplyPointApiService.save(data);

    //return navigateTo('/service/supplypoints/')
    emits('saved', response);

  } catch (error) {
    console.error(error);
  }
};

const deleteSupplyPoint = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete?'))) {
    await $SupplyPointApiService.deleteCluster(props.supply_point.id);
    return navigateTo('/service/supplypoints/')
  }
}

const clusterSaved = async (cluster) => {
  //await getCluster(cluster.id);
  selected_cluster.value = cluster;
  closeAllRegions();
}

const propertyClicked = (item) => {
  console.log("property");
  console.log(item);
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

  if (region == 'address') {
    editingAddress.value = true;
  }
  if (region == 'connection') {
    editingConnection.value = true;
  }
  if (region == 'createConnection') {
    creatingConnection.value = true;
  }
  if (region == 'property') {
    editingProperties.value = true;
  }
  if (region == 'selectCluster') {
    editingCluster.value = true;
  }
  if (region == 'createCluster') {
    creatingCluster.value = true;
  }
  showRegion.value = true;
};

const closeAllRegions = () => {
  // tanquem tots els components
  isSubRegionOpen.value = false;
  editingAddress.value = false;
  editingConnection.value = false;
  creatingConnection.value = false;
  editingProperties.value = false;
  editingCluster.value = false;
  creatingCluster.value = false;
  // tanquem region
  showRegion.value = false;
};

const getConnection = async (id) => {
  const connection = await $ConnectionApiService.getDetail(id);
  selected_connection.value = connection;
}

const getCluster = async (id) => {
  const cluster = await $ClusterApiService.getDetail(id);
  selected_cluster.value = cluster;
}

onMounted(async () => {
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
  <div>
    <div class="form">
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label for="clusterToken" class="block text-sm font-medium text-gray-700">{{ t('common.identification') }}</label>
          <input v-model="token" type="text" id="clusterToken" name="clusterToken"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
        </div>
        <div class="mb-4">
          <label for="spCadastral" class="block text-sm font-medium text-gray-700">{{ t('common.cadastral')
          }}</label>
          <input v-model="spCadastral" type="text" id="spCadastral" name="spCadastral"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
        </div>
      </div>
      <!-- Connexió/Escomesa (obligatori) -->
      <div class="mb-4">
        <div class="field">
          <label for="connection" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('connection') }} <span class="text-red-500">*</span>
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
            class="group relative grid grid-cols-4 divide-x text-sm text-center leading-4 ">
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
            <button
              class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
              @click="selected_connection = null">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
          <div class="footering" v-if="selected_connection == null">
            <button @click="openRegion('connection')"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ t('connection') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Finca (obligatori) -->
      <div class="mb-4">
        <div class="field">
          <label for="properties" class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('property') }} <span class="text-red-500">*</span>
          </label>
        </div>
        <div :class="{ 'mt-1': selected_property }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_property"
            class="group grid grid-cols-[1fr,2fr,1fr] divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('common.code') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('address_block.address') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.cadastral') }}
            </span>
          </div>
          <div v-if="selected_property"
            class="group grid grid-cols-[1fr,2fr,1fr] divide-x text-sm text-center leading-4 ">
            <div class="p-2 text-slate-800">{{ selected_property.token }}</div>
            <div class="p-2 text-slate-800">{{ selected_property.address }}</div>
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
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.select') }} {{ t('property') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Adreça (obligatori) -->
      <div class="mb-4">
        <div class="field">
          <label for="address" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('address_block.address') }} <span class="text-red-500">*</span>
          </label>
        </div>
        <div :class="{ 'mt-1': selected_address == null }" class="text-gray-900 divide-y rounded shadow">
          <div class="footering" v-if="selected_address == null">
            <button @click="openRegion('address')"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ $t('address_block.address') }}
            </button>
          </div>
          <div v-else class="relative group footering text-slate-500 rounded shadow p-2">
            {{ selected_address.address_complete }}
            <button
              class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-8 top-1 rounded-md text-slate-600 hover:text-blue-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
              @click="openRegion('address')">
              <Icon name="fa6-solid:pencil" />
            </button>
            <button
              class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
              @click="selected_address = null">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
        </div>
      </div>

      <!-- Cluster (opcional) -->
      <div class="mb-4">
        <div class="field">
          <label for="cluster" class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('cluster') }}
          </label>
        </div>
        <div v-if="selected_cluster != null" class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
          <span class="p-1 text-slate-400">
            {{ t('common.code') }}
          </span>
          <span class="p-1 text-slate-400">
            {{ t('address_block.address') }}
          </span>
          <span class="p-1 text-slate-400">
            {{ t('common.status') }}
          </span>
        </div>
        <div v-if="selected_cluster != null"
          class="group relative grid grid-cols-3 shadow divide-x text-sm text-center leading-4 ">
          <div class="p-2 text-slate-800">{{ selected_cluster.token }}</div>
          <div class="p-2 text-slate-800">
            {{ selected_cluster.address }}
          </div>
          <div class="p-2 text-slate-800 relative">
            <AtomsColorBadge :value="selected_cluster.status?.name" :color="selected_cluster.status?.color" />
          </div>
          <button
            class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
            @click="selected_cluster = null">
            <Icon name="fa6-solid:trash" />
          </button>
        </div>

        <div v-else class="footering grid grid-cols-[1fr,30px] shadow">
          <button @click="openRegion('selectCluster')" :disabled="!selected_connection"
            class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b enabled:hover:bg-slate-200 text-left active:bg-slate-300 disabled:opacity-70 disabled:cursor-not-allowed">
            {{ $t('common.assign') }} {{ t('cluster') }}
          </button>
          <button @click="openRegion('createCluster')" class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300 border-l border-slate-300 items-center justify-center flex">
            <abbr :title="`${$t('common.add')} ${t('cluster')}`">
              <Icon name="fa6-solid:plus" class="text-slate-400" />
            </abbr>
          </button>
        </div>
      </div>

      <div>
        <div class="grid grid-cols-4  gap-2">
          <div class="mb-2">
            <div class="flex">
              <label for="type" class="block text-sm text-slate-500 my-1 ml-1">
                {{ t('common.type') }}</label>
            </div>
            <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="type"
              @update:modelValue="updateSelected({ entity: 'type', id: $event })" :options="types" />
          </div>
          <div class="mb-2">
            <div class="flex">
              <label for="source" class="block text-sm text-slate-500 my-1 ml-1">
                {{ t('service_block.supply_source') }}</label>
            </div>
            <v-select class="block w-full mr-2 required" :disabled="sources.length == 0" :model-value="source"
              @update:modelValue="updateSelected({ entity: 'source', id: $event })" :options="sources" />
          </div>
          <div class="mb-2">
            <div class="flex">
              <label for="supply_type" class="block text-sm text-slate-500 my-1 ml-1">
                {{ t('service_block.supply_type') }}</label>
            </div>
            <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="supply_type"
              @update:modelValue="updateSelected({ entity: 'supply_type', id: $event })" :options="supply_types" />
          </div>
          <div class="mb-2">
            <div class="flex">
              <label for="type" class="block text-sm text-slate-500 my-1 ml-1">
                {{ t('service_block.placement') }}</label>
            </div>
            <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="placement"
              @update:modelValue="updateSelected({ entity: 'placement', id: $event })" :options="placements" />
          </div>
        </div>
      </div>



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
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10 w-[95%]"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="px-10">
      <MoleculesAddAddress v-if="editingAddress" @new-address="newAddress" />
      <MoleculesAddConnections v-if="editingConnection" :selected_items="[selected_connection]"
        @item-clicked="connectionClicked" :multiple="false" />
      <MoleculesAddProperties v-if="editingProperties" @item-clicked="propertyClicked" :multiple="false"
        :selected_items="[selected_property]" />
      <ClusterEdit v-if="creatingCluster" :id="selected_cluster?.id" :connection="selected_connection"
        :allowNavigation="false" @saved="clusterSaved" />
      <MoleculesAddClusters v-if="editingCluster" :connection_id="selected_connection?.id"
        :selected_items="[selected_cluster]" @item-clicked="clusterSaved" :multiple="false" />
      <ConnectionEdit v-if="creatingConnection" :connection="selected_connection? selected_connection.id : null" 
      :isSubRegion="true" @saved="connectionClicked" />
    </div>
  </div>
</template>