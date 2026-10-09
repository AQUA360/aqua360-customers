<script setup>
// components/molecules/ContractRequestOrderBilling.vue
import { ref, onMounted, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import AddClauseTemplate from '~/components/molecules/AddClauseTemplate.vue'; // Assegura't que aquest component està importat
import ClauseDetail from '~/components/molecules/ClauseDetail.vue';
import ContractRequestDetail from '~/components/molecules/ContractRequestDetail.vue';
import { formatMoneyWithCurrency } from '~/utils/money';
import OrderTypeDetail from '~/components/molecules/OrderTypeDetail.vue';
import AddInvoiceBudget from './AddInvoiceBudget.vue';
import InvoiceView from '~/components/organisms/InvoiceView.vue';
import OrderRegion from '~/components/organisms/OrderRegion.vue';
import { checkPermission } from '~/middleware/permission';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import { useConfigStore } from '~/stores/useConfigStore';
import { storeToRefs } from 'pinia';

const { $ContractClausesApiService, $PersonApiService, $ContractApiService, $ContractRequestApiService, $DocumentManagerApiService, $ConfigProjectApiService, $InvoiceApiService, $ContractTerminationApiService } = useNuxtApp();
const { t } = useI18n();

const configStore = useConfigStore();
const { documentSignEnabled } = storeToRefs(configStore);
configStore.fetchDocumentSignEnabled();

const props = defineProps({
  request: {
    type: Object,
    required: false
  }
});

const emit = defineEmits(['change', 'show-subregion']);

const showRegion = ref(false);
const showRegionComponent = ref(null);
const showRegionDetailId = ref(null);
const isSubRegionOpen = ref(false);

const loading_holder = ref(false);
const loadingInvoice = ref(null);
const loading_file = ref(false);
const uploadedFile = ref(null);
const fileDetail = ref(null);

const termination_contract = ref(null);
const clauses = ref([]);

const holder = ref(null);
const invoices = ref([])
const terminationInvoices = ref({});
const finalInvoice = ref(null)
const { fetchFinalInvoiceTokens, isInvoice, findFinalInvoice } = useFinalInvoiceTokens();

const invoicePermissions = ref(null);
const billCutReading = ref(false);

// Policy number (token) regeneration flow
const policyToken = ref(null);
const candidateToken = ref(null);
const regeneratingToken = ref(false);
const savingToken = ref(false);

/**
 * Id del contracte real associat, per firma OTP (DocumentSign.contract). Si la sol·licitud
 * encara no té contracte (alta abans de finalitzar), s'usa `signContractRequestId` com a
 * fallback (backend accepta `contract_request_id`).
 */
const signContractId = computed(() => props.request?.contract?.id || props.request?.contract || null);
const signContractRequestId = computed(() => (signContractId.value ? null : props.request?.id || null));

const signOtpDefaultName = computed(() => {
  if (!holder.value) return '';
  return holder.value.full_name || [holder.value.name, holder.value.surname].filter(Boolean).join(' ') || '';
});

const signOtpDefaultEmail = computed(() => {
  const digitalContact = props.request?.person_contact_email;
  if (digitalContact?.email) return digitalContact.email;
  const contactWithEmail = (props.request?.contacts || []).find(c => c.email);
  return contactWithEmail?.email || holder.value?.email || '';
});

const signOtpDefaultPhone = computed(() => {
  const contactWithPhone = (props.request?.contacts || []).find(c => c.phone);
  return contactWithPhone?.phone || holder.value?.phone || '';
});

const getInvoicePermissions = async () => {
  const data = await checkPermission($InvoiceApiService);
  invoicePermissions.value = data;
}

const openAddClauseTemplate = () => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddClauseTemplate';
};

const openInvoiceContract = () => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddInvoiceContract';
};

const openInvoiceTermination = (terminationId) => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddInvoiceTermination';
  showRegionDetailId.value = terminationId;
};

const toggleRegion = (value) => {
  showRegion.value = value;
  if (!value) {
    closeAllRegions();
    showRegionComponent.value = null;
  }
};

const closeAllRegions = () => {
  showRegionComponent.value = null;
  showRegionDetailId.value = null;
  showRegion.value = false;
  isSubRegionOpen.value = false;
};

const emitChange = () => {
  let data = {
    contract_file: uploadedFile.value
  };
  emit('change', data);
};


const loadData = async () => {

  if (props.request) {
    // Assigna les dades del request si estan disponibles
    policyToken.value = props.request.token || null;
    clauses.value = props.request.clauses || [];
    uploadedFile.value = null;
    if (props.request.contract_file) {
      uploadedFile.value = await $DocumentManagerApiService.viewDocument(props.request.contract_file.id);
      fileDetail.value = await $DocumentManagerApiService.getDetail(props.request.contract_file.id);
    }

    // agafem el contracte del termination si existeix
    /* if (props.request.contract_termination_request && props.request.contract_termination_request.id) {
      termination_contract.value = await $ContractApiService.getDetail(props.request.contract_termination_request.contract.id);
    } */
    await fetchInvoiceData()
  }
  loading_holder.value = true;
  holder.value = await $PersonApiService.getFullDetail(props.request.holder);
  loading_holder.value = false;
};

const fetchInvoiceData = async () => {
  try {
    const result = await $ContractRequestApiService.getDetail(props.request.id);
    const allInvoices = result.results?.invoices || result.invoices || [];
    
    // Filtrem les de l'Alta (contract_request)
    invoices.value = allInvoices.filter(inv => inv.entity === 'contract_request' || !inv.entity);
    
    // Filtrem i agrupem les de la Baixa (contract_termination_request) per object_id
    const tInvoices = {};
    allInvoices.filter(inv => inv.entity === 'contract_termination_request').forEach(inv => {
      if (!tInvoices[inv.object_id]) tInvoices[inv.object_id] = [];
      tInvoices[inv.object_id].push(inv);
    });

    // Fem fetch explícit per a cada termination request per assegurar-nos que tenim les factures
    const terminations = result.contract_termination_requests || props.request.contract_termination_requests || [];
    for (const tr of terminations) {
      try {
        const trDetail = await $ContractTerminationApiService.getDetail(tr.id);
        if (trDetail.invoices && trDetail.invoices.length > 0) {
          // Unifiquem (evitem duplicats si el back ja les enviava)
          const existingIds = (tInvoices[tr.id] || []).map(i => i.id);
          trDetail.invoices.forEach(inv => {
            if (!existingIds.includes(inv.id)) {
              if (!tInvoices[tr.id]) tInvoices[tr.id] = [];
              tInvoices[tr.id].push(inv);
            }
          });
        }
      } catch (err) {
        console.error("Error fetching termination invoices", tr.id, err);
      }
    }
    terminationInvoices.value = tInvoices;

    if (invoices.value.length > 0) {
      await fetchFinalInvoiceTokens();
      finalInvoice.value = findFinalInvoice(invoices.value)
    }
  } catch (error) {
    console.error(error);
  }
}


onMounted(async () => {
  await getInvoicePermissions();
  loadData();
});

// Observa canvis en la sol·licitud per recarregar les dades si cal
watch(() => props.request, (newVal) => {
  if (newVal) {
    billCutReading.value = newVal.bill_cut_reading || false;
    loadData();
  }
}, { immediate: true, deep: true });

watch(billCutReading, async (newVal, oldVal) => {
  if (props.request?.id && newVal !== props.request.bill_cut_reading) {
    try {
      await $ContractRequestApiService.patch({
        id: props.request.id,
        bill_cut_reading: newVal
      });

      if (newVal === false && oldVal === true) {
        // L'usuari ha deshabilitat l'opció. Eliminem factures de tancament generades.
        const hasInvoices = Object.values(terminationInvoices.value).some(list => list.length > 0);
        if (hasInvoices && confirm(t('confirmation_text_block.confirm_delete_bill_cut_invoices') || 'Es deshabilitarà la lectura de tall i s\'eliminaran els pressupostos/factures associats. Vols continuar?')) {
          for (const tid in terminationInvoices.value) {
            for (const invoice of terminationInvoices.value[tid]) {
              try {
                await $InvoiceApiService.deleteInvoiceBudget(invoice.id);
              } catch (err) {
                console.error("Error deleting invoice", invoice.id, err);
              }
            }
          }
          await fetchInvoiceData();
        } else if (hasInvoices) {
          // Si no confirma, revertim el canvi local i el del back
          billCutReading.value = true;
          await $ContractRequestApiService.patch({
            id: props.request.id,
            bill_cut_reading: true
          });
        }
      }
    } catch (e) {
      console.error("Error saving bill_cut_reading", e);
    }
  }
});

const generateContract = async () => {
  const contract = await $ContractApiService.getDocument(props.request.id);
  await openAuthenticatedFileUrl(contract.pdf_url);
}

const onClauseTemplateSelected = async (clauseTemplate) => {
  var clause_save = {
    token: clauseTemplate.token,
    title: clauseTemplate.title,
    clause: clauseTemplate.clause,
    template: clauseTemplate.id,
    contract_request: props.request.id
  };

  var clause_response = await $ContractClausesApiService.save(clause_save);
  clauses.value.push(clause_response);

  toggleRegion(false);
  emitChange();
};

const deleteClause = async (clause) => {
  clauses.value = clauses.value.filter((item) => item.id !== clause.id);
  await $ContractClausesApiService.doDelete(clause)
  emitChange();
};

const inputContract = async (event) => {
  loading_file.value = true
  var data_file = {
    id: props.request.id,
    file: event.target.files[0]
  }
  let item_saved = await $ContractRequestApiService.save(data_file)
  uploadedFile.value = await $DocumentManagerApiService.viewDocument(item_saved.contract_file.id);
  fileDetail.value = await $DocumentManagerApiService.getDetail(item_saved.contract_file.id);
  emitChange();
  loading_file.value = false
  successDocMessage()
};

const successDocMessage = () => {
  const toast = useToast();
  toast.success(t("common.doc_correct_upload"), {
    position: "top-right",
    timeout: 5000,
    closeOnClick: true,
    pauseOnFocusLoss: false,
    pauseOnHover: true,
    draggable: true,
    draggablePercent: 0.6,
    showCloseButtonOnHover: false,
    hideProgressBar: false,
    closeButton: 'button',
    icon: true,
    rtl: false,
  });
}

const showDetail = (component, id) => {
  showRegion.value = true;
  showRegionComponent.value = component;
  showRegionDetailId.value = id;
}

const closeInvoiceData = async (close = true) => {
  if (close) closeAllRegions();
  await emitChange()
  //await loadData();
  await fetchInvoiceData()
}

const showContract = async () => {
  try {
    const pdfBlob = new Blob([uploadedFile.value], { type: 'application/pdf' });

    const blob_file_url = URL.createObjectURL(pdfBlob);
    const newWindow = window.open(blob_file_url, '_blank');

    if (newWindow) {
      setTimeout(() => {
        window.URL.revokeObjectURL(blob_file_url);
      }, 250);
    }

  } catch (error) {
    console.log(error)
  }
}

const printContract = async () => {
  try {
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(uploadedFile.value);
    link.href = file_url
    link.download = fileDetail.value.document_name;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.log(error)
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
    console.log(error)
  } finally {
    loadingInvoice.value = null;
  }

}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const regeneratePolicyToken = async () => {
  regeneratingToken.value = true;
  try {
    const response = await $ContractRequestApiService.regenerateToken(props.request.id);
    candidateToken.value = response?.token || null;
  } catch (error) {
    console.error(error);
    const toast = useToast();
    toast.error(t('common.error'));
  } finally {
    regeneratingToken.value = false;
  }
}

const acceptPolicyToken = async () => {
  if (!candidateToken.value) return;
  savingToken.value = true;
  try {
    await $ContractRequestApiService.patch({ id: props.request.id, token: candidateToken.value });
    policyToken.value = candidateToken.value;
    candidateToken.value = null;
    const toast = useToast();
    toast.success(t('common.correct_save'));
    emit('change', {});
  } catch (error) {
    console.error(error);
    const toast = useToast();
    toast.error(t('common.error'));
  } finally {
    savingToken.value = false;
  }
}

const denyPolicyToken = () => {
  candidateToken.value = null;
}

</script>

<template>
  <div id="wrapper" class="text-base">
    <!-- Títol del Component -->
    <h2 class="text-xl font-semibold mb-4">{{ $t('common.summary') }} {{ t('common.and') }} {{ t('contract') }}</h2>
    <!-- /end Títol del Component -->


    <div class="grid grid-cols-2 gap-3">
      <div class="" role="columna1">
        <!-- Detall de request -->
        <div>
          <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon name="fa6-solid:asterisk" class="text-lg text-slate-600" />
            <span>{{ $t('common.summary') }}:</span>
          </label>

          <div class="ml-3 max-w-xl">
            <ContractRequestDetail :id="request.id" :request="request" :isSubRegion="true" :showContractSection="false"
              :showInvoiceSection="false" />
          </div>
          <fieldset v-if="request?.orders?.length > 0" id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50 ml-3 max-w-xl">
            <legend class="px-3 font-semibold bg-white shadow">{{ $t('work_orders') }}</legend>
            <div v-for="order in request.orders" :key="order.id" class="flex items-center gap-3">
              <MoleculesOrderTypeDetail :data="order.type" :order="order" :id="order.type.id" />
            </div>
          </fieldset>
        </div>
        <!-- /end Detall de request -->
      </div>

      <div role="columna2">
        <div v-if="request.contract_termination_requests && request.contract_termination_requests.length > 0" class="">
          <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon name="fa6-solid:asterisk" class="text-lg text-slate-600" />
            <span>{{ $t('common.contract_termination_detail') }}:</span>
          </label>
          <div v-for="termination_request in request.contract_termination_requests" :key="termination_request.id">

            <fieldset class="mb-3 border px-3 py-2 bg-gray-50 w-full rounded m-3 max-w-xl">
              <div class="grid grid-cols-2 gap-3">
                <AtomsFieldDetail :label="t('contract_block.holder')"
                  :value="termination_request.contract.holder_full_name" />
                <AtomsFieldDetail :label="t('contract_termination')" :value="termination_request.contract.token">
                  <strong>{{ termination_request.contract.token }}</strong>
                </AtomsFieldDetail>
              </div>

              <div class="grid grid-cols-2 gap-3">
                <AtomsFieldDetail v-if="termination_request.type.name" :label="t('order_block.reason')"
                  :value="termination_request.type.name" />
              </div>

              <template v-if="termination_request.readings">
                <hr class="my-2" />
                <div v-for="reading in termination_request.readings" :key="reading.id" class="grid grid-cols-2 gap-3">
                  <AtomsFieldDetail :label="t('reading')" :value="reading.reading_value" />
                  <AtomsFieldDetail :label="t('billing_block.reading_date')"
                    :value="formatDate(reading.reading_date)" />
                </div><!-- end for readings -->
              </template>

              <div v-if="termination_request.orders">
                <AtomsFieldDetail v-for="order in termination_request.orders" :label="t('work_orders')" :value="null">
                  <OrderTypeDetail :data="order.type" :order="order"
                    @show-detail="showDetail('OrderRegion', order.id)" />
                </AtomsFieldDetail>
              </div>

            </fieldset>

            <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded m-3 max-w-xl">
              <legend class="px-3 font-semibold bg-white shadow flex items-center gap-2">
                <Icon name="fa6-solid:faucet-drip" class="text-sky-600" />
                {{ t('common.water_consumption') }} ({{ t('common.termination') }})
                <span v-if="billCutReading"
                  class="ml-2 text-[10px] font-normal text-sky-600 bg-sky-50 px-2 py-0.5 rounded-full border border-sky-200 uppercase tracking-wider">
                  {{ t('common.billing_to_applicant') }}
                </span>
              </legend>

              <div class="flex items-center gap-4 mb-4">
                <div class="flex items-center gap-2">
                  <label class="text-sm font-medium text-gray-700 whitespace-nowrap">
                    {{ $t('common.bill_cut_reading') }}:
                  </label>
                  <button type="button" @click="billCutReading = !billCutReading"
                    class="relative inline-flex h-6 w-11 items-center rounded-full focus:outline-none"
                    :class="billCutReading ? 'bg-sky-500' : 'bg-gray-300'" role="switch" :aria-checked="billCutReading">
                    <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                      :class="billCutReading ? 'translate-x-6' : 'translate-x-1'" />
                  </button>
                </div>
              </div>

              <div v-if="billCutReading">
                <div class="bg-sky-50 border-l-4 border-sky-400 p-3 ml-3 mb-4 rounded-r shadow-sm">
                  <div class="flex items-center">
                    <Icon name="fa6-solid:circle-info" class="text-sky-500 mr-3 text-lg" />
                    <p class="text-sm text-sky-800">
                      {{ $t('informative_block.info_bill_cut_reading_to_applicant') }}
                      <span class="font-bold underline decoration-sky-300 decoration-2 underline-offset-2">
                        {{ holder?.full_name || holder?.name || $t('common.requester') }}
                      </span>
                    </p>
                  </div>
                </div>
                <div class="ml-3 mb-4">
                  <button v-if="invoicePermissions?.can_change" class="button-default"
                    @click="openInvoiceTermination(termination_request.id)">
                    <Icon name="fa6-solid:file-pdf" class="mr-2" />
                    <span>
                      {{ $t('common.modify') }} {{ t('common.budget_detail') }}/{{ t('invoice') }}
                    </span>
                  </button>
                </div>

                <div v-if="terminationInvoices[termination_request.id]" class="ml-3">
                  <div v-for="invoice in terminationInvoices[termination_request.id]" :key="invoice.id"
                    class="flex items-center gap-4 mb-2">
                    <AtomsFieldDetail :label="isInvoice(invoice) ? t('invoice') : t('common.budget_detail')"
                      :value="invoice.serie_final" />
                    <AtomsColorBadge v-if="invoice.status_name" :value="invoice.status_name" :color="invoice.status_color" />
                    <div class="flex items-center gap-2">
                      <button @click="showDetail('InvoiceView', invoice.id)"
                        class="rounded-full w-6 h-6 border border-orange-500 bg-white hover:bg-orange-100 flex items-center"
                        :title="`${t('common.show')} ${t('invoice')}`">
                        <Icon name="fa6-solid:eye" class="text-orange-500 m-auto" />
                      </button>
                      <button @click="downloadInvoice(invoice)"
                        class="rounded-full w-6 h-6 border border-orange-500 bg-white hover:bg-orange-100 flex items-center"
                        :title="`${t('common.download')} ${t('invoice')}`">
                        <Icon name="fa6-solid:download" class="text-orange-500 m-auto" />
                      </button>
                    </div>
                  </div>
                  <div v-if="terminationInvoices[termination_request.id].length == 0" class="text-slate-500 italic text-sm">
                    {{ $t('billing_block.budget_invoice_not_generated') }}
                  </div>
                </div>
              </div>
              <div v-else class="ml-3">
                <div class="text-slate-500 italic text-sm mb-2">
                  {{ t('informative_block.info_no_bill_cut_reading') }}
                </div>
                <div class="bg-amber-50 border-l-4 border-amber-400 p-3 rounded-r shadow-sm flex items-center">
                  <Icon name="fa6-solid:circle-info" class="text-amber-500 mr-3 text-lg" />
                  <p class="text-sm text-amber-800">
                    {{ t('informative_block.info_bill_cut_reading_to_termination_holder') }}
                  </p>
                </div>
              </div>
            </fieldset>
          </div>
        </div>
        <!-- Clàusules -->
        <div>
          <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon name="fa6-solid:asterisk" class="text-lg text-slate-600" />
            <span>{{ $t('contract') }}:</span>
          </label>


          <div class="flex items-center gap-3 pl-3">
            <button name="" class="button-default-xs" @click="openAddClauseTemplate">
              <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
              {{ $t('common.add') }} {{ t('contract_block.clause') }}
            </button>
          </div>

          <ul class="pl-3 mt-3">
            <li v-for="clause in clauses" :key="clause.token"
              class="flex items-center justify-between max-w-xl bg-green-100 py-1 px-2 mb-2">
              <ClauseDetail :item="clause" />
              <button @click="deleteClause(clause)" class="text-slate-500 ml-2">
                <Icon name="fa6-solid:trash" />
              </button>
            </li>
          </ul>
        </div>
        <!-- /end Contracte i Clàusules -->

        <!-- Contracte document -->
        <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded m-3 max-w-xl">
          <legend class="px-3 font-semibold bg-white shadow">{{ $t('common.doc') }}</legend>

          <div class="my-3">
            <div class="mb-2">
              <button class="button-default-xs" @click="regeneratePolicyToken" :disabled="regeneratingToken">
                <Icon :name="regeneratingToken ? 'fa6-solid:spinner' : 'fa6-solid:rotate'"
                  class="text-slate-500 mr-1" :class="{ 'animate-spin': regeneratingToken }" />
                {{ t('common.regenerate') }} {{ t('contract_block.contract_code') }}
              </button>
            </div>

            <div v-if="candidateToken"
              class="mb-3 flex items-center gap-3 max-w-xl border border-amber-300 bg-amber-50 rounded p-2">
              <div class="flex-1">
                <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('contract_block.contract_code') }}</p>
                <p class="font-semibold text-slate-800">{{ candidateToken }}</p>
              </div>
              <button @click="acceptPolicyToken" :disabled="savingToken"
                class="rounded-full w-7 h-7 border border-emerald-500 bg-white hover:bg-emerald-100 flex items-center disabled:opacity-50"
                :title="t('common.accept')">
                <Icon :name="savingToken ? 'fa6-solid:spinner' : 'fa6-solid:check'" class="text-emerald-600 m-auto"
                  :class="{ 'animate-spin': savingToken }" />
              </button>
              <button @click="denyPolicyToken" :disabled="savingToken"
                class="rounded-full w-7 h-7 border border-red-500 bg-white hover:bg-red-100 flex items-center disabled:opacity-50"
                :title="t('common.deny')">
                <Icon name="fa6-solid:xmark" class="text-red-600 m-auto" />
              </button>
            </div>

            <AtomsFieldDetail :label="t('contract_block.contract_code')"
              :value="policyToken || new Date().toISOString().replace(/\D/g, '').slice(0, 14)" />
          </div>

          <div class="flex gap-3">
            <button class="button-default" @click="generateContract">
              <Icon name="fa6-solid:file-pdf" class="mr-2" />
              {{ $t('common.generate') }} {{ t('contract') }}
            </button>

            <!-- imprimir contracte -->
            <button class="button-default">
              <Icon name="fa6-solid:print" class="mr-2" />
              {{ $t('common.print') }}
            </button>

            <!--  <button @click="inputContract()" class="button-default">
            <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
            {{ $t('Afegir') }}
             </button>-->

          </div>

          <div v-if="documentSignEnabled" class="my-3">
            <MoleculesDocumentSignStatus :contractId="signContractId" :contractRequestId="signContractRequestId"
              :contractFileId="fileDetail?.id" :defaultName="signOtpDefaultName" :defaultEmail="signOtpDefaultEmail"
              :defaultPhone="signOtpDefaultPhone" />
          </div>

          <div class="my-3">
            <AtomsFieldDetail :label="t('common.doc_signed') + ':'" />
          </div>

          <div v-if="!loading_file" class="flex gap-3">


            <input type="file" @change="inputContract" ref="file" style="display: none" />
            <button v-if="!uploadedFile && !loading_file" @click="$refs.file.click()" class="button-default">
              <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
              {{ $t('common.add') }}
            </button>
            <button v-else-if="loading_file" class="button-default" :disabled="true">
              <Icon name="fa-solid:spinner" class="text-slate-500 mr-1 animate-spin" />
              {{ t('common.uploading') }}...
            </button>
            <button v-else @click="$refs.file.click()" class="button-default">
              <Icon v-show="uploadedFile" name="fa6-solid:arrow-right-arrow-left" class="text-slate-500 mr-1" />
              {{ $t('common.change') }}
            </button>
            <button v-if="uploadedFile && !loading_file" @click="showContract" class="button-default">
              <Icon v-show="uploadedFile" name="fa6-regular:file-pdf" class="text-slate-500 mr-1" />
              {{ $t('common.show') }} {{ t('common.doc') }}
            </button>
            <button v-if="uploadedFile && !loading_file" @click="printContract" class="button-default">
              <Icon v-show="uploadedFile" name="fa6-solid:download" class="text-slate-500 mr-1" />
              {{ $t('common.download') }} {{ t('common.doc') }}
            </button>

          </div>
          <div v-else class="flex gap-3">
            <div class="flex gap-3 mx-auto p-1">
              <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
              {{ $t('common.loading') }}...
            </div>

          </div>

        </fieldset>



        <!-- Factura -->
        <div>
          <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="invoices?.length == 0" name="fa6-solid:asterisk" class="text-lg text-slate-600" />
            <Icon v-show="invoices?.length > 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <span>{{ $t('common.contract_fees') }}:</span>
          </label>

          <div class="ml-3">
            <button v-if="invoicePermissions?.can_change" class="button-default" @click="openInvoiceContract">
              <Icon name="fa6-solid:file-pdf" class="mr-2" />
              <span>
                {{ $t('common.modify') }} {{ t('common.budget_detail') }}/{{ t('invoice') }}
              </span>
            </button>
          </div>

          <div class="ml-3 mt-4">
            <div v-for="invoice in invoices" :key="invoice.id" class="flex items-center gap-4">
              <AtomsFieldDetail
                :label="finalInvoice?.id == invoice.id ? t('billing_block.final_invoice') :
                  isInvoice(invoice) ? t('invoice') : t('common.budget_detail')"
                :value="invoice.serie_final" />
              <AtomsColorBadge v-if="invoice.status_name" :value="invoice.status_name" :color="invoice.status_color" />
              <div class="flex items-center gap-2">
                <button @click="showDetail('InvoiceView', invoice.id)" :disabled="loading_holder"
                  class="rounded-full w-6 h-6 border border-orange-500 bg-white mb-2 hover:bg-orange-100 flex items-center"
                  :title="`${t('common.show')} ${t('invoice')}`">
                  <Icon :name="loading_holder ? 'fa6-solid:spinner' : 'fa6-solid:eye'" class="text-orange-500 m-auto"
                    :class="{ 'animate-spin': loading_holder }" />
                </button>
                <button @click="downloadInvoice(invoice)"
                  class="rounded-full w-6 h-6 border border-orange-500 bg-white mb-2 hover:bg-orange-100 flex items-center"
                  :title="`${t('common.download')} ${t('invoice')}`">
                  <Icon name="fa6-solid:download" class="text-orange-500 m-auto" />
                </button>
              </div>
            </div>
            <div v-if="invoices.length == 0" class="text-slate-500 italic">
              {{ $t('billing_block.budget_invoice_not_generated') }}
            </div>
          </div>

        </div>
        <!-- /end Contracte i Clàusules -->
      </div>
    </div><!-- end grid -->
  </div>

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-[100]"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)"
        class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded" aria-label="Tancar formulari">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <!-- Components per afegir informació -->
      <AddClauseTemplate v-if="showRegionComponent == 'AddClauseTemplate'"
        @selected-item="onClauseTemplateSelected" />
      <AddInvoiceBudget v-if="showRegionComponent == 'AddInvoiceContract'" :object_id="props.request.id"
        :service="$ContractRequestApiService" :entity="'contract_request'" :persons="[holder]"
        @change="closeInvoiceData" @show-subregion="handleSubRegionEvent" />
      <AddInvoiceBudget v-if="showRegionComponent == 'AddInvoiceTermination'" :object_id="showRegionDetailId"
        :service="$ContractTerminationApiService" :entity="'contract_termination_request'" :persons="[]"
        @change="closeInvoiceData" @show-subregion="handleSubRegionEvent" />
      <InvoiceView v-if="showRegionComponent == 'InvoiceView'" :id="showRegionDetailId" />
      <OrderRegion v-if="showRegionComponent == 'OrderRegion'" :id="showRegionDetailId" :isSubRegion="true"
        class="mt-10" @changed="loadData" />
    </div>
  </div>
    <!-- /end Regió lateral per formularis -->
</template>

<style scoped>
/* Estils addicionals per al component */
</style>
