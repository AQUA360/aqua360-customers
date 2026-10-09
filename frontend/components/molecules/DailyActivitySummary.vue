<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatMoneyWithCurrency } from '~/utils/money';

/**
 * Widget "La meva activitat d'avui" del dashboard.
 *
 * Demana el resum del dia sense cronologia (`includeDetails: false`), que és una
 * desena de consultes de comptatge i no el detall de cada moviment, i enllaça a
 * l'informe complet. Si la crida falla, el widget no es pinta: al dashboard no hi
 * ha d'haver un bloc d'error per una dada informativa.
 */

const { t } = useI18n();
const { $DailyActivityApiService } = useNuxtApp();

const activity = ref(null);
const loading = ref(true);
const failed = ref(false);

const today = new Date().toLocaleDateString('sv-SE'); // 'YYYY-MM-DD' en horari local

const load = async () => {
  loading.value = true;
  failed.value = false;
  try {
    activity.value = await $DailyActivityApiService.getSummary({
      dateFrom: today,
      dateTo: today,
      includeDetails: false,
    });
  } catch (error) {
    console.error(error);
    failed.value = true;
    activity.value = null;
  } finally {
    loading.value = false;
  }
};

const totals = computed(() => activity.value?.totals || null);

/** Les tres categories amb més moviments, per no omplir el dashboard de files a zero. */
const topCategories = computed(() => (activity.value?.categories || []).slice(0, 3));

const hasActivity = computed(() => !!totals.value && totals.value.total_actions > 0);

onMounted(load);
</script>

<template>
  <div v-if="!failed">
    <div class="flex items-center justify-between gap-3 px-6 mb-4">
      <span class="text-sm text-slate-500 flex gap-3 items-center">
        <Icon name="fa6-solid:list-check" class="text-slate-500" />
        {{ t('daily_activity_block.dashboard_title') }}
      </span>
      <div class="flex items-center gap-3">
        <button type="button" class="text-slate-400 hover:text-slate-600" :title="t('common.load_again')"
          @click="load">
          <Icon name="fa6-solid:rotate-right" :class="{ 'animate-spin': loading }" />
        </button>
        <NuxtLink to="/billing/reports/daily-activity-summary" class="text-sm text-sky-600 hover:underline">
          {{ t('daily_activity_block.see_full_report') }}
        </NuxtLink>
      </div>
    </div>

    <div v-if="loading" class="rounded-lg p-6">
      <AtomsSkeleton class="w-full" :height="4" :has_icon="false" />
    </div>

    <div v-else-if="!hasActivity" class="customers-shadow rounded-lg bg-white p-6 text-center text-slate-500">
      {{ t('daily_activity_block.dashboard_empty') }}
    </div>

    <div v-else class="customers-shadow rounded-lg bg-white p-4">
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-3">
        <NuxtLink to="/billing/reports/daily-activity-summary"
          class="rounded-lg p-3 hover:bg-slate-50 transition-colors">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('daily_activity_block.total_actions') }}</div>
          <div class="text-2xl font-bold text-sky-700">{{ totals.total_actions }}</div>
        </NuxtLink>

        <!-- Cobraments i devolucions separats: no són la mateixa cosa, i un dia pot
             tenir només devolucions de remeses cobrades un altre dia. -->
        <div class="rounded-lg p-3">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('daily_activity_block.collections') }}</div>
          <div class="text-xl font-bold text-slate-800">
            {{ formatMoneyWithCurrency(totals.collections_charged) }}
          </div>
          <div v-if="totals.remittances_sent_count" class="text-xs text-slate-500 mt-1">
            {{ t('daily_activity_block.remittances_sent') }}: {{ totals.remittances_sent_count }} ·
            {{ formatMoneyWithCurrency(totals.collections_charged_remittances) }}
          </div>
          <div v-if="totals.collections_count" class="text-xs text-slate-500">
            {{ t('daily_activity_block.manual_collections') }}: {{ totals.collections_count }} ·
            {{ formatMoneyWithCurrency(totals.collections_charged_manual) }}
          </div>
        </div>

        <div class="rounded-lg p-3">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('daily_activity_block.returns') }}</div>
          <div class="text-xl font-bold" :class="totals.returns_count ? 'text-red-600' : 'text-slate-800'">
            {{ formatMoneyWithCurrency(totals.collections_returned) }}
          </div>
          <div v-if="totals.returns_count" class="text-xs text-slate-500 mt-1">
            {{ t('daily_activity_block.returned_receipts') }}: {{ totals.returns_count }}
          </div>
          <div v-if="totals.remittance_returns_count" class="text-xs text-slate-500">
            {{ t('daily_activity_block.return_files') }}: {{ totals.remittance_returns_count }}
          </div>
        </div>

        <div class="rounded-lg p-3">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('daily_activity_block.new_orders') }}</div>
          <div class="text-2xl font-bold text-slate-800">{{ totals.orders_count }}</div>
        </div>
        <div class="rounded-lg p-3">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ t('daily_activity_block.contract_managements') }}</div>
          <div class="text-2xl font-bold text-slate-800">{{ totals.contracts_count }}</div>
        </div>
      </div>

      <div class="border-t border-slate-100 pt-3 space-y-1">
        <div v-for="category in topCategories" :key="category.key"
          class="flex items-center justify-between gap-3 text-sm px-3">
          <span class="text-slate-600 truncate">{{ category.label }}</span>
          <span class="font-medium text-slate-800 shrink-0">{{ category.count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
