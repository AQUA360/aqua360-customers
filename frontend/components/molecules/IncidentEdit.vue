<script setup>
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useToast } from 'vue-toastification';
import H1Region from '../atoms/H1Region.vue';
import SearchEntityInput from '../molecules/SearchEntityInput.vue';
import ContractDetail from './ContractDetail.vue';
import InvoiceDetail from './InvoiceDetail.vue';
import CommitmentDepositDetail from './CommitmentDepositDetail.vue';
import OrderDetail from './OrderDetail.vue';
import SupplyPointDetail from './SupplyPointDetail.vue';
import ClusterDetail from './ClusterDetail.vue';

const { $IncidentApiService, $ConfiglistApiService, $SupplyPointApiService, $ClusterApiService, $SupplyCutApiService, $UserApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast()
const props = defineProps({
  id: Number,
  contract_id: Number,
  invoice_id: Number,
  commitment_id: Number,
  order_id: Number,
  supply_point_id: Number,
  cluster_id: Number,
});

const emit = defineEmits(['change']);

const isLoading = ref(true);
const saving = ref(false);
const error = ref(null);
const attemptedSave = ref(false);

const name = ref('');
const description = ref('');
const selectedType = ref(null);
const selectedContract = ref(null);
const selectedInvoice = ref(null);
const selectedOrder = ref(null);
const selectedCommitment = ref(null);
const selectedSupplyPoint = ref(null);
const selectedCluster = ref(null);
const selectedSupplyCut = ref(null);
const selectedAssigned = ref(null);
const selectedChannel = ref(null);
const contactEmail = ref('');
const dueAt = ref('');
const firstResponseAt = ref('');
const resolution = ref('');

// Valors carregats: només s'envien els camps que l'usuari modifica (el camp de data
// no té segons i, si es reenviés sense canvis, alteraria el venciment i els avisos).
// També permeten que el backend recalculi el venciment en canviar el tipus.
const loadedTypeId = ref(null);
const loadedDueAt = ref('');
const loadedFirstResponseAt = ref('');
const loadedResolution = ref('');

const types = ref([]);
const users = ref([]);
const channels = ref([]);

// Conversió entre el format de l'API (ISO) i el del camp datetime-local (hora local)
const toLocalInput = (value) => {
  if (!value) return '';
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};
const fromLocalInput = (value) => (value ? new Date(value).toISOString() : null);


const getData = async () => {
  try {
    if (props.id) {
      const detail = await $IncidentApiService.getDetail(props.id);

      name.value = detail.name;
      description.value = detail.description;
      selectedType.value = detail.type ? {
        code: detail.type.id,
        label: detail.type.name
      } : null;
      selectedAssigned.value = detail.assigned_to ? userOption(detail.assigned_to) : null;
      selectedChannel.value = detail.channel ? { code: detail.channel.id, label: detail.channel.name } : null;
      contactEmail.value = detail.contact_email || '';
      dueAt.value = toLocalInput(detail.due_at);
      firstResponseAt.value = toLocalInput(detail.first_response_at);
      resolution.value = detail.resolution || '';
      selectedSupplyCut.value = detail.supply_cut;
      loadedTypeId.value = detail.type?.id || null;
      loadedDueAt.value = dueAt.value;
      loadedFirstResponseAt.value = firstResponseAt.value;
      loadedResolution.value = resolution.value;

      selectedContract.value = detail.contract;
      selectedInvoice.value = detail.invoice;
      selectedOrder.value = detail.order_incident;
      selectedCommitment.value = detail.commitment_deposit;
      selectedSupplyPoint.value = detail.supply_point;
      selectedCluster.value = detail.cluster ? await $ClusterApiService.getDetail(detail.cluster.id) : null;
    } else {
      name.value = '';
      description.value = '';
      selectedType.value = null;
      selectedContract.value = null;
      selectedInvoice.value = null;
      selectedOrder.value = null;
      selectedCommitment.value = null;
      selectedSupplyPoint.value = null;
      selectedCluster.value = props.cluster_id ? await $ClusterApiService.getDetail(props.cluster_id) : null;
      selectedSupplyCut.value = null;
      selectedAssigned.value = null;
      selectedChannel.value = channels.value.find(channel => channel.is_default) || null;
      contactEmail.value = '';
      dueAt.value = '';
      firstResponseAt.value = '';
      resolution.value = '';
    }

  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
};

const getTypes = async () => {
  try {
    const result = await $ConfiglistApiService.getAll('notification/incident-type');
    result.results.forEach(type => {
      types.value.push({
        label: type.name,
        code: type.id
      })
    });
  } catch (err) {
    console.error('Error obtenint els tipus:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
};

const userOption = (user) => ({
  label: user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.username,
  code: user.id,
});

const getChannels = async () => {
  try {
    const channelList = await $ConfiglistApiService.getAll('notification/incident-channel');
    channels.value = channelList.results.map(item => ({ code: item.id, label: item.name, is_default: item.is_default }));
  } catch (err) {
    console.error('Error obtenint els canals:', err);
  }
};

const getUsers = async () => {
  try {
    const response = await $UserApiService.getAll();
    users.value = response.results.map(userOption);
  } catch (err) {
    console.error('Error obtenint els usuaris:', err);
  }
};

const updateSelect = async (event, entity) => {
  switch (entity) {
    case 'type':
      selectedType.value = event;
      break;
    case 'assigned':
      selectedAssigned.value = event;
      break;
    case 'channel':
      selectedChannel.value = event;
      break;
  }
}

const onSupplyCutSelected = async (item) => {
  selectedSupplyCut.value = item;
}

const onContractSelected = async (item) => {
  selectedContract.value = item;
}

const onInvoiceSelected = async (item) => {
  selectedInvoice.value = item;
}

const onOrderSelected = async (item) => {
  selectedOrder.value = item;
}

const onCommitmentSelected = async (item) => {
  selectedCommitment.value = item;
}

const onSupplyPointSelected = async (item) => {
  selectedSupplyPoint.value = item;
}

// El llistat de bateries no porta totes les dades que mostra ClusterDetail
const onClusterSelected = async (item) => {
  try {
    selectedCluster.value = await $ClusterApiService.getDetail(item.id);
  } catch (err) {
    console.error('Error obtenint la bateria:', err);
  }
}

const isValid = () => {
  if (name.value == '') return false;
  if (selectedType.value == null) return false;
  if (
    selectedContract.value == null
    && selectedInvoice.value == null
    && props.contract_id == null
    && props.invoice_id == null
    && props.commitment_id == null
    && props.order_id == null
    && props.supply_point_id == null
    && selectedOrder.value == null
    && selectedCommitment.value == null
    && selectedSupplyPoint.value == null
    && selectedCluster.value == null
    && selectedSupplyCut.value == null
  ) {
    toast.warning(t('warning_block.warning_select_contract_invoice'))
    return false;
  };

  return true;
}

const save = async () => {
  attemptedSave.value = true;
  let contract_id = null;
  let invoice_id = null;
  let commitment_id = null;
  let order_id = null;
  let supply_point_id = null;
  let cluster_id = null;
  if (props.contract_id) contract_id = props.contract_id;
  else if (selectedContract.value) contract_id = selectedContract.value.id;
  if (props.invoice_id) invoice_id = props.invoice_id;
  else if (selectedInvoice.value) invoice_id = selectedInvoice.value.id;
  if (props.commitment_id) commitment_id = props.commitment_id;
  else if (selectedCommitment.value) commitment_id = selectedCommitment.value.id;
  if (props.order_id) order_id = props.order_id;
  else if (selectedOrder.value) order_id = selectedOrder.value.id;
  if (props.supply_point_id) supply_point_id = props.supply_point_id;
  else if (selectedSupplyPoint.value) supply_point_id = selectedSupplyPoint.value.id;
  if (props.cluster_id) cluster_id = props.cluster_id;
  else if (selectedCluster.value) cluster_id = selectedCluster.value.id;
  if (!isValid()) return;
  saving.value = true
  try {
    let save_data = {
      id: props.id || null,
      name: name.value,
      type: selectedType.value.code,
      description: description.value,
      contract: contract_id,
      invoice: invoice_id,
      commitment_deposit: commitment_id,
      order_incident: order_id,
      supply_point: supply_point_id,
      cluster: cluster_id,
      supply_cut: selectedSupplyCut.value ? selectedSupplyCut.value.id : null,
      assigned_to: selectedAssigned.value ? selectedAssigned.value.code : null,
      channel: selectedChannel.value ? selectedChannel.value.code : null,
      contact_email: contactEmail.value || null,
    };
    if (props.id) {
      if (resolution.value !== loadedResolution.value) {
        save_data.resolution = resolution.value;
      }
      if (firstResponseAt.value !== loadedFirstResponseAt.value) {
        save_data.first_response_at = fromLocalInput(firstResponseAt.value);
      }
    }
    // Sense data (o si es canvia el tipus sense tocar-la), el backend la calcula segons el tipus
    const typeChanged = props.id && selectedType.value.code !== loadedTypeId.value;
    if (!props.id) {
      if (dueAt.value) {
        save_data.due_at = fromLocalInput(dueAt.value);
      }
    } else if (dueAt.value !== loadedDueAt.value) {
      if (dueAt.value) {
        save_data.due_at = fromLocalInput(dueAt.value);
      } else if (!typeChanged) {
        save_data.due_at = null;
      }
    }

    let response = await $IncidentApiService.save(save_data);
    if (response) {
      emit('change', response.id)
    }
  } catch (error) {
    console.error(error);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  isLoading.value = true;
  await Promise.all([getTypes(), getUsers(), getChannels()]);
  await getData();
});

watch(() => props.id, async () => {
  isLoading.value = true;
  await getData();
});

</script>

<template>
  <div>

    <div v-if="isLoading" class="flex justify-center items-center h-48">
      <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
    </div>
  
    <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
      <span class="text-red-600">{{
        $t("common.error_load")
        }}</span>
    </div>
  
    <div v-else class="relative h-[90vh] overflow-y-auto scrollbar-hide">
      <div class="mb-4">
        <H1Region>{{ props.id? `${$t('common.modify')} ${t('incident')}` : $t('customer_service_block.new_incident') }}</H1Region>
      </div>
  
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.title') }}*</label>
          <input type="text" v-model="name" class="input" :class="{ 'invalid': attemptedSave && name == '' }" />
        </div>
  
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.type') }}*</label>
          <v-select class="block w-full mr-1 required" :model-value="selectedType"
            @update:modelValue="updateSelect($event, 'type')" :options="types"
            :class="{ 'invalid': attemptedSave && (!selectedType) }" />
        </div>
  
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('incident_block.assigned_to') }}</label>
          <v-select class="block w-full mr-1" :model-value="selectedAssigned"
            @update:modelValue="updateSelect($event, 'assigned')" :options="users"
            :placeholder="t('incident_block.unassigned')" />
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('incident_block.due_date') }}</label>
          <input type="datetime-local" v-model="dueAt" class="input" />
          <p class="text-xs text-slate-400 mt-1">{{ t('incident_block.due_date_auto') }}</p>
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('incident_block.channel') }}</label>
          <v-select class="block w-full mr-1" :model-value="selectedChannel"
            @update:modelValue="updateSelect($event, 'channel')" :options="channels" />
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('incident_block.contact_email') }}</label>
          <input type="email" v-model="contactEmail" class="input" />
          <p class="text-xs text-slate-400 mt-1">{{ t('incident_block.contact_email_help') }}</p>
        </div>

        <div v-if="props.id" class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('incident_block.first_response') }}</label>
          <input type="datetime-local" v-model="firstResponseAt" class="input" />
        </div>
  
        <div class="mb-4 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.description') }}</label>
          <textarea name="description" id="description" cols="30" rows="5" v-model="description"
            class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
        </div>

        <div v-if="props.id" class="mb-4 col-span-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('incident_block.resolution') }}</label>
          <textarea name="resolution" id="resolution" cols="30" rows="3" v-model="resolution"
            class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
        </div>

      </div>

      <div class="mb-4">
        <div v-if="selectedSupplyCut" class="relative group p-2 bg-green-100">
          <label class="block text-sm font-medium text-slate-500 mb-1">{{ t('incident_block.supply_cut') }}</label>
          <span class="font-semibold">{{ selectedSupplyCut.token }}</span>
          <span v-if="selectedSupplyCut.distinct_streets" class="text-sm text-slate-600"> - {{ selectedSupplyCut.distinct_streets }}</span>
          <button @click="selectedSupplyCut = null"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
            <Icon name="fa6-solid:xmark" class="m-auto" />
          </button>
        </div>
        <SearchEntityInput v-else :service="$SupplyCutApiService" @select="onSupplyCutSelected" :methodName="'getData'"
          :title="t('incident_block.search_supply_cut')" :result_value="'distinct_streets'" />
      </div>
  
      <!-- <hr class="mb-2" /> -->
  
      <div v-if="!contract_id && !invoice_id && !commitment_id && !order_id && !supply_point_id && !cluster_id" class="row grid grid-cols-2 gap-3 mb-4">
        <SearchEntityInput :service="$ContractApiService" @select="onContractSelected" :title="$t('search_block.search_contract')"
          :result_value="'holder_full_name'" class="mt-auto" />
        <SearchEntityInput :service="$InvoiceApiService" @select="onInvoiceSelected" :title="$t('search_block.search_invoice')"
          :result_value="'customer_token_final'" class="mt-auto" />
        <SearchEntityInput :service="$OrderApiService" @select="onOrderSelected" :title="$t('search_block.search_order')"
          :result_value="'type_name'" class="mt-auto" />
        <SearchEntityInput :service="$CommitmentDepositApiService" @select="onCommitmentSelected" :title="$t('search_block.search_commitment')"
          :result_value="'customer_token_final'" class="mt-auto" />
        <SearchEntityInput :service="$SupplyPointApiService" @select="onSupplyPointSelected" :methodName="'getData'"
          :title="$t('search_block.search_supply_point')" :result_value="'address_complete'" class="mt-auto" />
        <SearchEntityInput :service="$ClusterApiService" @select="onClusterSelected" :methodName="'getData'"
          :title="$t('search_block.search_cluster')" :result_value="'street'" class="mt-auto" />
      </div>
  
      <div v-if="selectedContract || contract_id" class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('contract') }}</label>
        <div class="relative group p-2 bg-green-100">
          <ContractDetail :id="selectedContract ? selectedContract.id : contract_id" :reducedDetail="true"
            :isSubRegion="true" />
          <button v-if="selectedContract && !props.id" @click="selectedContract = null"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
            <Icon name="fa6-solid:xmark" class="m-auto" />
          </button>
        </div>
      </div>
  
      <div v-if="selectedInvoice || invoice_id" class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('invoice') }}</label>
        <div class="relative group p-2 bg-green-100">
          <InvoiceDetail :id="selectedInvoice? selectedInvoice.id : invoice_id" :reducedDetail="true" :isSubRegion="true" />
          <button v-if="selectedInvoice && !props.id" @click="selectedInvoice = null"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
            <Icon name="fa6-solid:xmark" class="m-auto" />
          </button>
        </div>
      </div>
  
      <div v-if="selectedCommitment || commitment_id" class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('commitment_deposit') }}</label>
        <div class="relative group p-2 bg-green-100">
          <CommitmentDepositDetail :id="selectedCommitment ? selectedCommitment.id : commitment_id" :isSubRegion="true" />
          <button v-if="selectedCommitment && !props.id" @click="selectedCommitment = null"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
            <Icon name="fa6-solid:xmark" class="m-auto" />
          </button>
        </div>
      </div>
  
      <div v-if="selectedOrder || order_id" class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.work_order') }}</label>
        <div class="relative group p-2 bg-green-100">
          <OrderDetail :id="selectedOrder ? selectedOrder.id : order_id" :isSubRegion="true" />
          <button v-if="selectedOrder && !props.id" @click="selectedOrder = null"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
            <Icon name="fa6-solid:xmark" class="m-auto" />
          </button>
        </div>
      </div>

      <div v-if="selectedSupplyPoint || supply_point_id" class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('supply_point') }}</label>
        <div class="relative group p-2 bg-green-100">
          <SupplyPointDetail :id="selectedSupplyPoint ? selectedSupplyPoint.id : supply_point_id" :isSubRegion="true" />
          <button v-if="selectedSupplyPoint && !props.id" @click="selectedSupplyPoint = null"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
            <Icon name="fa6-solid:xmark" class="m-auto" />
          </button>
        </div>
      </div>

      <div v-if="selectedCluster" class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('cluster') }}</label>
        <div class="relative group p-2 bg-green-100">
          <ClusterDetail :data="selectedCluster" :canChange="false" :isSubRegion="true" />
          <button v-if="!props.id && !cluster_id" @click="selectedCluster = null"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
            <Icon name="fa6-solid:xmark" class="m-auto" />
          </button>
        </div>
      </div>

      <div class="h-20"></div>
  
    </div>
    <div class="sticky bottom-0 left-0 right-0 bg-white border-t border-slate-200 px-4 py-2">
      <div class="flex flex-row-reverse">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t("common.save") }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
