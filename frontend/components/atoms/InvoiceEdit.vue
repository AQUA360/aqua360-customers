<template>
  <div class="transition-all duration-300 border-b" :class="{
    'shadow-lg pb-2 m-3 rounded-lg': props.showDetail,
    'bg-orange-50': !!invoice.has_possible_leak_comm
    }">
    <div class="grid pt-2 gap-2 px-4 divide-gray-200 transition-all rounded-t-lg duration-300 ease-in-out"
      :class="[
        props.rowIndex != null && props.showCheckbox
          ? 'grid-cols-[48px_40px_minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_100px_260px]'
          : props.rowIndex != null
            ? 'grid-cols-[48px_minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_100px_260px]'
            : 'grid-cols-[40px_minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_100px_260px]',
        { 'mb-1 pb-2 pt-2 bg-slate-200': props.showDetail, 'bg-slate-100': excluded }
      ]">
      <div v-if="props.rowIndex != null" class="flex items-center justify-end pr-1">
        <span class="text-[11px] leading-none text-slate-400 tabular-nums select-none">#{{ props.rowIndex }}</span>
      </div>
      <div v-if="props.showCheckbox" class="p-3 flex items-center justify-center">
        <input type="checkbox" :checked="props.isSelected" @change="emit('selected', invoice.id)" class="w-4 h-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500" />
      </div>
      <div class="p-3 truncate">
        <span>{{ invoice.customer_final }}</span>
      </div>
      <div class="p-3 truncate">
        <span v-if="invoice.contract" class="cursor-pointer text-sky-600 underline" @click="openContractRegion">{{ invoice.contract_token }}</span>
        <span v-else>{{ invoice.contract_token }}</span>
      </div>
      <div class="p-3 truncate text-sm text-slate-600">
        <span>{{ invoice.use_type_final?.name || '-' }}</span>
      </div>
      <div class="p-3">
        <span>{{ invoice.payment_type_final }}</span>
      </div>
      <div class="p-3 font-bold truncate" :title="formatMoneyWithCurrency(invoice.total_final)">
        <span>{{ formatMoneyWithCurrency(invoice.total_final) }}</span>
      </div>
      <div class="p-3 font-bold truncate" :title="formatMoneyWithCurrency(invoice.left_to_pay)">
        <span>{{ formatMoneyWithCurrency(invoice.left_to_pay) }}</span>
      </div>
      <div class="p-3 text-sm font-mono text-slate-600 truncate">
        <span v-if="invoice.consumption != null" :title="`${invoice.consumption} m3`">{{ invoice.consumption }} <kbd>m3</kbd></span>
        <span v-else>-</span>
      </div>
      <div class="p-3 flex justify-center text-sm font-mono text-slate-500">
        <span v-if="duration !== null"><Icon v-if="hasWarning" name="fa6-solid:calendar-day" class="text-orange-500 w-5 h-5" :title="t('warning_block.warning_date_range')" /> {{ duration }}</span>
        <span v-else>-</span>
      </div>
      <div class="p-1 flex gap-1 items-center relative">
        <!-- Info popover (fixed, escapes overflow containers) -->
        <div class="relative">
          <button
            class="w-8 h-8 rounded-full flex flex-shrink-0 items-center justify-center transition-all duration-200 ml-1 bg-slate-100 text-slate-500 hover:bg-slate-200"
            :title="t('common.details')"
            @mouseenter="showInfoPopover"
            @mouseleave="hideInfoPopover">
            <Icon name="fa6-solid:circle-info" />
          </button>
          <Teleport to="body">
            <div v-if="showInfo"
              class="fixed z-[9999] w-72 rounded-lg border border-slate-200 bg-white shadow-lg text-sm pointer-events-none"
              :style="{ top: infoPos.y + 'px', left: infoPos.x + 'px' }">
              <div class="px-3 py-2 border-b border-slate-100 font-semibold text-slate-700 flex items-center gap-2">
                <Icon name="fa6-solid:circle-info" class="text-slate-400" />
                {{ t('common.details') }}
              </div>
              <div class="px-3 py-2 space-y-1.5">
                <div class="flex gap-2">
                  <span class="text-slate-400 shrink-0 w-28">{{ t('contract_block.billing_address') }}:</span>
                  <span class="text-slate-700 font-medium">{{ invoice.address_final || '-' }}</span>
                </div>
                <div class="flex gap-2">
                  <span class="text-slate-400 shrink-0 w-28">{{ t('address_block.location') }}:</span>
                  <span class="text-slate-700 font-medium">{{ invoice.location_final || '-' }}</span>
                </div>
              </div>
            </div>
          </Teleport>
        </div>
        <button
          class="w-8 h-8 bg-sky-400 text-white rounded-full flex flex-shrink-0 items-center justify-center enabled:hover:bg-sky-500 transition-all duration-200 disabled:opacity-30 ml-1"
          @click="invoicePDF()" :title="t('common.download')">
          <Icon :name="loadingPdf ? 'fa6-solid:spinner' : 'fa6-solid:file-pdf'" :class="{ 'animate-spin': loadingPdf }" />
        </button>
        <button :disabled="!props.allowEdit"
          class="w-8 h-8 rounded-full flex flex-shrink-0 items-center justify-center enabled:hover:bg-sky-500 transition-all duration-200 disabled:opacity-30 ml-1"
          :class="{
            'border border-sky-500 bg-white text-sky-500': props.showDetail,
            'bg-sky-400 text-white': !props.showDetail
            }"
          @click="toggleDetail" :title="t('common.edit')">
          <Icon name="fa6-solid:pencil" />
        </button>
        <button
          class="w-8 h-8 rounded-full flex flex-shrink-0 items-center justify-center transition-all duration-200 ml-1"
          :class="{
            'bg-amber-400 text-white': showHistory,
            'bg-amber-100 text-amber-600 hover:bg-amber-200': !showHistory
          }"
          @click="toggleHistory" :title="t('common.history')"
        >
          <Icon name="fa6-solid:chart-line" />
        </button>
        <button v-if="!props.finalized" :disabled="isInvoiceProcessed || loadingExclude"
          class="w-8 h-8 rounded-full flex flex-shrink-0 items-center justify-center transition-all duration-200 disabled:opacity-30 ml-1"
          :class="excluded ? 'bg-emerald-500 text-white enabled:hover:bg-emerald-600' : 'bg-rose-500 text-white enabled:hover:bg-rose-600'"
          @click="exclude" :title="isInvoiceProcessed ? t('billing_block.invoice_already_processed') : (excluded ? t('common.include') : t('common.exclude'))">
          <Icon :name="loadingExclude ? 'fa6-solid:spinner' : (excluded ? 'fa6-solid:plus' : 'fa6-solid:trash-can')" :class="{ 'animate-spin': loadingExclude }" />
        </button>
        <button v-if="!props.finalized" :disabled="isInvoiceProcessed || loadingRecalculate"
          class="w-8 h-8 bg-emerald-500 text-white rounded-full flex flex-shrink-0 items-center justify-center enabled:hover:bg-emerald-600 transition-all duration-200 disabled:opacity-30 ml-1"
          @click="recalculateSmart" :title="isInvoiceProcessed ? t('billing_block.invoice_already_processed') : t('common.recalculate')">
          <Icon :name="loadingRecalculate ? 'fa6-solid:spinner' : 'fa6-solid:arrows-rotate'" :class="{ 'animate-spin': loadingRecalculate }" />
        </button>
      </div>
    </div>
    <InvoiceListDetail :finalized="props.finalized" :show="props.showDetail" @show-detail="showDetail" @show-edit="showEdit" :id="invoice.id" :isSubRegion="true"></InvoiceListDetail>
    <InvoiceBillingHistoryDetail :finalized="props.finalized" :show="props.showHistory" @show-history="showHistory" @show-edit="showEdit" :invoice="invoice" :isSubRegion="true"/>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { useToast } from 'vue-toastification';
import InvoiceListDetail from '../molecules/InvoiceListDetail.vue';
import InvoiceBillingHistoryDetail from '../molecules/InvoiceBillingHistoryDetail.vue';
import { formatMoneyWithCurrency } from '~/utils/money';
import { getInvoiceDuration, hasDateRangeWarning } from '~/utils/stats';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

const { t } = useI18n();
const toast = useToast();
const { $ReadingApiService, $InvoiceApiService } = useNuxtApp();

const props = defineProps({
  invoice: {
    type: Object,
    required: true
  },
  showDetail: {
    type: Boolean,
    default: false
  },
  showHistory: {
    type: Boolean,
    default: false
  },
  finalized: {
    type: Boolean,
    default: false
  },
  allowEdit: {
    type: Boolean,
    default: true
  },
  medianDuration: {
    type: Number,
    default: 0
  },
  isSelected: {
    type: Boolean,
    default: false
  },
  rowIndex: {
    type: Number,
    required: false
  },
  showCheckbox: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['show-edit', 'show-history', 'open-region', 'excluded', 'selected']);

const invoice = ref(props.invoice);
const excluded = ref(props.invoice.is_excluded || false);
const loadingPdf = ref(false);
const loadingRecalculate = ref(false);
const loadingExclude = ref(false);
const showHistorical = ref(false);
const showInfo = ref(false);
const infoPos = ref({ x: 0, y: 0 });

const showInfoPopover = (event) => {
  const rect = event.currentTarget.getBoundingClientRect();
  infoPos.value = { x: rect.right - 288, y: rect.top - 8 };
  showInfo.value = true;
};
const hideInfoPopover = () => { showInfo.value = false; };

// `type_final === 'F'` indica que la factura ja és definitiva/processada (no un
// pressupost), i per tant no s'ha de poder tornar a eliminar ni recalcular.
const isInvoiceProcessed = computed(() => invoice.value.serie_token_final === 'FC');

const duration = computed(() => getInvoiceDuration(invoice.value));
const hasWarning = computed(() => {
  if (props.medianDuration === 0 || duration.value === null) return false;
  return hasDateRangeWarning(duration.value, props.medianDuration);
});

const toggleDetail =  () => {
  emit('show-edit', props.showDetail ? 0 : invoice.value.id);
}

const toggleHistory =  () => {
  emit('show-history', props.showHistory ? 0 : invoice.value.id);
}
const showEdit =  (e) => {
  emit('open-region', e);
}

const showDetail = (region, id) => {
  emit('show-detail', region, id);
}

const showHistory = (id) => {
  emit('show-history', id);
}

const openContractRegion = () => {
  emit('open-region', { id: props.invoice.contract, entity: 'ContractRegion' });
}

const invoicePDF = async () => {
  loadingPdf.value = true;

  try {
    if (invoice.value.invoice_file_template) {
      await openAuthenticatedFileUrl(invoice.value.invoice_file_template);
    } else {
      const data = await $InvoiceApiService.getTemporaryPDF(invoice.value.id);
      await openAuthenticatedFileUrl(data.url);
    }
  } catch (err) {
    console.error(err);
  } finally {
    loadingPdf.value = false;
  }
}

const onExcluded =  () => {
  emit('show-edit', 0);
  excluded.value = !excluded.value;
  emit('excluded', invoice.value.id);
}

const exclude = async () => {
  try {
    const wasExcluded = excluded.value;
    const confirmMsg = wasExcluded ? t("confirmation_text_block.confirm_include_invoice") : t("confirmation_text_block.confirm_exclude_invoice");
    if (confirm(confirmMsg)) {
      loadingExclude.value = true;
      await $InvoiceApiService.excludeInvoice({ invoice_id: invoice.value.id });
      toast.success(wasExcluded ? t("billing_block.correct_include_invoice") : t("billing_block.correct_exclude_invoice"));
      if (wasExcluded) {
        onExcluded();
      } else {
        emit('excluded', invoice.value.id);
      }
    }
  } catch (error) {
    console.error(error);
    toast.error(t("billing_block.error_exclude_invoice"));
  } finally {
    loadingExclude.value = false;
  }
}

const recalculateSmart = async () => {
  try {
    if (confirm(t("confirmation_text_block.confirm_recalculate_smart"))) {
      loadingRecalculate.value = true;
      const response = await $InvoiceApiService.recalculateSmart(invoice.value.id);
      if (response) {
        toast.success(t("billing_block.correct_recalculate_smart"));
        emit('open-region', { id: response.id || invoice.value.id, entity: 'InvoiceRegion' });
      }
      loadingRecalculate.value = false;
    }
  } catch (error) {
    loadingRecalculate.value = false;
    console.error(error);
    toast.error(t("billing_block.error_recalculate_smart"));
  }
}

const alertNote = ref('');
</script>
