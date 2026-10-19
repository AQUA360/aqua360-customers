<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  format, parseISO, isValid, startOfMonth, endOfMonth, startOfWeek, endOfWeek, addDays, addMonths, addWeeks,
  isSameMonth, isToday,
} from 'date-fns';
import CalendarTaskRegion from '~/components/organisms/CalendarTaskRegion.vue';
import { taskChipClass, taskDotClass, WEEKDAY_KEYS } from '~/utils/calendarTasks';
import { formatDate, formatDateVerbose } from '~/utils/date';

/**
 * Calendari de tasques: vista mensual, setmanal i de llista, amb filtres i
 * accés al detall de cada dia (CalendarTaskRegion) per crear o editar tasques.
 */

const { t } = useI18n();
const route = useRoute();
const { $CalendarTaskApiService } = useNuxtApp();
const sidebarStore = useSidebarStore();

// ?date=YYYY-MM-DD (des d'una notificació o una card); si no és una data vàlida, s'ignora
/** Parse a valid ISO date query string, returning null for invalid input. */
const queryDate = (value) => {
  if (typeof value !== 'string') return null;
  const date = parseISO(value);
  return isValid(date) ? date : null;
};

const VIEWS = ['month', 'week', 'list'];
const LIST_DAYS = 30;
const MONTH_CHIPS = 3;

const view = ref('month');
const currentDate = ref(queryDate(route.query.date) || new Date());
const assigned = ref('');
const showDone = ref(false);
const search = ref('');

const tasks = ref([]);
const overdueTasks = ref([]);
const pending = ref(false);

const preference = ref(null);
const savingPreference = ref(false);

const regionDate = ref(null);
const isSubRegionOpen = ref(false);

/** Format a date as the local calendar date key YYYY-MM-DD. */
const dateKey = (date) => format(date, 'yyyy-MM-dd');
// getDay(): 0 = diumenge; WEEKDAY_KEYS comença en dilluns
/** Map a date to its translation key using Monday as the first weekday. */
const weekdayKey = (date) => WEEKDAY_KEYS[(date.getDay() + 6) % 7];

const range = computed(() => {
  if (view.value === 'week') {
    const start = startOfWeek(currentDate.value, { weekStartsOn: 1 });
    return { start, end: endOfWeek(currentDate.value, { weekStartsOn: 1 }) };
  }
  if (view.value === 'list') {
    const start = new Date();
    return { start, end: addDays(start, LIST_DAYS) };
  }
  return {
    start: startOfWeek(startOfMonth(currentDate.value), { weekStartsOn: 1 }),
    end: endOfWeek(endOfMonth(currentDate.value), { weekStartsOn: 1 }),
  };
});

const days = computed(() => {
  const result = [];
  for (let day = range.value.start; day <= range.value.end; day = addDays(day, 1)) {
    result.push({
      date: day,
      key: dateKey(day),
      isCurrentMonth: isSameMonth(day, currentDate.value),
      isToday: isToday(day),
    });
  }
  return result;
});

const tasksByDay = computed(() => tasks.value.reduce((acc, task) => {
  (acc[task.set_date] = acc[task.set_date] || []).push(task);
  return acc;
}, {}));

const listDays = computed(() => days.value.filter(day => tasksByDay.value[day.key]?.length));

const title = computed(() => {
  if (view.value === 'list') return t('calendar_tasks.next_days', { count: LIST_DAYS });
  if (view.value === 'week') return `${formatDate(dateKey(range.value.start))} – ${formatDate(dateKey(range.value.end))}`;
  return `${t(`date.${format(currentDate.value, 'MMMM').toLowerCase()}`)} ${format(currentDate.value, 'yyyy')}`;
});

const filters = computed(() => ({
  assigned: assigned.value,
  task_done: showDone.value ? '' : 'false',
  search: search.value,
}));

// Si es canvia de mes o de filtre ràpidament, només es pinta la resposta de l'última petició
let requestId = 0;
/** Load the visible range and overdue list, accepting only the latest response. */
const getData = async () => {
  const current = ++requestId;
  pending.value = true;
  try {
    const isList = view.value === 'list';
    const [response, overdue] = await Promise.all([
      $CalendarTaskApiService.getRange(dateKey(range.value.start), dateKey(range.value.end), filters.value),
      // A la llista, les endarrerides van a part (abans d'avui)
      isList ? $CalendarTaskApiService.getRange(null, null, { ...filters.value, overdue: 'true' }) : null,
    ]);
    if (current !== requestId) return;
    tasks.value = response.results;
    overdueTasks.value = overdue ? overdue.results : [];
  } catch (err) {
    console.error(err);
  } finally {
    if (current === requestId) pending.value = false;
  }
};

/** Move the calendar by weeks or months according to the active view. */
const move = (direction) => {
  if (view.value === 'week') currentDate.value = addWeeks(currentDate.value, direction);
  else currentDate.value = addMonths(currentDate.value, direction);
};

/** Reset the calendar focus to today. */
const goToday = () => {
  currentDate.value = new Date();
};

/** Reopen the task region for a day after clearing its previous selection. */
const openDay = (key) => {
  regionDate.value = null;
  isSubRegionOpen.value = false;
  nextTick(() => { regionDate.value = key; });
};

/** Clear the selected day and close the nested task region. */
const closeRegion = () => {
  regionDate.value = null;
  isSubRegionOpen.value = false;
};

/** Toggle task completion and refresh the calendar and sidebar counts. */
const toggleDone = async (task) => {
  await $CalendarTaskApiService.setDone(task.id, !task.task_done);
  sidebarStore.tasksChanged();
  getData();
};

/** Return task time as HH:mm, or an empty string when absent. */
const taskTime = (task) => task.time ? task.time.slice(0, 5) : '';

/** Load the current user task email preference. */
const loadPreference = async () => {
  try {
    preference.value = await $CalendarTaskApiService.getNotificationPreference();
  } catch (err) {
    console.error(err);
  }
};

/** Persist the opposite daily task email preference and update local state. */
const toggleEmailPreference = async () => {
  savingPreference.value = true;
  try {
    preference.value = await $CalendarTaskApiService.saveNotificationPreference({
      email_daily_tasks: !preference.value.email_daily_tasks,
    });
  } finally {
    savingPreference.value = false;
  }
};

let searchTimeout = null;
watch(search, () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(getData, 400);
});
watch([view, () => dateKey(currentDate.value), assigned, showDone], getData);
// Des d'una notificació o una card es pot arribar amb ?date= estant ja al calendari
watch(() => route.query.date, (value) => {
  const date = queryDate(value);
  if (!date) return;
  currentDate.value = date;
  openDay(dateKey(date));
});

onMounted(() => {
  getData();
  loadPreference();
  if (queryDate(route.query.date)) openDay(dateKey(queryDate(route.query.date)));
});
</script>

<template>
  <div class="w-full max-w-7xl mx-auto px-6 pb-24">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <h1 class="text-3xl font-semibold text-slate-800">{{ t('calendar_tasks.title') }}</h1>
      <div class="flex flex-wrap items-center gap-2">
        <label v-if="preference" class="flex items-center gap-2 text-sm text-slate-600 cursor-pointer mr-2"
          :title="preference.has_email ? t('calendar_tasks.email_daily_info') : t('calendar_tasks.email_missing')">
          <input type="checkbox" :checked="preference.email_daily_tasks" :disabled="savingPreference || !preference.has_email"
            @change="toggleEmailPreference" />
          <Icon name="fa6-solid:envelope" class="text-slate-400" />
          {{ t('calendar_tasks.email_daily') }}
        </label>
        <button type="button" class="button-primary" @click="openDay(dateKey(new Date()))">
          <Icon name="fa6-solid:plus" />&nbsp;{{ t('dashboard.new_task') }}
        </button>
      </div>
    </div>

    <div class="customers-shadow rounded-lg bg-white">
      <div class="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-slate-100">
        <div class="flex items-center gap-2">
          <template v-if="view !== 'list'">
            <button type="button" class="p-2 rounded-full hover:bg-slate-100" :aria-label="t('common.previous')" @click="move(-1)">
              <Icon name="fa6-solid:chevron-left" />
            </button>
            <button type="button" class="button-default" @click="goToday">{{ t('calendar_tasks.today') }}</button>
            <button type="button" class="p-2 rounded-full hover:bg-slate-100" :aria-label="t('common.next')" @click="move(1)">
              <Icon name="fa6-solid:chevron-right" />
            </button>
          </template>
          <span class="text-lg font-semibold text-slate-700 ml-2">{{ title }}</span>
          <Icon v-if="pending" name="fa6-solid:rotate-right" class="animate-spin text-slate-400" />
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <input v-model="search" type="text" class="input w-48" :placeholder="t('common.search')" />
          <select v-model="assigned" class="input w-44">
            <option value="">{{ t('calendar_tasks.filter_visible') }}</option>
            <option value="me">{{ t('calendar_tasks.filter_mine') }}</option>
            <option value="all_users">{{ t('calendar_tasks.filter_all_users') }}</option>
          </select>
          <label class="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <input v-model="showDone" type="checkbox" />
            {{ t('calendar_tasks.show_done') }}
          </label>
          <div class="flex rounded-md border border-slate-200 overflow-hidden">
            <button v-for="option in VIEWS" :key="option" type="button" class="px-3 py-1 text-sm"
              :class="view === option ? 'bg-sky-50 text-sky-700 font-semibold' : 'text-slate-600 hover:bg-slate-50'"
              @click="view = option">
              {{ t(`calendar_tasks.views.${option}`) }}
            </button>
          </div>
        </div>
      </div>

      <!-- Vista mensual -->
      <div v-if="view === 'month'" class="p-4">
        <div class="grid grid-cols-7 gap-1 mb-1">
          <div v-for="weekday in WEEKDAY_KEYS" :key="weekday" class="text-center text-xs font-semibold text-slate-500 uppercase"
            :title="t(`date.${weekday}`)">
            <span class="lg:hidden">{{ t(`date.weekdays_short.${weekday}`) }}</span>
            <span class="hidden lg:inline">{{ t(`date.${weekday}`) }}</span>
          </div>
        </div>
        <div class="grid grid-cols-7 gap-1">
          <div v-for="day in days" :key="day.key" role="button" tabindex="0"
            class="min-h-[96px] rounded-md border p-1 text-left cursor-pointer hover:border-sky-300 focus:outline-none focus:ring-2 focus:ring-sky-200"
            :class="[day.isCurrentMonth ? 'bg-white border-slate-100' : 'bg-slate-50 border-slate-50 text-slate-400', { 'ring-2 ring-sky-300': day.isToday }]"
            @click="openDay(day.key)" @keydown.enter="openDay(day.key)">
            <div class="text-xs font-semibold mb-1" :class="day.isToday ? 'text-sky-700' : ''">{{ format(day.date, 'd') }}</div>
            <div v-for="task in (tasksByDay[day.key] || []).slice(0, MONTH_CHIPS)" :key="task.id"
              class="flex items-center gap-1 text-xs rounded px-1 mb-0.5 border-l-4 truncate"
              :class="[taskChipClass(task.color), { 'line-through text-slate-400': task.task_done, 'text-red-600': task.is_overdue }]">
              <span v-if="task.time" class="text-slate-500">{{ taskTime(task) }}</span>
              <span class="truncate">{{ task.name }}</span>
              <Icon v-if="task.recurrence" name="fa6-solid:repeat" class="text-slate-400 text-[9px] shrink-0" />
            </div>
            <div v-if="(tasksByDay[day.key] || []).length > MONTH_CHIPS" class="text-xs text-slate-500 px-1">
              {{ t('calendar_tasks.more', { count: tasksByDay[day.key].length - MONTH_CHIPS }) }}
            </div>
          </div>
        </div>
      </div>

      <!-- Vista setmanal -->
      <div v-else-if="view === 'week'" class="p-4 grid grid-cols-1 md:grid-cols-7 gap-2">
        <div v-for="day in days" :key="day.key" class="rounded-md border min-h-[240px] flex flex-col"
          :class="day.isToday ? 'border-sky-300' : 'border-slate-100'">
          <button type="button" class="text-left px-2 py-1 border-b border-slate-100 hover:bg-slate-50" @click="openDay(day.key)">
            <span class="text-xs font-semibold uppercase text-slate-500" :title="t(`date.${weekdayKey(day.date)}`)">
              <span class="xl:hidden">{{ t(`date.weekdays_short.${weekdayKey(day.date)}`) }}</span>
              <span class="hidden xl:inline">{{ t(`date.${weekdayKey(day.date)}`) }}</span>
            </span>
            <span class="text-sm font-semibold ml-1" :class="day.isToday ? 'text-sky-700' : 'text-slate-700'">{{ format(day.date, 'd') }}</span>
          </button>
          <ul class="p-1 space-y-1 flex-1">
            <li v-for="task in tasksByDay[day.key] || []" :key="task.id"
              class="rounded border-l-4 px-2 py-1 text-xs" :class="taskChipClass(task.color)">
              <div class="flex items-start gap-1">
                <input type="checkbox" class="mt-0.5" :checked="task.task_done" @change="toggleDone(task)" />
                <button type="button" class="text-left min-w-0" @click="openDay(day.key)">
                  <span v-if="task.time" class="text-slate-500 mr-1">{{ taskTime(task) }}</span>
                  <span :class="{ 'line-through text-slate-400': task.task_done }">{{ task.name }}</span>
                </button>
              </div>
              <div class="flex gap-1 mt-0.5 text-slate-400">
                <Icon v-if="task.recurrence" name="fa6-solid:repeat" class="text-[9px]" :title="t('calendar_tasks.recurring')" />
                <Icon v-if="task.source === 'auto'" name="fa6-solid:robot" class="text-[9px]" :title="t('calendar_tasks.automatic')" />
                <span v-if="task.user" class="truncate">{{ task.user.username }}</span>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <!-- Vista de llista -->
      <div v-else class="p-4 space-y-6">
        <section v-if="overdueTasks.length">
          <h2 class="text-sm font-semibold text-red-600 mb-2">{{ t('calendar_tasks.overdue') }} ({{ overdueTasks.length }})</h2>
          <ul class="divide-y divide-slate-100">
            <li v-for="task in overdueTasks" :key="task.id" class="flex items-center gap-3 py-2 text-sm">
              <input type="checkbox" :checked="task.task_done" @change="toggleDone(task)" />
              <span class="h-2 w-2 rounded-full shrink-0" :class="taskDotClass(task.color)" />
              <button type="button" class="text-left text-slate-700 hover:text-sky-700" @click="openDay(task.set_date)">{{ task.name }}</button>
              <span class="ml-auto text-xs text-red-500">{{ formatDate(task.set_date) }}</span>
            </li>
          </ul>
        </section>
        <section v-for="day in listDays" :key="day.key">
          <h2 class="text-sm font-semibold mb-2" :class="day.isToday ? 'text-sky-700' : 'text-slate-600'">
            {{ formatDateVerbose(day.key) }}
          </h2>
          <ul class="divide-y divide-slate-100">
            <li v-for="task in tasksByDay[day.key]" :key="task.id" class="flex items-center gap-3 py-2 text-sm">
              <input type="checkbox" :checked="task.task_done" @change="toggleDone(task)" />
              <span class="h-2 w-2 rounded-full shrink-0" :class="taskDotClass(task.color)" />
              <span v-if="task.time" class="text-xs text-slate-500 w-10">{{ taskTime(task) }}</span>
              <button type="button" class="text-left min-w-0 truncate hover:text-sky-700"
                :class="task.task_done ? 'line-through text-slate-400' : 'text-slate-700'" @click="openDay(day.key)">
                {{ task.name }}
              </button>
              <Icon v-if="task.recurrence" name="fa6-solid:repeat" class="text-slate-300 text-xs" :title="t('calendar_tasks.recurring')" />
              <Icon v-if="task.source === 'auto'" name="fa6-solid:robot" class="text-slate-300 text-xs" :title="t('calendar_tasks.automatic')" />
              <NuxtLink v-if="task.order" :to="`/order/orders?id=${task.order.id}`" class="text-xs text-sky-600 hover:underline">
                {{ task.order.token }}
              </NuxtLink>
              <span class="ml-auto text-xs text-slate-400">{{ task.user ? task.user.username : t('calendar_tasks.everyone') }}</span>
            </li>
          </ul>
        </section>
        <p v-if="!pending && !listDays.length && !overdueTasks.length" class="text-center text-slate-400 py-8">
          {{ t('calendar_tasks.nothing_pending') }}
        </p>
      </div>
    </div>

    <div v-if="regionDate" role="region"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 z-10 ease py-2 text-base bg-white"
      :class="isSubRegionOpen ? 'w-[95%]' : 'w-1/2'">
      <div class="mb-3 px-3">
        <button @click="closeRegion" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <CalendarTaskRegion :current_date="regionDate" :isSubRegionOpen="isSubRegionOpen"
          @show-subregion="isSubRegionOpen = $event" @changed="getData" />
      </div>
    </div>
  </div>
</template>
