<script setup>
import { useRouter } from 'vue-router';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ContractRegion from './ContractRegion.vue';
import IncidentDetail from '../molecules/IncidentDetail.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import IncidentEdit from '../molecules/IncidentEdit.vue';
import ChangeStatus from '../molecules/ChangeStatus.vue';
import CalendarTaskList from '../molecules/CalendarTaskList.vue';
import CalendarTaskEdit from '../molecules/CalendarTaskEdit.vue';
import IncidentReportMiniDetail from '../molecules/IncidentReportMiniDetail.vue';
import IncidentReportEdit from '../molecules/IncidentReportEdit.vue';
import OrderEdit from './OrderEdit.vue';
import OrderMiniDetail from '../molecules/OrderMiniDetail.vue';
import OrderRegion from './OrderRegion.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import SupplyPointRegion from './SupplyPointRegion.vue';
import ClusterRegion from './ClusterRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);

const router = useRouter();
const { $IncidentApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('tasks');
const objectPermissions = ref(null);
const observationNumber = ref(0)
const reportNumber = ref(0)
const logNumber = ref(0)
const orderNumber = ref(0)

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateReportCount = (num) => {
  reportNumber.value = num;
}

const updateLogCount = (num) => {
  logNumber.value = num;
}

const updateOrderCount = (num) => {
  orderNumber.value = num;
}

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $IncidentApiService.getPermissions();
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
    const result = await $IncidentApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const newOrder = (order) => {
  //?
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = async function (component, id) {
  await closeSubRegion()
  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  showSubRegion();
}

const refresh = async (close = true) => {
  await getData()
  if (close) closeSubRegion()
  emit('changed')
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});
</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">
        {{ $t('common.load_again') }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative mb-3">
        <H1Region class="mb-3">{{ $t('incident') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="FraudRegionOptions">
          <DropdownOption :name="`${t('common.modify')}`" @click="showDetail('IncidentEdit', props.id)">
            <Icon name="fa6-solid:pencil" class="display-inline mr-2" /> {{ t('common.modify') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.change')} ${t('common.status')}`" @click="showDetail('StatusChange', props.id)">
            <Icon name="fa6-solid:arrows-rotate" class="display-inline mr-2" /> {{ t('common.change') }} {{ t('common.status') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.add')} ${t('dashboard.task')}`" @click="showDetail('CalendarTaskEdit', null)">
            <Icon name="fa6-solid:calendar" class="display-inline mr-2" /> {{ t('common.add') }} {{ t('dashboard.task') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.add')} ${t('common.report_detail')}`" @click="showDetail('IncidentReportEdit', null)">
            <Icon name="fa6-solid:paperclip" class="display-inline mr-2" /> {{ t('common.add') }} {{ t('common.report_detail') }}
          </DropdownOption>
          <DropdownOption v-if="data.contract || data.order_incident" :name="`${t('common.add')} ${t('common.work_order')}`" @click="showDetail('OrderEdit', props.id)">
            <Icon name="fa6-solid:screwdriver-wrench" class="display-inline mr-2" /> {{ t('common.add') }} {{ t('common.work_order') }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <IncidentDetail :id="props.id" :data="data" @show-detail="showDetail" :isSubRegion="isSubRegion" />
      </div>

      <AtomsTabs>

        <li class="me-2">
          <a href="#tab_tasks" @click.prevent="setActiveTab('tasks')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'tasks', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'tasks' }"
            aria-current="page">
            <Icon name="fa6-solid:calendar-check" class="display-inline mr-2" />
            {{ $t('dashboard.tasks') }} ({{ data.tasks?.length || 0 }})
          </a>
        </li>

        <li class="me-2">
          <a href="#tab_reports" @click.prevent="setActiveTab('reports')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'reports', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'reports' }"
            aria-current="page">
            <Icon name="fa6-solid:newspaper" class="display-inline mr-2" />
            {{ $t('common.reports') }} ({{ reportNumber }})
          </a>
        </li>
        <li v-if="(data.contract || data.order_incident) && permissions?.permissions?.view_order" class="me-2">
          <a href="#tab_orders" @click.prevent="setActiveTab('orders')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'orders', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'orders' }"
            aria-current="page">
            <Icon name="fa6-solid:screwdriver-wrench" class="display-inline mr-2" />
            {{ $t('work_orders') }} ({{ orderNumber || 0 }})
          </a>
        </li>

        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }"
            aria-current="page">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t('common.observations') }} ({{
              observationNumber }})
          </a>
        </li>

        <li class="me-2">
          <a href="#tab_log" @click.prevent="setActiveTab('log')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }">
            <Icon name="fa6-solid:list" class="display-inline mr-2" /> {{ $t('common.history') }} ({{ logNumber }})
          </a>
        </li>

      </AtomsTabs>

      <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations" class="bg-white antialiased">
        <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
          parent_entity="incident" url_entity="incident" :id="props.id" module="notification">
        </MoleculesObservationList>
      </section>

      <section v-show="activeTab === 'tasks'" role="tabpanel" id="tab_tasks" class="bg-white antialiased">
        <CalendarTaskList :id="props.id" :data="data?.tasks" @show-detail="showDetail" />
      </section>

      <section v-show="activeTab === 'reports'" role="tabpanel" id="tab_reports" class="bg-white antialiased">
        <IncidentReportMiniDetail v-if="data" @show-detail="showDetail" :id="props.id" @update:count="updateReportCount" />
      </section>

      <section v-if="permissions?.permissions?.view_order" v-show="activeTab === 'orders'" role="tabpanel" id="tab_orders" class="bg-white antialiased">
        <OrderMiniDetail v-if="data" @show-detail="showDetail" :incident_id="props.id" 
        @update:count="updateOrderCount" :isSubRegion="isSubRegion" />
      </section>

      <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log" class="bg-white antialiased">
        <MoleculesLogList v-if="data" entity="incident-status" parent_entity="incident" :id="props.id"
          @update:count="updateLogCount" :service="$LoggerApiService">
        </MoleculesLogList>
      </section>

    </div><!-- end if pending -->

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
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" @update-id="(newId) => regionDetailId = newId" />
        <IncidentEdit v-if="showRegionDetailComponent === 'IncidentEdit'" :id="regionDetailId" :isSubRegion="true"
          @change="refresh" />
        <ChangeStatus v-if="showRegionDetailComponent === 'StatusChange'" parent_entity="incident" :id="props.id"
          :status="data.status?.id" module="notification" @changed="refresh" entity="incident" />
        <CalendarTaskEdit v-if="showRegionDetailComponent === 'CalendarTaskEdit'" :id="regionDetailId"
          :object_id="props.id" :object_service="$IncidentApiService" @change="refresh" />
        <IncidentReportEdit v-if="showRegionDetailComponent === 'IncidentReportEdit'" :id="regionDetailId"
          :incident_id="props.id" @changed="refresh" />
        <OrderEdit v-if="showRegionDetailComponent === 'OrderEdit'" :isSubRegion="true" :incident_id="props.id"
          :contract_id="data.contract?.id" @changed="refresh" />
        <OrderRegion v-if="showRegionDetailComponent === 'OrderRegion'" :id="regionDetailId" :isSubRegion="true"
          @changed="refresh" />
        <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId"
          :isSubRegion="true" @changed="refresh" />
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <ClusterRegion v-if="showRegionDetailComponent === 'ClusterRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
