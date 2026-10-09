<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';
import { useToast } from 'vue-toastification';

const { $AddressHelper, $SupplyPointApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  data: {
    type: Object,
    required: false
  },
  reduced: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-detail', 'activar', 'show-map']);

// Variables locals
const localData = ref(props.data ? { ...props.data } : null);
const isLoading = ref(false);
const error = ref(null);
const activeContractToken = ref(null)
const toast = useToast();
const isEditingObservation = ref(false);
const editObservationText = ref('');
const isSavingObservation = ref(false);

const startEditObservation = () => {
  editObservationText.value = localData.value?.reader_observation || '';
  isEditingObservation.value = true;
};

const cancelEditObservation = () => {
  isEditingObservation.value = false;
};

const saveObservation = async () => {
  isSavingObservation.value = true;
  try {
    await $SupplyPointApiService.patch(props.id, {
      reader_observation: editObservationText.value
    });
    if (localData.value) {
      localData.value.reader_observation = editObservationText.value;
    }
    toast.success(t('common.saved_successfully') || 'Guardat correctament');
    isEditingObservation.value = false;
  } catch (err) {
    console.error('Error updating observation:', err);
    toast.error(t('common.error_save') || 'Error en desar');
  } finally {
    isSavingObservation.value = false;
  }
};


// Funció per mostrar detalls
const showDetail = (component, id) => {
  emit('show-detail', component, id);
};

// Funció per activar el punt de subministrament
const activar = async () => {
  try {
    await $SupplyPointApiService.activate(props.id);
    emit('activar', { id: props.id });
  } catch (err) {
    console.error('Error activant el punt de subministrament:', err);
  }
};

// Funció per obtenir les dades des de l'API
const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $SupplyPointApiService.getDetail(props.id);
    localData.value = detail;

  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
};

// Llista de contractes actius filtrada, recalculada automàticament
// cada cop que canvien localData o activeContractToken (p. ex. en canviar
// de supply point seleccionat), en lloc de calcular-se una sola vegada.
const contracts = computed(() => {
  if (!localData.value?.contracts) return [];

  const distinctContractsMap = new Map();

  return localData.value.contracts.filter((contract) => {
    if (activeContractToken.value && contract.status_token == activeContractToken.value) {
      const contractString = JSON.stringify(contract);
      if (!distinctContractsMap.has(contractString)) {
        distinctContractsMap.set(contractString, true);
        return true;
      }
    }
    return false;
  });
});

// Executar la funció quan el component es munta
onMounted(async () => {
  activeContractToken.value = await $ConfigProjectApiService.get('contract_active_token');
  if (!props.data && props.id) {
    await fetchData();
  }
});

// Observa canvis en l'id per tornar a carregar les dades si cal
watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});

watch(() => props.data, (newValue) => {
  localData.value = newValue;
}, { deep: true, immediate: true });

const showMap = () => {
  emit('show-map');
}
</script>

<template>
  <div v-if="isLoading" class="loading">
    <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
    {{ $t('common.loading') }}...
  </div>

  <div v-else-if="error" class="error">
    <!-- Gestiona l'error segons sigui necessari -->
    {{ $t('common.error_load') }}
  </div>

  <div v-else-if="localData">
    <div v-if="localData?.contract_debt && localData?.contract_debt > 0" role="alert" class="mb-2">
      <div class="flex items-center gap-3 w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-1 shadow-sm">
        <div
          class="flex h-4 w-4 shrink-0 items-center justify-center text-amber-700">
          <Icon name="fa6-solid:money-bill-wave" class="text-sm" />
        </div>
        <div class="min-w-0 flex-1 flex flex-wrap items-center justify-between gap-2">
          <span class="text-sm font-semibold text-amber-900 leading-snug">
            {{ $t('service_block.supply_with_contract_debt') }}
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-md bg-amber-600 px-2.5 py-1 text-sm font-bold tabular-nums text-white shadow-sm">
            <Icon name="fa6-solid:circle-exclamation" class="text-[10px] opacity-90" />
            {{ formatMoneyWithCurrency(localData?.contract_debt) }}
          </span>
        </div>
      </div>
    </div>
    <div v-if="localData?.supply_cut_alert" role="alert" class="mb-2">
      <div class="flex items-center gap-3 w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-1 shadow-sm">
        <div class="flex h-4 w-4 shrink-0 items-center justify-center text-amber-700">
          <Icon name="fa6-solid:scissors" class="text-sm" />
        </div>
        <div class="min-w-0 flex-1 flex flex-wrap items-center gap-x-2 gap-y-1">
          <span class="text-sm font-semibold text-amber-900 leading-snug">
            {{ $t('service_block.supply_with_cut') }}
          </span>
          <span class="text-sm text-amber-800 leading-snug">
            {{ localData.supply_cut_alert.status_name }}
            ({{ localData.supply_cut_alert.temporary ? $t('service_block.cut_temporary') : $t('service_block.cut_indefinite') }})
          </span>
          <span v-if="localData.supply_cut_alert.date_end" class="text-sm text-amber-800 leading-snug">
            &middot; {{ $t('service_block.until') }} {{ formatDateTime(localData.supply_cut_alert.date_end) }}
          </span>
        </div>
      </div>
    </div>
    <div v-if="localData.current_fraud" role="row" class="">
      <div class="flex justify-center items-center gap-2 border border-orange-500 rounded p-1 w-fit">
        <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-orange-500 my-auto" />
        <span class="text-orange-400 font-semibold">
          {{ $t('service_block.supply_with_fraud') }}
        </span>
      </div>
      <hr class="my-2 col-span-2" />
    </div>
    <div v-else-if="!localData.current_fraud && localData.previous_fraud" role="row" class="">
      <div class="flex justify-center items-center gap-2 border border-slate-500 rounded p-1 w-fit">
        <Icon name="fa6-solid:circle-exclamation" class="font-bold text-slate-400 my-auto" />
        <span class="text-slate-400 font-semibold">
          {{ $t('service_block.supply_with_fraud_history') }}
        </span>
      </div>
      <hr class="my-2 col-span-2" />
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label="$t('common.identification')" :value="localData.token">
        <button v-if="reduced && !isSubRegion" @click="showDetail('SupplyPointRegion', localData.id)"
          class="text-start text-sky-500 underline">{{
            localData.token }}</button>
        <span v-else>{{ localData.token }}</span>
      </FieldDetail>
      <FieldDetail :label="t('common.registration_date')" :value="formatDate(localData.created_at)">
        <Date :date="localData.created_at"></Date>
      </FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail v-if="localData.address" :label="$t('address_block.street')"
        :value="$AddressHelper.getStreetString(localData.address)"></FieldDetail>
      <FieldDetail :label="$t('address_block.locality')"
        :value="`${localData.address?.postal_code} ${localData.address?.city?.name}`">
      </FieldDetail>

      <FieldDetail v-if="localData.address?.street_number" :label="$t('common.number')"
        :value="$AddressHelper.getNumberString(localData.address.street_number)"></FieldDetail>
      <FieldDetail v-if="localData.address?.floor"
        :label="`${$t('address_block.floor')} - ${$t('address_block.door')}`">
        <span>
          <span v-if="localData.address?.floor && localData.address?.floor != 0">{{ localData.address.floor + ' - '
            }}</span>
          <span>{{ localData.address.door }}</span>
        </span>
      </FieldDetail>
      <FieldDetail v-else-if="localData.address?.door" :label="$t('address_block.door')"
        :value="localData.address.door"></FieldDetail>
      <FieldDetail v-if="localData.address?.stair" :label="$t('address_block.stair')" :value="localData.address.stair">
      </FieldDetail>
      <FieldDetail v-if="localData.address?.building" :label="$t('address_block.building')"
        :value="localData.address.building">
      </FieldDetail>
      <FieldDetail v-if="localData.address?.address_extra" :label="$t('address_block.address_extra')"
        :value="localData.address.address_extra">
      </FieldDetail>
      <FieldDetail v-if="localData.connection" :label="$t('exploitation')"
        :value="localData.connection.exploitation?.name"></FieldDetail>
    </div>
    <hr class="my-2" />
    <div v-if="!reduced" role="row" class="grid grid-cols-2">
      <FieldDetail :label="$t('common.type')" :value="localData.type?.name"></FieldDetail>
      <FieldDetail :label="$t('service_block.potable')"
        :value="localData.is_potable ? $t('common.yes') : $t('common.no')"></FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label="$t('common.status')" class="flex">
        <AtomsColorBadge :value="localData.status?.name" :color="localData.status?.color" />
      </FieldDetail>
      <FieldDetail v-if="!reduced" :label="$t('address_block.location')" :value="localData.placement?.name">
      </FieldDetail>
    </div>
    <div v-if="!reduced" role="row" class="grid grid-cols-2">
      <FieldDetail :label="$t('service_block.supply_source')" :value="localData.source?.name"></FieldDetail>
      <FieldDetail :label="$t('service_block.supply_type')" :value="localData.supply_type?.name"></FieldDetail>
    </div>

    <hr v-if="!reduced" class="my-2" />
    <!-- Contracts -->
    <div v-if="contracts && contracts.length >= 1 && !reduced" class="">
      <!-- <span class="ml-2 p-1 bg-sky-50 border rounded italic font-medium text-slate-600">{{ $t('Contractes') }}</span> -->
      <div class="mt-2">
        <div v-for="contract in contracts" :key="contract.id" class="grid grid-cols-2">
          <FieldDetail :label="$t('contract')" :value="contract.token">
            <div class="flex gap-2">
              <button v-if="!isSubRegion" @click="showDetail('ContractRegion', contract.id)"
                class="text-start text-sky-500 underline">{{
                  contract.token }}</button>
              <span v-else>{{ contract.token }}</span>
              <AtomsRedirectButton :id="contract.id" :path="'/contract/contracts/'" />
            </div>
          </FieldDetail>
          <FieldDetail :label="$t('contract_block.holder')" :value="contract.holder" />
        </div>
      </div>
    </div>
    <!-- <div v-if="localData.contracts && localData.contracts.length > 1" class="">
      <span class="ml-2 p-1 bg-sky-50 border rounded italic font-medium text-slate-600">{{ $t('Contractes') }}</span>
      <div class="mt-2">
        <div v-for="contract in localData.contracts" :key="contract.id" class="grid grid-cols-2">
          <FieldDetail :label="$t('Contracte')" :value="contract.token">
            <button v-if="!isSubRegion" @click="showDetail('ContractRegion', contract.id)"
              class="text-start text-sky-500 underline">{{
                contract.token }}</button>
            <span v-else>{{ contract.token }}</span>
          </FieldDetail>
          <FieldDetail :label="$t('Titular')" :value="contract.holder" />
        </div>
      </div>
    </div>
    <div v-else-if="localData.contracts && localData.contracts.length === 1" class="grid grid-cols-2">
      <FieldDetail :label="$t('Contracte')" :value="localData.contracts[0].token">
        <button v-if="!isSubRegion" @click="showDetail('ContractRegion', localData.contracts[0].id)"
          class="text-start text-sky-500 underline">{{
            localData.contracts[0].token }}</button>
        <span v-else>{{ localData.contracts[0].token }}</span>
      </FieldDetail>
      <FieldDetail :label="$t('Titular')" :value="localData.contracts[0].holder" />
    </div> -->
    <div v-else class="grid grid-cols-2">
      <FieldDetail v-if="!reduced" :label="$t('contract')" value="-"></FieldDetail>
      <FieldDetail v-if="!reduced" :label="$t('contract_block.holder')" value="-"></FieldDetail>
    </div>
    <!-- /end Contracts -->

    <hr v-if="!reduced" class="my-2" />
    <div v-if="!reduced" role="row" class="grid grid-cols-2">
      <FieldDetail :label="$t('common.cadastral')" :value="localData.cadastral?.toUpperCase()"></FieldDetail>
      <FieldDetail v-if="!isSubRegion && localData.connection" :label="$t('address_block.location')">
        <!--a href="" class="underline text-gray-700">Veure mapa</a-->
        <button @click="showMap()" class="text-sky-600 hover:text-sky-800 text-left"
          v-if="localData.connection?.longitude && localData.connection?.latitude">
          <Icon name="fa6-solid:map" class="display-inline mr-2" /> {{ $t("service_block.check_map") }} ({{
            $t('connection') }})
        </button>
      </FieldDetail>
    </div>
    <div v-if="!reduced" role="row" class="grid grid-cols-2">
      <FieldDetail :label="$t('property')">
        <div class="flex gap-2">
          <span v-if="isSubRegion && localData.property">{{ localData.property.token }}</span>
          <button v-else-if="localData.property" @click="showDetail('PropertyRegion', localData.property.id)"
            class="text-start text-sky-500 underline">{{ localData.property.token }}</button>
          <span v-else>-</span>
          <AtomsRedirectButton v-if="localData.property" :id="localData.property.id" :path="'/service/properties/'" />
        </div>
      </FieldDetail>
      <FieldDetail :label="$t('meter')">
        <div class="flex gap-2">
          <span v-if="isSubRegion && localData.meter">{{ localData.meter?.code }}</span>
          <button v-else-if="localData.meter" @click="showDetail('MeterRegion', localData.meter.id)"
            class="text-start text-sky-500 underline">{{ localData.meter?.code }}</button>
          <span v-else>-</span>
          <AtomsRedirectButton v-if="localData.meter" :id="localData.meter?.id" :path="'/service/meters/'" />
        </div>
      </FieldDetail>
      <FieldDetail :label="$t('route')">
        <span v-if="isSubRegion && localData.property && localData.property.route_position">{{
          localData.property.route_position.token }}</span>
        <button v-else-if="localData.property && localData.property.route_position"
          @click="showDetail('RouteRegion', localData.property.route_position.route.id)"
          class="text-start text-sky-500 underline">{{ localData.property?.route_position?.token }}</button>
        <span v-else>-</span>
      </FieldDetail>
      <FieldDetail :label="$t('service_block.zone')">
        <span v-if="localData.property && localData.property?.route_position?.route?.route_zone">
          {{ localData.property?.route_position?.route?.route_zone?.token }}</span>
        <span v-else>-</span>
      </FieldDetail>
    </div>
    <div v-if="!reduced" role="row" class="grid grid-cols-2">
      <FieldDetail :label="$t('cluster')">
        <span v-if="isSubRegion && localData.cluster_nozzle">{{ localData.cluster_nozzle?.token }}</span>
        <button v-else-if="localData.cluster_nozzle"
          @click="showDetail('ClusterRegion', localData.cluster_nozzle.cluster.id)"
          class="text-start text-sky-500 underline">{{ localData.cluster_nozzle?.token }}</button>
        <span v-else>-</span>
      </FieldDetail>
      <FieldDetail :label="$t('connection')">
        <span v-if="isSubRegion && localData.connection">{{ localData.connection?.token }}</span>
        <button v-else-if="localData.connection" @click="showDetail('ConnectionRegion', localData.connection.id)"
          class="text-start text-sky-500 underline">{{ localData.connection?.token }}</button>
        <span v-else>-</span>
      </FieldDetail>
    </div>

    <div v-if="!reduced" class="my-3">
      <div class="bg-slate-50/75 border border-slate-200/80 rounded-lg p-3 transition-all duration-200 hover:shadow-sm">
        <div class="flex justify-between items-start gap-2 mb-1.5">
          <label class="text-xs font-semibold uppercase tracking-wide text-slate-500 flex items-center gap-1.5 leading-snug">
            <Icon name="fa6-solid:comment-dots" class="text-sky-500" />
            {{ $t('common.reader_observation') }}
          </label>
          <button v-if="!isEditingObservation" @click="startEditObservation"
            class="text-xs text-sky-600 hover:text-sky-800 flex items-center gap-1 font-medium transition-colors px-2 py-0.5 rounded hover:bg-sky-50"
            :title="$t('common.edit') || 'Editar'">
            <Icon name="fa6-solid:pen" class="text-[10px]" />
            <span>{{ localData.reader_observation ? ($t('common.edit') || 'Editar') : ($t('common.add') || 'Afegir')
              }}</span>
          </button>
        </div>

        <div v-if="isEditingObservation" class="mt-2 space-y-2">
          <textarea v-model="editObservationText" rows="3"
            class="w-full text-sm border border-slate-300 rounded-md p-2 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 outline-none transition-all resize-y bg-white"
            :placeholder="$t('common.reader_observation')"></textarea>
          <div class="flex justify-end gap-2">
            <button @click="cancelEditObservation" :disabled="isSavingObservation"
              class="px-2.5 py-1 text-xs text-slate-600 hover:text-slate-800 font-medium rounded hover:bg-slate-200/60 transition-colors disabled:opacity-50">
              {{ $t('common.cancel') || 'Cancel·lar' }}
            </button>
            <button @click="saveObservation" :disabled="isSavingObservation"
              class="px-3 py-1 text-xs bg-sky-600 text-white font-medium rounded hover:bg-sky-700 transition-colors shadow-sm inline-flex items-center gap-1 disabled:opacity-50">
              <Icon v-if="isSavingObservation" name="fa6-solid:spinner" class="animate-spin text-[10px]" />
              <Icon v-else name="fa6-solid:check" class="text-[10px]" />
              <span>{{ isSavingObservation ? ($t('common.saving') || 'Desant...') : ($t('common.save') || 'Desar')
                }}</span>
            </button>
          </div>
        </div>

        <div v-else class="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
          <span v-if="localData.reader_observation">{{ localData.reader_observation }}</span>
          <span v-else class="text-slate-400 italic text-xs">{{ $t('common.no_data') || 'Sense observacions' }}</span>
        </div>
      </div>
    </div>

    <hr v-if="!reduced" class="my-2" />
    <div v-if="!reduced" role="row" :class="{ 'grid grid-cols-2': true, 'opacity-50': !localData.removal_at }">
      <FieldDetail :label="$t('common.termination_date')"
        :value="localData.removal_at ? formatDate(localData.removal_at) : '-'">
      </FieldDetail>
      <FieldDetail :label="$t('order_block.reason')" :value="localData.removal_reason"></FieldDetail>
    </div>

    <div v-if="localData.removal_at && !reduced" role="row" class="grid grid-cols-2">
      <ButtonOutline @click="activar">{{ $t('common.activate') }} {{ $t('supply_point') }}</ButtonOutline>
    </div>
    <hr v-if="!reduced" class="my-2" />
  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
