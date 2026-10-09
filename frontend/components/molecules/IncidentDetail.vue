<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import PersonDetail from '../molecules/PersonDetail.vue';

const { $IncidentApiService } = useNuxtApp();
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
      <FieldDetail :label='$t("common.type")' :value=localData.type.name />
      <FieldDetail :label='$t("common.description")' class="col-span-2">
        <p class="whitespace-pre-line border border-gray-300 bg-gray-50 p-2 rounded-md">{{ localData.description }}</p>
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
