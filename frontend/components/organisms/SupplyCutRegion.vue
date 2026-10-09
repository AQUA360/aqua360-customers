<script setup>
import { ref, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import ButtonAcceptarRegion from '~/components/atoms/ButtonAcceptarRegion.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import SupplyCutDetail from '~/components/molecules/SupplyCutDetail.vue';
import SupplyPointDetail from '~/components/molecules/SupplyPointDetail.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import { format } from 'date-fns';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['accept', 'show-subregion', 'deleted', 'close-subregion', 'changed']);

const router = useRouter();
const { $SupplyCutApiService, $ConfiglistApiService, $LoggerApiService, $OrderApiService, $ConfigProjectApiService, $CommunicationProcessApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('supply_points');
const observationNumber = ref(0)
const logNumber = ref(0)
const savingLifecycleAction = ref(false);
// Sub-panels of the side region. Only one can be open at a time, so they all
// read from this single ref: with independent flags, closing the region left
// them set and the next one opened on top of the previous one.
const subPanel = ref(null); // 'cause' | 'status' | 'review'
const resolvingReview = computed(() => subPanel.value === 'review');
const resolveStatus = ref('1');
const resolveObservation = ref('');
const resolveCauseError = ref(false);

// Motiu llegible del per què el tall està en quarantena (requires_review).
const reviewReason = computed(() => {
  if (!data.value?.requires_review) return '';
  const isConflicte = data.value?.status?.token === '5';
  const causeRaw = data.value?.cause_raw;
  const stateRaw = data.value?.state_raw;
  if (isConflicte) return t('service_block.review_reason_conflicte');
  if (causeRaw && stateRaw) return t('service_block.review_reason_both', { cause: causeRaw, state: stateRaw });
  if (causeRaw) return t('service_block.review_reason_cause', { cause: causeRaw });
  if (stateRaw) return t('service_block.review_reason_state', { state: stateRaw });
  return t('service_block.review_reason_generic');
});

// Re-mount the SP detail (banner/status) after actions that touch its state.
const spDetailKey = ref(0);
const refreshSPDetail = () => { spDetailKey.value += 1; };
const notifyChanged = () => {
  refreshSPDetail();
  emit('changed');
};

// -- Canviar motiu (edició compacta del motiu/observació/data de fi) --
const causes = ref([]);
const editingCauseChange = computed(() => subPanel.value === 'cause');
const editCause = ref(null);
const editCauseDateEnd = ref('');
const editCauseObservation = ref('');
const savingCauseChange = ref(false);

const loadCauses = async () => {
  try {
    const results = await $SupplyCutApiService.getCauses();
    causes.value = results.filter((item) => item.token !== 'Accidental' && item.token !== 'Planificada');
  } catch (err) {
    console.error('Error fetching causes:', err);
  }
};

const editTemporaryCause = computed(() => {
  const c = causes.value.find((item) => item.id == editCause.value);
  return !!c?.is_temporary;
});

const handleClickChangeCause = async () => {
  if (!causes.value.length) await loadCauses();
  editCause.value = data.value?.cause?.id ?? null;
  editCauseDateEnd.value = data.value?.date_end ? String(data.value.date_end).slice(0, 16) : '';
  editCauseObservation.value = '';
  openSubPanel('cause');
};

const saveCauseChange = async () => {
  if (!editCause.value) {
    toast.error(t('service_block.choose_reason'));
    return;
  }
  if (editTemporaryCause.value && !editCauseDateEnd.value && !data.value?.date_end) {
    toast.error(t('service_block.supply_cut_date_end_required'));
    return;
  }
  const newCause = causes.value.find((c) => c.id == editCause.value);
  const currentTemporary = Boolean(data.value?.cause?.is_temporary);
  if (newCause && Boolean(newCause.is_temporary) !== currentTemporary) {
    const effect = newCause.is_temporary
      ? t('supply_cut_actions.change_reason_effect_temporary')
      : t('supply_cut_actions.change_reason_effect_indefinite');
    if (!confirm(t('supply_cut_actions.change_reason_flips_type', { effect }))) return;
  }
  savingCauseChange.value = true;
  try {
    const payload = { id: props.id, cause_id: editCause.value };
    if (editCauseDateEnd.value) payload.date_end = editCauseDateEnd.value;
    if (editCauseObservation.value) payload.observation = editCauseObservation.value;
    const result = await $SupplyCutApiService.save(payload);
    if (result?.id) data.value = result;
    toast.success(t('common.correct_save'));
    closeSubRegion();
    await getOrder();
    notifyChanged();
  } catch (err) {
    console.error(err);
    toast.error(err?.response?.data?.detail || err?.response?.data?.message || t('common.error_save'));
  } finally {
    savingCauseChange.value = false;
  }
};

const currentStatusToken = () => data.value?.status?.token || null;

// Transicions permeses per la màquina d'estats: el desplegable de ChangeStatus
// només ofereix estats assolibles des de l'estat actual (i mai Conflicte).
const allowedStatusTokens = computed(() => {
  switch (currentStatusToken()) {
    case '0': return ['1', '3']; // Planificat -> Actiu/Cancel·lat
    case '1': return ['2', '3']; // Actiu -> Acabat/Cancel·lat
    default: return [];          // terminals i Conflicte: es resolen per l'acció
  }
});

// Els talls no temporals (indefinits) tornen el PP a actiu en cancel·lar-se.
const causeIsTemporary = computed(() => {
  const causeToken = data.value?.cause?.token;
  return causeToken == '4'; // Manteniment o obres: previst temporal
});

const canCancel = computed(() => ['0', '1'].includes(currentStatusToken()));

const objectPermissions = ref(null);
const editingChangeStatus = computed(() => subPanel.value === 'status');
const SubRegion = ref(props.isSubRegionOpen);
const statuses = ref([]);

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateLogCount = (num) => {
  logNumber.value = num
}

const processNumber = ref(0)

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $SupplyCutApiService.getPermissions();
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
    ({ results: statuses.value } = await $ConfiglistApiService.getAll('service/supply-cut-status'));

    // agafem els valors de l'entitat
    const result = await $SupplyCutApiService.getDetail(props.id);

    data.value = result;

    if (data.value?.supply_points.length > 0) {
      selectedSuppplyPoint.value = data.value?.supply_points[0]
    }

    if (!orderTypeSupplyCut.value) await getOrderConfig();
    await getOrder();

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
  subPanel.value = null;
  regionDetailId.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}
// Obre un dels sub-panels (motiu / estat / revisió) tancant-ne la resta, de
// manera que només se'n mostri un.
const openSubPanel = function (panel) {
  showRegionDetailComponent.value = null;
  document.querySelector('[role="region"]')?.scrollTo(0, 0);
  showSubRegion();
  subPanel.value = panel;
}

// subregions details

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (res) {
  subPanel.value = null;
  showRegionDetailComponent.value = res.component;
  regionDetailId.value = res.id;
  showSubRegion();
}

const handleStatusChanged = (payload) => {
  closeSubRegion();
  if (payload?.response) {
    data.value = payload.response;
  } else if (payload?.status && data.value) {
    data.value.status = statuses.value.find((s) => s.id === payload.status) || data.value.status;
  }
  notifyChanged();
}

const handleClickChangeStatus = () => {
  openSubPanel('status');
}

const showMap = () => {
  document.querySelector('[role="region"]').scrollTop = 0
  showRegionDetailComponent.value = 'Map';
  showSubRegion()
}

const selectedSuppplyPoint = ref(null)
const supplyPointClicked = (item) => {
  selectedSuppplyPoint.value = item
  getOrder();
}

// supply cut work orders
const supplyCutOrderTypeToken = ref('cut_supply');
const orderTypeSupplyCut = ref(null);
const orderStatuses = ref([]);
const order = ref(null);
const savingOrder = ref(false);

const getOrderConfig = async () => {
  try {
    const order_types = await $ConfiglistApiService.getAll('order/order-type');
    const order_type_token = await $ConfigProjectApiService.get('order_type_supply_cut_token');
    if (order_type_token) supplyCutOrderTypeToken.value = order_type_token;
    orderTypeSupplyCut.value = order_types.results.find(item => item.token == supplyCutOrderTypeToken.value);

    const order_statuses = await $ConfiglistApiService.getAll('order/order-status');
    orderStatuses.value = order_statuses.results;
  } catch (err) {
    console.error(err);
  }
}

const getOrder = async () => {
  order.value = null;
  if (!selectedSuppplyPoint.value || !orderTypeSupplyCut.value) return;
  try {
    const response = await $OrderApiService.getAll('', [], 1, null, false, null,
      [orderTypeSupplyCut.value.id], null, null, null, null, '', '', null, [], [],
      [selectedSuppplyPoint.value.id]);
    order.value = response.results?.[0] || null;
  } catch (err) {
    console.error(err);
  }
}

const generateWorkOrder = async () => {
  if (!selectedSuppplyPoint.value) return;

  if (!orderTypeSupplyCut.value) {
    toast.error(`${t('warning_block.warning_order_type_not_found')}: ${supplyCutOrderTypeToken.value} (order_type_supply_cut_token)`);
    return;
  }

  const defaultOrderStatus = orderStatuses.value.find(s => s.is_default == true);
  const statusId = defaultOrderStatus?.id || orderStatuses.value[0]?.id;
  if (!statusId) {
    toast.error(t('warning_block.warning_order_status_not_found'));
    return;
  }

  if (!confirm(t('confirmation_text_block.confirm_create_orders'))) return;

  const sp = selectedSuppplyPoint.value;
  const description = `${t('supply_cut')}: ${data.value?.token || ''}\n` +
    `${t('address_block.location')}: ${sp.address_complete || ''}\n` +
    `${sp.address_postal_code || ''} ${sp.address_city || ''}\n` +
    `${t('supply_point')}: ${sp.token || ''}\n` +
    (sp.connection_token ? `${t('connection')}: #${sp.connection_token}\n` : '') +
    (sp.meter_code ? `${t('meter')}: #${sp.meter_code}\n` : '') +
    (data.value?.cause?.name ? `${t('order_block.reason')}: ${data.value.cause.name}` : '');

  const order_data = {
    // OrderSaveSerializer.validate() requires a token when creating; the
    // backend overrides it with the final token inside create().
    token: format(new Date(), 'yyyyMMddHHmmss'),
    supply_point: sp.id,
    type: orderTypeSupplyCut.value.id,
    status: statusId,
    description: description,
  };

  const contract_id = sp.contracts?.[0]?.id;
  if (contract_id) order_data.contract = contract_id;
  const dueDate = data.value?.exec_start || data.value?.date_start;
  if (dueDate) order_data.dueDateAt = dueDate.substring(0, 10);

  savingOrder.value = true;
  try {
    const order_saved = await $OrderApiService.save(order_data);
    order.value = order_saved;
    toast.success(t('common.correct_creation'));
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_save'));
  } finally {
    savingOrder.value = false;
  }
};

// remove a supply point from the cut (stops affecting its contract)
const removingSupplyPoint = ref(null);
const clickRemoveSupplyPoint = async (item) => {
  if (!item?.id) return;
  if (!confirm(t('service_block.confirm_remove_supply_point_from_cut'))) return;

  removingSupplyPoint.value = item.id;
  try {
    const result = await $SupplyCutApiService.removeSupplyPoint(props.id, item.id);
    if (result?.id) data.value = result;
    toast.success(t('common.correct_save'));
    if (selectedSuppplyPoint.value?.id == item.id) selectedSuppplyPoint.value = null;
    await getOrder();
    notifyChanged();
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_save'));
  } finally {
    removingSupplyPoint.value = null;
  }
}

const clickDeleteOrder = async (id) => {
  if (!id) return;
  if (!confirm(t('confirmation_text_block.confirm_delete'))) return;
  try {
    await $OrderApiService.deleteItem(id);
    order.value = null;
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  }
}

const runLifecycleAction = async (action, confirmKey) => {
  if (!props.id) return;
  if (!confirm(t(confirmKey))) return;
  savingLifecycleAction.value = true;
  try {
    let result = null;
    if (action === 'start') result = await $SupplyCutApiService.startCut(props.id);
    else if (action === 'finish') result = await $SupplyCutApiService.finishCut(props.id);
    if (result?.id) data.value = result;
    toast.success(t('common.correct_save'));
    await getOrder();
    notifyChanged();
  } catch (err) {
    console.error(err);
    toast.error(err?.response?.data?.message || t('common.error_save'));
  } finally {
    savingLifecycleAction.value = false;
  }
}

const clickStartCut = () => runLifecycleAction('start', 'confirmation_text_block.confirm_start_cut');
const clickFinishCut = () => runLifecycleAction('finish', 'confirmation_text_block.confirm_finish_cut');

const handleClickResolveReview = () => {
  resolveStatus.value = '1';
  resolveObservation.value = '';
  resolveCauseError.value = false;
  openSubPanel('review');
}

// Preflight before opening the wizard: the server decides whether an existing
// process blocks the new one or only deserves a warning. The save itself is
// guarded too, so this is a courtesy, not the enforcement point.
const checkingProcessConflict = ref(false);
const openProcessWizard = () => navigateTo('/communication/process-communications/add?supply_cut_id=' + props.id);

const clickStartCommunicationProcess = async () => {
  if (!props.id) return;
  checkingProcessConflict.value = true;
  try {
    const result = await $CommunicationProcessApiService.getSupplyCutStatus(props.id);
    if (result?.tier === 'block') {
      toast.error(t('communication_process_actions.already_running', { count: result.processes?.length || 1 }));
      return;
    }
    if (result?.tier === 'warn') {
      const proceed = confirm(t('communication_process_actions.confirm_existing_process', { count: result.processes?.length || 1 }));
      if (!proceed) return;
    }
    openProcessWizard();
  } catch (err) {
    console.error(err);
    // Never trap the user because the preflight request failed; the save is
    // guarded server side.
    openProcessWizard();
  } finally {
    checkingProcessConflict.value = false;
  }
}

const saveResolveReview = async () => {
  if (!['0', '1', '2', '3'].includes(resolveStatus.value)) {
    toast.error(t('service_block.resolve_review_invalid_status'));
    return;
  }
  savingLifecycleAction.value = true;
  try {
    const result = await $SupplyCutApiService.resolveReview(props.id, resolveStatus.value, resolveObservation.value);
    if (result?.id) data.value = result;
    toast.success(t('common.correct_save'));
    closeSubRegion();
    await getOrder();
    notifyChanged();
  } catch (err) {
    console.error(err);
    toast.error(err?.response?.data?.message || t('common.error_save'));
  } finally {
    savingLifecycleAction.value = false;
  }
}
</script>

<template>
  <div class="region__content">
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{t('common.error')}}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions.can_view" class="transition-all duration-500 ease"
      :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between">
        <H1Region class="mb-3">{{ $t('supply_cut') }}</H1Region>
        <div class="relative" v-if="objectPermissions.can_change">
          <OptionsDropdown id="ConnectionRequestRegionOptions">
            <DropdownOption v-if="currentStatusToken() === '0'" :name="$t('supply_cut_actions.start')" @click="clickStartCut">
              <span class="flex items-center gap-3">
                <Icon name="fa6-solid:play" class="w-3.5 h-3.5 text-slate-400" />
                <span>{{ $t('supply_cut_actions.start') }}</span>
              </span>
            </DropdownOption>
            <DropdownOption v-if="currentStatusToken() === '1'" :name="$t('supply_cut_actions.finish')" @click="clickFinishCut">
              <span class="flex items-center gap-3">
                <Icon name="fa6-solid:flag" class="w-3.5 h-3.5 text-slate-400" />
                <span>{{ $t('supply_cut_actions.finish') }}</span>
              </span>
            </DropdownOption>
            <DropdownOption v-if="data.requires_review" :name="$t('supply_cut_actions.resolve_review')"
              @click="handleClickResolveReview">
              <span class="flex items-center gap-3">
                <Icon name="fa6-solid:circle-check" class="w-3.5 h-3.5 text-slate-400" />
                <span>{{ $t('supply_cut_actions.resolve_review') }}</span>
              </span>
            </DropdownOption>
            <DropdownOption v-if="!data.requires_review" :name="$t('supply_cut_actions.change_reason')"
              @click="handleClickChangeCause">
              <span class="flex items-center gap-3">
                <Icon name="fa6-solid:triangle-exclamation" class="w-3.5 h-3.5 text-slate-400" />
                <span>{{ $t('supply_cut_actions.change_reason') }}</span>
              </span>
            </DropdownOption>
            <DropdownOption
              v-if="!data.requires_review && allowedStatusTokens.length"
              :name="`${$t('common.change')} ${$t('common.status')}`" @click="handleClickChangeStatus">
              <span class="flex items-center gap-3">
                <Icon name="fa6-solid:arrows-rotate" class="w-3.5 h-3.5 text-slate-400" />
                <span>{{ `${$t('common.change')} ${$t('common.status')}` }}</span>
              </span>
            </DropdownOption>
            <DropdownOption :name="$t('supply_cut_actions.start_communication_process')" :disabled="checkingProcessConflict"
              @click="clickStartCommunicationProcess">
              <span class="flex items-center gap-3">
                <Icon :name="checkingProcessConflict ? 'fa6-solid:spinner' : 'fa6-solid:comment-sms'"
                  :class="{ 'animate-spin': checkingProcessConflict }" class="w-3.5 h-3.5 text-slate-400" />
                <span>{{ $t('supply_cut_actions.start_communication_process') }}</span>
              </span>
            </DropdownOption>
          </OptionsDropdown>
        </div>
      </div>

      <div v-if="data.requires_review" role="alert" class="mb-2">
        <div class="flex items-center gap-3 w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-1 shadow-sm">
          <div class="flex h-4 w-4 shrink-0 items-center justify-center text-amber-700">
            <Icon name="fa6-solid:triangle-exclamation" class="text-sm" />
          </div>
          <div class="min-w-0 flex-1 flex flex-wrap flex-col items-start gap-y-1">
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span class="text-sm font-semibold text-amber-900 leading-snug">
                {{ $t('service_block.requires_review') }}
              </span>
              <span class="text-sm text-amber-800 leading-snug">{{ reviewReason }}</span>
            </div>
            <span v-if="objectPermissions?.can_change" class="text-xs text-amber-700 leading-snug">
              {{ $t('service_block.review_reason_action') }}
            </span>
          </div>
          <button v-if="objectPermissions?.can_change" :disabled="savingLifecycleAction"
            class="shrink-0 inline-flex items-center gap-1.5 rounded-md bg-amber-600 px-2.5 py-1 text-sm font-bold text-white shadow-sm hover:bg-amber-700 disabled:opacity-50"
            @click="handleClickResolveReview">
            <Icon v-if="savingLifecycleAction" name="fa6-solid:spinner" class="animate-spin text-[10px]" />
            {{ $t('supply_cut_actions.resolve_review') }}
          </button>
        </div>
      </div>

      <div v-if="pending">
        <div class="border border-gray-300 rounded-b p-4 bg-white">
          <div class="flex justify-center items-center">
            <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
            <span class="ml-2">{{ $t('common.loading') }}...</span>
          </div>
        </div>
      </div>
      <div v-else>
        <SupplyCutDetail :id="props.id" :data="data" @clickChangeStatus="handleClickChangeStatus" @show-map="showMap()"></SupplyCutDetail>
      </div>

      <AtomsTabs>
        <li class="me-2">
          <a href="#tab_log" @click.prevent="setActiveTab('supply_points')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'supply_points', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'supply_points' }" >
            <Icon name="fa6-solid:street-view" class="display-inline mr-2" /> {{ $t("common.supply_points") }} ({{ data.supply_points.length }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }" >
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.observations") }} ({{
              observationNumber }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_log" @click.prevent="setActiveTab('log')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }" >
            <Icon name="fa6-solid:list" class="display-inline mr-2" /> {{ $t("common.history") }} ({{ logNumber }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_communication_processes" @click.prevent="setActiveTab('communication_processes')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'communication_processes', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'communication_processes' }" >
            <Icon name="fa6-solid:comment-sms" class="display-inline mr-2" /> {{ $t("supply_cut_actions.communication_processes") }} ({{ processNumber }})
          </a>
        </li>
      </AtomsTabs>
      <div id="supply_cut_tabpanels">
        <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
          class="bg-white antialiased">
          <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
            parent_entity="supplypoint_request" url_entity="supply-cut" :id="props.id" module="service">
          </MoleculesObservationList>
        </section>
        <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log" class="bg-white antialiased">
          <MoleculesLogList v-if="data" entity="supply-cut-status" parent_entity="supply_cut" :id="props.id"
            @update:count="updateLogCount" :service="$LoggerApiService">
          </MoleculesLogList>
        </section>

        <section v-show="activeTab === 'communication_processes'" role="tabpanel" id="tab_communication_processes"
          class="bg-white antialiased">
          <MoleculesSupplyCutCommunicationProcessList v-if="data" :id="props.id"
            @update:count="processNumber = $event" />
        </section>

        <section v-show="activeTab === 'supply_points'" role="tabpanel" id="tab_log" class="bg-white antialiased">
      
          <section class="bg-white antialiased py-3">
            <div v-if="data.supply_points && data.supply_points.length != 0" class="mb-4 rounded-md border border-gray-300  bg-white divide-y">
              <div class="group grid grid-cols-[150px,1fr,40px] divide-x text-sm leading-4">
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.identificator') }} </span>
                <span class="p-2 pl-3 text-slate-600"> {{ t('address_block.address') }} </span>
                <span class="p-2 text-slate-600"></span>
              </div>
              <div class="max-h-[100px] overflow-y-auto divide-y">
                <div v-for="item in data.supply_points" 
                  class="group grid grid-cols-[150px,1fr,40px] divide-x text-sm leading-4 transition-all duration-100 cursor-pointer"
                  :class="{ 'bg-yellow-50 font-bold': selectedSuppplyPoint?.id == item.id }"
                  @click="supplyPointClicked(item)">
                  <div class="relative group footering text-slate-500 p-2 w-full">  
                    {{ item.token }}
                  </div>
                  <div class="relative group footering text-slate-500 p-2 w-full">
                    {{ item.address_complete }}
                  </div>
                  <div class="relative footering p-2 w-full text-center">
                    <button v-if="objectPermissions?.can_change" :disabled="removingSupplyPoint == item.id"
                      @click.stop="clickRemoveSupplyPoint(item)" class="text-slate-500 hover:text-red-600 disabled:opacity-50"
                      :title="t('service_block.remove_supply_point_from_cut')">
                      <Icon :name="removingSupplyPoint == item.id ? 'fa6-solid:spinner' : 'fa6-solid:link-slash'"
                        :class="{ 'animate-spin': removingSupplyPoint == item.id }" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="footering text-slate-500 p-2">
                  {{ t('common.no_records') }}
            </div>

            <div v-if="selectedSuppplyPoint">
              <fieldset id="solicitant__box" v-if="selectedSuppplyPoint" class="mb-3 border px-3 py-2 bg-sky-50">
                <SupplyPointDetail :key="'sp-' + selectedSuppplyPoint.id + '-' + spDetailKey" :id="selectedSuppplyPoint.id" :isSubRegion="true" :isSubRegionOpen="isSubRegionOpen"/>
              </fieldset>

              <fieldset id="ordre_treball__box" v-if="selectedSuppplyPoint"
                class="mb-3 border px-3 py-2 bg-sky-50 h-full rounded">
                <legend class="px-3 font-semibold bg-white shadow">
                  <h3>{{t('common.work_order')}}</h3>
                </legend>
                <div class="grid grid-cols-2">
                  <div>
                    <p class="font-semibold ml-3">{{t('address_block.location')}}</p>
                    <div class="px-3 mb-3">
                      {{ selectedSuppplyPoint.address_complete }}<br />
                      {{ selectedSuppplyPoint.address_postal_code || "" }} - {{ selectedSuppplyPoint.address_city || "" }}
                    </div>

                    <div class="px-3 mb-3" v-if="selectedSuppplyPoint.connection_token">
                      <FieldDetail :label="t('connection')" :strong="true" :value="'#' + selectedSuppplyPoint.connection_token" />
                    </div>

                  </div>
                  <div>
                    <div class="px-3 mb-3" v-if="selectedSuppplyPoint.meter_id">
                      <FieldDetail :label="t('meter')" :strong="true" :value="'#' + selectedSuppplyPoint.meter_code" />
                      <FieldDetail :label="t('service_block.model')" :value="selectedSuppplyPoint.meter_manufacturer + ' ' + selectedSuppplyPoint.meter_model" />
                      <FieldDetail :label="t('address_block.address')" :value="selectedSuppplyPoint.meter_address_street" />
                    </div>
                  </div>

                </div>
                <div v-if="order" class="flex items-center justify-between max-w-xl bg-green-100 py-1 px-2 mb-2">
                  <MoleculesOrderTypeDetail :data="order.type" :order="order"
                    @show-detail="showDetail({ component: 'OrderRegion', id: order.id })" />
                  <button v-if="objectPermissions?.can_change" @click="clickDeleteOrder(order.id)"
                    class="text-slate-500 ml-2" :title="`${t('common.delete')} ${t('common.work_order')}`">
                    <Icon name="fa6-solid:trash" />
                  </button>
                </div>
                <div v-else-if="!orderTypeSupplyCut" class="flex items-start gap-2 max-w-xl bg-amber-50 border border-amber-300 text-amber-700 text-sm py-1 px-2 mb-2">
                  <Icon name="fa6-solid:triangle-exclamation" class="mt-1 shrink-0" />
                  <span>
                    {{ t('warning_block.warning_order_type_not_found') }}:
                    <code>{{ supplyCutOrderTypeToken }}</code>
                    (<code>order_type_supply_cut_token</code>)
                  </span>
                </div>
                <ButtonOutline v-else-if="objectPermissions?.can_change" :disabled="savingOrder" @click="generateWorkOrder">
                  <Icon v-if="savingOrder" name="fa6-solid:spinner" class="animate-spin mr-2" />
                  {{ $t('common.generate') }} {{ $t('common.work_order') }}
                </ButtonOutline>
                <ButtonOutline v-if="objectPermissions?.can_change" @click="handleClickChangeStatus">{{ $t('common.change') }} {{ $t('common.status') }}</ButtonOutline>

              </fieldset>
            </div>  
          </section>

        </section>
      </div>
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <Transition enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 -translate-y-1" enter-to-class="opacity-100 translate-y-0">
          <div v-if="editingChangeStatus" class="mt-4">
            <ChangeStatus entity="supply-cut" parent_entity="supply_cut" :id="props.id"
              icon="fa6-solid:arrows-rotate" :status="data.status?.id" :allowedTokens="allowedStatusTokens"
              :confirmTokens="canCancel ? ['3'] : []"
              :confirmMessage="causeIsTemporary ? 'confirmation_text_block.confirm_cancel_temporary_cut' : 'confirmation_text_block.confirm_cancel_permanent_cut'"
              showCancel module="service" @changed="handleStatusChanged" @cancel="closeSubRegion" />
          </div>
        </Transition>

        <Transition enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 -translate-y-1" enter-to-class="opacity-100 translate-y-0">
          <div v-if="resolvingReview" class="mt-4">
            <H1Region icon="fa6-solid:circle-check">{{ $t('supply_cut_actions.resolve_review') }}</H1Region>
            <p class="text-sm text-slate-600 mb-3">{{ $t('service_block.resolve_review_intro') }}</p>
            <label class="block text-sm mb-1">{{ $t('common.status') }}:</label>
            <select v-model="resolveStatus" class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
              <option v-for="s in statuses.filter(x => ['0','1','2','3'].includes(String(x.token)))" :key="s.id" :value="s.token">
                {{ s.name }}
              </option>
            </select>
            <div class="mt-4">
              <label>{{ $t('common.observations') }}:</label>
              <AtomsInputTextarea :autosave="false" @update:text="resolveObservation = $event" text="" :placeholder="'common.write_comment'"></AtomsInputTextarea>
            </div>
            <div class="mt-4">
              <button class="button-primary" :disabled="savingLifecycleAction" @click="saveResolveReview">
                <Icon :name="savingLifecycleAction ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': savingLifecycleAction }" />
                {{ $t('common.save') }}
              </button>
              <button class="ml-2 px-3 py-2 border border-gray-300 rounded-md text-sm text-slate-600 hover:bg-slate-100" @click="closeSubRegion">
                {{ $t('common.cancel') }}
              </button>
            </div>
          </div>
        </Transition>

        <Transition enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 -translate-y-1" enter-to-class="opacity-100 translate-y-0">
          <div v-if="editingCauseChange" class="mt-4">
            <H1Region icon="fa6-solid:triangle-exclamation">{{ $t('supply_cut_actions.change_reason') }}</H1Region>
            <label class="block text-sm mb-1">{{ $t('order_block.reason') }}:</label>
            <select v-model="editCause" class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
              <option v-for="c in causes" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
            <div v-if="editTemporaryCause" class="mt-4">
              <AtomsInputDateTime v-model="editCauseDateEnd" class="w-full" :label="$t('service_block.cut_date_expected_end')"
                :placeholder="$t('common.end')" />
            </div>
            <div class="mt-4">
              <label>{{ $t('common.observations') }}:</label>
              <AtomsInputTextarea :autosave="false" @update:text="editCauseObservation = $event" text="" :placeholder="'common.write_comment'"></AtomsInputTextarea>
            </div>
            <div class="mt-4">
              <button class="button-primary" :disabled="savingCauseChange" @click="saveCauseChange">
                <Icon :name="savingCauseChange ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': savingCauseChange }" />
                {{ $t('common.save') }}
              </button>
              <button class="ml-2 px-3 py-2 border border-gray-300 rounded-md text-sm text-slate-600 hover:bg-slate-100" @click="closeSubRegion">
                {{ $t('common.cancel') }}
              </button>
            </div>
          </div>
        </Transition>

        <OrganismsOrderRegion v-if="showRegionDetailComponent === 'OrderRegion'" :id="regionDetailId" :isSubRegion="true" />

        <OrganismsMapRegion v-if="showRegionDetailComponent === 'Map'" :longitude="parseFloat(selectedSuppplyPoint.connection?.longitude)" :latitude="parseFloat(selectedSuppplyPoint.connection?.latitude)" :address="selectedSuppplyPoint.address_complete"></OrganismsMapRegion>
      </div>
    </div>

  </div>
</template>
