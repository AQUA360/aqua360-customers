<script setup>
// Abans de processar o recalcular una facturació: si té contractes amb el titular insolvent,
// se'n avisa l'usuari (es facturen igualment). ask() resol amb true si es pot continuar
// (no n'hi ha cap o l'usuari accepta) i amb false si cancel·la o no s'han pogut carregar.
import { ref } from 'vue';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const { $BillingApiService } = useNuxtApp();

const props = defineProps({
  billingId: Number,
});

const visible = ref(false);
const contracts = ref([]);
let resolver = null;
let pending = false;

const finish = (value) => {
  visible.value = false;
  pending = false;
  const resolve = resolver;
  resolver = null;
  if (resolve) resolve(value);
};

const ask = async (recalculate = false) => {
  if (pending) return false;
  pending = true;
  let response;
  try {
    response = await $BillingApiService.getInsolventHolders(props.billingId, recalculate);
  } catch (error) {
    console.error(error);
    toast.error(t('common.error_load'));
    pending = false;
    return false;
  }
  const results = response?.results || [];
  if (results.length === 0) {
    pending = false;
    return true;
  }
  contracts.value = results;
  visible.value = true;
  return new Promise((resolve) => { resolver = resolve; });
};

defineExpose({ ask });
</script>

<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
    <div class="bg-white rounded-md shadow-md w-full max-w-2xl max-h-[80vh] flex flex-col">
      <div class="flex justify-between items-center p-4 border-b">
        <h2 class="text-xl font-semibold flex items-center gap-2">
          <Icon name="fa6-solid:triangle-exclamation" class="text-red-600" />
          {{ t('insolvency.billing_warning_title') }}
        </h2>
        <button @click="finish(false)" class="hover:text-slate-700 p-2">
          <Icon name="fa6-solid:xmark" />
        </button>
      </div>
      <div class="p-4 overflow-y-auto">
        <p class="mb-4 text-slate-600">{{ t('insolvency.billing_warning_text') }}</p>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-slate-400 border-b">
              <th class="py-1">{{ t('insolvency.contract') }}</th>
              <th class="py-1">{{ t('insolvency.holder') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="contract in contracts" :key="contract.id" class="border-b">
              <td class="py-1">{{ contract.token }}</td>
              <td class="py-1">{{ contract.holder || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex justify-end gap-3 p-4 border-t">
        <button class="px-4 py-2 bg-slate-500 text-white rounded hover:bg-slate-600" @click="finish(false)">
          {{ t('insolvency.cancel') }}
        </button>
        <button class="button-primary" @click="finish(true)">
          <Icon name="fa6-solid:check" class="mr-2" />
          {{ t('insolvency.continue') }}
        </button>
      </div>
    </div>
  </div>
</template>
