<script setup>
import { ref, onMounted } from 'vue';
import _ from 'lodash';

const { t }= useI18n();
const { $ExploitationApiService, $ClusterApiService } = useNuxtApp();

const props = defineProps({
  request: Object
});

const emit = defineEmits(['change-setup']);

const loading = ref(true);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingConnection = ref(false);
const selected_connection = ref(null); 

const exploitations = ref([]);
const exploitation = ref(null);

const clusters_data = ref([]);
const clusters = ref([]);
const cluster = ref(null);

const nozzles = ref([]);
const nozzle = ref(null);

const token = ref('');

const loadData = async () => {
  if (props.request) {
    token.value = props.request.token;
    if (props.request.exploitation) {
      exploitation.value = {
        code: props.request.exploitation.id,
        label: props.request.exploitation.name,
      }
    }

    if (props.request.connection) {
      selected_connection.value = props.request.connection
      await getClusters();
      if (props.request.cluster) {
        cluster.value = {
          code: props.request.cluster.id,
          label: props.request.cluster.token,
        }
      }
      await setNozzles();
      if (props.request.cluster_nozzle) {
        nozzle.value = {
          code: props.request.cluster_nozzle.id,
          label: props.request.cluster_nozzle.token,
        }
      }
    }
  }
  else {
    token.value = _.random(100000, 999999);
  }
  emitSetup();
};
const getData = async () => {
  await getExploitations();
  loadData();
};

const getExploitations = async () => {
  loading.value = true;
  try {
    const data = await $ExploitationApiService.getData();
    exploitations.value = data.results.map(exploitation => {
      return {
        label: exploitation.name,
        code: exploitation.id
      }
    });
    exploitation.value = exploitations.value[0];
  } catch (error) {
    console.error('Error loading draft:', error);
  }
  loading.value = false;
  emitSetup();
};

const getClusters = async () => {
  try {
    const data = await $ClusterApiService.getData('',[],1,null,false, selected_connection.value?.id);
    clusters_data.value = data.results;
    clusters.value = data.results.map(cluster => {
      return {
        label: cluster.token,
        code: cluster.id
      }
    });
    if (clusters.value.length > 0 && !props.request) {
      cluster.value = clusters.value[0];
      emitSetup();
      setNozzles();
    }
  } catch (error) {
    console.error('Error loading draft:', error);
  }
};

const setNozzles = async () => {
  if (cluster.value) {
    let myCluster = clusters_data.value.find(c => c.id == cluster.value.code);
    if (myCluster) {
      nozzles.value = myCluster.nozzles.map(nozzle => {
        return {
          label: nozzle.token,
          code: nozzle.id
        }
      });

      if (nozzles.value.length > 0 && !props.request) {
        nozzle.value = nozzles.value[0];
        emitSetup();
      }
    }
  }
};

const updateSelected = (e) => {
  if (e == 'exploitation') {
    selected_connection.value = null;
    clusters.value = [];
    cluster.value = null;
    nozzles.value = [];
    nozzle.value = null;
  }
  else if (e == 'cluster') {
    setNozzles();
  }
  emitSetup();
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const openRegion = (region) => {
  closeAllRegions();

  if (region == 'connection') {
    editingConnection.value = true;
  }

  showRegion.value = true;
};

const closeAllRegions = () => {
  // tanquem tots els components
  editingConnection.value = false;

  // tanquem region
  showRegion.value = false;
};

const connectionClicked = (connection) => {
  if (connection != selected_connection.value) {
    selected_connection.value = connection;
    getClusters();
  }
  else {
    selected_connection.value = null;
    clusters.value = [];
    cluster.value = null;
    nozzles.value = [];
    nozzle.value = null;
  }
  setTimeout(() => {
    closeAllRegions();
  }, 200)
  emitSetup();
}

const emitSetup = () => {
  emit('change-setup', {
    exploitation_id: exploitation.value?.code || null,
    connection_id: selected_connection.value?.id || null,
    cluster_id: cluster.value?.code || null,
    nozzle_id: nozzle.value?.code || null,
    token: token.value
  });
}

onMounted(() => {
  getData();
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <h2 class="text-xl font-semibold mb-4">{{ $t('common.step') }} 1: {{ $t('service_block.request_setup_title') }}</h2>
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
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ $t('common.code') }}</label>
          <input type="text" v-model="token" class="input" :disabled="props.request?.token != null"/>
        </div>
      <div class="mb-2">
        <div class="flex">
          <label for="exploitation" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('exploitation') }}</label>
        </div>
        <v-select class="block w-full mr-2 required" :disabled="exploitations.length == 0" :v-model="exploitation"
        @update:modelValue="updateSelected('exploitation')" :options="exploitations"/>
      </div>

      <div class="mb-2 col-span-2">
        <div class="field">
          <label for="connection" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('connection') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selected_connection == null }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_connection != null"
            class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ $t('common.code') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ $t('address_block.address') }} {{ $t('connection') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ $t('exploitation') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ $t('common.status') }}
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
              <button
                class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                @click="connectionClicked(selected_connection)">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
          </div>
          <div class="footering" v-if="selected_connection == null">
            <button @click="openRegion('connection')" :disabled="exploitation == null"
              class="display-block block disabled:bg-slate-100 w-full px-1 py-1 text-base text-slate-400 enabled:hover:bg-slate-200 text-left enabled:active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ $t('connection') }}</button>
          </div>
        </div>
      </div>
      <div class="mb-2">
        <div class="flex">
          <label for="cluster" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('cluster') }}</label>
        </div>
        <v-select class="block w-full mr-2 required mb-2" :disabled="clusters.length == 0 || exploitation == null" :v-model="cluster"
        @update:modelValue="updateSelected('cluster')" :options="clusters"/>
      </div>

      <div class="mb-2">
        <div class="flex">
          <label for="nozzle" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('service_block.nozzle') }}</label>
        </div>
        <v-select class="block w-full mr-2 required mb-2" :disabled="nozzles.length == 0 || cluster == null" :v-model="nozzle"
        @update:modelValue="emitSetup" :options="nozzles"/>
      </div>

    </div>

  </div>
  <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <MoleculesAddConnections v-if="editingConnection" :selected_items="[selected_connection]" :exploitation_id="exploitation?.code"
          @item-clicked="connectionClicked" :multiple="false" />
      </div>
    </div>
</template>
