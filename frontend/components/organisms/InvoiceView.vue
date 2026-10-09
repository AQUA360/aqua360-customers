<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '../atoms/H1.vue';
import IBAN from '~/components/atoms/IBAN.vue';
import InvoiceConsumptionDetail from '~/components/molecules/InvoiceConsumptionDetail.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

const { t } = useI18n();
const toast = useToast();
const { $apiManager, $ConfigProjectApiService, $InvoiceApiService, $DocumentManagerApiService } = useNuxtApp()

const props = defineProps({
  id: {
    type: Number,
    default: null
  },
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['changed']);

const pending = ref(true);
const error = ref(null);

const item = ref(null);

const status_pending_token = ref(null);
const type_budget_token = ref(null)

const getData = async () => {
  pending.value = true;

  $InvoiceApiService.getDetail(props.id).then((data) => {
    item.value = data;
    pending.value = false;
    error.value = null;
  }).catch((err) => {
    error.value = err;
    pending.value = false;
  });
}

// Hi ha dues fonts possibles de PDF: el document definitiu (`invoice_file`), que
// només existeix un cop generada la factura, i el PDF provisional, que el
// backend genera sota demanda a `temporary-pdf/{id}/` per a qualsevol factura,
// sigui pre-factura, pressupost o factura ja emesa. Es fa servir el primer que
// hi hagi, de manera que veure i descarregar funcionen sempre.
const loadingView = ref(false);
const loadingDownload = ref(false);

const pdfFileName = () =>
  `${String(item.value?.serie_final || item.value?.token || 'factura').replace(/\//g, '_')}.pdf`;

const openInvoicePdf = async (download = false) => {
  const flag = download ? loadingDownload : loadingView;
  if (flag.value) return;
  flag.value = true;

  try {
    if (item.value?.invoice_file) {
      const file = await $DocumentManagerApiService.viewDocument(item.value.invoice_file);
      const blob = file.type === 'application/pdf' ? file : new Blob([file], { type: 'application/pdf' });
      const objectUrl = URL.createObjectURL(blob);

      if (download) {
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = pdfFileName();
        link.click();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 250);
      } else {
        const newWindow = window.open(objectUrl, '_blank');
        if (!newWindow) {
          URL.revokeObjectURL(objectUrl);
        } else {
          // No es pot alliberar de seguida: la pestanya nova encara el necessita.
          const revoke = window.setInterval(() => {
            if (newWindow.closed) {
              URL.revokeObjectURL(objectUrl);
              window.clearInterval(revoke);
            }
          }, 500);
        }
      }
      return;
    }

    // Sense document definitiu, es demana el provisional. `openAuthenticatedFileUrl`
    // ja obre en pestanya nova o descarrega segons el segon paràmetre, i avisa ell
    // mateix amb un toast si el fitxer no hi és.
    const data = await $InvoiceApiService.getTemporaryPDF(props.id);
    await openAuthenticatedFileUrl(data.url, !download);
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    flag.value = false;
  }
}

watch(() => props.id, getData);

onMounted( async () => {
  status_pending_token.value = await $ConfigProjectApiService.get('invoice_status_pending_token');
  type_budget_token.value = await $ConfigProjectApiService.get('invoice_type_budget_token');
  
  getData();
});
</script>

<template>
  <div class="region__content pr-2 relative pb-24" :class="{ 'h-full overflow-y-auto': !isSubRegion }">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button>
      </p>
    </div>
    <div v-else>
      <div class="flex justify-between items-center mb-6">
        <H1>
          {{ item.type_final != type_budget_token ? t('invoice') : t('common.budget_detail') }} 
        </H1>
      </div>
  
      <p class="font-semibold pb-2">{{ t('contract_block.contract_data') }}</p>
      <div class="invoice__heading max-w-md pb-3">
        <p v-if="item.contract" class="flex justify-between">
          <label>{{ t('common.identification') }} {{ t('contract') }}:</label>
          <span>{{ item.contract.token }}</span>
        </p>
        <p v-else-if="item.contract_request" class="flex justify-between">
          <label>{{ t('common.identification') }} {{ t('contract_block.short_contract_request') }}:</label>
          <span>{{ item.contract_request.token }}</span>
        </p>
        <p v-else-if="item.contract_termination" class="flex justify-between">
          <label>{{ t('common.identification') }} {{ t('contract_block.short_contract_termination') }}:</label>
          <span>{{ item.contract_termination.token }}</span>
        </p>
        <p v-else-if="item.connection_request" class="flex justify-between">
          <label>{{ t('common.identification') }} {{ t('connection') }}:</label>
          <span>{{ item.connection_request.token }}</span>
        </p>
        <!-- <p v-else class="flex justify-between">
          <label>{{ t('common.identification') }} -:</label>
          <span>{{ t('common.no_records') }}</span>
        </p> -->
        <p v-if="item.serie_final" class="flex justify-between">
          <label>{{ t('billing_block.serie') }}:</label>
          <span>{{ item.serie_final }}</span>
        </p>
        <p class="flex justify-between">
          <label>{{ t('contract_block.holder') }}:</label>
          <span>{{ item.customer_final }}</span>
        </p>
        <p class="flex justify-between">
          <label>{{ t('common.person_id') }}:</label>
          <span>{{ item.customer_token_final }}</span>
        </p>
        <p class="flex justify-between">
          <label>{{ t('address_block.address') }}:</label>
          <span>{{ item.address_final }}</span>
        </p>
        <p class="flex justify-between">
          <label>{{ t('address_block.municipality') }}:</label>
          <span>{{ item.location_final }}</span>
        </p>
        <p v-if="item.persons_final" class="flex justify-between">
          <label>{{ t('contract_block.total_persons') }}:</label>
          <span>{{ item.persons_final }}</span>
        </p>
      </div>
  
      <p class="font-semibold pb-2">{{ t('billing') }}</p>
      <div class="invoice__heading max-w-md pb-3">
        <p class="flex justify-between">
          <label>{{ t('common.date') }}:</label>
          <span>{{ formatDate(item.issue_date) }}</span>
        </p>
        <p class="flex justify-between">
          <label>{{ t('common.number') }}:</label>
          <span>{{ item.serie_final }}</span>
        </p>
        <p class="flex justify-between">
          <label>{{ t('common.identification') }}:</label>
          <span>{{ item.token }}</span>
        </p>
      </div>
  
      <div class="pb-10 max-w-[800px]">
        <InvoiceConsumptionDetail
          :data="item"
          :isSubRegion="true"
          :showContractReadings="false"
        />
      </div>
  
      <div class="invoice__main max-w-[800px] pb-10">
        <h3 class="font-bold">{{ item.title_final }}</h3>
        <div class="invoice__main_heading mb-3 p-1">
          <div class="grid grid-cols-[1fr,80px,80px,100px,50px] gap-2">
            <div><strong>{{ t('line_item') }}</strong></div>
            <div><strong>{{ t('common.units') }}</strong></div>
            <div><strong>{{ t('billing_block.price_unit_short') }}</strong></div>
            <div><strong>{{ t('common.amount') }}</strong></div>
            <div><strong>{{ t('common.iva') }}</strong></div>
          </div>
        </div>
        <div v-for="(line, index) in item.line_items.sort((a, b) => (a.custom_order || a.product_order || 0) - (b.custom_order || b.product_order || 0))" :key="index"
          :class="['grid grid-cols-[1fr,80px,80px,100px,50px] gap-2 pb-3 p-1', { 'bg-slate-100': !(index % 2) }]">
          <div>
            <div><strong>{{ line.product_name }}</strong></div>
            <div class="pl-2">
              {{ line.description ? line.description : line.name }}
            </div>
          </div>
          <div>{{ parseFloat(line.units).toFixed(4) }}</div>
          <div>{{ parseFloat(line.price_unit).toFixed(4) }}</div>
          <div><strong>{{ formatMoneyWithCurrency(line.price) }}</strong></div>
          <div>{{ parseInt(line.tax_percent) ? parseInt(line.tax_percent) + " %" : 'EX' }}</div>
        </div>
      </div>
  
      <div class="invoice__totals max-w-md pb-10">
        <p class="flex justify-between">
          <label>{{ t('billing_block.taxable_base') }}:</label>
          <span>{{ formatMoneyWithCurrency(item.subtotal_final) }}</span>
        </p>
  
        <p v-for="tax_value, percent in item.taxes" class="flex justify-between">
          <label>{{ t('common.iva') }} ({{ parseFloat(percent) }}%): {{ t('billing_block.taxable_base') }} {{
            formatMoneyWithCurrency(item.taxes_base[percent]) }}:</label>
          <span>{{ formatMoneyWithCurrency(tax_value) }}</span>
        </p>
  
        <span class="flex justify-between">
          <h3 class="font-bold">{{ t('billing_block.total_to_pay') }}:</h3>
          <span>{{ formatMoneyWithCurrency(item.total_final) }}</span>
        </span>
      </div>
  
      <div class="invoice__footer  max-w-md pb-10">
        <p class="flex justify-between">
          <label>{{ t('common.payment_method') }}:</label>
          <span>{{ item.payment_type_final }}</span>
        </p>
        <p v-if="item.payment_bank_final" class="flex justify-between">
          <label>{{ t('common.iban') }}:</label>
          <span>
            <IBAN :value="item.payment_bank_final" />
          </span>
        </p>
        <!-- <div v-if="item.accounting_office_final">
          <p  class="flex justify-between">
            <label>{{ t('Oficina comptable') }}:</label>
            <span>{{ item.accounting_office_final }}</span>
          </p>
          <p  class="flex justify-between">
            <label>{{ t('Òrgan gestor') }}:</label>
            <span>{{ item.managing_body_final }}</span>
          </p>
          <p  class="flex justify-between">
            <label>{{ t('Unitat tramitadora') }}:</label>
            <span>{{ item.processing_unit_final }}</span>
          </p>
        </div> -->
      </div>
      <Teleport to="body">
        <!-- Sempre disponibles: veure el PDF en una pestanya nova i descarregar-lo.
             Si la factura encara no té el document definitiu generat, totes dues
             accions treballen amb el PDF provisional. -->
        <div class="fixed bottom-8 right-8 z-[110] flex items-center gap-3">
          <abbr :title="item.invoice_file
            ? `${t('common.check')} ${t('invoice').toLowerCase()}`
            : `${t('common.check')} ${t('common.provisional').toLowerCase()}`">
            <button @click="openInvoicePdf(false)" :disabled="loadingView"
              class="rounded-full bg-slate-700/50 w-12 h-12 hover:bg-slate-700/75 transition-all duration-150 p-4 shadow-lg flex items-center justify-center disabled:opacity-60">
              <Icon :name="loadingView ? 'fa6-solid:spinner' : 'fa6-solid:eye'" class="text-white w-8 h-8 text-2xl"
                :class="{ 'animate-spin': loadingView }" />
            </button>
          </abbr>

          <abbr :title="`${t('common.download')} ${t('invoice').toLowerCase()}`">
            <button @click="openInvoicePdf(true)" :disabled="loadingDownload"
              class="rounded-full bg-slate-700/50 w-12 h-12 hover:bg-slate-700/75 transition-all duration-150 p-4 shadow-lg flex items-center justify-center disabled:opacity-60">
              <Icon :name="loadingDownload ? 'fa6-solid:spinner' : 'fa6-solid:download'" class="text-white w-8 h-8 text-2xl"
                :class="{ 'animate-spin': loadingDownload }" />
            </button>
          </abbr>
        </div>
      </Teleport>
  
    </div>
  </div>
</template>

<style scoped>
.invoice__heading p {
  border-bottom: 1px solid #000;
}
</style>
