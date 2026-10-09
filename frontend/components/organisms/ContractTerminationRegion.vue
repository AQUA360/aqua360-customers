<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import ContractTerminationDetail from '~/components/molecules/ContractTerminationDetail.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import AddInvoiceBudget from '../molecules/AddInvoiceBudget.vue';
import InvoiceView from '~/components/organisms/InvoiceView.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

// Importar components per a la subregion
import OrderRegion from './OrderRegion.vue';
import ContractRegion from './ContractRegion.vue';
import SupplyPointRegion from './SupplyPointRegion.vue';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion']);
const router = useRouter();
const { $ContractTerminationApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('observations');
const SubRegion = ref(props.isSubRegionOpen);
const objectPermissions = ref(null);
const allContracts = ref([]);
const editingChangeStatus = ref(false);
const showRegion = ref(false);
const observationNumber = ref(0)
const finishedToken = ref(null);

const reload = ref(false)

const updateObservationCount = (num) => {
  observationNumber.value = num;
}
const handleStatusChanged = () => {
  editingChangeStatus.value = false;
  SubRegion.value = false;
  emit('show-subregion', false)
  getData()
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ContractTerminationApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (load=false) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;
  reload.value = !load;
  try {
    finishedToken.value = await $ConfigProjectApiService.get('contract_termination_completed_token');

    const result = await $ContractTerminationApiService.getDetail(props.id);
    data.value = result;

    allContracts.value = [];
    result.contracts_holder?.forEach(c => {
      allContracts.value.push({
        ...c,
        role: t('contract_block.holder')
      });
    });
    result.contracts_owner?.forEach(c => {
      allContracts.value.push({
        ...c,
        role: t('contract_block.owner')
      });
    });
    result.contracts_tenant?.forEach(c => {
      allContracts.value.push({
        ...c,
        role: t('contract_block.tenant')
      });
    });
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}
const handleClickChangeStatus = () => {
  editingChangeStatus.value = true;
  SubRegion.value = true;
  emit('show-subregion', true)
}
watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = true;
  getData();
  closeSubRegion();
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData()
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
})

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const refresh = async () => {
  await getData()
}

const closeSubRegion = function () {
  SubRegion.value = false;
  editingChangeStatus.value = false;
  showRegionDetailComponent.value = null;
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
  editingChangeStatus.value = false;
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const cancelTermination = async function () {
  if (!confirm(t('confirmation_text_block.confirm_cancel_termination'))) return
  try {
    const result = await $ContractTerminationApiService.cancelTermination(props.id);
    if (result) {
      toast.success(t('common.correct_save'));
      getData(true);
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_cancel_termination'));
  }
}

const edit = function () {
  return navigateTo('/contract/contract-terminations/edit/' + props.id);
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <div class="flex justify-center items-center">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        <span class="ml-2">{{ $t('common.loading') }}...</span>
      </div>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('common.contract_termination_detail') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ContractTerminationRegionOptions">
          <DropdownOption :name="`${$t('common.modify')} ${$t('common.termination')}`" @click="edit"></DropdownOption>
          <DropdownOption :disabled="data?.status?.token == finishedToken" :name="`${$t('common.cancel')} ${$t('common.termination')}`" @click="cancelTermination"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data">
        <ContractTerminationDetail @show-subregion="showDetail" @finalized="refresh" :termination="data" 
        :isSubRegion="isSubRegion" :reload="reload" :canChange="objectPermissions?.can_change" />
      </div><!-- end if pending -->
      <AtomsTabs>
        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.observations") }} ({{
              observationNumber }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_orders" @click.prevent="setActiveTab('orders')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'orders', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'orders' }">
            <Icon name="fa6-solid:gears" class="display-inline mr-2" /> {{ $t("work_orders") }} ({{
              data?.orders?.length || 0 }})
          </a>
        </li>
      </AtomsTabs>
      <div id="contract_termination_tabpanels">
        <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
          class="bg-white antialiased">
          <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
            url_entity="contract-termination-request" parent_entity="contract_termination" :id="props.id"
            module="contract"></MoleculesObservationList>
        </section>
        <section v-show="activeTab === 'orders'" role="tabpanel" id="tab_orders"
          class="bg-white antialiased">
          <div v-if="data?.orders?.length" class="p-4">
            <div class="grid grid-cols-[200px,1fr,80px,120px] text-gray-400 border-b pb-2 mb-2">
              <span>{{ $t('order') }}</span>
              <span>{{ $t('common.type') }}</span>
              <span>{{ $t('common.date') }}</span>
              <span>{{ $t('common.status') }}</span>
            </div>
            <div v-for="order in data.orders" :key="order.id" class="grid grid-cols-[200px,1fr,80px,120px] py-1 border-b last:border-0 items-center">
              <button class="text-sky-500 hover:text-sky-900 text-left" @click="showDetail('OrderRegion', order.id);">
                {{ order.token }}
              </button>
              <span>{{ order.type.name }}</span>
              <span>{{ formatDate(order.created_at) }}</span>
              <span>
                <AtomsColorBadge :value="order.status?.name || order.status?.token || ''" :color="order.status?.color" />
              </span>
            </div>
          </div>
          <div v-else class="p-4 text-gray-500 italic text-center">
            {{ $t('order_block.no_orders') }}
          </div>
        </section>
      </div>
    </div><!-- end region__content -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <ChangeStatus v-if="editingChangeStatus" entity="contract-termination-request"
          parent_entity="connection_termination_request" :id="data?.id" :status="data?.status?.id" module="contract"
          @changed="handleStatusChanged" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="Number(regionDetailId)"
          :isSubRegion="true" @show-subregion="emit('show-subregion', $event)" />
        <OrderRegion v-if="showRegionDetailComponent === 'OrderRegion'" :id="regionDetailId" :isSubRegion="true" />
        <AddInvoiceBudget v-if="showRegionDetailComponent == 'AddInvoiceContract'" :object_id="data.id"
          :service="$ContractTerminationApiService" :entity="'contract_termination_request'"
          :persons="[data.person]" @change="getData(false)" :isSubRegion="true" :bill_termination_requester="true" />
        <InvoiceView v-if="showRegionDetailComponent == 'InvoiceView'" :id="regionDetailId" />
      </div>
    </div>
  </div>
</template>
