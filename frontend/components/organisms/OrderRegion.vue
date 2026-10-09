<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
// Importar el component SupplyPointRegion per a la subregion
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OrderDetail from '~/components/molecules/OrderDetail.vue';
import ConnectionRegion from '~/components/organisms/ConnectionRegion.vue';
import SupplyPointRegion from '~/components/organisms/SupplyPointRegion.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import ContractRequestRegion from '~/components/organisms/ContractRequestRegion.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import OrderReportList from '~/components/molecules/OrderReportList.vue';
import OrderReportEdit from '~/components/molecules/OrderReportEdit.vue';
import IncidentEdit from '../molecules/IncidentEdit.vue';
import IncidentRegion from './IncidentRegion.vue';
import IncidentList from '../molecules/IncidentList.vue';
import ConnectionRequestRegion from './ConnectionRequestRegion.vue';
import ChangeMeterStatus from '~/components/molecules/ChangeMeterStatus.vue';
import ChangeMeterPreview from '~/components/molecules/ChangeMeterPreview.vue';
import MeterEdit from '~/components/organisms/MeterEdit.vue';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const objectPermissions = ref(null);
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const config = useRuntimeConfig();
const externalGot = String(config.public.externalGot).toLowerCase() === 'true';


const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);
const router = useRouter();

const { $OrderApiService, $ConfigProjectApiService,$DocumentManagerApiService } = useNuxtApp();
const forValidateStatusToken = ref(null);
const orderStatusCompletedToken = ref(null);
const orderStatusCompletedId = ref(null);

const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('statusLog');
const SubRegion = ref(props.isSubRegionOpen);
const observationNumber = ref(0)
const logNumber = ref(0)

const reportsVersion = ref(0)

const operators = ref([]);

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateLogCount = (num) => {
  logNumber.value = num;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $OrderApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const fetchConfigs = async () => {
  try {
    forValidateStatusToken.value = await $ConfigProjectApiService.get('for_validate_order_status_token');
    orderStatusCompletedToken.value = await $ConfigProjectApiService.get('order_status_completed_token');

    if (orderStatusCompletedToken.value) {
      const statuses = await $OrderApiService.getFilterStatus();
      const completedStatus = statuses.find(s => s.token === orderStatusCompletedToken.value);
      if (completedStatus) {
        orderStatusCompletedId.value = completedStatus.id;
      }
    }
  } catch (error) {
    console.error('Error fetching configs:', error);
  }
}

const handleValidate = async () => {
  if (!orderStatusCompletedId.value) {
    toast.error(t('common.error_save'));
    return;
  }

  try {
    pending.value = true;
    const payload = {
      id: props.id,
      status: orderStatusCompletedId.value
    };
    await $OrderApiService.save(payload);
    toast.success(t('common.saved_successfully'));
    await getData();
    emit('changed');
  } catch (error) {
    toast.error(t('common.error_save'));
  } finally {
    pending.value = false;
  }
}

const handleInvalidate = async () => {
  try {
    pending.value = true;
    await $OrderApiService.invalidateOrder(props.id);
    toast.success(t('common.saved_successfully'));
    await getData();
    emit('changed');
  } catch (error) {
    toast.error(t('common.error_save'));
  } finally {
    pending.value = false;
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;

  try {
    const result = await $OrderApiService.getDetail(props.id);
    data.value = null;
    data.value = result;
    reportsVersion.value++;

    // omplim els valors
    operators.value = [];
    operators.value.push(...result.operators);

  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const refresh = async (close = true) => {
  if (close) {
    closeSubRegion();
  }
  await getData(close);
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

onMounted(async() => {
  await getPermissions();
  if (!objectPermissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  }
  if (externalGot) {
    await fetchConfigs();
  }
  await getData();
});

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

// "Double subregion": when OrderRegion is already being shown as a subregion (e.g. opened
// from a contract's "Ordres de treball" tab), a nested detail (e.g. a report) is opened as
// a second panel layered on top of the current subregion, instead of being blocked.
const doubleSubRegion = ref(false);
const doubleRegionDetailComponent = ref(null);
const doubleRegionDetailId = ref(null);

const closeDoubleSubRegion = function () {
  doubleSubRegion.value = false;
  doubleRegionDetailComponent.value = null;
  doubleRegionDetailId.value = null;
}

const showDetail = function (component, id) {
  if (props.isSubRegion) {
    doubleRegionDetailComponent.value = component;
    doubleRegionDetailId.value = id;
    doubleSubRegion.value = true;
    return;
  }

  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const refreshDoubleSubRegion = async (close = true) => {
  if (close) {
    closeDoubleSubRegion();
  }
  await getData(close);
}

const handleClickChangeOrderStatus = () => {
  closeSubRegion();
  showRegionDetailComponent.value = 'OrderChangeStatus';
  showSubRegion();
  //emit('changed');
}

const handleStatusChanged = () => {
  closeSubRegion();
  getData();
  emit('changed');
}

const edit = function () {
  return navigateTo('/order/orders/edit/' + props.id);
}

const printOrder = async (token) => {
  const response = await $OrderApiService.downloadOrder(props.id);
  downloadDocument(response.document_id, token)
}

const downloadDocument = async (order_file, token) => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(order_file);
    
    const blob = new Blob([file], { type: file.type || "application/pdf" });

    const fileUrl = URL.createObjectURL(blob);
    console.log('fileUrl', fileUrl);
    const link = document.createElement('a');
    console.log('link', link);

    link.href = fileUrl;
    const file_name = t('common.work_order').replace(' ', '_').toLowerCase();
    link.download = `${file_name}_${token.replace('/', '_')}.pdf`;
    
    
    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(fileUrl);
    }, 250);

  } catch (error) {
    console.error(error)
  }
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const handlePreviewChangeMeter = () => {
  showDetail('ChangeMeterPreview', props.id);
}

const changeMeterPrefillCode = ref(null);
const previewRefreshKey = ref(0);

const handleCreateMeterFromPreview = (code) => {
  changeMeterPrefillCode.value = code;
  doubleRegionDetailComponent.value = 'CreateMeterFromChangeMeter';
  doubleRegionDetailId.value = props.id;
  doubleSubRegion.value = true;
}

const handleMeterCreatedFromPreview = () => {
  closeDoubleSubRegion();
  changeMeterPrefillCode.value = null;
  previewRefreshKey.value++;
}

const handleChangeMeterApplied = () => {
  closeSubRegion();
  getData(); // refresca l'ordre, l'informe i el requadre d'estat (ChangeMeterStatus)
}

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button>
      </p>
    </div>
    <div v-else-if="objectPermissions.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('order') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions.can_change" id="OrderRegionOptions">
          <DropdownOption v-if="!externalGot" :name="`${t('common.modify')} ${t('order')}`" @click="edit"></DropdownOption>
          <DropdownOption :name="`${t('common.add')} ${t('common.report_detail')}`" @click="showDetail('OrderReportEdit', null)"></DropdownOption>
          <DropdownOption :name="`${t('customer_service_block.new_incident')}`" @click="showDetail('IncidentEdit', props.id)"></DropdownOption>
          <DropdownOption :name="`${t('order_block.print_order')}`" @click="printOrder(data.token)"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>

        <OrderDetail :data="data" :isSubRegion="false" :isSubRegionOpen="isSubRegionOpen" @show-detail="showDetail"
          @clickChangeStatus="handleClickChangeOrderStatus" :canChange="objectPermissions?.can_change"
          :forValidateStatusToken="forValidateStatusToken" @validate="handleValidate" @invalidate="handleInvalidate" />

        <!-- Operaris fora de la tab -->
        <div v-if="!externalGot" class="mt-4 mb-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">{{ $t("common.assigned_operators") }} ({{ operators?.length || 0 }})</h3>
          <div v-if="operators.length != 0" class="rounded-md border border-gray-300 divide-y bg-white">
            <div v-for="operator in operators" :key="operator.id"
              class="p-3 border-b hover:bg-slate-50">
              <!-- Primera línia: nom #identificador -->
              <div class="flex justify-between items-center mb-2">
                <span class="text-slate-600">{{ operator.name }} {{ operator.surname }}</span>
                <button class="group flex items-center gap-1 text-sky-500"
                  @click="showDetail('Operator', operator.id);">
                  <span class="text-sky-500">#{{ operator.token }}</span>
                  <Icon :name="isSubRegion ? 'fa6-solid:external-link' : 'fa6-solid:eye'"
                    class="opacity-0 group-hover:opacity-100 text-slate-500 transition-opacity duration-200 ease-in-out text-xs" />
                </button>
              </div>
              <!-- Segona línia: telèfon email -->
              <div class="flex justify-between items-center text-sm">
                <span>
                  <a v-if="operator.phone" :href="'tel:' + operator.phone" class="text-sky-500 underline hover:no-underline">{{ operator.phone }}</a>
                  <span v-else class="text-slate-400">-</span>
                </span>
                <span>
                  <a v-if="operator.email" :href="'mailto:' + operator.email" class="text-sky-500 underline hover:no-underline break-all">{{ operator.email }}</a>
                  <span v-else class="text-slate-400">-</span>
                </span>
              </div>
            </div>
          </div>
          <div v-else class="footering text-slate-500 p-2">
            {{ t('common.no_operators') }}
          </div>
        </div>
        
        <ChangeMeterStatus :orderId="data.id" :orderType="data.type?.token"
          :refreshKey="reportsVersion" :alreadyApplied="!!data.change_meter_applied_at"
          @preview="handlePreviewChangeMeter" />

        <AtomsTabs> 
          <li v-if="externalGot" class="me-2">
            <a href="#tab_statusLog" @click.prevent="setActiveTab('statusLog')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'statusLog', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'statusLog' }"
              class="inline-flex items-center justify-center p-2 md:p-4 border-b-2 rounded-t-lg text-sm md:text-base">
              <Icon name="fa6-solid:person-walking-arrow-right" class="display-inline mr-1 md:mr-2" />
              <span class="whitespace-nowrap">{{ $t("common.status_change") }} ({{ logNumber }})</span>
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }"
              class="inline-flex items-center justify-center p-2 md:p-4 border-b-2 rounded-t-lg group text-sm md:text-base" aria-current="page">
              <Icon name="fa6-solid:note-sticky" class="display-inline mr-1 md:mr-2" />
              <span class="whitespace-nowrap">{{ $t("common.observations") }} ({{
                observationNumber }})</span>
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_report" @click.prevent="setActiveTab('report')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'report', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'report' }"
              class="inline-flex items-center justify-center p-2 md:p-4 border-b-2 rounded-t-lg group text-sm md:text-base" aria-current="page">
              <Icon name="fa6-solid:file-contract" class="display-inline mr-1 md:mr-2" />
              <span class="whitespace-nowrap">{{ $t("common.reports") }} ({{ data.total_reports }})</span>
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_incident" @click.prevent="setActiveTab('incident')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'incident', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'incident' }"
              class="inline-flex items-center justify-center p-2 md:p-4 border-b-2 rounded-t-lg group text-sm md:text-base" aria-current="page">
              <Icon name="fa6-solid:bug" class="display-inline mr-1 md:mr-2" />
              <span class="whitespace-nowrap">{{ $t("common.incidents") }} ({{
                data.related_incidents || 0 }})</span>
            </a>
          </li>

          <li v-if="!externalGot" class="me-2">
            <a href="#tab_statusLog" @click.prevent="setActiveTab('statusLog')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'statusLog', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'statusLog' }"
              class="inline-flex items-center justify-center p-2 md:p-4 border-b-2 rounded-t-lg text-sm md:text-base">
              <Icon name="fa6-solid:person-walking-arrow-right" class="display-inline mr-1 md:mr-2" />
              <span class="whitespace-nowrap">{{ $t("common.status_change") }} ({{ logNumber }})</span>
            </a>
          </li>

        </AtomsTabs>
        <div id="order_tabpanels">
          <!-- panells -->
          <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
            class="bg-white antialiased py-3 flex flex-col"
            :style="{
              minHeight: 'calc(100vh - 320px)',
              maxHeight: 'calc(100vh - 320px)',
            }">
            <div class="flex-1 overflow-y-auto">
              <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
                parent_entity="order" :id="props.id" module="order">
              </MoleculesObservationList>
            </div>
          </section>

          <section v-show="activeTab === 'report'" role="tabpanel" id="tab_report" class="bg-white antialiased">
            <OrderReportList v-if="data" :id="data.id" :isSubRegion="isSubRegion" @show-detail="showDetail">
            </OrderReportList>
          </section>
          
          <section v-show="activeTab === 'incident'" role="tabpanel" id="tab_incident" class="bg-white antialiased">
            <IncidentList v-if="data" :order_id="data.id" :isSubRegion="isSubRegion" @show-detail="showDetail">
            </IncidentList>
          </section>

          <section v-show="activeTab === 'statusLog'" role="tabpanel" id="tab_statusLog" class="bg-white antialiased">
            <MoleculesLogList v-if="data" entity="order-status" parent_entity="order" :id="props.id"
              @update:count="updateLogCount" :service="$LoggerApiService">
            </MoleculesLogList>
          </section>

        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <!-- Fixed close button for mobile -->
    <button v-if="SubRegion == true && !isSubRegion" 
      @click.prevent="closeSubRegion()" 
      type="button" 
      class="fixed top-4 right-4 z-[80] md:hidden px-4 py-3 bg-white border-2 border-gray-300 rounded-lg shadow-lg flex items-center gap-2 text-sky-500 hover:bg-slate-50 active:bg-slate-100">
      <Icon name="fa6-solid:xmark" class="text-xl" />
      <span class="font-medium">{{ $t('common.close') }}</span>
    </button>

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-[100vh] transition-all duration-500 ease text-base bg-white overflow-x-hidden"
      :class="{
        'fixed top-0 text-base overflow-y-auto overflow-x-hidden': true,
        'left-0 md:right-0 md:left-auto': !isSubRegion,
        'right-0': isSubRegion,
        'w-screen max-w-full md:w-[48vw]': !isSubRegion,
        'w-[48vw]': isSubRegion,
        'z-[70] md:z-10': !isSubRegion,
        'z-10': isSubRegion,
        'border-l-0 md:border-l border-gray-100': !isSubRegion,
        'border-l border-gray-100': isSubRegion,
        'translate-x-0': SubRegion,
        '-translate-x-full md:translate-x-full': !SubRegion && !isSubRegion,
        'translate-x-full': !SubRegion && isSubRegion,
      }" 
      style="max-width: 100vw;">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <!-- Subregions aqui -->
        <OrganismsOperatorRegion v-if="showRegionDetailComponent === 'Operator'" :id="regionDetailId"
          :isSubRegion="true" />
        <ConnectionRegion v-if="showRegionDetailComponent === 'ConnectionRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ContractRequestRegion v-if="showRegionDetailComponent === 'ContractRequestRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ConnectionRequestRegion v-if="showRegionDetailComponent === 'ConnectionRequestRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ChangeStatus v-if="showRegionDetailComponent === 'OrderChangeStatus'" entity="order" parent_entity="order"
          :id="props.id" :status="data.status?.id" module="order" @changed="handleStatusChanged" />
        <OrderReportEdit v-if="showRegionDetailComponent === 'OrderReportEdit'" :id="regionDetailId"
          :order_id="props.id" :isSubRegion="true" @changed="refresh" />
        <IncidentEdit v-if="showRegionDetailComponent == 'IncidentEdit'" :order_id="regionDetailId" @change="refresh" />
        <IncidentRegion v-if="showRegionDetailComponent === 'IncidentRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <ChangeMeterPreview v-if="showRegionDetailComponent === 'ChangeMeterPreview'" :id="regionDetailId"
        :isSubRegion="true" :refreshKey="previewRefreshKey"
        @create-meter="handleCreateMeterFromPreview" @applied="handleChangeMeterApplied" />
        <!-- /end Subregions aqui -->
      </div>
    </div>

    <!-- Doble regió: apareix per sobre de la subregió actual quan OrderRegion ja s'està mostrant com a subregió -->
    <div v-if="doubleSubRegion" role="region" id="double-subregion"
     class="h-full border-l border-gray-100 py-2 text-base bg-white flex flex-col overflow-hidden fixed top-0 w-[48vw] z-[90] transition-[right] duration-500 ease"
      :class="doubleSubRegion ? 'right-0' : 'right-[-48vw]'">
      <div id="double_region_nav" class="mb-3 px-3">
        <button @click.prevent="closeDoubleSubRegion()" type="button" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <OrderReportEdit v-if="doubleRegionDetailComponent === 'OrderReportEdit'" :id="doubleRegionDetailId"
          :order_id="props.id" :isSubRegion="true" @changed="refreshDoubleSubRegion" />
        <MeterEdit v-if="doubleRegionDetailComponent === 'CreateMeterFromChangeMeter'"
        :supply_point="data.supply_point" :prefillCode="changeMeterPrefillCode" :isSubRegion="true"
        @created="handleMeterCreatedFromPreview" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>