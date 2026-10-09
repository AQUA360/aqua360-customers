<script setup>
// components/organisms/ClusterDetail.vue
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import configProjectApi from '~/plugins/api/coredata/config-project-api';
import { formatDate } from '~/utils/date';

const { $apiManager, $JoinedPaymentApiService, $ConfigProjectApiService, $DocumentManagerApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
});

const emit = defineEmits(['show-detail']);

const toast = useToast();

const due_date = ref(null)
const statusPaidToken = ref(false)

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

onMounted(async () => {
  if (props.data.due_date) {
    due_date.value = props.data.due_date
  }
  statusPaidToken.value = await $ConfigProjectApiService.get('payment_status_paid_token');
})

watch(() => props.data, (newValue) => async () => {
  data.value = newValue;
}, { immediate: true });


</script>

<template>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.identification")' :value=data.number class="truncate"></FieldDetail>
    <FieldDetail :label="$t('common.status')" class="flex">
      <AtomsColorBadge :value="data.status?.name" :color="data.status?.color" />
    </FieldDetail>

    <FieldDetail v-if="data.contract" :label='$t("contract")' class="truncate col-span-2">
      <div class="flex items-center gap-x-2">
        <span v-if="isSubRegion">{{ data.contract.token }}</span>
        <button v-else @click="showDetail('ContractRegion', data.contract.id, null)"
          class="text-start text-sky-500 underline">{{ data.contract.token }}</button>
        <AtomsRedirectButton :id="data.contract.id" :path="'/contract/contracts/'" />
      </div>
    </FieldDetail>
    <FieldDetail class="col-span-2 max-w-lg" :label='$t("contract_block.holder")'>
      <div class="flex items-center gap-x-2">
        <AtomsPersonBadge :person="data.person" class="font-bold" />
        <AtomsRedirectButton :id="data.person.id" :path="'/contract/persons/'" />
      </div>
    </FieldDetail>
    <FieldDetail v-if="data.claim_request" :label='$t("claimrequest")' class="truncate col-span-2">
      <div class="flex items-center gap-x-2">
        <span>{{ data.claim_request.token }}</span>
        <AtomsRedirectButton :id="null" :path="`/billing/claim-managements/edit/${data.claim_request.id}`" />
      </div>
    </FieldDetail>
  </div>

  <hr class="my-2" />

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("service_block.barcode_ident")' :value=data.token class="truncate"></FieldDetail>
    <FieldDetail :label='$t("common.payment_method")' :value="data?.payment_type_name || t('common.no_payment_method')">
    </FieldDetail>
    <FieldDetail :label='$t("common.due_date")' :value="data.due_date ? formatDate(data.due_date) : '-'">
    </FieldDetail>
    <FieldDetail :label='$t("billing_block.payment_date")'
      :value="data.payment_date ? formatDate(data.payment_date) : '-'">
    </FieldDetail>
    <FieldDetail :label='$t("common.total")' :value="formatMoneyWithCurrency(data.total_final)"></FieldDetail>
  </div>

  <hr class="my-2" />

</template>
<style scoped>
.truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
