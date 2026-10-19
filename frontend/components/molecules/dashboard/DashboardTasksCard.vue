<script setup>
import { computed, ref, toRef } from 'vue';
import { useI18n } from 'vue-i18n';
import DashboardCardFrame from './DashboardCardFrame.vue';
import { useDashboardCardData } from '~/composables/useDashboardCardData';
import { formatDate } from '~/utils/date';
import { taskDotClass } from '~/utils/calendarTasks';

// Tasques pendents d'avui i endarrerides; es poden marcar com a fetes des d'aquí.
const props = defineProps({
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
});
const emit = defineEmits(['configure', 'remove']);

const { t } = useI18n();
const { $CalendarTaskApiService } = useNuxtApp();
const sidebarStore = useSidebarStore();
const refreshKey = ref(0);
const config = toRef(() => props.item.config);
const { data, loading, error } = useDashboardCardData(props.item.key, config, refreshKey);

const subtitle = computed(() => props.item.config?.scope === 'mine' ? t('home_dashboard.config.scope.mine') : null);

const markDone = async (task) => {
  try {
    await $CalendarTaskApiService.setDone(task.id, true);
    sidebarStore.tasksChanged();
  } catch (err) {
    console.error(err);
  } finally {
    refreshKey.value++;
  }
};
</script>

<template>
  <DashboardCardFrame :card-key="item.key" :editing="editing" :loading="loading" :subtitle="subtitle"
    @refresh="refreshKey++" @configure="emit('configure')" @remove="emit('remove')">
    <template #actions>
      <NuxtLink v-if="!editing" to="/calendar" class="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
        :title="t('calendar_tasks.open_calendar')">
        <Icon name="fa6-solid:up-right-from-square" />
      </NuxtLink>
    </template>
    <div v-if="loading && !data">
      <AtomsSkeleton class="w-full" :height="3" :has_icon="false" />
    </div>
    <div v-else-if="error" class="text-sm text-red-600">
      {{ t('common.error_load') }}
      <button class="underline ml-1" @click="refreshKey++">{{ t('common.load_again') }}</button>
    </div>
    <div v-else-if="data">
      <div class="flex gap-4 mb-2 text-sm">
        <span><strong class="text-2xl text-slate-800">{{ data.today }}</strong> <span class="text-slate-400">{{ t('calendar_tasks.today') }}</span></span>
        <span v-if="data.overdue"><strong class="text-2xl text-red-600">{{ data.overdue }}</strong> <span class="text-slate-400">{{ t('calendar_tasks.overdue') }}</span></span>
      </div>
      <p v-if="!data.items.length" class="text-sm text-slate-400">{{ t('calendar_tasks.nothing_pending') }}</p>
      <ul v-else class="divide-y divide-slate-100">
        <li v-for="task in data.items" :key="task.id" class="flex items-center gap-2 py-1.5 text-sm">
          <input type="checkbox" class="shrink-0" :title="t('calendar_tasks.mark_done')" @change="markDone(task)" />
          <span class="h-2 w-2 rounded-full shrink-0" :class="taskDotClass(task.color)" />
          <NuxtLink :to="`/calendar?date=${task.set_date}`" class="min-w-0 truncate text-slate-700 hover:text-sky-700">
            {{ task.name }}
          </NuxtLink>
          <Icon v-if="task.is_recurring" name="fa6-solid:repeat" class="text-slate-300 text-xs shrink-0" :title="t('calendar_tasks.recurring')" />
          <Icon v-if="task.source === 'auto'" name="fa6-solid:robot" class="text-slate-300 text-xs shrink-0" :title="t('calendar_tasks.automatic')" />
          <span class="ml-auto text-xs shrink-0" :class="task.is_overdue ? 'text-red-500' : 'text-slate-400'">
            {{ task.is_overdue ? formatDate(task.set_date) : (task.time ? task.time.slice(0, 5) : '') }}
          </span>
        </li>
      </ul>
    </div>
  </DashboardCardFrame>
</template>
