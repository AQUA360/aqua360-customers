<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import ButtonAcceptarRegion from '~/components/atoms/ButtonAcceptarRegion.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import AddInvoiceBudget from '~/components/molecules/AddInvoiceBudget.vue';
import OrderMiniDetail from '~/components/molecules/OrderMiniDetail.vue';
import ConnectionRequestDetail from '~/components/molecules/ConnectionRequestDetail.vue';
import OrderRegion from '~/components/organisms/OrderRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();

const props = defineProps({
  id: Number, // ID de l'element
});

const emit = defineEmits(['accept', 'show-subregion', 'changed', 'close-subregion']);

const router = useRouter();
const { $ConnectionRequestApiService, $ConfiglistApiService, $LoggerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('observations');
const observationNumber = ref(0)
const logNumber = ref(0)
const ordersNumber = ref(0)

const objectPermissions = ref(null);
const editingChangeStatus = ref(false);
const SubRegion = ref(false);
const statuses = ref([]);
const reload = ref(false);

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateLogCount = (num) => {
  logNumber.value = num;
}

const updateOrdersCount = (num) => {
  ordersNumber.value = num;
}

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll('service/' + entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ConnectionRequestApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = true;
  error.value = null;
  try {

    // agafem la llista d'statuses
    ({ results: statuses.value } = await $ConfiglistApiService.getAll('service/connection-request-status'));

    // agafem els valors de l'entitat
    const result = await $ConnectionRequestApiService.getDetail(props.id);

    data.value = result;

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
});

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

const closeSubRegion = function () {
  SubRegion.value = false;
  regionDetailId.value = null;
  emit('show-subregion', false);
  emit('changed');
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

const handleStatusChanged = (close) => {
  if (close) {
    closeSubRegion();
  }
  getData();
  reload.value = !reload.value;
  emit('changed');
}

const handleClickChangeStatus = () => {
  showSubRegion();
  editingChangeStatus.value = true;
}

const handleClickModify = () => {
  router.push(`/service/connection-requests/edit/${props.id}`);
}

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between">
        <H1Region class="mb-3">{{ $t('connection_request') }}</H1Region>
        <div class="relative" v-if="objectPermissions.can_change">
          <OptionsDropdown id="ConnectionRequestRegionOptions">
            <DropdownOption :name="`${t('common.modify')} ${t('connection_request')}`" 
            @click="handleClickModify"></DropdownOption>
            <DropdownOption :name="`${t('common.change')} ${t('common.status')}`" @click="handleClickChangeStatus"></DropdownOption>
          </OptionsDropdown>
        </div>
      </div>

      <AtomsStatusesNav :statuses="statuses" :active="data.status" class="my-3 mb-6" />

      <ConnectionRequestDetail :id="props.id" @clickChangeStatus="handleClickChangeStatus" 
      @show-detail="showDetail" :isRegion="true" :canChange="objectPermissions?.can_change" :reload="reload" />

      <AtomsTabs>
        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.observations") }} ({{
              observationNumber }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_log" @click.prevent="setActiveTab('log')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.history") }} ({{ logNumber }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_orders" @click.prevent="setActiveTab('orders')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'orders', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'orders' }">
            <Icon name="fa6-solid:screwdriver-wrench" class="display-inline mr-2" /> 
            {{ $t("work_orders") }} ({{ ordersNumber }})
          </a>
        </li>
      </AtomsTabs>
      <div id="cluster_tabpanels">
        <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
          class="bg-white antialiased">
          <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
            parent_entity="connection_request" url_entity="connection-request" :id="props.id" module="service">
          </MoleculesObservationList>
        </section>
        <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log" class="bg-white antialiased">
          <MoleculesLogList v-if="data" entity="connection-request-status" parent_entity="connection_request"
            :id="props.id" @update:count="updateLogCount" :service="$LoggerApiService">
          </MoleculesLogList>
        </section>
        <section v-show="activeTab === 'orders'" role="tabpanel" id="tab_orders" class="bg-white antialiased">
          <OrderMiniDetail :connection_request_id="props.id" @show-detail="showDetail" @update:count="updateOrdersCount" />
        </section>
      </div>
    </div><!-- end if pending -->


    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <ChangeStatus v-if="editingChangeStatus" entity="connection-request" parent_entity="connection_request"
          :id="props.id" :status="data.status?.id" module="service" @changed="handleStatusChanged" />
        <OrderRegion v-if="showRegionDetailComponent == 'OrderRegion'" :id="regionDetailId" :isSubRegion="true" />
        <AddInvoiceBudget v-if="showRegionDetailComponent == 'AddInvoiceContract'" :object_id="data.id"
          :service="$ConnectionRequestApiService" :entity="'connection_request'" :company="data.company"
          :persons="[data.person]" @change="handleStatusChanged" :isSubRegion="true" />
        <InvoiceRegion v-if="showRegionDetailComponent == 'InvoiceRegion' || showRegionDetailComponent == 'InvoiceView'" :id="regionDetailId" :isSubRegion="true" />
      </div>
    </div>

  </div>
</template>
