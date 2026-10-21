<script setup>
import { ref, toRef } from 'vue';
import { useI18n } from 'vue-i18n';
import DashboardCardFrame from './DashboardCardFrame.vue';
import { useDashboardCardData } from '~/composables/useDashboardCardData';

// Lots de lectures en curs, amb el progrés de les lectures de cada un.
const props = defineProps({
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
});
const emit = defineEmits(['configure', 'remove']);

const { t } = useI18n();
const refreshKey = ref(0);
const config = toRef(() => props.item.config);
const { data, loading, error } = useDashboardCardData(props.item.key, config, refreshKey);
</script>

<template>
  <DashboardCardFrame :card-key="item.key" :editing="editing" :loading="loading"
    @refresh="refreshKey++" @configure="emit('configure')" @remove="emit('remove')">
    <div v-if="loading && !data">
      <AtomsSkeleton class="w-full" :height="3" :has_icon="false" />
    </div>
    <div v-else-if="error" class="text-sm text-red-600">
      {{ t('common.error_load') }}
      <button class="underline ml-1" @click="refreshKey++">{{ t('common.load_again') }}</button>
    </div>
    <div v-else-if="data">
      <p v-if="!data.items.length" class="text-sm text-slate-400">{{ t('home_dashboard.cards.reading_batches_in_progress.empty') }}</p>
      <ul v-else class="space-y-3">
        <li v-for="batch in data.items" :key="batch.id">
          <NuxtLink :to="`/reading/reading-batches?id=${batch.id}`" class="block hover:bg-slate-50 rounded px-1 py-1">
            <div class="flex items-center justify-between gap-2 text-sm">
              <span class="font-medium text-slate-700 truncate">{{ batch.name }}</span>
              <!-- El color de l'estat és un codi (yellow, green...), no un color CSS -->
              <AtomsColorBadge v-if="batch.status" :value="batch.status.name" :color="batch.status.color" class="shrink-0" />
            </div>
            <div class="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
              <div class="h-full bg-sky-500 transition-all" :style="{ width: `${batch.progress}%` }" />
            </div>
            <div class="mt-1 flex flex-wrap gap-x-3 text-xs text-slate-500">
              <span>{{ t('home_dashboard.readings_read', { read: batch.readings_read, total: batch.readings_total }) }} ({{ batch.progress }}%)</span>
              <span v-if="batch.readings_alerts" class="text-amber-600">
                <Icon name="fa6-solid:triangle-exclamation" class="text-[10px]" />
                {{ t('home_dashboard.readings_alerts', { count: batch.readings_alerts }) }}
              </span>
            </div>
          </NuxtLink>
        </li>
      </ul>
      <NuxtLink v-if="data.count > data.items.length" to="/reading/reading-batches" class="block text-xs text-sky-600 hover:underline mt-2">
        {{ t('home_dashboard.see_all', { count: data.count }) }}
      </NuxtLink>
    </div>
  </DashboardCardFrame>
</template>
