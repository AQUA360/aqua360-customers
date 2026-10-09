<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import ContractStatusBadges from '~/components/molecules/ContractStatusBadges.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

const { t } = useI18n();

const toast = useToast();
const { $ConfigProjectApiService, $InvoiceApiService, $DocumentManagerApiService, $ContractTerminationApiService, $ReadingApiService, $StatusApiService } = useNuxtApp();

const props = defineProps({
  termination: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  reload: {
    type: Boolean,
    default: false
  },
  canChange: {
    type: Boolean,
    default: true
  },
  // Hidden inside the termination wizard, which already has its own finish step
  showQuickFinalize: {
    type: Boolean,
    default: true
  }
});

const { fetchFinalInvoiceTokens, isInvoice, findFinalInvoice } = useFinalInvoiceTokens();
const finalInvoice = ref(null)
const terminationData = ref(null)
const loadingInvoice = ref(null)

const loading_file = ref(false)
const uploadedFile = ref(null)

const invoicePermissions = ref(null);
const ignoreInvoice = ref(false)

const resetIgnoreInvoiceIfFinal = () => {
  if (finalInvoice.value && terminationData.value) {
    ignoreInvoice.value = false
  }
}

const toggleIgnoreInvoice = async () => {
  console.log('toggleIgnoreInvoice')
  console.log(ignoreInvoice.value)
  ignoreInvoice.value = !ignoreInvoice.value
  console.log(ignoreInvoice.value)
  try {
    const save_data = {
      id: props.termination.id,
      ignore_invoice: ignoreInvoice.value
    }
    const response = await $ContractTerminationApiService.save(save_data)
  } catch (error) {
    console.error(error)
  }
}

const previousReadings = ref({});

const loadPreviousReadings = async () => {
  const supplyPoints = terminationData.value?.contract?.supply_points;
  if (!supplyPoints?.length) return;
  for (const sp of supplyPoints) {
    try {
      const response = await $ReadingApiService.getAll('', [], 1, null, false, [], sp.id);
      previousReadings.value[sp.id] = response?.results?.[0] ?? null;
    } catch {
      previousReadings.value[sp.id] = null;
    }
  }
};

const lastReadingsWithInvoice = computed(() => {
  return Object.values(previousReadings.value).filter(r => r?.invoice);
});

const finalizableStatusTokens = ref([]);
const notContractableToken = ref(null);
const finalizing = ref(false);

// The consumption is invoiced when the final invoice exists or every supply point's last reading is invoiced
const consumptionInvoiced = computed(() => {
  if (finalInvoice.value) return true;
  const supplyPoints = terminationData.value?.contract?.supply_points || [];
  return supplyPoints.length > 0 && supplyPoints.every((sp) => previousReadings.value[sp.id]?.invoice);
});

const canQuickFinalize = computed(() => {
  return props.canChange && props.showQuickFinalize && consumptionInvoiced.value
    && !terminationData.value?.connection
    && finalizableStatusTokens.value.includes(terminationData.value?.status?.token);
});

const loadFinalizeConfig = async () => {
  try {
    const [draftToken, pendingToken, notContractable] = await Promise.all([
      $ConfigProjectApiService.get('contract_termination_draft'),
      $ConfigProjectApiService.get('contract_termination_pending_status'),
      $ConfigProjectApiService.get('supply_point_status_not_contractable_token'),
    ]);
    finalizableStatusTokens.value = [draftToken, pendingToken].filter(Boolean);
    notContractableToken.value = notContractable;
  } catch (error) {
    console.error(error);
  }
};

const quickFinalize = async () => {
  if (!confirm(t('confirmation_text_block.confirm_finalize_request'))) return;
  finalizing.value = true;
  try {
    const response = await $StatusApiService.getAll('supply-point-status', 'service');
    const supplyPointStatus = response?.results?.find((s) => s.token === notContractableToken.value);
    if (!supplyPointStatus) {
      toast.error(t('contract_block.unexpected_error'));
      return;
    }
    const closed = await $ContractTerminationApiService.close(props.termination.id, {
      status: supplyPointStatus.id,
      status_name: supplyPointStatus.name,
    });
    if (closed?.id) {
      toast.success(t('common.correct_finish'));
      await fetchData();
      emits('finalized');
    }
  } catch (error) {
    console.error(error);
    toast.error(t('contract_block.unexpected_error'));
  } finally {
    finalizing.value = false;
  }
};

const contractDate = computed(() => {
  const c = terminationData.value?.contract;
  return c?.registration_date || c?.created_at || null;
});

const getData = async () => {
  terminationData.value = props.termination
  finalInvoice.value = findFinalInvoice(terminationData.value.invoices)

  ignoreInvoice.value = terminationData.value.ignore_invoice

  if (terminationData.value.termination_file) {
    try {
      uploadedFile.value = await $DocumentManagerApiService.getDetail(terminationData.value.termination_file);
    } catch (error) {
      console.error(error)
    }
  }
  await loadPreviousReadings();
}

const fetchData = async () => {
  try {
    const result = await $ContractTerminationApiService.getDetail(props.termination.id);
    terminationData.value = result;
    finalInvoice.value = findFinalInvoice(terminationData.value.invoices)
    ignoreInvoice.value = terminationData.value.ignore_invoice
    if (terminationData.value.termination_file) {
      uploadedFile.value = await $DocumentManagerApiService.getDetail(terminationData.value.termination_file);
    }
    await loadPreviousReadings();
  } catch (error) {
    console.error(error);
  }
}

const downloadInvoice = async (invoice) => {
  loadingInvoice.value = invoice.id;
  try {
    if (!invoice.invoice_file) {
      $InvoiceApiService.getTemporaryPDF(invoice.id).then(async (data) => {
        await openAuthenticatedFileUrl(data.url);
        loadingInvoice.value = null;
      }).catch((err) => {
        error.value = err;
        loadingInvoice.value = null;
      });
    } else {
      const file = await $DocumentManagerApiService.viewDocument(invoice.invoice_file);
      const pdfBlob = new Blob([file], { type: 'application/pdf' });
      const blob_file_url = URL.createObjectURL(pdfBlob);
      const newWindow = window.open(blob_file_url, '_blank');

      if (newWindow) {
        setTimeout(() => {
          window.URL.revokeObjectURL(blob_file_url);
        }, 250);
      }

    }
  } catch (error) {
    console.error(error)
  } finally {
    loadingInvoice.value = null;
  }
}

const generateDocument = async () => {
  const contract = await $ContractTerminationApiService.getDocument(props.termination.id);
  await openAuthenticatedFileUrl(contract.pdf_url);
}

const uploadDocument = async (event) => {
  loading_file.value = true
  try {
    var data_file = {
      id: props.termination.id,
      file: event.target.files[0]
    }
    terminationData.value = await $ContractTerminationApiService.save(data_file)
    uploadedFile.value = await $DocumentManagerApiService.getDetail(terminationData.value.termination_file);
    if (uploadedFile.value) {
      toast.success(t("common.doc_correct_upload"))
    }
  } catch (error) {
    console.error(error)
  } finally {
    loading_file.value = false
  }
};

const showDocument = async () => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(terminationData.value.termination_file);
    window.open(file.file_url, '_blank');

  } catch (error) {
    console.error(error)
  }
}

watch(() => props.termination, (newVal) => {
  getData()
}, { immediate: true, deep: true });

watch(() => props.reload, () => {
  fetchData();
});

watch(finalInvoice, () => {
  resetIgnoreInvoiceIfFinal()
});

onMounted(async () => {
  invoicePermissions.value = await checkPermission($InvoiceApiService);
  await fetchFinalInvoiceTokens();
  loadFinalizeConfig();
  getData()
});

const emits = defineEmits(['show-subregion', 'finalized']);

const showDetail = function (component, id) {
  emits('show-subregion', component, id);
}

</script>

<template>
  <div>
    <div v-if="terminationData" id="item_data">
      <div v-if="canChange"
        class="bg-blue-50 border border-blue-500 text-blue-700 px-4 py-2 rounded-md relative mb-4 flex items-center gap-3"
        role="alert">
        <Icon name="fa6-solid:circle-info" class="text-xl" />
        <span class="block sm:inline text-sm font-semibold">{{
          t('informative_block.info_meter_deactivation_no_contracts')
          }}</span>
      </div>
      <fieldset id="solicitant__box" v-if="terminationData.person" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ t("common.request") }}</legend>
        <div class=" grid grid-cols-2 gap-4">
          <FieldDetail :label="t('common.requester')" :value="terminationData.person?.full_name || ''"></FieldDetail>
          <FieldDetail :label="t('common.identification')" :value="terminationData.person?.token || ''"></FieldDetail>
          <FieldDetail :label="t('common.date')"
            :value="terminationData.created_at ? formatDate(terminationData.created_at) : '-'"></FieldDetail>
          <FieldDetail :label="t('order_block.reason')" :value="terminationData.type?.name || ''"></FieldDetail>
          <FieldDetail v-if="terminationData.approved_at" :label="t('common.approval_date')"
            :value="formatDate(terminationData.approved_at)"></FieldDetail>
        </div>
      </fieldset>

      <fieldset id="contract__box" v-if="terminationData.contract && typeof terminationData.contract === 'object'"
        class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ t('contract') }}</legend>
        <div class="grid grid-cols-2 gap-x-4">
          <FieldDetail :label="t('common.identification')" :value="terminationData.contract.token || ''">
            <button v-if="!isSubRegion && terminationData.contract.id" type="button"
              class="group inline-flex items-center gap-1 text-sky-500 hover:text-sky-900 text-left"
              @click="showDetail('ContractRegion', terminationData.contract.id)">
              <span>{{ terminationData.contract.token }}</span>
              <Icon name="fa6-solid:eye" class="text-slate-500 opacity-70 group-hover:opacity-100 transition-opacity" />
            </button>
            <span v-else>{{ terminationData.contract.token }}</span>
          </FieldDetail>
          <FieldDetail :label="t('common.registration_date')"
            :value="contractDate ? formatDate(contractDate) : '-'" />
          <FieldDetail :label="t('contract_block.holder')" :value="terminationData.contract.holder?.full_name || ''">
            <AtomsPersonBadge v-if="terminationData.contract.holder" :person="terminationData.contract.holder" />
          </FieldDetail>
          <FieldDetail :label="t('common.short_supply')"
            :value="terminationData.contract.supply_point_default?.address_complete || ''">
            <button v-if="!isSubRegion && terminationData.contract.supply_point_default?.id" type="button"
              class="group inline-flex items-center gap-1 text-sky-500 hover:text-sky-900 text-left"
              @click="showDetail('SupplyPointRegion', terminationData.contract.supply_point_default.id)">
              <span>{{ terminationData.contract.supply_point_default.address_complete }}</span>
              <Icon name="fa6-solid:eye" class="text-slate-500 opacity-70 group-hover:opacity-100 transition-opacity" />
            </button>
            <span v-else>{{ terminationData.contract.supply_point_default?.address_complete }}</span>
          </FieldDetail>
        </div>
        <ContractStatusBadges class="mt-2" :contract="terminationData.contract" :isSubRegion="isSubRegion"
          :showExtra="false" @show-detail="showDetail" />
      </fieldset>

      <fieldset id="contract__box" v-if="terminationData.contract && typeof terminationData.contract === 'object'"
        class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ t('common.documentation') }}</legend>
        <div v-if="canChange" class="flex gap-4">
          <button class="button-default" @click="generateDocument">
            <Icon name="fa6-solid:file-pdf" class="mr-2" />
            {{ t('common.generate') }} {{ t('common.doc') }}
          </button>
          <button v-if="uploadedFile && !loading_file" class="button-default" @click="$refs.file.click()">
            <Icon v-show="uploadedFile" name="fa6-solid:arrow-right-arrow-left" class="text-slate-500 mr-1" />
            {{ t('common.change') }}
          </button>
          <button v-else-if="loading_file" class="button-default" :disabled="true">
            <Icon name="fa-solid:spinner" class="text-slate-500 mr-1 animate-spin" />
            {{ t('common.uploading') }}...
          </button>
          <button v-else class="button-default" @click="$refs.file.click()">
            <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
            {{ t('common.upload_doc') }}
          </button>
          <input type="file" @change="uploadDocument" ref="file" style="display: none" />
          <button v-if="uploadedFile && !loading_file" class="button-default" @click="showDocument">
            <Icon v-show="uploadedFile" name="fa6-regular:file-pdf" class="text-slate-500 mr-1" />
            {{ t('common.show') }} {{ t('common.doc') }}
          </button>
        </div>
        <div v-else>
          <button v-if="uploadedFile && !loading_file" class="button-default" @click="showDocument">
            <Icon v-show="uploadedFile" name="fa6-regular:file-pdf" class="text-slate-500 mr-1" />
            {{ t('common.show') }} {{ t('common.doc') }}
          </button>
          <div v-else>
            {{ t('common.no_doc') }}
          </div>
        </div>
      </fieldset>



      <fieldset id="contract__box" v-if="terminationData.contract && typeof terminationData.contract === 'object'"
        class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ t('billing_block.final_invoice') }}</legend>
        <div v-if="lastReadingsWithInvoice.length > 0" class="mb-3 flex items-start gap-2 text-sm font-semibold text-amber-700 bg-amber-50 border border-amber-300 rounded px-3 py-2">
          <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500 mt-0.5 shrink-0" />
          <div>
            <span>{{ t('billing_block.last_reading_already_invoiced') || 'La última lectura ja està facturada' }}</span>
            <span v-for="r in lastReadingsWithInvoice" :key="r.supply_point" class="ml-1 font-normal text-amber-600">
              ({{ r.invoice?.serie_final }})
            </span>
          </div>
        </div>
        <div v-if="canChange && invoicePermissions?.can_change" class="flex items-center mb-2">
          <input type="checkbox" id="ignore_invoice" class="checkbox" :checked="ignoreInvoice"
            :disabled="!!finalInvoice" @change="toggleIgnoreInvoice"/>
          <label for="ignore_invoice" class="ml-2 text-slate-500">
            {{ t('contract_block.termination_without_invoice') }}
          </label>
        </div>
        <div v-if="canChange && invoicePermissions?.can_change">
          <ButtonOutline class="my-2" :disabled="ignoreInvoice"
            @click="showDetail('AddInvoiceContract', null)">
            <span v-if="terminationData.invoices.length == 0">
              {{ t('common.generate') }} {{ t('common.budget_detail') }}
            </span>
            <span v-else-if="terminationData.invoices.length > 0 && !finalInvoice">
              {{ t('common.show') }} {{ t('common.budget_detail') }}
            </span>
            <span v-else>
              {{ t('common.show') }} {{ t('invoice') }}
            </span>
          </ButtonOutline>
        </div>
        <div v-if="!ignoreInvoice" class="py-1 px-3 text-sm rounded-md border w-fit mb-5" :class="{
          'bg-green-50 text-green-600 border-green-600': finalInvoice,
          'bg-orange-50 text-orange-600 border-orange-600': !finalInvoice,
        }">
          <span v-if="terminationData.invoices.length == 0">
            {{ $t('billing_block.budget_invoice_not_generated') }}
          </span>
          <span v-else-if="terminationData.invoices.length > 0 && !finalInvoice">
            {{ $t('billing_block.budget_invoice_generated') }}
          </span>
          <span v-else>
            {{ $t('billing_block.generated_invoice') }}
          </span>
        </div>
        <div v-for="invoice in terminationData.invoices" :key="invoice.id" class="flex items-center gap-4 ">
          <AtomsFieldDetail :label="finalInvoice?.id == invoice.id ? t('billing_block.final_invoice') :
            isInvoice(invoice) ? t('invoice') : t('common.budget_detail')"
            :value="invoice.serie_final" />
          <AtomsColorBadge v-if="invoice.status_name" :value="invoice.status_name" :color="invoice.status_color" />
          <div class="flex items-center gap-2">
            <button @click="showDetail('InvoiceView', invoice.id)"
              class="rounded-full w-6 h-6 border border-orange-500 bg-white mb-2 hover:bg-orange-100 flex items-center"
              :title="`${t('common.check')} ${t('invoice')}`">
              <Icon name="fa6-solid:eye" class="text-orange-500 m-auto" />
            </button>
            <button @click="downloadInvoice(invoice)"
              class="rounded-full w-6 h-6 border border-orange-500 bg-white mb-2 hover:bg-orange-100 flex items-center"
              :title="`${t('common.download')} ${t('invoice')} `">
              <Icon :name="loadingInvoice == invoice.id ? 'fa6-solid:spinner' : 'fa6-solid:download'"
                class="text-orange-500 m-auto" :class="{ 'animate-spin': loadingInvoice == invoice.id }" />
            </button>
          </div>
        </div>
        <button v-if="canQuickFinalize" type="button" :disabled="finalizing" @click="quickFinalize"
          class="mt-3 px-4 py-2 bg-green-500 text-white rounded font-bold enabled:hover:bg-green-600 disabled:opacity-50">
          <Icon :name="finalizing ? 'fa6-solid:spinner' : 'fa6-solid:circle-check'"
            :class="{ 'animate-spin': finalizing }" />&nbsp;
          {{ t('contract_block.finalize_termination') }}
        </button>
      </fieldset>

    </div><!-- end if data -->
  </div><!-- end if pending -->
</template>
