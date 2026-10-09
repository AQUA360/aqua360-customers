<script setup>
import { ref, watch, shallowRef } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import SupplyPointDetail from '~/components/molecules/SupplyPointDetail.vue';
import AddAddress from '../molecules/AddAddress.vue';
import AddMeters from '../molecules/AddMeters.vue';
import FraudMiniDetail from '../molecules/FraudMiniDetail.vue';
import SupplyCutMiniDetail from '../molecules/SupplyCutMiniDetail.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

// subregions
import MeterRegion from '~/components/organisms/MeterRegion.vue';
import ClusterRegion from '~/components/organisms/ClusterRegion.vue';
import ConnectionRegion from '~/components/organisms/ConnectionRegion.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import RouteRegion from '~/components/organisms/RouteRegion.vue';
import SupplyPointRemoval from '~/components/organisms/SupplyPointRemoval.vue';
import PropertyRegion from '~/components/organisms/PropertyRegion.vue';
import AddProperties from '../molecules/AddProperties.vue';
import AddConnections from '../molecules/AddConnections.vue';
import ReadingDetail from '../molecules/ReadingDetail.vue';
import AddFraud from '../molecules/AddFraud.vue';
import FraudRegion from './FraudRegion.vue';
import SupplyCutRegion from './SupplyCutRegion.vue';
import SupplyMeterChange from '../molecules/SupplyMeterChange.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import InvoiceRegion from './InvoiceRegion.vue';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion']);
const router = useRouter();
const { $SupplyPointApiService, $ConfigProjectApiService, $ContractApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const selectedAddress = ref(null);

const SubRegion = ref(props.isSubRegionOpen);
const activeTab = ref('observations');
const observationNumber = ref(0)
const logNumber = ref(0)
const fraudNumber = ref(0)
const supplyCutNumber = ref(0)
const objectPermissions = ref(null);
const forceToken = ref(null)
const contractableToken = ref(null)
const notContractableToken = ref(null)
const activeToken = ref(null)
const deactivateToken = ref(null)

const previous_address = ref(null);
const current_address = ref(null);

/** El detall del PS no serialitza created_at als contractes; es complementa amb el llistat de contractes per SP. */
const contractCreatedAtById = shallowRef({});

const loadContractCreatedDates = async () => {
  contractCreatedAtById.value = {};
  if (!data.value?.contracts?.length || !props.id) return;
  try {
    const list = await $ContractApiService.getBySupplyPoint(props.id);
    const map = {};
    for (const c of list || []) {
      if (c?.id != null && c.created_at) map[c.id] = c.created_at;
    }
    contractCreatedAtById.value = map;
  } catch (e) {
    console.error(e);
  }
};

const getContractCreatedAt = (item) =>
  item?.created_at ?? item?.contract?.created_at ?? contractCreatedAtById.value[item?.id] ?? null;

const formatContractCreatedAt = (item) => {
  const raw = getContractCreatedAt(item);
  return raw ? formatDate(raw) : '–';
};

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateFraudCount = (num) => {
  fraudNumber.value = num;
}

const updateSupplyCutCount = (num) => {
  supplyCutNumber.value = num;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $SupplyPointApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;
  error.value = null;
  try {
    const result = await $SupplyPointApiService.getDetail(props.id);
    data.value = result;
    selectedAddress.value = result.address;
    current_address.value = result.address ? result.address?.address_complete : '-';
    void loadContractCreatedDates();
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});



const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const closeSubRegion = function () {
  SubRegion.value = false;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const editAddress = function () {
  showRegionDetailComponent.value = 'AddAddress';
  showSubRegion();
}

const setAddress = async function (address) {
  if (props.id) {
    await $SupplyPointApiService.save({
      id: props.id,
      address: address?.id || address
    });
  }

  await getData();
  closeSubRegion();
}


const editMeter = async function () {
  await getData();
  showRegionDetailComponent.value = 'SupplyMeterChange';
  showSubRegion();
}

const setMeter = function (meter) {
  data.value.meter = meter;
  $SupplyPointApiService.save({
    id: data.value.id,
    meter_id: meter.id
  });
  getData();
  closeSubRegion();
}

const handleStatusChanged = () => {
  closeSubRegion();
  getData();
}

const editConnection = function () {
  showRegionDetailComponent.value = 'AddConnections';
  showSubRegion();
}
const editNotContractable = function () {
  forceToken.value = notContractableToken.value;
  showRegionDetailComponent.value = 'NotContractable';
  showSubRegion();
}

const editContractable = function () {
  forceToken.value = contractableToken.value;
  showRegionDetailComponent.value = 'NotContractable';
  showSubRegion();
}

const activateSupplyPoint = async () => {
  if (!confirm(t('confirmation_text_block.confirm_activate'))) return;
  try {
    await $SupplyPointApiService.activate(props.id);
    getData();
    closeSubRegion();
  } catch (err) {
    console.error('Error activating supply point', err);
  }
}

const deactivateSupplyPoint = async () => {
  if (!confirm(t('confirmation_text_block.confirm_deactivate'))) return;
  try {
    await $SupplyPointApiService.deactivate(props.id, null, null);
    getData();
    closeSubRegion();
  } catch (err) {
    console.error('Error deactivating supply point', err);
  }
}

const setConnection = function (connection) {
  data.value.connection = connection;
  $SupplyPointApiService.save({
    id: data.value.id,
    connection_id: connection.id
  });
  getData();
  closeSubRegion();
}

const editProperty = function () {
  showRegionDetailComponent.value = 'AddProperties';
  showSubRegion();
}

const setProperty = async function (property) {
  if (!property || !property.id) return;
  try {
    const res = await $SupplyPointApiService.getByProperty(property.id);
    const existingSpIds = (res.results || []).map(sp => sp.id);
    if (!existingSpIds.includes(props.id)) {
      existingSpIds.push(props.id);
    }
    const bulkPayload = [{
      property_id: Number(property.id),
      supply_points: existingSpIds
    }];
    await $SupplyPointApiService.bulkUpdateProperty(bulkPayload);
    await getData();
    closeSubRegion();
    toast.success(t('common.saved_successfully') || 'Guardat correctament');
  } catch (err) {
    console.error('Error setting property:', err);
    toast.error(t('common.error'));
  }
}

const editRemove = function () {
  showRegionDetailComponent.value = 'SupplyPointRemoval';
  showSubRegion();
}

const removalSave = function () {
  getData();
  closeSubRegion();
}

const activar = function () {
  getData();
}

const cutSupplyPoint = () => {
  return navigateTo({
    path: '/service/supply-cut/add',
    query: {
      action: 'SP',
      supply_point: props.id
    }
  })
}

const dismissFraud = async () => {
  if (!confirm(t('confirmation_text_block.confirm_fraud_dismiss'))) return;
  try {
    let save_data = {
      id: props.id,
      dismiss_frauds: true,
    }
    await $SupplyPointApiService.save(save_data);
    getData(false);
    closeSubRegion();
  } catch (err) {
    console.error('Error dismissing fraud', err);
  }
}

const edit = function () {
  return router.push(`/service/supplypoints/edit/${props.id}`);
}

const updateLogCount = (num) => {
  logNumber.value = num;
}

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value?.can_view) {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  }
  notContractableToken.value = await $ConfigProjectApiService.get('supply_point_status_not_contractable_token');
  activeToken.value = await $ConfigProjectApiService.get('supply_point_status_activate_token');
  contractableToken.value = await $ConfigProjectApiService.get('supply_point_pending_contract');
  deactivateToken.value = await $ConfigProjectApiService.get('supply_point_status_deactivate_token');
  getData();
})

const showMap = () => {
  showRegionDetailComponent.value = 'Map';
  showSubRegion()
}

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between">
        <H1Region class="mb-2">{{ $t('supply_point') }}</H1Region>
        <div v-if="objectPermissions?.can_change" class="relative">
          <OptionsDropdown id="SupplyPointRegionOptions">

            <div v-if="data.active_reading_batch">
              <div class="max-w-xs px-2">
                <span class="text-sm text-slate-500">{{ $t('informative_block.info_block_changes_reading_batch') }}</span>
              </div>
              <hr class="my-2" />
            </div>

            <DropdownOption :name="`${t('common.modify')}`" @click="edit">
              <Icon name="fa6-solid:pencil" class="display-inline mr-2" /> {{ t('common.modify') }}
            </DropdownOption>
            <DropdownOption :name="`${t('common.modify')} ${t('address_block.address')}`" @click="editAddress">
              <Icon name="fa6-solid:location-dot" class="display-inline mr-2" /> {{ t('common.modify') }} {{
                t('address_block.address') }}
            </DropdownOption>
            <DropdownOption :name="`${t('common.modify')} ${t('meter')}`" @click="editMeter" :disabled="data.active_reading_batch">
              <Icon name="my-icon:meter-icon-black" class="display-inline mr-2" /> {{ t('common.modify') }} {{
                t('meter') }}
            </DropdownOption>
            <DropdownOption :name="`${t('common.modify')} ${t('connection')}`" @click="editConnection" :disabled="data.active_reading_batch">
              <Icon name="fa6-solid:plug" class="display-inline mr-2" /> {{ t('common.modify') }} {{ t('connection') }}
            </DropdownOption>
            <DropdownOption :name="`${t('common.modify')} ${t('property')}`" @click="editProperty" :disabled="data.active_reading_batch">
              <Icon name="fa6-solid:house" class="display-inline mr-2" /> {{ t('common.modify') }} {{ t('property') }}
            </DropdownOption>
            <hr class="my-2" />
            <DropdownOption v-if="!data.current_fraud" :name="t('customer_service_block.new_fraud_title')"
              @click="showDetail('AddFraud', data.id)">
              <Icon name="fa6-solid:mask" class="display-inline mr-2" /> {{ t('customer_service_block.new_fraud_title')
              }}
            </DropdownOption>
            <DropdownOption v-if="data.previous_fraud || data.current_fraud"
              :name="t('customer_service_block.dismiss_fraud_titles')" @click="dismissFraud">
              <Icon name="fa6-solid:check" class="display-inline mr-2" /> {{
                t('customer_service_block.dismiss_fraud_titles') }}
            </DropdownOption>
            <DropdownOption :name="`${t('common.forbid')} ${t('contracting')}`"
              v-if="data.status?.token != notContractableToken" @click="editNotContractable">
              <Icon name="fa6-solid:xmark" class="display-inline mr-2" /> {{ t('common.forbid') }} {{ t('contracting')
              }}
            </DropdownOption>
            <DropdownOption :name="`${t('common.enable')} ${t('contracting')}`" v-else @click="editContractable">
              <Icon name="fa6-solid:check" class="display-inline mr-2" /> {{ t('common.enable') }} {{ t('contracting')
              }}
            </DropdownOption>
            <DropdownOption v-if="data.status?.token != activeToken" :name="`${t('common.activate')}`"
              @click="activateSupplyPoint">
              <Icon name="fa6-solid:check" class="display-inline mr-2" /> {{ t('common.activate') }}
            </DropdownOption>
            <DropdownOption v-if="data.status?.token != deactivateToken" :name="`${t('common.deactivate')}`"
              @click="deactivateSupplyPoint">
              <Icon name="fa6-solid:xmark" class="display-inline mr-2" /> {{ t('common.deactivate') }}
            </DropdownOption>
            <DropdownOption :name="t('common.terminate')" @click="editRemove">
              <Icon name="fa6-regular:circle-xmark" class="display-inline mr-2" /> {{ t('common.terminate') }}
            </DropdownOption>
            <DropdownOption :name="t('service_block.cut_supply')" @click="cutSupplyPoint">
              <Icon name="fa6-solid:scissors" class="display-inline mr-2" /> {{ t('service_block.cut_supply') }}
            </DropdownOption>
          </OptionsDropdown>
        </div>
      </div>
      <div v-if="data" id="item_data" :data-rel=id>

        <SupplyPointDetail :id="props.id" :isSubRegion="props.isSubRegion" :isSubRegionOpen="props.isSubRegionOpen"
          :data="data" @show-detail="showDetail" @activar="activar" @show-map="showMap()" />

        <AtomsTabs>
          <li class="me-2">
            <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }"
              aria-current="page">
              <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t('common.observations') }} ({{
                observationNumber }})
            </a>
          </li>
          <li v-if="data.supply_point_children.length > 0" class="me-2">
            <a href="#tab_supply_children" @click.prevent="setActiveTab('supply_children')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'supply_children', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'supply_children' }">
              <Icon name="fa6-solid:street-view" class="display-inline mr-2" /> {{
                $t('service_block.child_supply_points') }} ({{
                data.supply_point_children.length }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_supply_cuts" @click.prevent="setActiveTab('supply_cuts')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'supply_cuts', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'supply_cuts' }">
              <Icon name="fa6-solid:droplet-slash" class="display-inline mr-2" /> {{ $t('common.supply_cuts') }} ({{
                supplyCutNumber }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_contracts" @click.prevent="setActiveTab('contracts')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'contracts', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'contracts' }">
              <Icon name="fa6-solid:address-card" class="display-inline mr-2" /> {{ $t('common.contracts') }} ({{
                data.contracts?.length || 0 }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_readings" @click.prevent="setActiveTab('readings')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'readings', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'readings' }">
              <Icon name="fa6-solid:list" class="display-inline mr-2" /> {{ $t('readings') }}
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_frauds" @click.prevent="setActiveTab('frauds')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'frauds', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'frauds' }">
              <Icon name="fa6-solid:mask" class="display-inline mr-2" />
              {{ $t('common.frauds') }} ({{ fraudNumber }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_log" @click.prevent="setActiveTab('log')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }">
              <Icon name="fa6-solid:list" class="display-inline mr-2" /> {{ $t('common.history') }} ({{ logNumber }})
            </a>
          </li>
        </AtomsTabs>
        <div id="tabpanels">
          <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
            class="bg-white antialiased">
            <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
              parent_entity="supply_point" url_entity="supply-point" :id="props.id" module="service">
            </MoleculesObservationList>
          </section>
          <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log" class="bg-white antialiased">
            <MoleculesLogChangeList v-if="data" entity="supply-point-change" parent_entity="supplypoint" :id="props.id"
              @update:count="updateLogCount" :service="$LoggerChangeApiService">
            </MoleculesLogChangeList>
          </section>

          <section v-show="activeTab === 'frauds'" role="tabpanel" id="tab_frauds" class="bg-white antialiased">
            <FraudMiniDetail :id="props.id" :isSubRegion="isSubRegion" @show-detail="showDetail"
              @update:count="updateFraudCount" />
          </section>

          <section v-show="activeTab === 'supply_cuts'" role="tabpanel" id="tab_supply_cuts"
            class="bg-white antialiased">
            <SupplyCutMiniDetail :id="props.id" :isSubRegion="isSubRegion" @show-detail="showDetail"
              @update:count="updateSupplyCutCount" />
          </section>

          <section v-if="activeTab === 'readings'" role="tabpanel" id="tab_readings" class="bg-white antialiased">
            <ReadingDetail :supply_point_id="props.id" :isSubRegion="isSubRegion" @show-detail="showDetail" />
          </section>

          <section v-show="activeTab === 'supply_children'" role="tabpanel" id="tab_supply_children"
            class="bg-white antialiased">

            <div class="m-4 rounded-md border border-gray-300 divide-y bg-white">
              <div class="group grid grid-cols-[1fr,2fr] divide-x text-sm leading-4 ">
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.status') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('supply_point') }} </span>
              </div>
              <div v-for="item in data.supply_point_children"
                class="group grid grid-cols-[1fr,2fr] divide-x text-sm leading-4 transition-all duration-100">
                <div class="footering text-slate-500 p-2 w-full">
                  <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                </div>
                <div class="group grid grid-cols-[1fr,2fr] divide-x text-sm leading-4 transition-all duration-100 px-3">
                  <button v-if="!props.isSubRegion" @click="showDetail(SupplyPointRegion, item.id)"
                    class="text-start text-sky-500 underline">{{ item.address_complete }}</button>
                  <span v-else>{{ item.address_complete }}</span>
                </div>

              </div>

            </div>
          </section>

          <section v-show="activeTab === 'contracts'" role="tabpanel" id="tab_contracts" class="bg-white antialiased">
            <div v-if="data.contracts && data.contracts.length != 0"
              class="m-4 rounded-md border border-gray-300 divide-y bg-white">
              <div class="group grid grid-cols-[1fr,1fr,1fr,2fr,1fr] divide-x text-sm leading-4 ">
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.status') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('contract') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center whitespace-nowrap"> {{ t('common.creation_date')
                  }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t("contract_block.holder") }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t("common.debt") }} </span>
              </div>
              <div v-for="item in data.contracts"
                class="group grid grid-cols-[1fr,1fr,1fr,2fr,1fr] divide-x text-sm leading-4 transition-all duration-100">
                <div class="footering text-slate-500 p-2 w-full">
                  <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                </div>
                <div class="footering text-slate-500 p-2 w-full">
                  <button v-if="!props.isSubRegion" @click="showDetail('ContractRegion', item.id)"
                    class="text-start text-sky-500 underline">{{ item.token }}</button>
                  <span v-else>{{ item.token }}</span>
                </div>
                <div class="footering text-slate-500 p-2 w-full text-nowrap">
                  <span>{{ formatContractCreatedAt(item) }}</span>
                </div>
                <div class="footering text-slate-500 p-2 w-full">
                  <span>{{ item.holder }}</span>
                </div>
                <div class="footering text-slate-500 p-2 w-full">
                  <span :class="{ 'text-green-500': item.total_debt == 0 }">
                    {{ formatMoneyWithCurrency(item.total_debt) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="footering text-slate-500 p-2">
              {{ t('common.no_records') }}
            </div>
          </section>
        </div>
      </div>
    </div>
    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ClusterRegion v-if="showRegionDetailComponent === 'ClusterRegion'" :id="regionDetailId" :isSubRegion="true" />
        <RouteRegion v-if="showRegionDetailComponent === 'RouteRegion'" :id="regionDetailId" :isSubRegion="true" />

        <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId" :isSubRegion="true" />
        <AddMeters v-if="showRegionDetailComponent === 'AddMeters'" :selected_items="[data.meter]"
          :exclude="data.meter?.id" :multiple=false :show="true" @item-clicked="setMeter"></AddMeters>

        <PropertyRegion v-if="showRegionDetailComponent === 'PropertyRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <AddProperties v-if="showRegionDetailComponent === 'AddProperties'"
          :selected_items="data?.property ? [data.property] : []" :multiple="false" :show="true"
          @item-clicked="setProperty" />

        <ConnectionRegion v-if="showRegionDetailComponent === 'ConnectionRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <AddConnections v-if="showRegionDetailComponent === 'AddConnections'" :selected_items="[data.connection]"
          :multiple="false" @item-clicked="setConnection" />

        <AddAddress v-if="showRegionDetailComponent === 'AddAddress'" :selectedAddress="selectedAddress"
          @new-address="setAddress" :isSubRegion="true" />

        <SupplyPointRemoval v-if="showRegionDetailComponent === 'SupplyPointRemoval'" :id="data.id"
          @save-success="removalSave" :isSubRegion="true" />

        <ChangeStatus v-if="showRegionDetailComponent === 'NotContractable'" entity="supply-point"
          parent_entity="supply_point" :id="data?.id" :status="data?.status?.id" :forceToken="forceToken"
          @changed="handleStatusChanged" />

        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />

        <OrganismsMapRegion v-if="showRegionDetailComponent === 'Map'"
          :longitude="parseFloat(data.connection?.longitude)" :latitude="parseFloat(data.connection?.latitude)"
          :address="data.address_complete">
        </OrganismsMapRegion>

        <AddFraud v-if="showRegionDetailComponent === 'AddFraud'" :supply_point_id="data.id"
          @changed="handleStatusChanged()" />

        <FraudRegion v-if="showRegionDetailComponent === 'FraudRegion'" :id="regionDetailId" :isSubRegion="true" />

        <SupplyCutRegion v-if="showRegionDetailComponent === 'SupplyCutRegion'" :id="regionDetailId"
          :isSubRegion="true" />

        <SupplyMeterChange v-if="showRegionDetailComponent === 'SupplyMeterChange'" :id="props.id"
          :meter_id="data.meter?.id" :data="data" @save="handleStatusChanged" />

        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
