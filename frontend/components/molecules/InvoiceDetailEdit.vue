<script setup>
// components/organisms/ClusterDetail.vue
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import { hideIban } from '~/utils/iban';
import IBAN from '~/components/atoms/IBAN.vue';

const { t } = useI18n();
const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  show: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-detail']);

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

const { $InvoiceApiService } = useNuxtApp();

const localData = ref(null);
const pending = ref(false)

const getData = async () => {
  pending.value = true;
  try {
    const result = await $InvoiceApiService.getDetail(props.id);
    localData.value = result;
  } catch (err) {
    console.error(err)
  } finally {
    pending.value = false;
  }
}

onMounted(() => {
  if(props.id) {
    getData();
  }else if(props.data) {
    localData.value = props.data;
  }
});

watch(() => props.id, () => {
  getData();
});

watch(() => props.data, () => {
  localData.value = props.data;
});


</script>

<template>
  <div v-if="!pending && localData">

    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.code")' :value=localData.token></FieldDetail>
      <FieldDetail :label='$t("common.date")' :value="formatDate(localData.issue_date)"></FieldDetail>
    </div>
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail v-if="localData.contract" :label='$t("contract")'>
        <span v-if="isSubRegion">{{ localData.contract.token }}</span>
        <button v-else @click="showDetail('ContractRegion', localData.contract.id, null)"
          class="text-start text-sky-500 underline">{{ localData.contract.token }}</button>
      </FieldDetail>
      <FieldDetail v-else-if="localData.contract_request" :label='$t("contract_block.short_contract_request")'>
        <span v-if="isSubRegion">{{ localData.contract_request.token }}</span>
        <button v-else @click="showDetail('ContractRequestRegion', localData.contract_request.id, null)"
          class="text-start text-sky-500 underline">{{ localData.contract_request.token }}</button>
      </FieldDetail>
      <FieldDetail v-else-if="localData.connection_request" :label='$t("service_block.short_connection_request")'>
        <span v-if="isSubRegion">{{ localData.connection_request.token }}</span>
        <button v-else @click="showDetail('ContractRequestRegion', localData.connection_request.id, null)"
          class="text-start text-sky-500 underline">{{ localData.connection_request.token }}</button>
      </FieldDetail>
      <!-- <FieldDetail v-else :label='$t("Contracte")' :value="'Sense contracte associat'" /> -->
      <FieldDetail :label='$t("common.status")'>
        <AtomsColorBadge :value="localData.status?.name" :color="localData.status?.color"></AtomsColorBadge>
      </FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.origin")' :value="localData.origin?.name"></FieldDetail>
      <FieldDetail :label='$t("billing_block.reading_batch")'>
        <span v-if="isSubRegion && localData.invoice_batch">{{ localData.invoice_batch.token }}</span>
        <button v-else-if="!isSubRegion && localData.invoice_batch"
          @click="showDetail('InvoiceBatchRegion', localData.invoice_batch.id, null)"
          class="text-start text-sky-500 underline">{{ localData.invoice_batch.token }}</button>
        <span v-else> - </span>
      </FieldDetail>
    </div>
  
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("contract_block.holder")' :value=localData.customer_final></FieldDetail>
      <FieldDetail :label='$t("address_block.address")' :value=localData.address_final></FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("address_block.location")' :value="localData.location_final"></FieldDetail>
    </div>
  
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("exploitation")'>
        <span v-if="isSubRegion && localData.exploitation">{{ localData.exploitation.name }}</span>
        <button v-else-if="!isSubRegion && localData.exploitation"
          @click="showDetail('ExploitationRegion', localData.exploitation.id, null)"
          class="text-start text-sky-500 underline">{{ localData.exploitation.name }}</button>
        <span v-else> - </span>
      </FieldDetail>
      <FieldDetail :label='$t("company")'>
        <span v-if="isSubRegion && localData.company">{{ localData.company.alias }}</span>
        <button v-else-if="!isSubRegion && localData.company" @click="showDetail('CompanyRegion', localData.company.id, null)"
          class="text-start text-sky-500 underline">{{ localData.company.alias }}</button>
        <span v-else> - </span>
      </FieldDetail>
    </div>
  
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("billing_block.payment")' :value=localData.payment_type_final></FieldDetail>
      <FieldDetail v-if="localData.payment_bank_final" :label='$t("common.iban")'>
        <IBAN :value="localData.payment_bank_final" />
      </FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.total")' :value="localData.total_final + ' €'"></FieldDetail>
    </div>
  </div>
  <div v-else>
    <p>{{ $t('common.loading') }}...</p>
  </div>


</template>
