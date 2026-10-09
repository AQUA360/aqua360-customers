
<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useNuxtApp } from '#app';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';

const { $StatusApiService, $ObservationApiService, $OrderApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  entity: { // per ex. supply-point
    type: String,
    required: true
  },
  status: { // per exemple, l'id de l'estat actual: 1
    type: Number,
    required: false
  },
  parent_entity: { // per enviar al payload post, exemple: supply_point
    type: String,
    required: false
  },
  module: { // plugin service
    type: String,
    default: 'service',
    required: false
  },
  forceToken: {
    type: String,
    required: false
  },
  allowedTokens: { // si s'informa, el desplegable només ofereix aquests tokens d'estat
    type: Array,
    default: () => [],
  },
  confirmTokens: { // si l'estat destí és un d'aquests tokens, es demana confirmació abans de desar
    type: Array,
    default: () => [],
  },
  confirmMessage: { // clau i18n del missatge de confirmació (només amb confirmTokens)
    type: String,
    default: '',
  },
  reasonToken: { // token (o llista de tokens) d'estat que fan sortir el camp de motiu
    type: [String, Array],
    required: false
  },
  reasonLabel: { // clau i18n per la etiqueta del motiu (per defecte, 'Motiu')
    type: String,
    default: 'order_block.reason',
  },
  reasonPlaceholder: { // clau i18n pel placeholder del motiu
    type: String,
    default: 'common.write_reasons',
  },
  reasonRequired: { // si true, no es deixa desar sense motiu quan el camp es visible
    type: Boolean,
    default: false,
  },
  has_observation: {
    type: Boolean,
    default: true,
  },
  // Title icon, to keep the panel header consistent with the other sub-panels.
  icon: {
    type: String,
    default: null,
  },
  // Renders the same secondary "Cancel" button the other sub-panels use and
  // emits `cancel`, so the caller can close the panel.
  showCancel: {
    type: Boolean,
    default: false,
  },
});

const saving = ref(false);

const status = ref({}); // l'objecte 
const statusSelected = ref(props.status); // el id selected
const statusSelectedToken = ref(null); // el token selected

const statuses = ref([]);
const observation = ref('');
const reason = ref('');

const orderStatusCompletedToken = ref('CLOSED');
const incidentStatusClosedToken = ref('CLOSED');

const fetchStatuses = async (entity_status) => {
  try {
    const data = await $StatusApiService.getAll(entity_status, props.module);
    statuses.value = data.results;
    // agafem el status actual en funció del props.status (id) i guardem l'object a status.value
    status.value = statuses.value.find(s => s.id === props.status) || {};
  } catch (error) {
    console.error('Error fetching ' + props.entity + '-status statuses:', error);
  }
};

onMounted( async () => {
  await fetchStatuses(props.entity + '-status');

  if (props.forceToken) {
    statusSelected.value = statuses.value.find(s => s.token === props.forceToken)?.id;
  }
  if (allowed.value.length > 0 && !selectableStatuses.value.some(s => s.id === statusSelected.value)) {
    statusSelected.value = selectableStatuses.value[0]?.id;
  }
  statusSelectedToken.value = statuses.value.find(s => s.id === statusSelected.value)?.token || null;

  const orderToken = await $ConfigProjectApiService.get('order_status_completed_token');
  if (orderToken) orderStatusCompletedToken.value = orderToken;
  
  const incidentToken = await $ConfigProjectApiService.get('incident_status_closed_token');
  if (incidentToken) incidentStatusClosedToken.value = incidentToken;
});

const emits = defineEmits(['changed', 'cancel']);

const handleTextareaUpdate = (value) => {
  observation.value = value;
};

const handleReasonTextareaUpdate = (value) => {
  reason.value = value;
};

const allowed = computed(() =>
  props.allowedTokens
    .filter(token => token !== null && token !== undefined && token !== '')
    .map(String)
);

const selectableStatuses = computed(() => {
  if (allowed.value.length === 0) return statuses.value;
  // seguim l'ordre d'allowedTokens: el primer és el que queda preseleccionat
  return allowed.value
    .map(token => statuses.value.find(s => String(s.token) === token))
    .filter(Boolean);
});

const reasonTokens = computed(() =>
  (Array.isArray(props.reasonToken) ? props.reasonToken : [props.reasonToken])
    .filter(token => token !== null && token !== undefined && token !== '')
    .map(String)
);

const showReason = computed(() => {
  if (reasonTokens.value.length === 0) return false;
  const current = props.forceToken ?? statusSelectedToken.value;
  if (current === null || current === undefined) return false;
  return reasonTokens.value.includes(String(current));
});

const saveChanges = async () => {
  saving.value = true;
  try {
    await doSaveChanges();
  } finally {
    saving.value = false;
  }
};

const doSaveChanges = async () => {
  let statusObj = statuses.value.find(s => s.id === statusSelected.value);
  let closeAssociatedOrders = false;

  console.log('ChangeStatus: saveChanges', {
    entity: props.entity,
    selectedStatusToken: statusObj?.token,
    incidentStatusClosedToken: incidentStatusClosedToken.value,
    orderStatusCompletedToken: orderStatusCompletedToken.value
  });

  if (props.confirmTokens.length > 0 && statusObj && props.confirmTokens.reduce((acc, t) => acc || String(t) === String(statusObj.token), false)) {
    if (!confirm(props.confirmMessage ? t(props.confirmMessage) : t('confirmation_text_block.confirm_status_change'))) {
      return;
    }
  }

  if (props.entity === 'incident' && statusObj?.token === incidentStatusClosedToken.value) {
    try {
      // Check for pending orders
      const ordersResponse = await $OrderApiService.getAll('', [], 1, null, false, null, [], null, null, null, props.id);
      console.log('ChangeStatus: orders found', ordersResponse.results);
      
      const pendingOrders = ordersResponse.results.filter(o => o.status.token !== orderStatusCompletedToken.value);
      console.log('ChangeStatus: pending orders', pendingOrders);
      
      if (pendingOrders.length > 0) {
        if (confirm(t('incident_block.confirm_close_orders'))) {
          closeAssociatedOrders = true;
        }
      }
    } catch (error) {
      console.error('Error checking associated orders:', error);
    }
  }

  if (props.reasonRequired && showReason.value && reason.value.trim() === '') {
    toast.error(t('common.reason_required'));
    return;
  }

  let payload = {
    'status': statusSelected.value,
    'status_token': statusObj?.token || statusSelectedToken.value,
    'status_name': statusObj?.name,
    'observation': observation.value,
    'close_associated_orders': closeAssociatedOrders
  }

  // Només enviem el motiu si s'ha omplert, per no esborrar el que ja tingui l'objecte.
  if (reason.value.trim() !== '') {
    payload['reason'] = reason.value;
  }

  console.log('ChangeStatus: sending payload', payload);

  // canviem estat
  const saved = await $StatusApiService.save(props.entity, props.id, payload, props.module);
  

  // guardem l'observació
  if( observation.value.trim() !== '' ) {
    payload[ props.parent_entity ] = props.id;
    await $ObservationApiService.postObservation(payload, props.module, props.entity); 
  }

  emits('changed', {
    status: statusSelected.value,
    observation: observation.value,
    response: saved,
  });
};

// fem watch de la prop.status per actualitzar el statusSelected quan canvia
watch(() => props.status, (newVal) => {
  statusSelected.value = newVal;
  statusSelectedToken.value = statuses.value.find(s => s.id === newVal)?.token;
});
watch(() => props.forceToken, (newVal) => {
  statusSelected.value = statuses.value.find(s => s.token === props.forceToken)?.id;
});

watch(() => statusSelected.value, (newVal) => {
  statusSelectedToken.value = statuses.value.find(s => s.id === newVal)?.token;
});
 
</script>
<template>
  <H1Region :icon="icon">{{ t('common.change') }} {{ t('common.status') }}</H1Region>
  
  <div class="mt-1 flex gap-2 items-center">
    <label class="inline-block text-slate-400">{{  t('common.actual_status')  }}:</label>
    <AtomsColorBadge :value="status?.name || status?.token || ''" :color="status?.color"></AtomsColorBadge>
  </div>

  <div class="mt-4">
    <label>{{  t('common.status') }}:</label>
    <div v-if="forceToken != null" class="py-2 px-3">
      <AtomsColorBadge :value="statuses.find(s => s.token === forceToken)?.name || ''" :color="statuses.find(s => s.token === forceToken)?.color"></AtomsColorBadge>
    </div>
    <select v-else v-model="statusSelected"
    class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
      <option v-for="s in selectableStatuses" :key="s.id" :value="s.id">
        {{ s.name }}
      </option>
    </select>
  </div>

  <div v-if="showReason" class="mt-4">
    <label>{{ t(reasonLabel) }}:</label>
    <AtomsInputTextarea :autosave="false" @update:text="handleReasonTextareaUpdate" text="" :placeholder="reasonPlaceholder"></AtomsInputTextarea>
  </div>

  <div v-if="has_observation" class="mt-4">
    <label>{{ t('common.observations') }}:</label>
    <AtomsInputTextarea :autosave="false" @update:text="handleTextareaUpdate" text="" :placeholder="'common.write_comment'"></AtomsInputTextarea>
  </div>
  
  <div class="mt-4">
    <button class="button-primary" :disabled="saving" @click="saveChanges">
      <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': saving }" />
      &nbsp;{{ t('common.save') }}
    </button>
    <button v-if="showCancel"
      class="ml-2 px-3 py-2 border border-gray-300 rounded-md text-sm text-slate-600 hover:bg-slate-100"
      @click="emits('cancel')">
      {{ t('common.cancel') }}
    </button>
  </div>
</template>

