<script setup>
// components/organisms/ClusterDetail.vue
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import { hideIban } from '~/utils/iban';
import IBAN from '~/components/atoms/IBAN.vue';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

const { $InvoiceApiService } = useNuxtApp();

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
  },
  finalized: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-detail', 'show-edit']);

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

const data = ref(null);
const loaded = ref(false);

const getData = async () => {
  data.value = await $InvoiceApiService.getDetail(props.id);
  loaded.value = true;
};

const openPdf = async () => {
  if (!data.value?.invoice_file_template) return;

  try {
    await openAuthenticatedFileUrl(data.value.invoice_file_template);
  } catch (err) {
    console.error(err);
  }
};

const editReading = () => {
  emit('show-edit', props.id);
}

onMounted( async () => {
  if (props.data) {
    data.value = props.data;
    loaded.value = true;
  }
});

watch( () => props.show, (newValue) => {
  if (newValue) {
    getData();
  }
  else {
    loaded.value = false;
  }
});

</script>

<template>
  <div class="overflow-hidden transition-all duration-300 ease-in-out"
  :style="{ height: loaded ? '350px' : '0px', opacity: loaded ? '1' : '0', marginBottom: loaded ? '1rem' : '0', padding: loaded ? '1rem' : '0' }">
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.code")' :value="data ? data.token : ''"></FieldDetail>
      <FieldDetail :label='$t("common.date")' :value="data ? formatDate(data.issue_date) : ''"></FieldDetail>
    </div>
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail v-if="data && data.contract" :label='$t("contract")'>
        <span v-if="isSubRegion">{{ data.contract.token }}</span>
        <button v-else @click="showDetail('ContractRegion', data.contract.id, null)"
          class="text-start text-sky-500 underline">{{ data.contract.token }}</button>
      </FieldDetail>
      <FieldDetail v-else-if="data &&data.contract_request" :label='$t("contract_block.short_contract_request")'>
        <span v-if="isSubRegion">{{ data.contract_request.token }}</span>
        <button v-else @click="showDetail('ContractRequestRegion', data.contract_request.id, null)"
          class="text-start text-sky-500 underline">{{ data.contract_request.token }}</button>
      </FieldDetail>
      <!-- <FieldDetail v-else :label='$t("Contracte")' :value="'Sense contracte associat'" /> -->
      <FieldDetail :label='$t("common.status")'>
        <AtomsColorBadge v-if="data" :value="data.status?.name" :color="data.status?.color"></AtomsColorBadge>
      </FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.origin")' :value="data ? data.origin?.name : ''"></FieldDetail>
      <FieldDetail v-if="data" :label='$t("billing_block.reading_batch")'>
        <span v-if="isSubRegion && data.invoice_batch">{{ data.invoice_batch.token }}</span>
        <button v-else-if="!isSubRegion && data.invoice_batch"
          @click="showDetail('InvoiceBatchRegion', data.invoice_batch.id, null)"
          class="text-start text-sky-500 underline">{{ data.invoice_batch.token }}</button>
        <span v-else> - </span>
      </FieldDetail>
    </div>
  
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("contract_block.holder")' :value="data ? data.customer_final : ''"></FieldDetail>
      <FieldDetail :label='$t("address_block.address")' :value="data ? data.address_final : ''"></FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("address_block.location")' :value="data ? data.location_final : ''"></FieldDetail>
    </div>
  
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail v-if="data" :label='$t("exploitation")'>
        <span v-if="isSubRegion && data.exploitation">{{ data.exploitation.name }}</span>
        <button v-else-if="!isSubRegion && data.exploitation"
          @click="showDetail('ExploitationRegion', data.exploitation.id, null)"
          class="text-start text-sky-500 underline">{{ data.exploitation.name }}</button>
        <span v-else> - </span>
      </FieldDetail>
      <FieldDetail v-if="data" :label='$t("company")'>
        <span v-if="isSubRegion && data.company">{{ data.company.alias }}</span>
        <button v-else-if="!isSubRegion && data.company" @click="showDetail('CompanyRegion', data.company.id, null)"
          class="text-start text-sky-500 underline">{{ data.company.alias }}</button>
        <span v-else> - </span>
      </FieldDetail>
    </div>
  
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("billing_block.payment")' :value="data ? data.payment_type_final : ''"></FieldDetail>
      <FieldDetail v-if="data && data.payment_bank_final" :label='$t("common.iban")'>
        <IBAN :value="data.payment_bank_final" />
      </FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.total")' :value=" data ? data.total_final + ' €' : ''"></FieldDetail>
    </div>
    <div class="flex justify-end">
      <button v-if="!props.finalized" @click="editReading" class="button-primary mr-2"> {{t('common.show')}} {{ t('common.details') }}</button>
      <button v-else @click="openPdf" class="button-primary mr-2"> {{t('common.show')}} {{ t('invoice') }}</button>
    </div>
  </div>
</template>
