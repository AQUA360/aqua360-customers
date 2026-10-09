<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';
const { t } = useI18n();

const props = defineProps({
  id: Number,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  allowChanges: {
    type: Boolean,
    default: true
  },
  // Show a "Download XLSX" button that exports exactly the rows/columns shown.
  exportable: {
    type: Boolean,
    default: true
  },
  exportFileName: {
    type: String,
    default: 'wallet_payment_commitments'
  }
});
const emit = defineEmits(['show-detail', 'update:count', 'open-date-modal', 'generate-payment-proof']);

const { $apiManager, $PaymentApiService, $ConfigProjectApiService, $DocumentManagerApiService } = useNuxtApp();

// Column definitions for the XLSX export — mirror the visible columns below.
const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.status'), value: (row) => row.status?.name, key: 'status' },
  { header: t('common.payment_method'), value: (row) => row.payment_type, key: 'payment_type' },
  { header: t('common.total'), value: (row) => Number(row.amount ?? 0), key: 'amount' },
  { header: t('billing_block.payment'), value: (row) => row.payment_date ? formatDate(row.payment_date) : '', key: 'payment_date' },
  { header: t('common.limit'), value: (row) => row.due_date ? formatDate(row.due_date) : '', key: 'due_date' },
]);

const loading = ref(false)
const localData = ref(null);
const localAllowChanges = ref(props.allowChanges);
const tokenPaymentPaid = ref(null)
const tokenPaymentSent = ref(null)

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

const getData = async () => {
  loading.value = true
  try {
    const result = await $PaymentApiService.getAll(
      '', [], 1,
      null, null, null,
      null, null, null,
      [], null, null,
      null, [], null,
      props.id);
    localData.value = result.results;
    emit('update:count', localData.value.length);
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false;
  }
}

const gridTemplateColumns = computed(() => {
  return '125px 1fr 1fr 1fr 80px 80px 100px';
});

const individualPayment = async (item) => {
  if (item.payment_type_token == 'DIRECT_DEBIT') {
    return navigateTo({
      path: '/billing/wallet-managements/manage',
      query: {
        action: 'idvMng',
        payment_id: item.id,
        is_commitment: true,
      }
    })
  } 
}

const printDocument = async (id) => {
  try {
    const document_file = await $DocumentManagerApiService.getDetail(id)
    const file = await $DocumentManagerApiService.viewDocument(id);
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

const generatePaymentDoc = async (item) => {
  try {
    const file =await $PaymentApiService.generatePaymentDoc(item.id, item.payment_date);
    const pdfBlob = new Blob([file], { type: 'application/pdf' });

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

onMounted(async () => {
  tokenPaymentPaid.value = await $ConfigProjectApiService.get('payment_status_paid_token');
  tokenPaymentSent.value = await $ConfigProjectApiService.get('payment_status_sent_token');
  getData()
})

watch(() => props.item, (newVal) => {
  localData.value = newVal
});

watch(() => props.allowChanges, (newVal) => {
  localAllowChanges.value = newVal;
});

</script>
<template>
  <div v-if="loading" class="flex gap-3 mx-auto p-1">
    <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
    {{ $t('common.loading') }}...
  </div>
  <div v-else class="mt-2">
    <div v-if="exportable && localData?.length > 0" class="flex justify-end mb-1">
      <AtomsDownloadXlsxButton :rows="localData" :columns="exportColumns" :file-name="exportFileName" />
    </div>
    <div v-if="localData && localData.length > 0" class="min-w-full text-sm text-slate-800">

      <div class="group grid bg-gray-100 border-b text-left " :style="{ gridTemplateColumns: gridTemplateColumns }">
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.identification') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.status') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.payment_method') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.total') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('billing_block.payment') }} </span>
        <span class="p-2 pl-2 text-slate-900 font-bold flex items-center"> {{ t('common.limit') }} </span>
        <span></span>
      </div>
      <div v-for="item in localData" class="border-b group grid text-sm leading-4 transition-all duration-100"
        :style="{ gridTemplateColumns: gridTemplateColumns }">

        <div class="footering text-slate-500 p-2 w-full">
          <button v-if="!isSubRegion"
            class="text-sky-500 hover:underline hover:text-sky-600 flex text-left items-left min-w-0 w-full"
            @click="showDetail('PaymentRegion', item.id)">
            <span class="mr-2 truncate flex-1">{{ item.token }}</span>
          </button>
          <div v-else class="truncate">{{ item.token }}</div>
        </div>
        <div class="footering text-slate-500 p-2 w-full">
          <AtomsColorBadge :value="item.status?.name" :color="item.status?.color" />
        </div>
        <div class="footering text-slate-500 p-2 w-full">
          {{ item.payment_type }}
        </div>
        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ formatMoneyWithCurrency(item.amount) }}</p>
        </div>

        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ item.payment_date? formatDate(item.payment_date) : '-' }}</p>
        </div>

        <div class="footering text-slate-500 p-2 w-full">
          <p>{{ formatDate(item.due_date) }}</p>
        </div>

        <div class="footering text-slate-500 p-2 w-full flex justify-center gap-x-1">
          <abbr 
          :title="`${t('common.generate')} ${t('billing_block.payment')}`">
            <button @click="emit('open-date-modal', item.id, item.payment_date)"
            :disabled="!localAllowChanges"
            class="group rounded-full w-6 h-6 border border-orange-500 bg-orange-50 flex justify-center items-center hover:bg-orange-100 disabled:opacity-50 disabled:cursor-not-allowed">
              <Icon name="fa6-solid:file" class="text-sm text-orange-500 group-hover:text-orange-600" />
            </button>
          </abbr>
          <abbr v-if="item.status.token == tokenPaymentPaid"
          :title="`${t('common.generate')} ${t('billing_block.payment_proof')}`">
            <button @click="emit('generate-payment-proof', item.id, item.payment_date)"
            class="h-6 w-6 rounded-full bg-green-500 hover:bg-green-600 text-white transition-colors duration-200 shadow-sm hover:shadow-md flex items-center justify-center">
            <Icon name="fa6-solid:receipt" class="text-sm"></Icon>
            </button>
          </abbr>
          <abbr v-if="item.status.token != tokenPaymentPaid && item.status.token != tokenPaymentSent && item.payment_type_token == 'DIRECT_DEBIT'" 
          :title="t('billing_block.single_pay')">
            <button @click="individualPayment(item)"
            :disabled="!localAllowChanges"
            class="group rounded-full w-6 h-6 border border-orange-500 bg-orange-50 flex justify-center items-center hover:bg-orange-100 disabled:opacity-50 disabled:cursor-not-allowed">
              <Icon name="fa6-solid:money-bill-transfer" class="text-sm text-orange-500 group-hover:text-orange-600" />
            </button>
          </abbr>
          <div v-else-if="item.document">
            <abbr v-if="item.payment_type_token == 'DIRECT_DEBIT'"   
            :title="`${t('common.show')} ${t('common.remittance')}`">
              <button @click="showDetail('SEPADocumentRegion', item.document.id)"
              class="group rounded-full w-6 h-6 border border-orange-500 bg-orange-50 flex justify-center items-center hover:bg-orange-100">
                <Icon name="fa6-solid:file-lines" class="text-sm text-orange-500 group-hover:text-orange-600" />
              </button>
            </abbr>
            
            <abbr v-else   
            :title="`${t('common.download')} ${t('common.document')}`">
              <button @click="printDocument(item.document.id)"
              class="group rounded-full w-6 h-6 border border-orange-500 bg-orange-50 flex justify-center items-center hover:bg-orange-100">
                <Icon name="fa6-solid:file-lines" class="text-sm text-orange-500 group-hover:text-orange-600" />
              </button>
            </abbr>
          </div>
        </div>

      </div>
    </div>
    <div v-else>
      <div class="footering text-slate-500 p-2">
        {{ t('common.no_data_found') }}
      </div>
    </div>
  </div>

</template>
<style scoped>
.truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.flex-1 {
  flex: 1;
}
</style>