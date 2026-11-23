<script setup>
// Abans de processar o recalcular una facturació: si té contractes de baixa amb lectures
// per facturar, l'usuari tria quins es facturen (per defecte, cap). ask() resol amb els ids
// triats ([] si no n'hi ha cap) o amb null si l'usuari cancel·la, no s'han pogut carregar
// o ja hi ha una altra crida en marxa (un segon clic no fa res).
import { ref, computed } from 'vue';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const { $BillingApiService } = useNuxtApp();

const props = defineProps({
  billingId: Number,
});

const visible = ref(false);
const contracts = ref([]);
const selectedIds = ref([]);
let resolver = null;
let pending = false;

const allSelected = computed(() =>
  contracts.value.length > 0 && selectedIds.value.length === contracts.value.length
);

const finish = (value) => {
  visible.value = false;
  pending = false;
  const resolve = resolver;
  resolver = null;
  if (resolve) resolve(value);
};

const ask = async (recalculate = false) => {
  if (pending) return null;
  pending = true;
  let response;
  try {
    response = await $BillingApiService.getTerminatedContracts(props.billingId, recalculate);
  } catch (error) {
    console.error(error);
    toast.error(t('billing_block.terminated_contracts_error'));
    pending = false;
    return null;
  }
  const results = response?.results || [];
  if (results.length === 0) {
    pending = false;
    return [];
  }
  contracts.value = results;
  selectedIds.value = [];
  visible.value = true;
  return new Promise((resolve) => { resolver = resolve; });
};

const toggleAll = () => {
  selectedIds.value = allSelected.value ? [] : contracts.value.map(c => c.id);
};

const formatDate = (value) => (value ? new Date(value).toLocaleDateString() : '-');

defineExpose({ ask });
</script>

<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
    <div class="bg-white rounded-md shadow-md w-full max-w-2xl max-h-[80vh] flex flex-col">
      <div class="flex justify-between items-center p-4 border-b">
        <h2 class="text-xl font-semibold">{{ t('billing_block.terminated_contracts_title') }}</h2>
        <button @click="finish(null)" class="hover:text-slate-700 p-2">
          <Icon name="fa6-solid:xmark" />
        </button>
      </div>
      <div class="p-4 overflow-y-auto">
        <p class="mb-4 text-slate-600">{{ t('billing_block.terminated_contracts_text') }}</p>
        <label class="flex items-center gap-2 mb-2 font-semibold cursor-pointer">
          <input type="checkbox" :checked="allSelected" @change="toggleAll" />
          {{ t('billing_block.terminated_contracts_select_all') }}
        </label>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-slate-400 border-b">
              <th class="py-1 w-8"></th>
              <th class="py-1">{{ t('contract') }}</th>
              <th class="py-1">{{ t('common.holder') }}</th>
              <th class="py-1">{{ t('billing_block.terminated_contracts_termination_date') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="contract in contracts" :key="contract.id" class="border-b">
              <td class="py-1">
                <input type="checkbox" :value="contract.id" v-model="selectedIds" />
              </td>
              <td class="py-1">{{ contract.token }}</td>
              <td class="py-1">{{ contract.holder || '-' }}</td>
              <td class="py-1">{{ formatDate(contract.termination_date) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex justify-end gap-3 p-4 border-t">
        <button class="px-4 py-2 bg-slate-500 text-white rounded hover:bg-slate-600" @click="finish(null)">
          {{ t('common.cancel') }}
        </button>
        <button class="button-primary" @click="finish([...selectedIds])">
          <Icon name="fa6-solid:check" class="mr-2" />
          {{ t('billing_block.terminated_contracts_confirm', { count: selectedIds.length }) }}
        </button>
      </div>
    </div>
  </div>
</template>
