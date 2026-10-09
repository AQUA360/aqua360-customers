<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';
import { useConfigStore } from '~/stores/useConfigStore';
import { storeToRefs } from 'pinia';

const { t } = useI18n();

const languageLabel = (code) => {
  const lang = AVAILABLE_LANGUAGES.find((l) => l.code === code);
  return lang ? t(lang.name) : null;
};

const props = defineProps({
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  id: Number, // ID de l'element
  showOrdersType: {
    type: Boolean,
    default: true
  },
  showContractSection: {
    type: Boolean,
    default: true
  },
  showInvoiceSection: {
    type: Boolean,
    default: false
  },
  reload: {
    type: Boolean,
    default: false
  },
  request: {
    type: Object,
    default: null
  },
  canChange: {
    type: Boolean,
    default: true
  }
});

const router = useRouter();
const { $ContractRequestApiService, $ConfiglistApiService, $ContractApiService, $InvoiceApiService, $ConfigProjectApiService, $DocumentManagerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const ContractStatuses = ref([]);
const invoices = ref([])
const loadingInvoice = ref(null)
const finalInvoice = ref(null)
const { fetchFinalInvoiceTokens, isInvoice, findFinalInvoice } = useFinalInvoiceTokens();

const configStore = useConfigStore();
const { documentSignEnabled } = storeToRefs(configStore);
configStore.fetchDocumentSignEnabled();

const signContractId = computed(() => data.value?.contract?.id || data.value?.contract || null);
const signContractRequestId = computed(() => (signContractId.value ? null : data.value?.id || props.id || null));
const signContractFileId = computed(() => data.value?.contract_file?.id || null);

const signOtpDefaultName = computed(() => {
  return data.value?.holder_full_name
    || data.value?.person_full_name
    || '';
});

const signOtpDefaultEmail = computed(() => {
  const digitalContact = data.value?.person_contact_email;
  if (digitalContact?.email) return digitalContact.email;
  const contactWithEmail = (data.value?.contacts || []).find(c => c.email);
  return contactWithEmail?.email || '';
});

const signOtpDefaultPhone = computed(() => {
  const contactWithPhone = (data.value?.contacts || []).find(c => c.phone);
  return contactWithPhone?.phone || '';
});

const emit = defineEmits(['show-detail', 'show-invoice', 'clickChangeStatus']);

const SubRegion = ref(props.isSubRegionOpen);

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

// Funció per mostrar detalls
const showDetail = (component, id) => {
  SubRegion.value = true;
  emit('show-detail', component, id);
};

const fetchContractStatuses = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-request-status');
    ContractStatuses.value = data.results;
  } catch (error) {
    console.error('Error fetching Contract statuses:', error);
  }
};

// tabs
const getData = async (load = true) => {
  if (load) pending.value = true;
  error.value = null;
  try {
    if (props.request) {
      data.value = props.request;
    } else {
      const result = await $ContractRequestApiService.getDetail(props.id);
      data.value = result;
    }
    let invoice_statuses = { results: [] };
    try {
      invoice_statuses = await $ConfiglistApiService.getAll('billing/invoice-status');
    } catch (e) {
      console.error('Error fetching invoice statuses:', e);
    }
    invoices.value = (data.value.invoices || []).map(inv => {
      const statusObj = invoice_statuses.results?.find(s => String(s.id) === String(inv.status));
      const statusToken = statusObj?.token || inv.status_token || inv.status?.token || inv.status_final || (typeof inv.status === 'string' ? inv.status : null);
      return {
        ...inv,
        type_token: inv.type_token || inv.type?.token || inv.type_final || (typeof inv.type === 'string' ? inv.type : null),
        status_token: statusToken,
        status_name: inv.status_name || statusObj?.name || null,
        status_color: inv.status_color || statusObj?.color || null,
      };
    });
    if (invoices.value.length > 0) {
      await fetchFinalInvoiceTokens();
      finalInvoice.value = findFinalInvoice(invoices.value);
    }
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

onMounted(async () => {
  await fetchFinalInvoiceTokens();
  fetchContractStatuses();
  getData();
});

watch(() => props.id, () => {
  getData();
});

// Watch key to trigger data reload
watch(() => props.id, () => {
  getData();
});

watch(() => props.reload, () => {
  getData(false);
});

const generateContract = async () => {
  const contract = await $ContractApiService.getDocument(props.id);
  await openAuthenticatedFileUrl(contract.pdf_url);
}

const getInvoiceData = async () => {
  try {
    const response = await $InvoiceApiService.getContractInvoice(props.id);
    let invoice_statuses = { results: [] };
    try {
      invoice_statuses = await $ConfiglistApiService.getAll('billing/invoice-status');
    } catch (e) {
      console.error('Error fetching invoice statuses:', e);
    }
    invoices.value = (response.results || []).map(inv => {
      const statusObj = invoice_statuses.results?.find(s => String(s.id) === String(inv.status));
      const statusToken = statusObj?.token || inv.status_token || inv.status?.token || inv.status_final || (typeof inv.status === 'string' ? inv.status : null);
      return {
        ...inv,
        type_token: inv.type_token || inv.type?.token || inv.type_final || (typeof inv.type === 'string' ? inv.type : null),
        status_token: statusToken,
        status_name: inv.status_name || statusObj?.name || null,
        status_color: inv.status_color || statusObj?.color || null,
      };
    });
    finalInvoice.value = findFinalInvoice(invoices.value);
  } catch (error) {
    console.log(error);
  }
}

const downloadInvoice = async (invoice) => {
  loadingInvoice.value = invoice.id;
  try {
    if (!invoice.invoice_file) {
      const pdf = await $InvoiceApiService.getTemporaryPDF(invoice.id);
      await openAuthenticatedFileUrl(pdf.url);
    } else {
      const file = await $DocumentManagerApiService.viewDocument(invoice.invoice_file);
      const pdfBlob = new Blob([file], { type: 'application/pdf' });
      const blobUrl = URL.createObjectURL(pdfBlob);
      const newWindow = window.open(blobUrl, '_blank');
      if (newWindow) {
        setTimeout(() => URL.revokeObjectURL(blobUrl), 250);
      } else {
        URL.revokeObjectURL(blobUrl);
      }
    }
  } catch (err) {
    console.error(err);
  } finally {
    loadingInvoice.value = null;
  }
}

const generateSignedContract = async () => {
  const newWindow = window.open(data.value.contract_file, '_blank');

  if (newWindow) {
    newWindow.focus();

    newWindow.onload = () => {
      newWindow.print();
    };
  } else {
    console.error("Failed to open a new window. Please check popup blocker settings.");
  }
}

</script>

<template>
  <div v-if="pending">
    <p>{{ $t('common.loading') }}...</p>
  </div>
  <div v-else-if="error">
    <p>Error: {{ error.message }}</p>
    <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button></p>
  </div>
  <div v-else>
    <div v-if="data" id="item_data" :data-rel=id>

      <fieldset id="setup__box" v-if="data.person || data.holder" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ $t('contracting') }}</legend>
        <div class="grid grid-cols-2 gap-3">
          <FieldDetail :label="`${$t('contract_block.contract_type')}`">{{ data.type?.name }}</FieldDetail>
          <FieldDetail :label="`${$t('common.registration_date')}`">{{ data.registration_date ? formatDate(data.registration_date) : '-' }}</FieldDetail>
          <FieldDetail v-if="data.language" :label="`${$t('common.language')}`">{{ languageLabel(data.language) }}</FieldDetail>
          <FieldDetail v-if="!data.contract" :label="`${$t('common.identification')}`">{{ data.token }}</FieldDetail>
          <FieldDetail v-else :label="`${$t('contract')}`">
            <span v-if="isSubRegion">{{ data.contract.token }}</span>
            <div v-else class="flex gap-2">
              <button @click="showDetail('ContractRegion', data.contract.id)"
                class="text-start text-sky-500 underline">{{
                  data.contract.token }}</button>
              <AtomsRedirectButton :id="data.contract.id" :path="'/contract/contracts/'" />
            </div>
          </FieldDetail>
          <div class="flex flex-col">
            <FieldDetail :label="$t('common.requester')">
              <span v-if="isSubRegion && data.person">{{ data.person_full_name }}</span>
              <div v-else-if="data.person" class="flex gap-2">
                <button @click="showDetail('PersonRegion', data.person_id)" class="text-start text-sky-500 underline">{{
                  data.person_full_name }}</button>
                <AtomsRedirectButton :id="data.person_id" :path="'/contract/persons/'" />
              </div>
              <span v-else>-</span>
            </FieldDetail>
          </div>
          <span></span>
          <div>
            <FieldDetail v-if="data.holder" :label="$t('contract_block.holder')" :value="data.holder_full_name" />
            <FieldDetail v-if="data.owner" :label="$t('contract_block.owner')" :value="data.owner_full_name" />
            <FieldDetail v-if="data.tenant" :label="$t('contract_block.tenant')" :value="data.tenant_full_name" />
            <FieldDetail :label="$t('contract_block.debt_management_type')"
              :value="data.debt_management ? data.debt_management.name : t('contract_block.no_debt_management_type')" />
          </div>
        </div><!-- end grid -->
        <div>
          <FieldDetail v-if="data.supply_point_default" :label="$t('address_block.address')"
            :value="data.supply_point_default.address_complete" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <FieldDetail v-for="supply_point in data.supply_points" :key="supply_point.id"
            :label="$t('common.short_supply')">
            <span v-if="isSubRegion && supply_point">{{ supply_point.token }} {{ data.supply_point_default.id ==
              supply_point.id ? `(${t('common.main')})` : '' }}</span>
            <div v-else-if="supply_point" class="flex gap-2">
              <button @click="showDetail('SupplyPointRegion', supply_point.id)"
                class="text-start text-sky-500 underline">{{ supply_point.token }} {{ data.supply_point_default.id ==
                  supply_point.id ? `${t('common.main')}` : '' }}</button>
              <AtomsRedirectButton :id="supply_point.id" :path="'/service/supplypoints/'" />
            </div>
            <span v-else>-</span>
          </FieldDetail>
        </div>
      </fieldset>

      <fieldset id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ $t('communication') }}</legend>
        <div>
          <FieldDetail v-if="data.address_billing" :label="$t('common.fiscal_address')"
            :value="data.address_billing.address_complete" />
          <FieldDetail v-if="data.address_contact" :label="$t('contract_block.contact_address')"
            :value="data.address_contact.address_complete" />
        </div>
        <div>
          <div v-if="data.communication_type == 'DIGITAL' || data.communication_type == 'BOTH'">
            <FieldDetail :label="$t('contract_block.short_digital_comm')"
              :value="data.person_contact_email?.email || null" />
          </div>
          <div v-if="data.communication_type == 'PAPER' || data.communication_type == 'BOTH'">
            <FieldDetail :label="$t('contract_block.short_paper_comm')"
              :value="data.address_contact?.address_complete || null" />
          </div>
          <FieldDetail v-if="data.communication_type == 'NONE'" :label="$t('communication')"
            :value="$t('contract_block.no_comm')" />
        </div>
        <FieldDetail :label="$t('common.tlf')" :value="null">
          <span class="">
            <span v-for="(phone, index) in data.contacts" :key="phone.id">
              {{ phone.phone }}<span v-if="index < data.contacts.length - 1">, </span>
            </span>
          </span>
        </FieldDetail>
      </fieldset>


      <fieldset v-if="data.price_rate" id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ $t('price_rate') }}</legend>
        <div>
          <div class="grid grid-cols-2 mb-2">
            <FieldDetail v-if="data.price_rate" :label="$t('price_rate')" :value="data.price_rate.name" />
            <FieldDetail v-if="data.category" :label="$t('contract_block.category')" :value="data.category.name" />
            <FieldDetail v-if="data.use_type" :label="$t('common.usage_type')" :value="data.use_type.name" />
            <FieldDetail v-if="data.client_type" :label="$t('contract_block.client_type')"
              :value="data.client_type.name" />

          </div>

          <!-- variables -->
          <FieldDetail v-if="data.variables" :label="$t('variables')" :value="null">
            <span>
              <span v-for="(variable, index) in data.variables" :key="variable.id" class="flex items-center gap-3">
                <Icon name="fa6-solid:gear" class="text-slate-500"></Icon> {{ variable.name }}<br />
              </span>
            </span>
          </FieldDetail>

          <!-- bonifications -->
          <FieldDetail v-if="data.bonifications" :label="$t('bonifications')" :value="null">
            <span>
              <span v-for="(bonification, index) in data.bonifications" :key="bonification.id"
                class="flex items-center gap-3">
                <Icon name="fa6-solid:gear" class="text-slate-500"></Icon> {{ bonification.bonification_type.name
                }}<br />
              </span>
            </span>
          </FieldDetail>
        </div>
      </fieldset>

      <!-- seccio order_types -->
      <fieldset v-if="showOrdersType && data.order_types" id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ $t('order_block.order_types_long') }}</legend>
        <div>
          <div class="grid grid-cols-2 mb-2">
            <div v-if="data.order_types" :label="$t('order_block.command_type')" :value="null">
              <div v-for="(order_type, index) in data.order_types" :key="order_type.id" class="flex items-center gap-3">
                <Icon name="fa6-solid:screwdriver-wrench" class="text-slate-500"></Icon> {{ order_type.name }}
              </div>
            </div>
          </div>
          <div v-if="data.order_types.length == 0" class="italic text-sm">
            {{ t('common.no_data_found') }}
          </div>
        </div>
      </fieldset>


      <fieldset v-if="showContractSection" id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ $t('contract') }}</legend>

        <div class="flex gap-3">
          <button class="button-default" @click="generateContract">
            <Icon name="fa6-solid:file-pdf" class="mr-2" />
            {{ $t('common.generate') }} {{ $t('contract') }}
          </button>

          <!-- imprimir contracte -->
          <button class="button-default">
            <Icon name="fa6-solid:print" class="mr-2" />
            {{ $t('common.print') }}
          </button>

          <!-- signar contracte -->
          <!-- <button v-if="canChange" class="button-default">
            <Icon name="fa6-solid:signature" class="mr-2" />
            {{ $t('common.sign') }}
          </button> -->
        </div>

        <div v-if="documentSignEnabled" class="my-3">
          <MoleculesDocumentSignStatus :contractId="signContractId" :contractRequestId="signContractRequestId"
            :contractFileId="signContractFileId" :defaultName="signOtpDefaultName" :defaultEmail="signOtpDefaultEmail"
            :defaultPhone="signOtpDefaultPhone" />
        </div>

        <div v-else class="flex gap-3 mt-1">

          <span v-if="!(data.contract_file && data.contract_file.is_active !== false)"
            class="text-gray-700 mt-1 font-medium italic text-sm bg-yellow-100 rounded-md px-2 py-1">
            {{ t('contract_block.no_signed_contract') }}
          </span>

          <button v-else class="button-default" @click="generateSignedContract">
            <Icon name="fa6-solid:file-pdf" class="mr-2" />
            {{ $t('common.download') }} {{ $t('contract_block.signed_contract') }}
          </button>

        </div>
      </fieldset>

      <fieldset v-if="showInvoiceSection" id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">{{ $t('billing') }}</legend>

        <div v-if="canChange && !isSubRegion" class="flex gap-3">
          <button class="button-default" @click="showDetail('AddInvoiceContract', null)">
            <Icon name="fa6-solid:file-pdf" class="mr-2" />
            <span>
              {{ $t('common.modify') }} {{ $t('common.budget_detail') }}/{{ $t('invoice') }}
            </span>
          </button>
        </div>
        <div class="flex gap-3 mt-1">

          <span class="text-gray-700 mt-1 font-medium italic text-sm bg-yellow-100 rounded-md px-2 py-1"
            v-if="invoices.length == 0">
            {{ $t('billing_block.budget_invoice_not_generated') }}
          </span>
          <span class="text-gray-700 mt-1 font-medium italic text-sm bg-yellow-100 rounded-md px-2 py-1"
            v-else-if="invoices.length > 0 && !finalInvoice">
            {{ $t('billing_block.budget_invoice_generated') }}
          </span>

        </div>

        <div class="ml-3 mt-4">
          <div v-for="invoice in invoices" :key="invoice.id" class="flex items-center gap-4">
            <AtomsFieldDetail
              :label="finalInvoice?.id == invoice.id ? t('billing_block.final_invoice') :
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
                :title="`${t('common.download')} ${t('invoice')}`">
                <Icon :name="loadingInvoice == invoice.id ? 'fa6-solid:spinner' : 'fa6-solid:download'"
                  class="text-orange-500 m-auto" :class="{ 'animate-spin': loadingInvoice == invoice.id }" />
              </button>
            </div>
          </div>
        </div>

      </fieldset>


    </div><!-- end if data -->
  </div><!-- end if pending -->
</template>
