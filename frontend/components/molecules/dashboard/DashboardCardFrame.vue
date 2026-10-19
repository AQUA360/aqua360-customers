<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { DASHBOARD_CARDS } from '~/utils/dashboardCards';

const { t } = useI18n();

const props = defineProps({
  cardKey: { type: String, required: true },
  editing: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  refreshable: { type: Boolean, default: true },
  // Text petit al costat del títol (p. ex. el període configurat)
  subtitle: { type: String, default: null },
});

const emit = defineEmits(['refresh', 'configure', 'remove']);

const meta = computed(() => DASHBOARD_CARDS[props.cardKey] || {});
</script>

<template>
  <section class="customers-shadow rounded-lg bg-white h-full flex flex-col min-h-[140px]"
    :class="{ 'ring-2 ring-sky-200 ring-dashed': editing }">
    <header class="flex items-center justify-between gap-2 px-4 pt-3 pb-2">
      <div class="flex items-center gap-2 min-w-0">
        <span v-if="editing" class="card-handle cursor-move text-slate-400 hover:text-slate-600"
          :title="t('home_dashboard.move')">
          <Icon name="fa6-solid:grip-vertical" />
        </span>
        <Icon :name="meta.icon || 'fa6-solid:square'" class="text-slate-400 shrink-0" />
        <h2 class="text-sm font-semibold text-slate-600 truncate">{{ t(`home_dashboard.cards.${cardKey}.title`) }}</h2>
        <span v-if="subtitle" class="text-xs text-slate-400 truncate">· {{ subtitle }}</span>
      </div>
      <div class="flex items-center gap-1 shrink-0">
        <slot name="actions" />
        <button v-if="refreshable && !editing" type="button" class="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          :title="t('common.load_again')" @click="emit('refresh')">
          <Icon name="fa6-solid:rotate-right" :class="{ 'animate-spin': loading }" />
        </button>
        <template v-if="editing">
          <button type="button" class="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
            :title="t('home_dashboard.configure')" @click="emit('configure')">
            <Icon name="fa6-solid:gear" />
          </button>
          <button type="button" class="p-1 rounded text-slate-400 hover:text-red-600 hover:bg-red-50"
            :title="t('home_dashboard.remove')" @click="emit('remove')">
            <Icon name="fa6-solid:trash" />
          </button>
        </template>
      </div>
    </header>
    <div class="px-4 pb-4 flex-1 min-h-0 min-w-0">
      <slot />
    </div>
  </section>
</template>
