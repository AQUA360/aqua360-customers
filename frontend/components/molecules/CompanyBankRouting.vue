<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import AppLoading from '~/components/atoms/AppLoading.vue';

// Mapa d'encaminament de remeses de l'empresa: per cada entitat bancària del
// client, a quin compte de l'empresa es cobren les remeses (`collection`) i des
// de quin es fan les transferències de retorn (`transfer`). Cada operació té
// el seu mapa i es mostra en una columna. Sense cap assignació, tot va al
// compte de la fila "Per defecte" de l'operació.
const OPERATIONS = ['collection', 'transfer'];

const props = defineProps({
  company_id: {
    type: [Number, String],
    default: null
  },
  // Operacions que s'ensenyen. A la pantalla de remeses només interessa la de
  // la remesa que s'està preparant. (Literal: `defineProps` no pot fer
  // referència a `OPERATIONS`.)
  operations: {
    type: Array,
    default: () => ['collection', 'transfer'],
  },
});

const { t } = useI18n();
const toast = useToast();
const { $ExploitationApiService } = useNuxtApp();

const shownOperations = computed(() => OPERATIONS.filter(operation => props.operations.includes(operation)));
const operationLabel = (operation) => t(operation === 'transfer' ? 'billing_block.transfer_from' : 'billing_block.remit_to');

const emptySpecial = () => ({ foreign: {}, default: {} });
const emptyByOperation = (factory) => Object.fromEntries(OPERATIONS.map(operation => [operation, factory()]));

const loading = ref(false);
const saving = ref(false);
// Cada fila porta `routes`: `{collection: id_compte|null, transfer: id_compte|null}`.
const rows = ref([]);
const companyBanks = ref([]);
const special = ref(emptyByOperation(emptySpecial));
// Compte on va tot el que no està assignat, per operació. El calcula el
// backend amb la mateixa funció que la generació de la remesa, per no
// divergir-ne.
const effectiveDefault = ref(emptyByOperation(() => ({ bank: null, explicit: true })));
const onlyUsed = ref(true);
const search = ref('');
const selected = ref(new Set());
const bulkBank = ref('');
const bulkOperation = ref('all');

// El backend torna les claus de cobrament a l'arrel (com abans que hi hagués
// transferències) i les de transferència dins de `transfer`.
const operationData = (result, operation) => (operation === 'transfer' ? result.transfer || {} : result);

// De 572 entitats del catàleg només se'n fan servir unes desenes: per defecte
// només es mostren les que té algun client, i el commutador ensenya la resta.
const load = async () => {
  if (!props.company_id) return;
  loading.value = true;
  try {
    const result = await $ExploitationApiService.getBankRoutingMatrix(props.company_id, {
      only_used: onlyUsed.value,
      search: search.value,
    });
    rows.value = (result.banks || []).map(row => ({
      ...row,
      routes: {
        collection: row.company_bank || null,
        transfer: row.transfer?.company_bank || null,
      },
    }));
    companyBanks.value = result.company_banks || [];
    OPERATIONS.forEach(operation => {
      const data = operationData(result, operation);
      special.value[operation] = data.special || emptySpecial();
      effectiveDefault.value[operation] = {
        bank: data.effective_default || null,
        explicit: data.effective_default_is_explicit !== false,
      };
    });
    selected.value = new Set();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    loading.value = false;
  }
};

const bankLabel = (companyBank) => {
  const name = companyBank.bank_name || t('common.bank');
  const tail = companyBank.iban ? ' ···' + companyBank.iban.slice(-4) : '';
  return name + tail + (companyBank.is_default ? ` (${t('billing_block.by_default')})` : '');
};

const assignedCount = computed(() => rows.value.filter(
  row => shownOperations.value.some(operation => row.routes[operation])
).length);

const clientsByBank = computed(() => {
  // Quants clients quedarien a cada compte segons el mapa de cada operació.
  // Els que no tenen assignació expressa cauen a la fila "Per defecte".
  return Object.fromEntries(shownOperations.value.map(operation => {
    const totals = {};
    let unassigned = 0;
    rows.value.forEach(row => {
      const companyBank = row.routes[operation];
      if (companyBank) {
        totals[companyBank] = (totals[companyBank] || 0) + (row.clients || 0);
      } else {
        unassigned += row.clients || 0;
      }
    });
    const fallback = special.value[operation]?.default?.company_bank || effectiveDefault.value[operation].bank;
    if (fallback) totals[fallback] = (totals[fallback] || 0) + unassigned;
    return [operation, { totals, unassigned, fallback }];
  }));
});

const estimateWarnings = computed(() => shownOperations.value
  .map(operation => {
    const estimate = clientsByBank.value[operation];
    if (!estimate.fallback && estimate.unassigned) {
      return { operation, text: `${estimate.unassigned} ${t('billing_block.info_clients_without_routing')}` };
    }
    if (!effectiveDefault.value[operation].explicit) {
      return { operation, text: t('billing_block.info_default_not_chosen') };
    }
    return null;
  })
  .filter(Boolean));

const setRowBank = async (row, operation, companyBankId) => {
  saving.value = true;
  try {
    await $ExploitationApiService.saveBankRoutingBulk(
      props.company_id, companyBankId || null, [row.bank], operation
    );
    row.routes[operation] = companyBankId || null;
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
};

const applyBulk = async () => {
  if (!selected.value.size) return;
  saving.value = true;
  try {
    const banks = Array.from(selected.value);
    const operations = bulkOperation.value === 'all' ? shownOperations.value : [bulkOperation.value];
    for (const operation of operations) {
      await $ExploitationApiService.saveBankRoutingBulk(
        props.company_id, bulkBank.value || null, banks, operation
      );
      rows.value.forEach(row => {
        if (selected.value.has(row.bank)) row.routes[operation] = bulkBank.value || null;
      });
    }
    selected.value = new Set();
    toast.success(t('billing_block.routing_saved'));
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
};

const setSpecial = async (operation, matchType, companyBankId) => {
  saving.value = true;
  try {
    await $ExploitationApiService.saveBankRoutingSpecial(
      props.company_id, matchType, companyBankId || null, operation
    );
    special.value[operation] = {
      ...special.value[operation],
      [matchType]: { ...(special.value[operation][matchType] || {}), company_bank: companyBankId || null },
    };
    if (matchType === 'default') {
      // Treure la fila torna el per defecte al compte marcat a la fitxa, que
      // només sap el backend: es rellegeix en comptes d'endevinar-lo.
      if (companyBankId) {
        effectiveDefault.value[operation] = { bank: companyBankId, explicit: true };
      } else {
        await load();
      }
    }
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
};

const saveName = async (row) => {
  const name = (row.name || '').trim();
  try {
    const result = await $ExploitationApiService.saveBankName(row.bank, name);
    row.name = result?.name || null;
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  }
};

const toggleRow = (row) => {
  const next = new Set(selected.value);
  if (next.has(row.bank)) next.delete(row.bank); else next.add(row.bank);
  selected.value = next;
};

const allSelected = computed(() => rows.value.length > 0 && selected.value.size === rows.value.length);

const toggleAll = () => {
  selected.value = allSelected.value ? new Set() : new Set(rows.value.map(row => row.bank));
};

// Una columna de 220px per operació, al costat de la descripció.
const specialGridStyle = computed(() => ({
  gridTemplateColumns: `1fr repeat(${shownOperations.value.length}, 220px)`,
}));

let searchTimer = null;
watch(search, () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(load, 350);
});
watch(onlyUsed, load);
watch(() => props.company_id, load);

onMounted(load);
</script>

<template>
  <div class="w-full">
    <div class="flex flex-wrap items-start justify-between gap-2 mb-3">
      <div>
        <h3 class="text-base font-semibold text-slate-700">{{ t('billing_block.bank_routing') }}</h3>
        <p class="text-xs text-slate-500 mt-0.5 max-w-xl">{{ t('billing_block.info_bank_routing') }}</p>
      </div>
      <span class="text-xs text-slate-500 whitespace-nowrap">
        {{ assignedCount }} / {{ rows.length }} {{ t('billing_block.assigned_entities') }}
      </span>
    </div>

    <div v-if="!companyBanks.length && !loading"
      class="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      {{ t('billing_block.info_routing_without_banks') }}
    </div>

    <!-- Amb un sol compte no hi ha res a encaminar: tot hi va igualment. -->
    <div v-else-if="companyBanks.length === 1 && !loading"
      class="rounded border border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-600">
      {{ t('billing_block.info_routing_single_bank') }}
    </div>

    <template v-else>

    <!-- Files especials: manen menys que una entitat concreta i més que res més -->
    <div class="mb-4 border border-slate-200 rounded bg-white divide-y divide-slate-100">
      <div v-if="shownOperations.length > 1" class="grid items-center gap-2 px-3 py-1.5 bg-slate-100"
        :style="specialGridStyle">
        <span></span>
        <span v-for="operation in shownOperations" :key="operation" class="text-xs font-medium text-slate-600">
          {{ operationLabel(operation) }}
        </span>
      </div>
      <div class="grid items-center gap-2 px-3 py-2" :style="specialGridStyle">
        <div>
          <span class="text-sm font-medium text-slate-700">{{ t('billing_block.foreign_iban') }}</span>
          <p class="text-xs text-slate-500">{{ t('billing_block.info_foreign_iban') }}</p>
        </div>
        <select v-for="operation in shownOperations" :key="operation" class="input py-1 text-sm"
          :value="special[operation].foreign?.company_bank || ''" :title="operationLabel(operation)"
          @change="setSpecial(operation, 'foreign', $event.target.value ? Number($event.target.value) : null)">
          <option value="">{{ t('billing_block.use_default_routing') }}</option>
          <option v-for="companyBank in companyBanks" :key="companyBank.id" :value="companyBank.id">
            {{ bankLabel(companyBank) }}
          </option>
        </select>
      </div>
      <div class="grid items-center gap-2 px-3 py-2 bg-sky-50/60" :style="specialGridStyle">
        <div>
          <span class="text-sm font-medium text-slate-700">{{ t('billing_block.default_routing') }}</span>
          <p class="text-xs text-slate-500">{{ t('billing_block.info_default_routing') }}</p>
        </div>
        <select v-for="operation in shownOperations" :key="operation" class="input py-1 text-sm"
          :value="special[operation].default?.company_bank || ''" :title="operationLabel(operation)"
          @change="setSpecial(operation, 'default', $event.target.value ? Number($event.target.value) : null)">
          <option value="">{{ t('billing_block.company_default_bank') }}</option>
          <option v-for="companyBank in companyBanks" :key="companyBank.id" :value="companyBank.id">
            {{ bankLabel(companyBank) }}
          </option>
        </select>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2 mb-2">
      <div class="relative flex-1 min-w-[180px] max-w-sm">
        <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
          <Icon name="fa6-solid:magnifying-glass" class="text-sm" />
        </div>
        <input v-model="search" type="text" :placeholder="t('billing_block.search_bank_entity')"
          class="pl-8 pr-3 py-1.5 w-full text-sm border border-slate-300 rounded focus:ring-1 focus:ring-slate-400" />
      </div>
      <label class="flex items-center gap-1.5 text-sm text-slate-600">
        <input type="checkbox" v-model="onlyUsed" />
        {{ t('billing_block.only_used_entities') }}
      </label>
      <div v-if="selected.size" class="flex items-center gap-2 ml-auto">
        <span class="text-xs text-slate-500">{{ selected.size }} {{ t('common.selected') }}</span>
        <select v-if="shownOperations.length > 1" v-model="bulkOperation" class="input py-1 text-sm max-w-[200px]">
          <option value="all">{{ t('billing_block.all_routing_operations') }}</option>
          <option v-for="operation in shownOperations" :key="operation" :value="operation">
            {{ operationLabel(operation) }}
          </option>
        </select>
        <select v-model="bulkBank" class="input py-1 text-sm max-w-[200px]">
          <option value="">{{ t('billing_block.use_default_routing') }}</option>
          <option v-for="companyBank in companyBanks" :key="companyBank.id" :value="companyBank.id">
            {{ bankLabel(companyBank) }}
          </option>
        </select>
        <button type="button" class="button-default py-1" :disabled="saving" @click="applyBulk">
          {{ t('billing_block.apply_to_selection') }}
        </button>
      </div>
    </div>

    <div class="border border-slate-200 rounded bg-white">
      <div v-if="loading" class="flex justify-center py-10">
        <AppLoading :size="32" />
      </div>
      <div v-else class="overflow-auto" style="max-height: 55vh;">
        <table class="w-full text-sm border-collapse">
          <thead class="sticky top-0 bg-slate-100 border-b border-slate-200 text-slate-600 font-medium">
            <tr>
              <th class="w-8 py-1.5 px-2">
                <input type="checkbox" :checked="allSelected" @change="toggleAll" />
              </th>
              <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ t('billing_block.bank_entity') }}</th>
              <th class="text-left py-1.5 px-2">{{ t('common.name') }}</th>
              <th class="text-right py-1.5 px-2 whitespace-nowrap">{{ t('billing_block.clients_count') }}</th>
              <th v-for="operation in shownOperations" :key="operation" class="text-left py-1.5 px-2 w-[230px]">
                {{ operationLabel(operation) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td :colspan="4 + shownOperations.length" class="py-4 px-2 text-center text-slate-500">{{ t('common.no_data_found') }}</td>
            </tr>
            <tr v-for="row in rows" :key="row.bank" class="border-b border-slate-100"
              :class="{ 'bg-sky-50/60': selected.has(row.bank) }">
              <td class="py-1 px-2">
                <input type="checkbox" :checked="selected.has(row.bank)" @change="toggleRow(row)" />
              </td>
              <td class="py-1 px-2 font-mono text-slate-700 whitespace-nowrap">{{ row.token }}</td>
              <td class="py-1 px-2 text-slate-700">
                <!-- El nom del catàleg és editable aquí mateix: hi ha entitats
                     molt usades que van arribar sense nom de la importació. -->
                <input v-model="row.name" type="text" :placeholder="t('billing_block.bank_name_placeholder')"
                  :title="t('billing_block.edit_bank_name')" @change="saveName(row)"
                  class="w-full bg-transparent px-1 py-0.5 rounded border border-transparent hover:border-slate-300 focus:border-sky-400 focus:bg-white focus:outline-none placeholder:italic placeholder:text-slate-400" />
              </td>
              <td class="py-1 px-2 text-right text-slate-500">{{ row.clients }}</td>
              <td v-for="operation in shownOperations" :key="operation" class="py-1 px-2">
                <select class="input py-0.5 text-sm w-full" :value="row.routes[operation] || ''" :disabled="saving"
                  @change="setRowBank(row, operation, $event.target.value ? Number($event.target.value) : null)">
                  <option value="">{{ t('billing_block.use_default_routing') }}</option>
                  <option v-for="companyBank in companyBanks" :key="companyBank.id" :value="companyBank.id">
                    {{ bankLabel(companyBank) }}
                  </option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Estimació amb els clients de cada entitat, per veure l'efecte del mapa
         sense haver de generar cap remesa -->
    <div v-if="companyBanks.length" class="mt-3 border border-slate-200 rounded bg-slate-50 px-3 py-2">
      <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
        {{ t('billing_block.routing_estimate') }}
      </p>
      <table class="w-full text-sm text-slate-700">
        <thead v-if="shownOperations.length > 1">
          <tr class="text-xs text-slate-500">
            <th></th>
            <th v-for="operation in shownOperations" :key="operation" class="text-right font-medium py-0.5 pl-3">
              {{ operationLabel(operation) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="companyBank in companyBanks" :key="companyBank.id">
            <td class="py-0.5">{{ bankLabel(companyBank) }}</td>
            <td v-for="operation in shownOperations" :key="operation" class="py-0.5 pl-3 text-right font-medium">
              {{ clientsByBank[operation].totals[companyBank.id] || 0 }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-for="warning in estimateWarnings" :key="warning.operation" class="text-xs text-amber-700 mt-1">
        <template v-if="shownOperations.length > 1">{{ operationLabel(warning.operation) }}: </template>{{ warning.text }}
      </p>
    </div>
    </template>
  </div>
</template>
