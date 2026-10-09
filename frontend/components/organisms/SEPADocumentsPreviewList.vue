<script setup>
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useNuxtApp } from '#app';
import { formatMoneyWithCurrency } from '~/utils/money';
import { formatDate } from '~/utils/date';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';

const props = defineProps({
  sepaFiles: {
    type: Array,
    default: () => []
  },
  searchData: {
    type: Object,
    default: null
  },
  isRegion: {
    type: Boolean,
    default: false
  }
});

const { t } = useI18n();
const emit = defineEmits(['close', 'show-detail']);
const { $PaymentApiService } = useNuxtApp();

const localSepaFiles = ref([]);
const loading = ref(false);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = (component, id) => {
  closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-detail', true);
}

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null
  regionDetailId.value = null
  emit('show-detail', false);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const loadFiles = async () => {
  loading.value = true;
  try {
    if (props.searchData) {
      const response = await $PaymentApiService.getSEPAFiles(props.searchData);
      if (response && response.sepa_files_preview) {
        localSepaFiles.value = response.sepa_files_preview;
      } else {
        localSepaFiles.value = [];
      }
    } else {
      localSepaFiles.value = props.sepaFiles || [];
    }
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
};

watch(() => props.searchData, loadFiles, { deep: true, immediate: true });
watch(() => props.sepaFiles, () => {
  if (!props.searchData) {
    localSepaFiles.value = props.sepaFiles || [];
  }
}, { deep: true, immediate: true });
</script>

<template>
  <div class="region__content pr-1 w-full">
    <div class="h-full flex flex-col w-full min-w-0 transition-all duration-500 ease" :class="{ 'mr-[50%]': showRegion && !isSubRegionOpen, 'mr-[95%]': showRegion && isSubRegionOpen }">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 class="text-base font-semibold text-slate-700">{{ $t('billing_block.sepa_preview') }}</h3>
        <span class="text-xs text-slate-500">{{ $t('common.total') }}: {{ localSepaFiles.length }}</span>
      </div>

      <div class="flex-1 overflow-y-auto space-y-4 pr-2">
        <div v-if="loading && !localSepaFiles.length" class="text-center py-8 text-slate-500 text-sm border border-slate-200 rounded bg-white">
          <Icon name="fa6-solid:spinner" class="animate-spin text-xl text-slate-500" />
        </div>
        <div v-else-if="!localSepaFiles.length" class="text-center py-8 text-slate-500 text-sm border border-slate-200 rounded bg-white">
          {{ $t('common.no_data_found') }}
        </div>
        
        <div v-for="(file, index) in localSepaFiles" :key="index" class="border border-slate-200 rounded overflow-hidden bg-white shadow-sm">
          <div class="bg-slate-50 border-b border-slate-200 px-4 py-3 flex justify-between items-center">
            <div>
              <h4 class="font-medium text-slate-800 flex items-center gap-2">
                <Icon name="fa6-solid:file-pdf" class="text-sky-600" />
                <span>{{ $t('common.sepa') }} - {{ file.remittance_date ? formatDate(file.remittance_date) : $t('common.unknown') }}</span>
              </h4>
              <p class="text-xs text-slate-500 mt-0.5">{{ file.invoices ? file.invoices.length : 0 }} {{ $t('billing_block.generated_invoices').toLowerCase() }}</p>
              <!-- Cada fitxer es remesa per un banc concret, i l'empresa emissora
                   del fitxer és la titular d'aquell compte. -->
              <p v-if="file.bank_name || file.company_name" class="text-xs text-slate-500 mt-0.5">
                <span v-if="file.company_name" class="font-medium">{{ file.company_name }}</span>
                <span v-if="file.company_name && file.bank_name"> · </span>
                <span v-if="file.bank_name">{{ file.bank_name }}</span>
                <span v-if="file.bank_iban"> · {{ file.bank_iban.slice(-4) }}</span>
              </p>
            </div>
            <div class="text-right">
              <span class="block font-bold text-slate-800">{{ formatMoneyWithCurrency(file.total_amount) }}</span>
            </div>
          </div>
          <div class="max-h-64 overflow-y-auto bg-white p-0">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 sticky top-0 border-b border-slate-100 z-[1]">
                <tr>
                  <th class="px-4 py-2 text-left font-medium text-slate-500 w-4/12">{{ $t('billing_block.generated_invoices') }}</th>
                  <th class="px-4 py-2 text-left font-medium text-slate-500 w-4/12">{{ $t('contract') }}</th>
                  <th class="px-4 py-2 text-right font-medium text-slate-500 w-4/12">{{ $t('billing_block.total_amount') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-50">
                <tr v-if="!file.invoices || !file.invoices.length">
                  <td class="px-4 py-3 text-center text-slate-400 italic">{{ $t('common.no_invoice') }}</td>
                </tr>
                <tr v-for="invoice in file.invoices" :key="invoice.id" class="hover:bg-slate-50/50">
                  <td class="px-4 py-2">
                    <div class="flex gap-2" v-if="invoice.id">
                      <button @click="showDetail('InvoiceRegion', invoice.id)"
                        class="text-sky-600 hover:text-sky-800 hover:underline font-medium focus:outline-none flex items-center gap-2">
                        <span>{{ invoice.token || invoice.serie_final }}</span>
                      </button>
                      <AtomsRedirectButton :id="invoice.id" :path="'/billing/invoice/'" />
                    </div>
                    <span v-else class="text-slate-400">-</span>
                  </td>
                  <td class="px-4 py-2">
                    <div class="flex gap-2" v-if="invoice.contract_id">
                      <button @click="showDetail('ContractRegion', invoice.contract_id)"
                        class="text-sky-600 hover:text-sky-800 hover:underline font-medium focus:outline-none flex items-center gap-2">
                        <span>{{ invoice.contract_token || $t('common.contract') }}</span>
                      </button>
                      <AtomsRedirectButton :id="invoice.contract_id" :path="'/contract/contracts/'" />
                    </div>
                    <span v-else class="text-slate-400">-</span>
                  </td>
                  <td class="px-4 py-2 text-right font-medium">
                    {{ formatMoneyWithCurrency(invoice.amount) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    
    <div role="region" :id="isRegion ? 'subregion' : 'right_page'"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 z-10" :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[50%]': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <InvoiceRegion v-if="showRegionDetailComponent == 'InvoiceRegion'" :id="parseInt(regionDetailId)"
          :isSubRegionOpen="isSubRegionOpen" :isSubRegion="isRegion" @show-subregion="handleSubRegionEvent">
        </InvoiceRegion>
        <ContractRegion v-if="showRegionDetailComponent == 'ContractRegion'" :id="parseInt(regionDetailId)"
          :isSubRegionOpen="isSubRegionOpen" :isSubRegion="isRegion" @show-subregion="handleSubRegionEvent">
        </ContractRegion>
      </div>
    </div>
  </div>
</template>
