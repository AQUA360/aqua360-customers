<script setup>
import { computed, ref, toRef } from 'vue';
import { useI18n } from 'vue-i18n';
import DashboardCardFrame from './DashboardCardFrame.vue';
import { useDashboardCardData } from '~/composables/useDashboardCardData';
import { DASHBOARD_CARDS } from '~/utils/dashboardCards';
import { formatMoneyWithCurrency } from '~/utils/money';
import { formatDate } from '~/utils/date';

// Card de facturació: nombre i import de factures d'un període, comparat amb l'anterior.
const props = defineProps({
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
});
const emit = defineEmits(['configure', 'remove']);

const { t } = useI18n();
const refreshKey = ref(0);
const config = toRef(() => props.item.config);
const { data, loading, error } = useDashboardCardData(props.item.key, config, refreshKey);

const tone = computed(() => DASHBOARD_CARDS[props.item.key]?.tone || 'neutral');
const amountClass = computed(() => ({
  positive: 'text-emerald-700',
  negative: 'text-red-600',
  neutral: 'text-slate-800',
}[tone.value]));

const variation = computed(() => {
  if (!data.value || !data.value.previous_count) return null;
  return Math.round(100 * (data.value.count - data.value.previous_count) / data.value.previous_count);
});

const subtitle = computed(() => props.item.config?.period ? t(`home_dashboard.config.period.${props.item.config.period}`) : null);
</script>

<template>
  <DashboardCardFrame :card-key="item.key" :editing="editing" :loading="loading" :subtitle="subtitle"
    @refresh="refreshKey++" @configure="emit('configure')" @remove="emit('remove')">
    <div v-if="loading && !data">
      <AtomsSkeleton class="w-full" :height="2" :has_icon="false" />
    </div>
    <div v-else-if="error" class="text-sm text-red-600">
      {{ t('common.error_load') }}
      <button class="underline ml-1" @click="refreshKey++">{{ t('common.load_again') }}</button>
    </div>
    <NuxtLink v-else-if="data" to="/billing/invoice" class="block group">
      <div class="flex items-baseline gap-2">
        <span class="text-3xl font-bold text-slate-800 group-hover:text-sky-700">{{ data.count }}</span>
        <span class="text-xs text-slate-400">{{ t('home_dashboard.invoices') }}</span>
      </div>
      <div class="text-lg font-semibold" :class="amountClass">{{ formatMoneyWithCurrency(data.amount) }}</div>
      <div class="mt-2 text-xs text-slate-400 flex flex-wrap gap-x-2">
        <span>{{ formatDate(data.date_from) }} – {{ formatDate(data.date_to) }}</span>
        <span v-if="variation !== null" :class="variation >= 0 ? 'text-emerald-600' : 'text-red-500'"
          :title="t('home_dashboard.previous_period', { count: data.previous_count })">
          <Icon :name="variation >= 0 ? 'fa6-solid:arrow-up' : 'fa6-solid:arrow-down'" class="text-[10px]" />
          {{ Math.abs(variation) }}% {{ t('home_dashboard.vs_previous') }}
        </span>
      </div>
    </NuxtLink>
  </DashboardCardFrame>
</template>
