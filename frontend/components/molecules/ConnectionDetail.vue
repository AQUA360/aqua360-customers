<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import { computed } from 'vue';

const { t } = useI18n();
const { $ConfigProjectApiService, $ConnectionApiService } = useNuxtApp();
const { $AddressHelper } = useNuxtApp();

const clusterConnectionToken = ref(null);
const supplyConnectionToken = ref(null);
const activeToken = ref(null);
const emit = defineEmits(['show-map', 'show-detail', 'refresh']);

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: Boolean,
});

const data = computed(() => {
  return props.data;
});

const router = useRouter();

const newCluster = async (id) => {
  router.push(`/service/clusters/add/?connection=${id}`);
}
const editCluster = async (cluster) => {
  router.push(`/service/clusters/edit/${cluster.id}`);
}

const newSupplyPoint = async (id) => {
  router.push(`/service/supplypoints/add/?connection=${id}`);
}
const showSupplyPoint = async (id) => {
  router.push(`/service/supplypoints/?id=${id}`);
}

const showMap = () => {
  emit('show-map');
}

const showDetail = (component, id) => {
  emit('show-detail', component, id);
}

const changeConnectionStatus = async () => {
  try {
    if (confirm(t('service_block.activate_connection_confirmation'))) {
      await $ConnectionApiService.activate(props.data.id);
      emit('refresh');
    }
  } catch (error) {
    console.error('Error changing connection status:', error);
  }
}

const address = computed(() => {
  if (props.data) {
    let text = $AddressHelper.getAddressString(props.data);
    return text;
  }
  else {
    return '';
  }
});

onMounted(async () => {
  clusterConnectionToken.value = await $ConfigProjectApiService.get('connection_has_cluster_token');
  supplyConnectionToken.value = await $ConfigProjectApiService.get('connection_has_supply_point_token');
  activeToken.value = await $ConfigProjectApiService.get('connection_status_active_token');
  console.log("clusterConnectionToken", clusterConnectionToken.value)
  console.log("supplyConnectionToken", supplyConnectionToken.value)
  console.log("activeToken", activeToken.value)

  console.log(!props.data.supply_points || props.data.supply_points.length == 0)
});

</script>

<template>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.identification")' :value=data.token></FieldDetail>
    <FieldDetail :label='$t("service_block.short_install_date")' :value=formatDate(data.installation_at)><Time
        :time="data.installation_at"></Time></FieldDetail>
  </div>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.status")' :value=data.status?.name>
      <AtomsColorBadge :color="data.status?.color" :value="data.status?.name"></AtomsColorBadge>
    </FieldDetail>
    <FieldDetail v-if="!isSubRegion" :label='$t("address_block.location")'>
      <button @click="showMap()" class="text-sky-600 hover:text-sky-800 text-left"
        v-if="data.longitude && data.latitude">
        <Icon name="fa6-solid:map" class="display-inline mr-2" /> {{ $t("service_block.check_map") }}
      </button>
    </FieldDetail>

    <FieldDetail v-if="data.connection_request" :label="$t('service_block.short_connection_request')">
      <div v-if="!isSubRegion" class="flex gap-2">
        <button @click="showDetail('ConnectionRequestRegion', data.connection_request?.id)"
          class="text-start text-sky-500 underline flex items-center gap-2">
          {{ data.connection_request?.token }}
        </button>
        <AtomsRedirectButton :id="data.connection_request.id" :path="'/service/connection-requests/'" />
      </div>
      <span v-else>
        {{ data.connection_request?.token }}
      </span>
    </FieldDetail>
  </div>

  <hr class="my-2" />

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.usage_type")' :value=data.use_type?.name></FieldDetail>
    <FieldDetail :label='$t("exploitation")' :value='data.exploitation?.name || data.exploitation?.token'></FieldDetail>
    <FieldDetail :label='$t("service_block.gis_code")' :value=data.code_gis></FieldDetail>
    <FieldDetail :label='$t("service_block.dma")' :value=data.dma?.token></FieldDetail>
    <FieldDetail :label='$t("address_block.address")' :value="address || data.address_complete"></FieldDetail>
  </div>

  <hr class="my-2" />

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.type")' :value=data.type?.name></FieldDetail>
    <FieldDetail :label='$t("service_block.supply_type")' :value="data.supply_type? data.supply_type.name : '-'"></FieldDetail>
    <FieldDetail :label='$t("service_block.valve_type")' :value=data.valve_type?.name></FieldDetail>
    <FieldDetail :label='$t("service_block.diameter")' :value=data.diameter?.name></FieldDetail>
    <FieldDetail :label='$t("service_block.material")' :value=data.material?.name></FieldDetail>
  </div>

  <hr class="my-2" />
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t(`service_block.installation_type`)' class="mr-3" :value=data.installation_type?.name></FieldDetail>

    <div v-if="data.installation_type?.token == clusterConnectionToken">
      <FieldDetail v-for="cluster in data.clusters" :label='$t("cluster")' :value=cluster?.token>
        <span>{{ cluster?.token }}
          <Icon name="fa6-solid:eye"
            class="transition-all ml-2 duration-200 cursor-pointer text-slate-500 hover:text-sky-500"
            @click="editCluster(cluster)" />
        </span>
      </FieldDetail>
      <button class="button-primary" @click="newCluster(data.id)">
        <Icon name="fa6-solid:plus" />
        {{ t('service_block.new_cluster') }}
      </button>
    </div>
    <div v-if="data.installation_type?.token == supplyConnectionToken">
      <FieldDetail v-for="sp in data.supply_points" :label='$t("supply_point")' :value=sp?.token>
        <button @click="showSupplyPoint(sp.id)" class="text-start text-sky-500 underline">{{ sp?.token }}</button>
      </FieldDetail>
      <button v-if="!data.supply_points || data.supply_points.length == 0" class="button-primary"
        @click="newSupplyPoint(data.id)">
        <Icon name="fa6-solid:plus" />
        {{ t('service_block.assign_supply_point') }}
      </button>
    </div>
  </div>
  <div role="row" class="grid grid-cols-2">
    <div v-if="data.status?.token != activeToken">
      <button class="button-primary"
        @click="changeConnectionStatus">
        <!-- <Icon name="fa6-solid:plus" /> -->
        {{ t('service_block.activate_connection') }}
      </button>
    </div>
  </div>

</template>
