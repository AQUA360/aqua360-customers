<script setup>
import { computed, ref, toRef } from 'vue';
import { useI18n } from 'vue-i18n';
import DashboardCardFrame from './DashboardCardFrame.vue';
import TimeRelative from '~/components/atoms/TimeRelative.vue';
import { useDashboardCardData } from '~/composables/useDashboardCardData';

// OT per validar o canvis de comptador pendents d'aplicar: total i les més recents.
const props = defineProps({
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
});
const emit = defineEmits(['configure', 'remove']);

const { t } = useI18n();
const refreshKey = ref(0);
const config = toRef(() => props.item.config);
const { data, loading, error } = useDashboardCardData(props.item.key, config, refreshKey);

const subtitle = computed(() => props.item.config?.scope === 'created_by_me' ? t('home_dashboard.config.scope.created_by_me') : null);
</script>

<template>
  <DashboardCardFrame :card-key="item.key" :editing="editing" :loading="loading" :subtitle="subtitle"
    @refresh="refreshKey++" @configure="emit('configure')" @remove="emit('remove')">
    <div v-if="loading && !data">
      <AtomsSkeleton class="w-full" :height="3" :has_icon="false" />
    </div>
    <div v-else-if="error" class="text-sm text-red-600">
      {{ t('common.error_load') }}
      <button class="underline ml-1" @click="refreshKey++">{{ t('common.load_again') }}</button>
    </div>
    <div v-else-if="data">
      <div class="flex items-baseline gap-2 mb-2">
        <span class="text-3xl font-bold" :class="data.count ? 'text-amber-600' : 'text-slate-400'">{{ data.count }}</span>
        <span class="text-xs text-slate-400">{{ t('home_dashboard.orders') }}</span>
      </div>
      <ul v-if="data.items.length" class="divide-y divide-slate-100">
        <li v-for="order in data.items" :key="order.id">
          <NuxtLink :to="`/order/orders?id=${order.id}`"
            class="flex items-center justify-between gap-2 py-1.5 text-sm hover:bg-slate-50 rounded px-1">
            <span class="min-w-0 truncate">
              <span class="font-medium text-slate-700">{{ order.token }}</span>
              <span v-if="order.type" class="text-slate-400 ml-2">{{ order.type }}</span>
            </span>
            <span class="text-xs text-slate-400 shrink-0"><TimeRelative :datetime="order.created_at" /></span>
          </NuxtLink>
        </li>
      </ul>
      <p v-else class="text-sm text-slate-400">{{ t(`home_dashboard.cards.${item.key}.empty`) }}</p>
      <NuxtLink v-if="data.count > data.items.length" to="/order/orders" class="block text-xs text-sky-600 hover:underline mt-2">
        {{ t('home_dashboard.see_all', { count: data.count }) }}
      </NuxtLink>
    </div>
  </DashboardCardFrame>
</template>
