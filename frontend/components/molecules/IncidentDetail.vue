<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate, formatDateTime } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import PersonDetail from '../molecules/PersonDetail.vue';

const { $IncidentApiService, $DocumentManagerApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  data: {
    type: Object,
    required: false
  },
  isSubRegion: {
    type: Boolean,
    default: false,
  }
});

const emit = defineEmits(['show-detail', 'edit']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $IncidentApiService.getDetail(props.id);
    localData.value = detail;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }

};

const userName = (user) => {
  if (!user) return '-';
  return user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.username;
};

// Els terminis en hores es mostren amb l'hora; els de dies, només la data
const formatDue = (data) => {
  if (!data.due_at) return '-';
  return data.type?.due_unit === 'hours' ? formatDateTime(data.due_at) : formatDate(data.due_at);
};

const openReceipt = async () => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(localData.value.receipt_document);
    window.open(URL.createObjectURL(file), '_blank');
  } catch (err) {
    console.error('Error obrint el justificant:', err);
  }
};

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}


onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
    }}</span>
  </div>

  <div v-else-if="localData">
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.identification")' :value=localData.token />
      <FieldDetail :label='$t("common.status")'>
        <AtomsColorBadge :value=localData.status.name :color=localData.status.color />
      </FieldDetail>
      <FieldDetail :label='$t("common.title")' :value=localData.name />
      <FieldDetail :label='$t("common.type")' :value="localData.type?.name" />
      <FieldDetail :label='$t("incident_block.channel")' :value="localData.channel?.name || '-'" />
      <FieldDetail :label='$t("incident_block.phase")'
        :value="localData.status?.phase ? $t(`incident_settings.phase_${localData.status.phase}`) : '-'" />
      <FieldDetail :label='$t("incident_block.created_by")'>
        {{ userName(localData.created_by) }} <span class="text-slate-400">({{ formatDate(localData.created_at) }})</span>
      </FieldDetail>
      <FieldDetail :label='$t("incident_block.assigned_to")'
        :value="localData.assigned_to ? userName(localData.assigned_to) : $t('incident_block.unassigned')" />
      <FieldDetail :label='$t("incident_block.due_date")'>
        <span :class="{ 'text-red-600 font-semibold': localData.is_overdue }">{{ formatDue(localData) }}</span>
        <span v-if="localData.is_overdue" class="ml-2 text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">
          {{ $t('incident_block.overdue') }}
        </span>
        <span v-if="localData.paused_at" class="ml-2 text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700"
          :title="formatDateTime(localData.paused_at)">
          {{ $t('incident_block.paused') }}
        </span>
      </FieldDetail>
      <FieldDetail :label='$t("incident_block.first_response")'
        :value="localData.first_response_at ? formatDateTime(localData.first_response_at) : '-'" />
      <FieldDetail v-if="localData.closed_at" :label='$t("incident_block.closed_at")'>
        {{ formatDateTime(localData.closed_at) }}
        <span v-if="localData.closed_on_time !== null" class="ml-2 text-xs px-2 py-0.5 rounded-full"
          :class="localData.closed_on_time ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
          {{ localData.closed_on_time ? $t('incident_block.on_time') : $t('incident_block.out_of_time') }}
        </span>
      </FieldDetail>
      <FieldDetail v-if="localData.contact_email" :label='$t("incident_block.contact_email")' :value="localData.contact_email" />
      <FieldDetail v-if="localData.receipt_document" :label='$t("incident_block.receipt")'>
        <button class="text-sky-500 underline" @click="openReceipt">{{ $t('incident_block.view_receipt') }}</button>
        <span v-if="localData.receipt_sent_at" class="text-slate-400 ml-2">({{ $t('incident_block.sent') }} {{ formatDateTime(localData.receipt_sent_at) }})</span>
      </FieldDetail>
      <FieldDetail :label='$t("common.description")' class="col-span-2">
        <p class="whitespace-pre-line border border-gray-300 bg-gray-50 p-2 rounded-md">{{ localData.description }}</p>
      </FieldDetail>
      <FieldDetail v-if="localData.resolution" :label='$t("incident_block.resolution")' class="col-span-2">
        <p class="whitespace-pre-line border border-gray-300 bg-gray-50 p-2 rounded-md">{{ localData.resolution }}</p>
      </FieldDetail>

      <hr class="my-2 col-span-2" />

      <FieldDetail v-if="localData.contract" :label="$t('contract')">
        <div v-if="!isSubRegion && localData.contract" class="flex gap-2">
          <button @click="showDetail('ContractRegion', localData.contract.id)"
            class="text-start text-sky-500 underline">{{ localData.contract.token }}</button>
          <AtomsRedirectButton :id="localData.contract.id" :path="'/contract/contracts/'" />
        </div>
        <span v-else>{{ localData.contract ? localData.contract.token : '-' }}</span>
      </FieldDetail>
      <FieldDetail v-if="localData.supply_point" :label="$t('supply_point')">
        <div v-if="!isSubRegion && localData.supply_point" class="flex gap-2">
          <button @click="showDetail('SupplyPointRegion', localData.supply_point.id)"
            class="text-start text-sky-500 underline">
            {{ localData.supply_point.address_complete ? localData.supply_point.address_complete :
              localData.supply_point.token }}
          </button>
          <AtomsRedirectButton :id="parseInt(localData.supply_point.id)" :path="'/service/supplypoints/'" />
        </div>
        <span v-else>
          {{ localData.supply_point.address_complete ? localData.supply_point.address_complete :
            localData.supply_point.token }}
        </span>
      </FieldDetail>
      <FieldDetail v-if="localData.cluster" :label="$t('cluster')">
        <div v-if="!isSubRegion" class="flex gap-2">
          <button @click="showDetail('ClusterRegion', localData.cluster.id)"
            class="text-start text-sky-500 underline">
            {{ localData.cluster.token }}
          </button>
          <AtomsRedirectButton :id="localData.cluster.id" :path="'/service/clusters/'" />
        </div>
        <span v-else>{{ localData.cluster.token }}</span>
      </FieldDetail>
      <FieldDetail v-if="localData.supply_cut" :label="$t('incident_block.supply_cut')">
        <div v-if="!isSubRegion" class="flex gap-2">
          <button @click="showDetail('SupplyCutRegion', localData.supply_cut.id)"
            class="text-start text-sky-500 underline">
            {{ localData.supply_cut.token }}
          </button>
        </div>
        <span v-else>{{ localData.supply_cut.token }}</span>
        <p v-if="localData.supply_cut.cause_name || localData.supply_cut.date_end" class="text-sm text-slate-500">
          <span v-if="localData.supply_cut.cause_name">{{ localData.supply_cut.cause_name }}</span>
          <span v-if="localData.supply_cut.date_end"> · {{ $t('incident_block.restoration_forecast') }} {{ formatDateTime(localData.supply_cut.date_end) }}</span>
        </p>
      </FieldDetail>
      <FieldDetail v-if="localData.invoice" :label="$t('invoice')">
        <div v-if="!isSubRegion && localData.invoice" class="flex gap-2">
          <button @click="showDetail('InvoiceRegion', localData.invoice.id)"
            class="text-start text-sky-500 underline">
            {{ localData.invoice.token }}
          </button>
          <AtomsRedirectButton :id="localData.invoice.id" :path="'/billing/invoice/'" />
        </div>
        <span v-else>{{ localData.invoice ? localData.invoice.token : '-' }}</span>
      </FieldDetail>
      <FieldDetail v-if="localData.commitment_deposit" :label="$t('claim_block.commitment')">
        <div v-if="!isSubRegion && localData.commitment_deposit" class="flex gap-2">
          <button @click="showDetail('CommitmentDepositRegion', localData.commitment_deposit.id)"
            class="text-start text-sky-500 underline">
            {{ localData.commitment_deposit.token }}
          </button>
          <AtomsRedirectButton :id="localData.commitment_deposit.id" :path="'/billing/commitment-deposits/'" />
        </div>
        <span v-else>{{ localData.commitment_deposit ? localData.commitment_deposit.token : '-' }}</span>
      </FieldDetail>
      <FieldDetail v-if="localData.order_incident" :label="$t('common.work_order')">
        <div v-if="!isSubRegion && localData.order_incident" class="flex gap-2">
          <button @click="showDetail('OrderRegion', localData.order_incident.id)"
            class="text-start text-sky-500 underline">
            {{ localData.order_incident.token }}
          </button>
          <AtomsRedirectButton :id="localData.order_incident.id" :path="'/order/orders/'" />
        </div>
        <span v-else>{{ localData.order_incident ? localData.order_incident.token : '-' }}</span>
      </FieldDetail>

    </div>

  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
