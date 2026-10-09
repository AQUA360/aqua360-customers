<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import ButtonAcceptarRegion from '~/components/atoms/ButtonAcceptarRegion.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import SupplyPointDetail from '~/components/molecules/SupplyPointDetail.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import PriceRateRegion from './PriceRateRegion.vue';
import ContractRequestDetail from '~/components/molecules/ContractRequestDetail.vue';
import PersonRegion from '~/components/organisms/PersonRegion.vue';
import SupplyPointRegion from '~/components/organisms/SupplyPointRegion.vue';
import OrderRegion from '~/components/organisms/OrderRegion.vue';
import InvoiceView from '~/components/organisms/InvoiceView.vue';
import AddInvoiceBudget from '../molecules/AddInvoiceBudget.vue';
import OrderMiniDetail from '../molecules/OrderMiniDetail.vue';
import ContractRegion from './ContractRegion.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const { permissions, loading } = usePermissions();

const emit = defineEmits(['accept', 'show-subregion', 'changed', 'close', 'close-subregion']);

const router = useRouter();
const { $ContractRequestApiService, $ConfiglistApiService, $LoggerApiService, $ConfigProjectApiService, $PersonApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('observations');
const observationNumber = ref(0)
const logNumber = ref(0)
const ordersNumber = ref(0)
const documentsNumber = ref(0);
const editingChangeStatus = ref(false);
const SubRegion = ref(false);
const statuses = ref([]);
const status_cancel = ref({});
const status_finalized = ref({});

const reload = ref(false)
const invoice = ref(null);
const holder = ref(null);

const objectPermissions = ref(null);

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateLogCount = (num) => {
  logNumber.value = num;
}

const updateOrdersCount = (num) => {
  ordersNumber.value = num;
}

const updateDocumentsCount = (num) => {
  documentsNumber.value = num;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ContractRequestApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll('contract/' + entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

const updateItem = (item) => {
  data.value = item;
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  if (load) pending.value = true;
  error.value = null;
  try {

    // agafem la llista d'statuses
    ({ results: statuses.value } = await $ConfiglistApiService.getAll('contract/contract-request-status'));

    let cancel_token = await $ConfigProjectApiService.get('contract_request_cancel_token')
    if (!cancel_token) cancel_token = '-1';
    status_cancel.value = statuses.value.find(s => s.token === cancel_token);

    let finalize_token = await $ConfigProjectApiService.get('contract_request_finalize_token');
    if (!finalize_token) finalize_token = '3';
    status_finalized.value = statuses.value.find(s => s.token === finalize_token);

    // agafem els valors de l'entitat
    const result = await $ContractRequestApiService.getDetail(props.id);
    data.value = result;

    if (data.value.contract){
      await getHolder(data.value.contract.holder);
    } else {
      await getHolder(data.value.holder);
    }

    ordersNumber.value = data.value.orders.length;

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const getHolder = async (person_id) => {
  try {
    const result = await $PersonApiService.getFullDetail(person_id);
    holder.value = result;
  } catch (err) {
    console.error(err);
    return null;
  }
}

watch(() => props.id, () => {
  closeSubRegion()
  getData();
});

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});


const closeSubRegion = function () {
  SubRegion.value = false;
  regionDetailId.value = null;
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

const handleStatusChanged = async () => {
  let currentTab = activeTab.value;
  closeSubRegion();
  await getData(false);
  await setActiveTab(null)
  await setActiveTab(currentTab);
}

const onClickModify = () => {
  router.push(`/contract/contract-requests/edit/${props.id}`);
}

const openOrderRegion = (id) => {
  showDetail({ component: 'OrderRegion', id: id });
}

const showInvoice = (component, id, invoice_show) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  invoice.value = invoice_show ? invoice_show : null;
  showSubRegion();
}

const onCancelContractRequest = async () => {
  if (confirm(t('Segur que vols cancel·lar la sol·licitud de contracte?'))) {
    // save status
    const save_data = {
      id: props.id,
      status: status_cancel.value.id
    }

    const result = await $ContractRequestApiService.save(save_data);

    // refresh data
    refresh(result);
  }
}


const onUndoContractRequest = async () => {
  // get a is_default status from statuses
  const status_default = statuses.value.find(s => s.is_default);

  // save status
  const save_data = {
    id: props.id,
    status: status_default.id
  }

  const result = await $ContractRequestApiService.save(save_data);

  // refresh data
  refresh(result);

}

const refresh = async (result) => {
  let currentTab = activeTab.value;
  await getData(false)
  emit('changed', result)
  reload.value = !reload.value
}

const onDeleteContractRequest = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    // delete
    const result = await $ContractRequestApiService.doDelete(data.value);

    // redirect
    router.push('/contract/contract-requests/');
    emit('close')
  }
}

const showValidationModal = ref(false);
const validationModalErrors = ref([]);

const mapErrorToStep = (errorText) => {
  if (!errorText) return null;
  const err = errorText.toLowerCase();
  
  // Step 1: Setup
  if (err.includes('sol·licitant') || err.includes('solicitante') || err.includes('applicant') || err.includes('tipus de sol·licitud') || err.includes('tipo de solicitud') || err.includes('request type') || err.includes('proveïdora') || err.includes('proveedora') || err.includes('company')) {
    return { index: 0, name: t('contract_block.request_setup_title') || 'Selecció de Tipus, Sol·licitant i Punt de subministrament' };
  }
  
  // Step 3: Address & Payment (evaluated before Step 2 to avoid 'titular de la compta' mapping to Persons step)
  if (err.includes('pagament') || err.includes('pago') || err.includes('payment') || err.includes('iban') || err.includes('banc') || err.includes('bank') || err.includes('adreça') || err.includes('direccio') || err.includes('dirección') || err.includes('address') || err.includes('sepa') || err.includes('compte') || err.includes('compta') || err.includes('cuenta')) {
    return { index: 2, name: `${t('address_block.addresses')} ${t('common.and')} ${t('billing_block.payment')}` };
  }
  
  // Step 2: Persons
  if (err.includes('titular') || err.includes('holder') || err.includes('propietari') || err.includes('propietario') || err.includes('owner') || err.includes('llogater') || err.includes('inquilí') || err.includes('inquilino') || err.includes('tenant') || err.includes('persona')) {
    return { index: 1, name: t('contract_block.request_persons_title') || 'Selecció de Titular, Propietari i Inquilí' };
  }
  
  // Step 4: Price rate & Categories
  if (err.includes('tarifa') || err.includes('price_rate') || err.includes('variable') || err.includes('categoria') || err.includes('category') || err.includes('ús') || err.includes('uso') || err.includes('use') || err.includes('client') || err.includes('cliente')) {
    return { index: 3, name: t('contract_block.request_price_rate_title') || 'Selecció de Tarifa i Variables' };
  }
  
  // Step 5: Order & Billing / meter
  if (err.includes('comptador') || err.includes('contador') || err.includes('meter') || err.includes('boquilla') || err.includes('caliber') || err.includes('calibre') || err.includes('ordre') || err.includes('orden') || err.includes('order')) {
    return { index: 4, name: t('contract_block.request_products_supply_point_title') || 'Alta de Punt de subministrament' };
  }
  
  // Step 6: Termination / Current situation
  if (err.includes('baixa') || err.includes('baja') || err.includes('termination') || err.includes('situació') || err.includes('situacion')) {
    return { index: 5, name: t('contract_block.current_situation') || 'Situació actual' };
  }
  
  return null;
};

const navigateToStep = (stepIndex) => {
  showValidationModal.value = false;
  router.push(`/contract/contract-requests/edit/${props.id}/?step=${stepIndex + 1}`);
};

const openValidationErrorsModal = (errors) => {
  validationModalErrors.value = Array.isArray(errors) ? errors : [errors];
  showValidationModal.value = true;
};

const onFinalizeContractRequest = async () => {
  if (confirm(t('confirmation_text_block.confirm_request_finalize_immediate'))) {
    try {
      const result = await $ContractRequestApiService.doContract(data.value);
      toast.success(t('contract_block.contract_finalized_success') || 'Contracte finalitzat correctament');
      refresh(result);
    } catch (errorResponse) {
      console.error(errorResponse);
      if (errorResponse.response?.status === 400) {
        const errData = errorResponse.response._data;
        openValidationErrorsModal(errData.errors || errData.message || [t('contract_block.validation_error_fallback')]);
      } else {
        toast.error(t('contract_block.unexpected_error') || 'S\'ha produït un error inesperat');
      }
    }
  }
}

watch(() => props.id, async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
})

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('contract_request') }}</H1Region>
        <div v-if="objectPermissions?.can_change" class="relative">
          <OptionsDropdown v-if="data.status.token !== status_finalized.token" id="ContractRequestRegionOptions">
            <DropdownOption :name="`${t('common.modify')} ${t('common.request')}`" @click="onClickModify">
              <Icon name="fa6-solid:pencil" class="mr-2" /> {{ $t('common.modify') }} {{ $t('common.request') }}
            </DropdownOption>
            <hr />
            <DropdownOption v-if="data.status.token !== status_cancel.token" :name="`${t('common.cancel')} ${t('common.request')}`"
              @click="onFinalizeContractRequest">
              <Icon name="fa6-solid:circle-check" class="mr-2" /> {{ $t('common.finalize') }} {{ $t('common.request') }}
            </DropdownOption>
            <DropdownOption v-if="data.status.token !== status_cancel.token" :name="`${t('common.cancel')} ${t('common.request')}`"
              @click="onCancelContractRequest">
              <Icon name="fa6-solid:circle-xmark" class="mr-2" /> {{ $t('common.cancel') }} {{ $t('common.request') }}
            </DropdownOption>
            <DropdownOption v-if="data.status.token === status_cancel.token" :name="t('contract_block.reestablish_request_status')"
              @click="onUndoContractRequest">
              <Icon name="fa6-solid:rotate-left" class="mr-2" /> {{ $t('contract_block.reestablish_request_status') }}
            </DropdownOption>
            <DropdownOption v-if="data.status.token === status_cancel.token" :name="`${t('common.delete')} ${t('common.request')}`"
              @click="onDeleteContractRequest">
              <Icon name="fa6-solid:trash" class="mr-2" /> {{ $t('common.delete') }} {{ $t('common.request') }}
            </DropdownOption>
          </OptionsDropdown>
        </div>
      </div>

      <AtomsStatusesNav :statuses="statuses" :active="data.status" class="my-3 mb-6" />

      <ContractRequestDetail :id="props.id" :request="data" @show-detail="showDetail" :showOrdersType="false" :reload="reload" :isSubRegion="isSubRegion"
        :isSubRegionOpen="isSubRegionOpen" :showInvoiceSection="true" @show-invoice="showInvoice" :canChange="objectPermissions?.can_change" />

      <AtomsTabs>
        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.observations") }} ({{
              observationNumber }})
          </a>
        </li>
        <li v-if="permissions?.permissions?.view_pricing" class="me-2">
          <a href="#tab_price_rate" @click.prevent="setActiveTab('price_rate')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'price_rate', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'price_rate' }">
            <Icon name="fa6-solid:tag" class="display-inline mr-2" /> {{ $t("price_rate") }} ({{ data.price_rates?.length ||
              0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_log" @click.prevent="setActiveTab('log')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }">
            <Icon name="fa6-solid:list" class="display-inline mr-2" /> {{ $t("common.history") }} ({{ logNumber }})
          </a>
        </li>
        <li v-if="permissions?.permissions?.view_order" class="me-2">
          <a href="#tab_orders" @click.prevent="setActiveTab('orders')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'orders', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'orders' }">
            <Icon name="fa6-solid:screwdriver-wrench" class="display-inline mr-2" /> {{ $t("work_orders") }} ({{
              ordersNumber }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_documents" @click.prevent="setActiveTab('documents')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'documents', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'documents' }">
            <Icon name="fa6-solid:file" class="display-inline mr-2" />
            {{ $t("common.docs") }} ({{ (data.contract_file && data.contract_file.is_active !== false ? 1 : 0) +
              (data?.documentation_files?.filter(d => d.is_active !== false)?.length || 0) }})
          </a>
        </li>
      </AtomsTabs>
      <div id="cluster_tabpanels">
        <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
          class="bg-white antialiased">
          <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
            parent_entity="contract_request" url_entity="contract-request" :id="props.id" module="contract">
          </MoleculesObservationList>
        </section>
        <section v-if="activeTab === 'price_rate'" role="tabpanel" id="tab_price_rate" class="bg-white antialiased">
          <MoleculesPriceRateListItem v-if="data" v-for="rate in data.price_rates" :price_rate="rate.price_rate"
          :isSubRegion="isSubRegionOpen || !permissions?.permissions?.view_pricing" @show-detail="showDetail"/>
        </section>
        <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log" class="bg-white antialiased">
          <MoleculesLogList v-if="data" entity="contract-request-status" parent_entity="contract-request" :id="props.id"
            @update:count="updateLogCount" :service="$LoggerApiService">
          </MoleculesLogList>
        </section>
        <section v-if="activeTab === 'orders'" role="tabpanel" id="tab_orders" class="bg-white antialiased">
          <OrderMiniDetail :contract_request_id="props.id" @show-detail="showDetail"
            :isSubRegionOpen="isSubRegionOpen" />
        </section>
        <section v-if="activeTab === 'documents'" role="tabpanel" id="tab_documents"
            class="bg-white antialiased py-3">
            <MoleculesContractDocumentsData :is_request="true" :contract="data" @update-item="updateItem" />
          </section>
      </div><!-- end cluster_tabpanels -->
    </div><!-- end if pending -->


    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50 shadow-2xl"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3 " >
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <PersonRegion v-if="showRegionDetailComponent == 'PersonRegion'" :id="regionDetailId"
          :isSubRegion="isSubRegionOpen" />
        <SupplyPointRegion v-if="showRegionDetailComponent == 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <PriceRateRegion v-if="showRegionDetailComponent == 'PriceRateRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ChangeStatus v-if="showRegionDetailComponent == 'ChangeStatus' && editingChangeStatus"
          entity="contract-request" parent_entity="contract_request" :id="props.id" :status="data.status?.id"
          module="contract" @changed="handleStatusChanged" />
        <OrderRegion v-if="showRegionDetailComponent == 'OrderRegion'" :id="regionDetailId" 
         @changed="handleStatusChanged" :isSubRegion="true" />
        <ContractRegion v-if="showRegionDetailComponent == 'ContractRegion'" :id="regionDetailId" 
         @changed="handleStatusChanged" :isSubRegion="true" />
        <AddInvoiceBudget v-if="showRegionDetailComponent == 'AddInvoiceContract'" :object_id="data.id"
          :service="$ContractRequestApiService" :entity="'contract_request'" :persons="[holder]"
          @change="refresh" :isSubRegion="true" />
        <InvoiceView v-if="showRegionDetailComponent == 'InvoiceView'" :id="regionDetailId" />
      </div>
    </div>

    <!-- Teleport Modal per Errors de Validació (Fallback) -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          v-if="showValidationModal"
          class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[150] p-4"
          @click.self="showValidationModal = false"
        >
          <div class="bg-white rounded-lg p-6 max-w-md w-full shadow-2xl">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
                <Icon name="fa6-solid:circle-xmark" class="text-red-600 text-lg" />
              </div>
              <h3 class="text-lg font-semibold text-gray-900">{{ t('contract_block.validation_error_title') }}</h3>
            </div>
            <p class="text-gray-600 mb-4 text-sm">
              {{ t('contract_block.validation_error_modal_msg') }}
            </p>
            <ul class="list-none text-sm text-red-700 bg-red-50/50 p-4 rounded-md border border-red-100 mb-6 space-y-2 max-h-[300px] overflow-y-auto pr-1">
              <li v-for="err in validationModalErrors" :key="err" class="flex flex-col gap-1.5 pb-2 border-b border-red-200/30 last:border-b-0 last:pb-0">
                <div class="flex items-start gap-1.5">
                  <span class="inline-block w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5 flex-shrink-0"></span>
                  <span class="flex-grow font-medium">{{ err }}</span>
                </div>
                <div v-if="mapErrorToStep(err)" class="pl-3">
                  <button 
                    @click="navigateToStep(mapErrorToStep(err).index)"
                    class="px-2 py-0.5 bg-red-100 hover:bg-red-200 text-red-800 text-xs font-semibold rounded border border-red-200 flex items-center gap-1 transition-all duration-150 active:scale-95 inline-flex"
                    title="Anar al pas corresponent"
                  >
                    <Icon name="fa6-solid:circle-arrow-right" class="text-[10px]" />
                    {{ mapErrorToStep(err).name }}
                  </button>
                </div>
              </li>
            </ul>
            
            <div class="flex">
              <button
                @click="showValidationModal = false"
                class="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium text-sm transition-all duration-150 shadow-sm"
              >
                {{ t('common.close') || 'Tancar' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>
