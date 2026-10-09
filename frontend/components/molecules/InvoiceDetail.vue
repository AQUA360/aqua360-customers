<script setup>
// components/organisms/ClusterDetail.vue
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import { hideIban } from '~/utils/iban';
import IBAN from '~/components/atoms/IBAN.vue';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

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
  reducedDetail: {
    type: Boolean,
    default: false
  },
  isBudget: {
    type: Boolean,
    default: false
  },
  // Compromís de dipòsit al qual pertany la factura, si n'hi ha (relació M2M sense FK directa;
  // obtingut a InvoiceRegion.vue via $CommitmentDepositApiService.getByInvoice).
  commitmentDeposit: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['show-detail']);

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

const { $InvoiceApiService } = useNuxtApp();

const localData = ref(null);
const pending = ref(false)
const showGeneralContractsDropdown = ref(false);
const generalContractsButtonRef = ref(null);

const { fetchFireUsageTypeTokens, isFireContract } = useFireUsageTypeTokens();
const { fetchFinalInvoiceTokens, isVoidedInvoice } = useFinalInvoiceTokens();

const toggleGeneralContractsDropdown = () => {
  showGeneralContractsDropdown.value = !showGeneralContractsDropdown.value;
};

const handleClickOutside = (event) => {
  if (generalContractsButtonRef.value && !generalContractsButtonRef.value.contains(event.target)) {
    showGeneralContractsDropdown.value = false;
  }
};

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

onMounted(async () => {
  if (props.data) {
    localData.value = props.data;
  } else if (props.id) {
    getData();
  }
  document.addEventListener('click', handleClickOutside);
  await fetchFireUsageTypeTokens();
  await fetchFinalInvoiceTokens();
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

watch(() => props.id, () => {
  getData();
});

watch(() => props.data, () => {
  localData.value = props.data;
});

const openInvoiceFileTemplate = async () => {
  if (!localData.value?.invoice_file_template) return;

  try {
    await openAuthenticatedFileUrl(localData.value.invoice_file_template);
  } catch (err) {
    console.error(err);
  }
};

</script>

<template>
  <div v-if="!pending && localData">

    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.number")' :value="localData.serie_final"></FieldDetail>
      <FieldDetail :label='$t("common.identification")' :value=localData.token></FieldDetail>
      <FieldDetail class="col-span-full" :label='$t("common.title")' :value=localData.title_final></FieldDetail>
      <FieldDetail :label='$t("common.date")' :value="formatDate(localData.issue_date)"></FieldDetail>
      <FieldDetail :label='$t("common.due_date")' :value="localData.due_date ? formatDate(localData.due_date) : '-'">
      </FieldDetail>
      <FieldDetail :label='$t("invoice")' v-if="localData.invoice_budget && !reducedDetail">
        <span v-if="isSubRegion">{{ localData.invoice_budget.serie_final }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('InvoiceRegion', localData.invoice_budget.id, null)"
            class="text-start text-sky-500 underline">{{ localData.invoice_budget.serie_final }}</button>
          <AtomsRedirectButton :id="localData.invoice_budget.id" :path="'/billing/invoice/'" />
        </div>
      </FieldDetail>
      <FieldDetail :label='$t("common.budget_detail")' v-if="localData.budget && !reducedDetail">
        <span v-if="isSubRegion">{{ localData.budget.serie_final }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('InvoiceRegion', localData.budget.id, null)"
            class="text-start text-sky-500 underline">{{ localData.budget.serie_final }}</button>
          <AtomsRedirectButton :id="localData.budget.id" :path="'/billing/invoice/'" />
        </div>
      </FieldDetail>

      <FieldDetail :label='$t("billing_block.returned")' v-if="localData.returned_invoice && !reducedDetail">
        <span v-if="isSubRegion">{{ localData.returned_invoice.serie_final }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('InvoiceRegion', localData.returned_invoice.id, null)"
            class="text-start text-sky-500 underline">{{ localData.returned_invoice.serie_final }}</button>
          <AtomsRedirectButton :id="localData.returned_invoice.id" :path="'/billing/invoice/'" />
        </div>
      </FieldDetail>
      <FieldDetail :label='$t("billing_block.refactored")' v-if="localData.refactored_invoice && !reducedDetail">
        <span v-if="isSubRegion">{{ localData.refactored_invoice.serie_final }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('InvoiceRegion', localData.refactored_invoice.id, null)"
            class="text-start text-sky-500 underline">{{ localData.refactored_invoice.serie_final }}</button>
          <AtomsRedirectButton :id="localData.refactored_invoice.id" :path="'/billing/invoice/'" />
        </div>
      </FieldDetail>
      <FieldDetail :label='$t("billing_block.refactoring")' v-if="localData.refactor_invoice && !reducedDetail">
        <span v-if="isSubRegion">{{ localData.refactor_invoice.serie_final }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('InvoiceRegion', localData.refactor_invoice.id, null)"
            class="text-start text-sky-500 underline">{{ localData.refactor_invoice.serie_final }}</button>
          <AtomsRedirectButton :id="localData.refactor_invoice.id" :path="'/billing/invoice/'" />
        </div>
      </FieldDetail>

      <FieldDetail :label='$t("common.doc")' v-if="localData.invoice_file_template && !reducedDetail">
        <button type="button" @click="openInvoiceFileTemplate"
          class="text-sky-500 underline flex items-center gap-2">
          <Icon name="fa6-solid:file-pdf" />
          {{ $t('common.download') }}
        </button>
      </FieldDetail>
      
      <hr v-if="!reducedDetail" class="my-2 col-span-2" />
      <FieldDetail :label='$t("billing_block.returned_invoice")' v-if="localData.return_invoice && !reducedDetail">
        <span v-if="isSubRegion">{{ localData.return_invoice.serie_final }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('InvoiceRegion', localData.return_invoice.id, null)"
            class="text-start text-sky-500 underline">{{ localData.return_invoice.serie_final }}</button>
          <AtomsRedirectButton :id="localData.return_invoice.id" :path="'/billing/invoice/'" />
        </div>
      </FieldDetail>
      <FieldDetail v-if="localData.return_invoice && !reducedDetail" :label='$t("common.date")'
        :value="localData.suppressed_at ? formatDate(localData.suppressed_at) : '-'"></FieldDetail>
      <FieldDetail v-if="localData.return_invoice && !reducedDetail" :label='$t("order_block.reason")'
        :value="localData.suppression_reason.name"></FieldDetail>
      <FieldDetail v-if="localData.return_invoice && !reducedDetail" :label='$t("billing_block.returned_by")'
        :value="localData.suppressed_by_username"></FieldDetail>
      <hr v-if="!reducedDetail && localData.return_invoice" class="my-2 col-span-2" />
      <span v-if="reducedDetail"></span>

      <FieldDetail v-if="localData.contract_request" :label='$t("contract_block.short_contract_request")'>
        <span v-if="isSubRegion">{{ localData.contract_request.token }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('ContractRequestRegion', localData.contract_request.id, null)"
            class="text-start text-sky-500 underline">{{ localData.contract_request.token }}</button>
          <AtomsRedirectButton :id="localData.contract_request.id" :path="'/contract/contract-requests/'" />
        </div>
      </FieldDetail>
      <FieldDetail v-else-if="localData.connection_request" :label='$t("service_block.short_connection_request")'>
        <span v-if="isSubRegion">{{ localData.connection_request.token }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('ConnectionRequestRegion', localData.connection_request.id, null)"
            class="text-start text-sky-500 underline">{{ localData.connection_request.token }}</button>
          <AtomsRedirectButton :id="localData.connection_request.id" :path="'/service/connection-requests/'" />
        </div>
      </FieldDetail>
      <FieldDetail v-else-if="localData.contract_termination" :label='$t("contract_block.short_contract_termination")'>
        <span v-if="isSubRegion">{{ localData.contract_termination.token }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('ContractTerminationRegion', localData.contract_termination.id, null)"
            class="text-start text-sky-500 underline">{{ localData.contract_termination.token }}</button>
          <AtomsRedirectButton :id="localData.contract_termination.id" :path="'/contract/contract-terminations/'" />
        </div>
      </FieldDetail>
      <FieldDetail v-else-if="localData.contract" :label='$t("contract")'>
        <span v-if="isSubRegion" class="flex items-center gap-1">
          <span>{{ localData.contract.token }}</span>
          <Icon v-if="isFireContract(localData.contract)" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
        </span>
        <div v-else class="flex gap-2 items-center">
          <button @click="showDetail('ContractRegion', localData.contract.id, null)"
            class="text-start text-sky-500 underline flex items-center gap-1">
            <span>{{ localData.contract.token }}</span>
            <Icon v-if="isFireContract(localData.contract)" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
          </button>
          <AtomsRedirectButton :id="localData.contract.id" :path="'/contract/contracts/'" />
        </div>
      </FieldDetail>
      <!-- <FieldDetail v-else :label='$t("contract")' :value="'-'" /> -->
      <FieldDetail v-if="commitmentDeposit && !reducedDetail" :label='$t("commitment_deposit")'>
        <span v-if="isSubRegion">{{ commitmentDeposit.token }}</span>
        <div v-else class="flex gap-2">
          <button @click="showDetail('CommitmentDepositRegion', commitmentDeposit.id, null)"
            class="text-start text-sky-500 underline">{{ commitmentDeposit.token }}</button>
          <AtomsRedirectButton :id="commitmentDeposit.id" :path="'/billing/commitment-deposits/'" />
        </div>
      </FieldDetail>
      <div v-if="isBudget"> </div>
      <FieldDetail v-else :label='$t("common.status")'>
        <AtomsColorBadge :value="localData.status?.name" :color="localData.status?.color"></AtomsColorBadge>
      </FieldDetail>
      <FieldDetail :label='$t("billing_block.general_invoice")'
        v-if="!reducedDetail && localData.general_contracts && localData.general_contracts.length > 0">
        <div class="relative" ref="generalContractsButtonRef">
          <button @click.stop="toggleGeneralContractsDropdown"
            class="text-start text-sky-500 underline hover:text-sky-600 flex-1 text-left">
            <span>{{ $t('contract_block.other_contracts') }}</span>
          </button>

          <div v-if="showGeneralContractsDropdown"
            class="absolute z-10 mt-2 w-full min-w-[250px] max-w-xl bg-white rounded-md shadow-lg border border-slate-200">
            <div class="py-1 max-h-60 overflow-y-auto">
              <div v-for="gn in localData.general_contracts.filter(gn => gn.id !== localData.contract.id)" :key="gn.id"
                class="px-3 py-2 hover:bg-slate-50 border-b border-slate-100 last:border-b-0">
                <span v-if="isSubRegion" class="text-sm text-slate-700 flex items-center gap-1">
                  <span>{{ gn.token }}</span>
                  <Icon v-if="isFireContract(gn)" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
                </span>
                <div v-else class="flex items-center gap-2">
                  <button @click="showDetail('ContractRegion', gn.id, null); showGeneralContractsDropdown = false"
                    class="text-sm text-sky-500 underline hover:text-sky-600 flex-1 text-left flex items-center gap-1">
                    <span>{{ gn.token }}</span>
                    <Icon v-if="isFireContract(gn)" name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
                  </button>
                  <AtomsRedirectButton :id="gn.id" :path="'/contract/contracts/'" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </FieldDetail>
      <FieldDetail v-if="!reducedDetail" :label='$t("common.origin")' :value="localData.origin?.name"></FieldDetail>
      <FieldDetail v-if="!reducedDetail" :label='$t("billingbatch")'>
        <span v-if="localData.billing">{{ localData.billing?.token }}</span>
        <span v-else> - </span>
      </FieldDetail>
      <!--
      <FieldDetail v-if="!reducedDetail" :label='$t("billing_block.reading_batch")'>
        <span v-if="isSubRegion && localData.invoice_batch">{{ localData.invoice_batch.token }}</span>
        <button v-else-if="!isSubRegion && localData.invoice_batch"
          @click="showDetail('InvoiceBatchRegion', localData.invoice_batch.id, null)"
          class="text-start text-sky-500 underline">{{ localData.invoice_batch.token }}</button>
        <span v-else> - </span>
      </FieldDetail>
      -->
      <FieldDetail v-if="localData.reason && !reducedDetail" class="col-span-2"
        :label="isVoidedInvoice(localData) ? $t('billing_block.reason_cancellation') : $t('billing_block.reason_unrecoverable')"
        :value=localData.reason></FieldDetail>

      <hr v-if="!reducedDetail" class="my-2 col-span-2" />
      <FieldDetail :label='$t("contract_block.holder")' :value=localData.customer_final></FieldDetail>
      <FieldDetail :label='$t("common.identification")' :value=localData.customer_token_final></FieldDetail>
      <FieldDetail v-if="!reducedDetail" :label='$t("address_block.address")' :value=localData.address_final>
      </FieldDetail>
      <FieldDetail v-if="!reducedDetail" :label='$t("address_block.location")' :value="localData.location_final">
      </FieldDetail>

      <hr v-if="!reducedDetail" class="my-2 col-span-2" />
      <FieldDetail v-if="!reducedDetail" :label='$t("exploitation")'>
        <span v-if="isSubRegion && localData.exploitation">{{ localData.exploitation.name }}</span>
        <div v-else-if="!isSubRegion && localData.exploitation" class="flex gap-2">
          <button @click="showDetail('ExploitationRegion', localData.exploitation.id, null)"
            class="text-start text-sky-500 underline">{{ localData.exploitation.name }}</button>
          <AtomsRedirectButton :id="localData.exploitation.id" :path="'/service/exploitations/'" />
        </div>
        <span v-else> - </span>
      </FieldDetail>
      <FieldDetail v-if="!reducedDetail" :label='$t("company")'>
        <span v-if="isSubRegion && localData.company">{{ localData.company.alias }}</span>
        <div v-else-if="!isSubRegion && localData.company" class="flex gap-2">
          <button @click="showDetail('CompanyRegion', localData.company.id, null)"
            class="text-start text-sky-500 underline">{{
              localData.company.alias }}</button>
          <AtomsRedirectButton :id="localData.company.id" :path="'/service/companies/'" />
        </div>
        <span v-else> - </span>
      </FieldDetail>
      <div
        v-if="!reducedDetail && localData.accounting_office_final && localData.managing_body_final && localData.processing_unit_final"
        class="col-span-2 grid grid-cols-2 gap-x-3">
        <hr class="my-2 col-span-2" />
        <FieldDetail :label='$t("billing_block.short_accounting_office")' :value=localData.accounting_office_final>
        </FieldDetail>
        <FieldDetail :label='$t("billing_block.short_managing_body")' :value=localData.managing_body_final>
        </FieldDetail>
        <FieldDetail :label='$t("billing_block.short_processing_unit")' :value=localData.processing_unit_final>
        </FieldDetail>
        <FieldDetail v-if="localData.command_final" :label='$t("billing_block.command")' :value=localData.command_final>
        </FieldDetail>
        <FieldDetail v-if="localData.record_final" :label='$t("billing_block.record")' :value=localData.record_final>
        </FieldDetail>
      </div>
      <hr v-if="!reducedDetail" class="my-2 col-span-2" />
      <FieldDetail :label='$t("billing_block.payment")' :value=localData.payment_type_final></FieldDetail>
      <FieldDetail v-if="localData.payment_bank_final" :label='$t("common.iban")'>
        <IBAN :value="localData.payment_bank_final" />
      </FieldDetail>
      <span v-else></span>
      <FieldDetail v-if="localData.payment_bank_final && localData.send_at" :label='$t("common.send_date_expected")' :value=formatDate(localData.send_at)></FieldDetail>
      <FieldDetail :label='$t("common.total")' :value="localData.total_final + ' €'"></FieldDetail>
      <FieldDetail v-if="localData.reject" :label='$t("common.return")' :value="localData.reject.name"></FieldDetail>
    </div>
  </div>
  <div v-else class="p-4">
    <div class="flex justify-center items-center">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>


</template>
