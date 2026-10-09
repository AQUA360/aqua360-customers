<script setup>
// components/organisms/ClusterDetail.vue
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { computed } from 'vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import configProjectApi from '~/plugins/api/coredata/config-project-api';
import { formatDate } from '~/utils/date';

const { $apiManager, $PaymentApiService, $ConfigProjectApiService, $DocumentManagerApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isPayment: {
    type: Boolean,
    default: false
  },
  canChange: {
    type: Boolean,
    default: false
  },
  // Fraccionament (PaymentCommitment) del compromís de dipòsit al qual correspon aquest pagament, si n'hi ha.
  paymentCommitment: {
    type: Object,
    default: null
  },
  // Compromís de dipòsit al qual pertany aquest pagament, resolt tant si el pagament el té informat
  // directament (data.commitment_deposit) com si hi arriba de forma indirecta a través de la factura
  // (relació M2M CommitmentDeposit.invoices), igual que fa InvoiceDetail.vue amb la seva prop `commitmentDeposit`.
  commitmentDeposit: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['show-detail', 'change', 'clickChangeStatus']);

const toast = useToast();

const due_date = ref(null)
const statusPaidToken = ref(false)

// El contracte no sempre penja directament del pagament: si ve d'una factura o d'un
// compromís de dipòsit, el contracte hi és igualment associat de forma anidada.
const contractLink = computed(() => {
  return props.data?.contract || props.data?.invoice?.contract || props.data?.commitment_deposit?.contract || null;
});

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

const doPayment = async function () {
  let data = {
    id: props.id,
    status_token: statusPaidToken.value,
  }
  let payment_update = await $PaymentApiService.save(data);
  console.log(payment_update);
  emit('change');
}


const printDocument = async () => {
  try {
    const document_file = await $DocumentManagerApiService.getDetail(props.data.document.id)
    const file = await $DocumentManagerApiService.viewDocument(props.data.document.id);

    //when downloading, allow user to select download folder instead of default download folder
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url;
    link.download = document_file.document_name;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.log(error)
  }
}

onMounted(async () => {
  if (props.data.due_date) {
    due_date.value = props.data.due_date
  }
  statusPaidToken.value = await $ConfigProjectApiService.get('payment_status_paid_token');
})

const ChangeDueDate = async (event) => {
  let saveData = {
    id: props.id,
    due_date: due_date.value
  }
  $PaymentApiService.save(saveData)
  await nextTick()
  emit('change')
}

watch(() => props.data, (newValue) => async () => {
  data.value = newValue;
}, { immediate: true });


</script>

<template>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.code")' :value=data.token class="truncate"></FieldDetail>
    <FieldDetail v-if="data.name" :label='$t("common.name")' :value=data.name class="truncate"></FieldDetail>
    <FieldDetail v-if="contractLink" :label='$t("contract")' class="truncate">
      <span v-if="isSubRegion">{{ contractLink.token }}</span>
      <span v-else class="flex items-center gap-2">
        <button @click="showDetail('ContractRegion', contractLink.id, null)"
          class="text-start text-sky-500 underline">{{ contractLink.token }}</button>
        <AtomsRedirectButton :id="contractLink.id" :path="'/contract/contracts/'" />
      </span>
    </FieldDetail>
    <FieldDetail v-if="data.invoice" :label='$t("invoice")' class="truncate">
      <span v-if="isSubRegion">{{ data.invoice.title_final }}</span>
      <span v-else class="flex items-center gap-2">
        <button @click="showDetail('InvoiceRegion', data.invoice.id, null)"
          class="text-start text-sky-500 underline">{{ data.invoice.title_final }}</button>
        <AtomsRedirectButton :id="data.invoice.id" :path="'/billing/invoice/'" />
      </span>
    </FieldDetail>
    <FieldDetail v-if="commitmentDeposit" :label='$t("commitment_deposit")' class="truncate">
      <span v-if="isSubRegion">{{ commitmentDeposit.token }}</span>
      <span v-else class="flex items-center gap-2">
        <button @click="showDetail('CommitmentDepositRegion', commitmentDeposit.id, null)"
          class="text-start text-sky-500 underline">{{ commitmentDeposit.token }}</button>
        <AtomsRedirectButton :id="commitmentDeposit.id" :path="'/billing/commitment-deposits/'" />
      </span>
    </FieldDetail>
    <FieldDetail v-if="paymentCommitment" :label='$t("claim_block.fractions")' class="truncate">
      <!-- Amb isSubRegion ja hi ha 2 regions obertes (aquesta i la que la conté): no es pot obrir una
           tercera region anidada, així que en lloc de text pla s'obre el compromís de dipòsit en una
           pestanya nova (AtomsRedirectButton), igual que la resta d'enllaços quan no es pot anidar més. -->
      <div v-if="isSubRegion" class="flex gap-2 items-center">
        <span>{{ paymentCommitment.due_date ? formatDate(paymentCommitment.due_date) : paymentCommitment.token }}</span>
        <AtomsRedirectButton v-if="paymentCommitment.commitment_deposit" :id="paymentCommitment.commitment_deposit.id" :path="'/billing/commitment-deposits/'" />
      </div>
      <div v-else class="flex gap-2 items-center">
        <button v-if="paymentCommitment.commitment_deposit" @click="showDetail('CommitmentDepositRegion', paymentCommitment.commitment_deposit.id, null)"
          class="text-start text-sky-500 underline flex items-center gap-1">
          <span>{{ paymentCommitment.due_date ? formatDate(paymentCommitment.due_date) : (paymentCommitment.token || paymentCommitment.id) }}</span>
        </button>
        <AtomsRedirectButton v-if="paymentCommitment.commitment_deposit" :id="paymentCommitment.commitment_deposit.id" :path="'/billing/commitment-deposits/'" />
      </div>
    </FieldDetail>
    <FieldDetail v-if="!data.invoice && !data.commitment_deposit" :label='$t("address_block.address")' class="truncate col-span-full">
      <span>{{ data.address_final }} - {{ data.location_final }}</span>
    </FieldDetail>
    <FieldDetail v-if="!data.invoice && !data.commitment_deposit" :label='$t("common.client")' class="truncate">
      <span>{{ data.customer_final }} ({{ data.customer_token_final }})</span>
    </FieldDetail>
    <FieldDetail :label='$t("common.doc")' v-if="data.document">
        <button class="text-sky-500 underline flex items-center gap-2" @click="printDocument">
          <Icon name="fa6-solid:file-pdf" />
          {{ $t('common.download') }}
    </button>
      </FieldDetail>
  </div>

  <div v-if="!isSubRegion" role="row" class="my-3">
    <!-- <FieldDetail :label='$t("Remesa")'>
      <button class="text-sky-500 underline flex items-center gap-2"
        @click="showDetail('SEPADocumentRegion', data.document.id)">
        <Icon name="fa6-solid:file-pdf" />
        {{ $t('Mostrar') }}
      </button>
    </FieldDetail> -->
  </div>

  <div role="row" class="grid grid-cols-2 my-1">
    <FieldDetail v-if="isSubRegion && !isPayment" :label='$t("common.identification")'
      :value="data.invoice ? data.invoice.token : data.commitment_deposit.token"></FieldDetail>
  </div>

  <hr class="my-2" />

  <div role="row" class="my-3">
    <FieldDetail :label='$t("common.payment_method")' :value="data.payment_type ? data.payment_type : ''">
    </FieldDetail>
  </div>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.total")' :value="formatMoneyWithCurrency(data.amount)"></FieldDetail>
    <FieldDetail :label='$t("billing_block.payment_date")' :value="data.payment_date ? formatDate(data.payment_date) : '-'">
    </FieldDetail>
  </div>

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.status")' class="h-[25px] mt-3 mr-2">
      <span>
        <AtomsColorBadge :value="data.status?.name" :color="data.status?.color">
        </AtomsColorBadge>
        <!-- <button class="px-2 py-1 text-gray-500" @click="showDetail('ChangeStatus', data.id)"><Icon name="fa6-solid:pencil" /></button> -->
      </span>
    </FieldDetail>
    <div v-if="!isSubRegion || isPayment" class="mb-2 mt-3 grid grid-cols-[120px,1fr] items-center h-[25px]">
      <label class="inline-block truncate text-slate-600">
        <Icon v-show="data.due_date == null" name="fa6-solid:asterisk" class="text-sm text-red-400" />
        {{ t('common.due_date') }}
      </label>
      <AtomsInputDate v-model="due_date" :disabled="!canChange" class="no-border compact-date mr-2" @change="ChangeDueDate($event)" />
    </div>
    <FieldDetail v-else :label='$t("common.due_date")' :value="data.due_date ? formatDate(data.due_date) : '-'"
      class="h-[25px] mt-3 mr-2">
    </FieldDetail>

  </div>


  <hr v-if="data.reject" class="my-2" />


  <div v-if="data.reject_date" role="row" class="">
    <FieldDetail :label='$t("common.return_date")' :value="formatDate(data.reject_date)"></FieldDetail>
  </div>
  <div v-if="data.reject" role="row" class="">
    <FieldDetail :label='$t("common.return_reason")' :value=data.reject.name></FieldDetail>
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
