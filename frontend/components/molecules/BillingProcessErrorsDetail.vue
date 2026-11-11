<script setup>
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import AppLoading from '../atoms/AppLoading.vue';

// Contractes que no s'han pogut facturar en processar la facturació: motiu, què cal fer
// i accions per tornar-los a processar (la factura s'afegeix a la facturació) o descartar-los.
const props = defineProps({
  billingId: Number,
  errors: {
    type: Array,
    default: () => []
  },
  loading: Boolean,
  // La llista s'està tornant a carregar
  reloading: Boolean,
  disabled: Boolean
});

const emit = defineEmits(['reload', 'open-region']);
const { t } = useI18n();
const toast = useToast();
const { $BillingApiService } = useNuxtApp();

// Contracte en curs (id) o 'all' mentre es tornen a processar tots.
const busy = ref(null);

// Contractes ja facturats: s'amaguen de seguida perquè un segon clic abans que arribi
// la llista nova no generi una altra pre-factura amb les lectures que quedin.
const processedIds = ref(new Set());
watch(() => props.errors, () => { processedIds.value = new Set(); });
const visibleErrors = computed(() => props.errors.filter(e => !processedIds.value.has(e.contract_id)));
const locked = computed(() => !!busy.value || props.reloading || props.disabled);

const markProcessed = (contractId) => {
  processedIds.value = new Set([...processedIds.value, contractId]);
};

const retryContract = async (contractId) => {
  // L'error ja el mostra el gestor de l'API; aquí només es refresca la llista.
  try {
    await $BillingApiService.processContract(props.billingId, contractId);
    markProcessed(contractId);
    return true;
  } catch (e) {
    console.error(e);
    return false;
  }
};

const retry = async (contractId) => {
  if (locked.value) return;
  busy.value = contractId;
  try {
    if (await retryContract(contractId)) {
      toast.success(t('billing_block.correct_process_contract'));
    }
  } finally {
    busy.value = null;
    emit('reload');
  }
};

const retryAll = async () => {
  if (locked.value) return;
  busy.value = 'all';
  let failed = 0;
  try {
    for (const err of [...visibleErrors.value]) {
      if (!(await retryContract(err.contract_id))) failed++;
    }
    if (failed === 0) {
      toast.success(t('billing_block.correct_process_contract'));
    } else {
      toast.error(`${t('billing_block.process_error_retry_failed')} (${failed})`);
    }
  } finally {
    busy.value = null;
    emit('reload');
  }
};

const dismiss = async (contractId) => {
  if (locked.value || !confirm(t('billing_block.process_error_confirm_dismiss'))) return;
  busy.value = contractId;
  try {
    await $BillingApiService.dismissProcessErrors(props.billingId, [contractId]);
    markProcessed(contractId);
  } catch (e) {
    console.error(e);
  } finally {
    busy.value = null;
    emit('reload');
  }
};
</script>

<template>
  <div class="region__content h-full">
    <div v-if="loading" class="h-full min-h-[400px] flex items-center justify-center">
      <AppLoading :text="t('common.loading')" />
    </div>
    <div v-else class="pr-2 pb-24 h-full overflow-y-auto">
      <header class="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-slate-900">{{ t('billing_block.process_errors_title') }}</h2>
          <p class="text-sm text-slate-500 max-w-3xl">{{ t('billing_block.process_errors_help') }}</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center rounded-full bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-700">
            {{ visibleErrors.length }}
          </span>
          <button v-if="visibleErrors.length > 1" type="button" :disabled="locked" @click="retryAll"
            class="flex items-center gap-2 rounded-md px-3 py-1.5 border text-sm font-medium transition-all bg-sky-50 border-sky-200 text-sky-700 enabled:hover:bg-sky-100 disabled:opacity-50">
            <Icon name="fa6-solid:rotate-right" :class="{ 'animate-spin': busy === 'all' }" class="w-3.5 h-3.5" />
            {{ t('billing_block.process_error_retry_all') }}
          </button>
        </div>
      </header>

      <p v-if="visibleErrors.length === 0" class="py-8 text-center text-slate-500">
        {{ t('billing_block.process_errors_empty') }}
      </p>

      <table v-else class="w-full text-sm border border-slate-200 rounded-md overflow-hidden">
        <thead class="bg-slate-50 text-left text-slate-600">
          <tr>
            <th class="px-3 py-2 font-semibold">{{ t('contract') }}</th>
            <th class="px-3 py-2 font-semibold">{{ t('billing_block.process_error_reason') }}</th>
            <th class="px-3 py-2 font-semibold">{{ t('billing_block.process_error_fix') }}</th>
            <th class="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200">
          <tr v-for="err in visibleErrors" :key="err.contract_id" class="align-top">
            <td class="px-3 py-2 whitespace-nowrap">
              <button type="button" class="font-medium text-sky-700 hover:underline"
                @click="emit('open-region', { id: err.contract_id, entity: 'ContractRegion' })">
                {{ err.contract_token || err.contract_id }}
              </button>
            </td>
            <td class="px-3 py-2 text-red-700">{{ err.message }}</td>
            <td class="px-3 py-2 text-slate-600">{{ err.hint }}</td>
            <td class="px-3 py-2">
              <div class="flex justify-end gap-2">
                <button type="button" :disabled="locked" @click="retry(err.contract_id)"
                  class="flex items-center gap-1 rounded px-2 py-1 border border-sky-300 bg-white text-sky-700 enabled:hover:bg-sky-50 disabled:opacity-50 text-xs font-semibold whitespace-nowrap">
                  <Icon name="fa6-solid:rotate-right" :class="{ 'animate-spin': busy === err.contract_id }" />
                  {{ t('billing_block.process_error_retry') }}
                </button>
                <button type="button" :disabled="locked" @click="dismiss(err.contract_id)"
                  class="flex items-center gap-1 rounded px-2 py-1 border border-slate-300 bg-white text-slate-600 enabled:hover:bg-slate-50 disabled:opacity-50 text-xs font-semibold whitespace-nowrap">
                  <Icon name="fa6-solid:xmark" />
                  {{ t('billing_block.process_error_dismiss') }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
