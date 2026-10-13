<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import AppLoading from '~/components/atoms/AppLoading.vue';

// Mapa d'encaminament de remeses de l'empresa: per cada entitat bancària del
// PAGADOR, a quin compte de l'empresa s'ha de remesar. Sense cap assignació,
// tot va al compte de la fila "Per defecte".
const props = defineProps({
  company_id: {
    type: [Number, String],
    default: null
  },
});

const { t } = useI18n();
const toast = useToast();
const { $ExploitationApiService } = useNuxtApp();

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const companyBanks = ref([]);
const special = ref({ foreign: {}, default: {} });
// Compte on va tot el que no està assignat. El calcula el backend amb la
// mateixa funció que la generació de la remesa, per no divergir-ne.
const effectiveDefault = ref(null);
const effectiveDefaultIsExplicit = ref(true);
const onlyUsed = ref(true);
const search = ref('');
const selected = ref(new Set());
const bulkBank = ref('');

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
    rows.value = result.banks || [];
    companyBanks.value = result.company_banks || [];
    special.value = result.special || { foreign: {}, default: {} };
    effectiveDefault.value = result.effective_default || null;
    effectiveDefaultIsExplicit.value = result.effective_default_is_explicit !== false;
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

const assignedCount = computed(() => rows.value.filter(row => row.company_bank).length);

const clientsByBank = computed(() => {
  // Quants clients quedarien a cada compte segons el mapa actual. Els que no
  // tenen assignació expressa cauen a la fila "Per defecte".
  const totals = {};
  let unassigned = 0;
  rows.value.forEach(row => {
    if (row.company_bank) {
      totals[row.company_bank] = (totals[row.company_bank] || 0) + (row.clients || 0);
    } else {
      unassigned += row.clients || 0;
    }
  });
  const fallback = special.value?.default?.company_bank || effectiveDefault.value;
  if (fallback) totals[fallback] = (totals[fallback] || 0) + unassigned;
  return { totals, unassigned, fallback };
});

const setRowBank = async (row, companyBankId) => {
  saving.value = true;
  try {
    await $ExploitationApiService.saveBankRoutingBulk(
      props.company_id, companyBankId || null, [row.bank]
    );
    row.company_bank = companyBankId || null;
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
    await $ExploitationApiService.saveBankRoutingBulk(
      props.company_id, bulkBank.value || null, banks
    );
    rows.value.forEach(row => {
      if (selected.value.has(row.bank)) row.company_bank = bulkBank.value || null;
    });
    selected.value = new Set();
    toast.success(t('billing_block.routing_saved'));
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
};

const setSpecial = async (matchType, companyBankId) => {
  saving.value = true;
  try {
    await $ExploitationApiService.saveBankRoutingSpecial(
      props.company_id, matchType, companyBankId || null
    );
    special.value = {
      ...special.value,
      [matchType]: { ...(special.value[matchType] || {}), company_bank: companyBankId || null },
    };
    if (matchType === 'default') {
      // Treure la fila torna el per defecte al compte marcat a la fitxa, que
      // només sap el backend: es rellegeix en comptes d'endevinar-lo.
      if (companyBankId) {
        effectiveDefault.value = companyBankId;
        effectiveDefaultIsExplicit.value = true;
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
      <div class="grid grid-cols-[1fr,220px] items-center gap-2 px-3 py-2">
        <div>
          <span class="text-sm font-medium text-slate-700">{{ t('billing_block.foreign_iban') }}</span>
          <p class="text-xs text-slate-500">{{ t('billing_block.info_foreign_iban') }}</p>
        </div>
        <select class="input py-1 text-sm" :value="special.foreign?.company_bank || ''"
          @change="setSpecial('foreign', $event.target.value ? Number($event.target.value) : null)">
          <option value="">{{ t('billing_block.use_default_routing') }}</option>
          <option v-for="companyBank in companyBanks" :key="companyBank.id" :value="companyBank.id">
            {{ bankLabel(companyBank) }}
          </option>
        </select>
      </div>
      <div class="grid grid-cols-[1fr,220px] items-center gap-2 px-3 py-2 bg-sky-50/60">
        <div>
          <span class="text-sm font-medium text-slate-700">{{ t('billing_block.default_routing') }}</span>
          <p class="text-xs text-slate-500">{{ t('billing_block.info_default_routing') }}</p>
        </div>
        <select class="input py-1 text-sm" :value="special.default?.company_bank || ''"
          @change="setSpecial('default', $event.target.value ? Number($event.target.value) : null)">
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
              <th class="text-left py-1.5 px-2 w-[230px]">{{ t('billing_block.remit_to') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td colspan="5" class="py-4 px-2 text-center text-slate-500">{{ t('common.no_data_found') }}</td>
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
              <td class="py-1 px-2">
                <select class="input py-0.5 text-sm w-full" :value="row.company_bank || ''" :disabled="saving"
                  @change="setRowBank(row, $event.target.value ? Number($event.target.value) : null)">
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
      <div v-for="companyBank in companyBanks" :key="companyBank.id"
        class="flex justify-between text-sm text-slate-700 py-0.5">
        <span>{{ bankLabel(companyBank) }}</span>
        <span class="font-medium">{{ clientsByBank.totals[companyBank.id] || 0 }}</span>
      </div>
      <p v-if="!clientsByBank.fallback && clientsByBank.unassigned" class="text-xs text-amber-700 mt-1">
        {{ clientsByBank.unassigned }} {{ t('billing_block.info_clients_without_routing') }}
      </p>
      <p v-else-if="!effectiveDefaultIsExplicit" class="text-xs text-amber-700 mt-1">
        {{ t('billing_block.info_default_not_chosen') }}
      </p>
    </div>
    </template>
  </div>
</template>
