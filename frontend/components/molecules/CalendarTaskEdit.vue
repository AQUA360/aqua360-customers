<script setup>
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import ButtonOutline from '../atoms/ButtonOutline.vue';
import { RECURRENCE_FREQUENCIES, WEEKDAY_KEYS } from '~/utils/calendarTasks';
import { useToast } from 'vue-toastification';

const { $CalendarTaskApiService, $UserApiService, $NotificationApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const sidebarStore = useSidebarStore();

/**
 * Una tasca per a avui s'avisa al backend just en desar-la: es refresca la
 * campana i el comptador de tasques del menú perquè es vegi al moment.
 */
const refreshNotifications = async (task) => {
  sidebarStore.tasksChanged();
  // Mateixa condició que el backend (notify_due_today): d'avui, pendent i no avisada.
  // Si ha canviat de dia o s'ha tornat a obrir, el backend esborra l'avís anterior.
  const today = new Date().toLocaleDateString('sv-SE'); // 'YYYY-MM-DD' en horari local
  if (task?.set_date !== today || task?.task_done) return;
  const resetByBackend = task.set_date !== originalDate.value || originalDone.value;
  if (originalNotifiedAt.value && !resetByBackend) return;
  try {
    sidebarStore.newNotificationsFound(await $NotificationApiService.checkNewNotifications());
  } catch (e) {
    // el comptador és informatiu
  }
  toast.info(t('calendar_tasks.notified_today', { name: task.name }));
};

const props = defineProps({
  current_date: String,
  id: {
    type: Number,
    required: false
  },
  object_id: {
    type: Number,
    required: false
  },
  object_service: {
    type: Object,
    required: false
  }
});

const emit = defineEmits(['change']);

const isLoading = ref(false);
const attemptedSave = ref(false);
const error = ref(null);

const name = ref('');
const description = ref('');
const color = ref('');
//const user = ref('');
const all_users = ref(true);

const selectedUser = ref(null);
const users = ref([]);

const selectedDate = ref(props.current_date? props.current_date : null);
const time = ref('');

// Recurrència: en una tasca nova o puntual, crea la sèrie; en una ocurrència
// d'una sèrie, només s'aplica si es marca «aplicar a les següents».
const isRecurring = ref(false);
const frequency = ref('weekly');
const interval = ref(1);
const weekdays = ref([]);
const endDate = ref(null);
const belongsToSeries = ref(false);
const applyToSeries = ref(false);
const originalRule = ref(null);
const originalNotifiedAt = ref(null);
const originalDate = ref(null);
const originalDone = ref(false);

/** Clear series state and restore the default recurrence form values. */
const resetRecurrenceForm = () => {
  isRecurring.value = false;
  frequency.value = 'weekly';
  interval.value = 1;
  weekdays.value = [];
  endDate.value = null;
  originalRule.value = null;
  belongsToSeries.value = false;
  applyToSeries.value = false;
};

/** Toggle a weekday in the recurrence selection, using Monday as zero. */
const toggleWeekday = (index) => {
  weekdays.value = weekdays.value.includes(index)
    ? weekdays.value.filter(day => day !== index)
    : [...weekdays.value, index].sort();
};

/** Build the recurrence payload from the form, omitting nonweekly weekdays. */
const currentRule = () => ({
  frequency: frequency.value,
  interval: Number(interval.value) || 1,
  weekdays: frequency.value === 'weekly' ? weekdays.value : [],
  end_date: endDate.value || null,
});

/** Compare the current recurrence payload with the originally loaded rule. */
const ruleChanged = () => JSON.stringify(currentRule()) !== JSON.stringify(originalRule.value);

/** Load available task assignees with display labels and user IDs. */
const getUsers = async () => {
  const response = await $UserApiService.getAll();
  users.value = response.results.map(user => ({
    label: user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.username,
    code: user.id,
    username: user.username
  }));
};

// Per defecte, una tasca privada s'assigna a l'usuari que la crea
/** Select the signed-in user as assignee when present in the loaded users. */
const selectCurrentUser = () => {
  let currentUsername = null;
  try {
    currentUsername = localStorage.getItem('user_username');
  } catch (e) { /* sense accés a localStorage */ }
  const me = users.value.find(user => user.username === currentUsername);
  if (me) selectedUser.value = me;
};

/** Set shared visibility and default private tasks to the current user. */
const setVisibility = (showToAll) => {
  all_users.value = showToAll;
  if (!showToAll && !selectedUser.value) selectCurrentUser();
};

/** Load task details and populate assignment, recurrence and notification state. */
const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $CalendarTaskApiService.getDetail(props.id);
    name.value = detail.name;
    description.value = detail.description;
    all_users.value = detail.user == null;
    selectedUser.value = detail.user
      ? { code: detail.user.id, label: detail.user.username }
      : null;
    selectedDate.value = detail.set_date;
    time.value = detail.time ? detail.time.slice(0, 5) : '';
    originalNotifiedAt.value = detail.notified_at;
    originalDate.value = detail.set_date;
    originalDone.value = detail.task_done;
    resetRecurrenceForm();
    belongsToSeries.value = !!detail.recurrence;
    isRecurring.value = !!detail.recurrence;
    applyToSeries.value = false;
    if (detail.recurrence) {
      frequency.value = detail.recurrence.frequency;
      interval.value = detail.recurrence.interval;
      weekdays.value = detail.recurrence.weekdays || [];
      endDate.value = detail.recurrence.end_date;
      originalRule.value = currentRule();
    }
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
};


const handleDescriptionTextareaUpdate = (value) => {
  description.value = value;
};

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'user':
      selectedUser.value = event;
      break;
  }
}

/** Validate and save the task, optionally updating its series and linked object. */
const save = async () => {

  attemptedSave.value = true;
  if (!isValid()) return

  let data = {
    id: props.id,
    name: name.value,
    description: description.value,
    set_date: selectedDate.value,
    time: time.value || null,
    all_users: all_users.value,
    user_id: all_users.value ? null : (selectedUser.value ? selectedUser.value.code : null),
  };

  if (!belongsToSeries.value) {
    if (isRecurring.value) data.recurrence_rule = currentRule();
  } else if (applyToSeries.value) {
    data.apply_to_series = true;
    if (!isRecurring.value) data.recurrence_rule = null;   // atura la sèrie després d'aquesta
    else if (ruleChanged()) data.recurrence_rule = currentRule();
  }

  let response = await $CalendarTaskApiService.save(data);
  if (response){
    refreshNotifications(response);
    if (props.object_id && props.object_service) {
      let object_save = {
        id: props.object_id,
        new_task: response.id
      }
      await props.object_service.save(object_save);
    }
    emit('change')
  }

};

/** Require a name, date and an assignee for private tasks. */
const isValid = () => {
  if (name.value == '') return false;
  if (!all_users.value && !selectedUser.value) return false;
  if (!selectedDate.value) return false;
  /* if (description.value == '') return false; */
  return true;
}

onMounted(() => {
  getUsers();
  if (props.id) fetchData();
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
  if (newId == null) {
    name.value = '';
    description.value = '';
    all_users.value = true;
    selectedUser.value = null;
    time.value = '';
    originalNotifiedAt.value = null;
    originalDate.value = null;
    originalDone.value = false;
    resetRecurrenceForm();
  }
});

const handleColorChanged = () => {
  emit('change', false);
}


</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again') }}</button>
  </div>

  <div v-else class="w-[90%]">
    <div class="flex justify-between relative">
      <H1Region class="mb-3">
        {{ id ? $t('dashboard.edit_task') : $t('dashboard.new_task') }}
        <span v-if="current_date" class="text-slate-500 text-sm ml-3">
          {{ formatDate(current_date) }}
        </span>
      </H1Region>
    </div>

    <!-- <div class="mt-2"> -->
    <div class="mt-2 row grid grid-cols-[1fr,auto] gap-3">
      <div class="col-span-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('dashboard.task_visibility') }}</label>
        <div class="flex flex-wrap gap-x-6 gap-y-2">
          <label class="flex items-center text-sm text-slate-700 cursor-pointer">
            <input type="radio" name="task_visibility" :checked="all_users" class="mr-2" @change="setVisibility(true)" />
            {{ t('dashboard.show_all') }}
          </label>
          <label class="flex items-center text-sm text-slate-700 cursor-pointer">
            <input type="radio" name="task_visibility" :checked="!all_users" class="mr-2" @change="setVisibility(false)" />
            {{ t('dashboard.show_only_assigned') }}
          </label>
        </div>
        <p class="text-xs text-slate-400 mt-1">
          {{ all_users ? t('dashboard.show_all_info') : t('dashboard.show_only_assigned_info') }}
        </p>
      </div>
      <div v-if="!props.current_date" class="my-2 col-span-2 w-[60%]">
        <AtomsInputDate v-model="selectedDate" :label="t('common.date')" class="mb-2" :required="true" />
      </div>
      <div class="mb-2 col-span-2 w-[30%]">
        <AtomsInputTime v-model="time" :label="t('calendar_tasks.time')" />
      </div>
      <div v-if="!all_users" class="mb-4 col-span-2 w-[60%]">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('dashboard.assigned_user') }}</label>
        <v-select class="block w-full" :class="{ 'invalid': attemptedSave && !selectedUser }" :model-value="selectedUser"
          @update:modelValue="updateSelect($event, 'user')" :options="users" />
      </div>
      <div class="mb-4 w-[60%]">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.title') }}</label>
        <input type="text" v-model="name" class="input"
          :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }" />
      </div>
      <span v-if="id" class="text-slate-900 p-1 my-auto">
        <AtomsColorPicker :entity="'notification/calendar-task'" :id="id" :code="color" @changed="handleColorChanged" />
      </span>
    </div>
    <div class="mb-4 rounded-md border border-slate-200 p-3">
      <label class="flex items-center gap-2 text-sm font-medium text-slate-600 cursor-pointer">
        <input v-model="isRecurring" type="checkbox" />
        <Icon name="fa6-solid:repeat" class="text-slate-400" />
        {{ t('calendar_tasks.recurring_task') }}
      </label>

      <div v-if="isRecurring" class="mt-3 space-y-3">
        <div class="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <span>{{ t('calendar_tasks.repeat_every') }}</span>
          <input v-model="interval" type="number" min="1" class="input w-16" />
          <select v-model="frequency" class="input w-40">
            <option v-for="option in RECURRENCE_FREQUENCIES" :key="option" :value="option">
              {{ t(`calendar_tasks.frequencies.${option}`) }}
            </option>
          </select>
        </div>
        <div v-if="frequency === 'weekly'" class="flex flex-wrap gap-1">
          <button v-for="(weekday, index) in WEEKDAY_KEYS" :key="weekday" type="button"
            class="px-2 py-1 text-xs rounded-md border"
            :class="weekdays.includes(index) ? 'border-sky-500 bg-sky-50 text-sky-700' : 'border-slate-200 text-slate-600'"
            :title="t(`date.${weekday}`)" @click="toggleWeekday(index)">
            {{ t(`date.weekdays_short.${weekday}`) }}
          </button>
          <span v-if="!weekdays.length" class="text-xs text-slate-400 self-center ml-1">{{ t('calendar_tasks.same_weekday') }}</span>
        </div>
        <div class="w-[60%]">
          <AtomsInputDate v-model="endDate" :label="t('calendar_tasks.end_date')" />
        </div>
      </div>

      <label v-if="belongsToSeries" class="flex items-center gap-2 text-sm text-slate-600 cursor-pointer mt-3">
        <input v-model="applyToSeries" type="checkbox" />
        {{ t('calendar_tasks.apply_to_series') }}
      </label>
      <p v-if="belongsToSeries && !applyToSeries" class="text-xs text-slate-400 mt-1">{{ t('calendar_tasks.only_this_occurrence') }}</p>
    </div>

    <div>
      <div class="mb-4">
        <AtomsInputTextarea :autosave="false" @update:text="handleDescriptionTextareaUpdate" :text="description"
          :placeholder="'dashboard.desc_task'" />
      </div>

    </div>

    <div class="col-span-3 flex flex-row-reverse mt-4">
      <button @click="save" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
      </button>
    </div>

  </div>
</template>

<style scoped>
.error {
  color: red;
}
</style>
