<script setup>
// components/organisms/ClusterDetail.vue
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';


const { $OrderApiService } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  canChange: {
    type: Boolean,
    default: true
  },
  forValidateStatusToken: {
    type: String,
    default: null
  }
});

const loading = ref(false);
const localData = ref(props.data ? props.data : null);
const config = useRuntimeConfig();
const externalGot = String(config.public.externalGot).toLowerCase() === 'true';

const emit = defineEmits(['show-detail', 'clickChangeStatus', 'validate', 'invalidate']);

const showDetail = function (component, id) {
  console.log(component)
  console.log(id)
  emit('show-detail', component, id)
}

const getData = async () => {
  try {
    const response = await $OrderApiService.getDetail(props.id);
    localData.value = response;
  } catch (error) {
    console.error('Error obtaining the data:', error);
    error.value = error;
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (props.id && (!props.data || props.data.length == 0)) {
    loading.value = true
    await getData()
  }
})
</script>

<template>
  <div id="wrapper" class="text-base">
    <div v-if="loading">
      <div class="p-4">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else-if="localData">
      <div role="row" class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <FieldDetail :label='$t("common.code")' :value=localData.token />
        <FieldDetail :label='$t("common.status")' :value="localData.status?.name || localData.token" class="items-center">
          <div class="flex items-center gap-2">
            <AtomsColorBadge :color="localData.status?.color" :value="localData.status?.name"></AtomsColorBadge>
            <button v-if="!isSubRegion && canChange && !externalGot" class="px-2 py-1 text-gray-500" @click="emit('clickChangeStatus')"><Icon name="fa6-solid:pencil" /></button>
            <template v-if="externalGot && localData.status?.token === forValidateStatusToken">
              <button class="p-1 text-green-600 hover:bg-green-50 rounded" :title="t('common.validate')" @click="emit('validate')">
                <Icon name="fa6-solid:check" />
              </button>
              <button class="p-1 text-red-600 hover:bg-red-50 rounded" :title="t('common.invalidate')" @click="emit('invalidate')">
                <Icon name="fa6-solid:xmark" />
              </button>
            </template>
          </div>
        </FieldDetail>
      </div>
      <div role="row" class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <FieldDetail :label='$t("common.type")' :value="localData.type?.name" />
        <FieldDetail :label='$t("order_block.reason")' :value="localData.reason? localData.reason.name : '-'" />
      </div>
      <div role="row" class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <FieldDetail v-if="localData.connection" :label='$t("connection")'>
          <button v-if="!isSubRegion" @click="showDetail('ConnectionRegion', localData.connection.id)" class="text-start text-sky-500 underline">
            <span>{{ localData.connection.token }}</span>
          </button>
          <span v-else> {{ localData.connection.token }}</span>
        </FieldDetail>
        <FieldDetail v-if="localData.connection_request" :label='$t("service_block.short_connection_request")'>
          <button v-if="!isSubRegion" @click="showDetail('ConnectionRequestRegion', localData.connection_request.id)" class="text-start text-sky-500 underline">
            <span>{{ localData.connection_request.token }}</span>
          </button>
          <span v-else> {{ localData.connection_request.token }}</span>
        </FieldDetail>
        <FieldDetail v-if="localData.supply_point" :label='$t("common.supply")'>
          <button v-if="!isSubRegion" @click="showDetail('SupplyPointRegion', localData.supply_point.id)" class="text-start text-sky-500 underline">
            <span>{{ localData.supply_point.address_complete ? localData.supply_point.address_complete : localData.supply_point.token }}</span>
          </button>
          <span v-else>
            {{ localData.supply_point.address_complete ? localData.supply_point.address_complete : localData.supply_point.token }}
          </span>
        </FieldDetail>
        <FieldDetail v-if="localData.incident" :label='$t("incident")'>
          <button v-if="!isSubRegion" @click="showDetail('IncidentRegion', localData.incident.id)" class="text-start text-sky-500 underline">
            <span>{{ localData.incident.token }}</span>
          </button>
          <span v-else>
            {{ localData.incident_token }}
          </span>
        </FieldDetail>
        <FieldDetail v-if="localData.contract" :label='$t("contract")'>
          <button v-if="!isSubRegion" @click="showDetail('ContractRegion', localData.contract.id)" class="text-start text-sky-500 underline">
            <span>{{ localData.contract_token }}</span>
          </button>
          <span v-else>
            {{ localData.contract_token }}
          </span>
        </FieldDetail>
        <FieldDetail v-if="localData.contract_request" :label='$t("contract_block.short_contract_request")'>
          <button v-if="!isSubRegion" @click="showDetail('ContractRequestRegion', localData.contract_request)" class="text-start text-sky-500 underline">
            <span>{{ localData.contract_request_token}}</span>
          </button>
          <span v-else>
            {{ localData.contract_request_token }}
          </span>
        </FieldDetail>
        <FieldDetail v-if="localData.address" :label='$t("common.address")' :value="localData.address.address_complete" />
      </div>
    </div>

  </div>
</template>
