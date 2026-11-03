<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import { formatDate } from '~/utils/date';

// Configuració de la gestió SAC de les incidències: el client decideix terminis,
// avisos, escalats, justificant, enquesta, fases, pauses, transicions i festius.
const { t } = useI18n();
const toast = useToast();
const { $apiManager, $UserApiService, $GroupApiService, $ExploitationApiService } = useNuxtApp();
const apiHost = useRuntimeConfig().public.apiHost;

const tab = ref('types');
const loading = ref(true);
const saving = ref(false);

const types = ref([]);
const statuses = ref([]);
const users = ref([]);
const groups = ref([]);
const exploitations = ref([]);
const holidays = ref([]);
const holidayYear = ref(new Date().getFullYear());
const newHoliday = ref({ date: '', name: '', exploitation: null });

const selectedType = ref(null);
const selectedStatus = ref(null);

const unitOptions = computed(() => [
  { code: 'business_days', label: t('incident_settings.business_days') },
  { code: 'natural_days', label: t('incident_settings.natural_days') },
  { code: 'hours', label: t('incident_settings.hours') },
]);
const phaseOptions = computed(() => ['registration', 'classification', 'assignment', 'processing', 'resolution', 'closing']
  .map(code => ({ code, label: t(`incident_settings.phase_${code}`) })));

const fetchList = async (entity) => {
  const response = await $apiManager.fetch(`${apiHost}/${entity}/?page_size=200`, 'GET');
  return response.results || response;
};

const patch = async (entity, id, data) => {
  return $apiManager.fetch(`${apiHost}/${entity}/${id}/`, 'PATCH', JSON.stringify(data), { 'Content-Type': 'application/json' });
};

const getHolidays = async () => {
  holidays.value = await $apiManager.fetch(`${apiHost}/coredata/holiday/?year=${holidayYear.value}`, 'GET');
};

const getData = async () => {
  loading.value = true;
  try {
    // Cada secció es carrega per separat: sense permís per veure usuaris o grups,
    // la resta de la configuració es pot continuar fent servir
    const [typeList, statusList, userList, groupList, exploitationList] = await Promise.allSettled([
      fetchList('notification/incident-type'),
      fetchList('notification/incident-status'),
      $UserApiService.getAll(),
      $GroupApiService.getAll(),
      $ExploitationApiService.getAll(),
    ]);
    const value = (result) => (result.status === 'fulfilled' ? result.value : null);
    types.value = value(typeList) || [];
    statuses.value = value(statusList) || [];
    users.value = (value(userList)?.results || []).map(user => ({ code: user.id, label: user.username }));
    groups.value = (value(groupList)?.results || []).map(group => ({ code: group.id, label: group.name }));
    exploitations.value = (value(exploitationList)?.results || []).map(item => ({ code: item.id, label: item.name }));
    await getHolidays();
  } catch (err) {
    console.error('Error carregant la configuració d\'incidències:', err);
  } finally {
    loading.value = false;
  }
};

const editType = (item) => {
  selectedType.value = {
    ...item,
    due_unit: unitOptions.value.find(option => option.code === item.due_unit) || unitOptions.value[0],
    escalation_user: findOrKeep(users.value, item.escalation_user),
    escalation_group: findOrKeep(groups.value, item.escalation_group),
  };
};

// Si no s'han pogut carregar les opcions (sense permís), es conserva l'identificador
// desat perquè en desar el tipus no es perdi el destinatari de l'escalat
const findOrKeep = (options, id) => {
  if (!id) return null;
  return options.find(option => option.code === id) || { code: id, label: `#${id}` };
};

const numberOrNull = (value) => (value === '' || value === null || value === undefined ? null : Number(value));

const saveType = async () => {
  const item = selectedType.value;
  saving.value = true;
  try {
    await patch('notification/incident-type', item.id, {
      due_term: numberOrNull(item.due_term),
      due_unit: item.due_unit?.code || 'business_days',
      warning_before: numberOrNull(item.warning_before),
      escalation_after: numberOrNull(item.escalation_after),
      escalation_user: item.escalation_user?.code || null,
      escalation_group: item.escalation_group?.code || null,
      send_receipt: item.send_receipt,
      receipt_text: item.receipt_text || null,
      resolution_template: item.resolution_template || null,
      blocks_commercial: item.blocks_commercial,
    });
    toast.success(t('common.correct_save'));
    types.value = await fetchList('notification/incident-type');
    selectedType.value = null;
  } finally {
    saving.value = false;
  }
};

const editStatus = (item) => {
  selectedStatus.value = {
    ...item,
    phase: phaseOptions.value.find(option => option.code === item.phase) || null,
    allowed_next: statuses.value.filter(status => (item.allowed_next || []).includes(status.id))
      .map(status => ({ code: status.id, label: status.name })),
  };
};

const saveStatus = async () => {
  const item = selectedStatus.value;
  saving.value = true;
  try {
    await patch('notification/incident-status', item.id, {
      phase: item.phase?.code || null,
      pauses_due: item.pauses_due,
      max_pause_days: numberOrNull(item.max_pause_days),
      allowed_next: item.allowed_next.map(option => option.code),
    });
    toast.success(t('common.correct_save'));
    statuses.value = await fetchList('notification/incident-status');
    selectedStatus.value = null;
  } finally {
    saving.value = false;
  }
};

const addHoliday = async () => {
  if (!newHoliday.value.date) return;
  await $apiManager.fetch(`${apiHost}/coredata/holiday/`, 'POST', JSON.stringify({
    date: newHoliday.value.date,
    name: newHoliday.value.name || null,
    exploitation: newHoliday.value.exploitation?.code || null,
  }), { 'Content-Type': 'application/json' });
  newHoliday.value = { date: '', name: '', exploitation: null };
  await getHolidays();
};

const deleteHoliday = async (holiday) => {
  if (!confirm(t('confirmation_text_block.confirm_delete'))) return;
  await $apiManager.fetch(`${apiHost}/coredata/holiday/${holiday.id}/`, 'DELETE');
  await getHolidays();
};

const unitLabel = (code) => unitOptions.value.find(option => option.code === code)?.label || '';
const phaseLabel = (code) => phaseOptions.value.find(option => option.code === code)?.label || '-';

watch(holidayYear, getHolidays);
onMounted(getData);
</script>

<template>
  <div>
    <H1Region class="mb-3">{{ t('incident_settings.title') }}</H1Region>
    <p class="text-sm text-slate-500 mb-3">{{ t('incident_settings.intro') }}</p>

    <AtomsTabs>
      <li v-for="item in ['types', 'statuses', 'holidays']" :key="item" class="me-2">
        <a href="#" @click.prevent="tab = item"
          :class="{ 'text-sky-600 border-sky-600': tab === item, 'hover:text-gray-600 hover:border-gray-300': tab !== item }">
          {{ t(`incident_settings.tab_${item}`) }}
        </a>
      </li>
    </AtomsTabs>

    <div v-if="loading" class="p-4 text-slate-500">{{ t('common.loading') }}...</div>

    <!-- Tipus: terminis, avisos, escalat, justificant, enquesta i bloqueig comercial -->
    <section v-else-if="tab === 'types'" class="mt-3">
      <div v-if="!selectedType">
        <div class="grid grid-cols-[1fr,140px,100px,100px,60px] text-sm font-semibold text-slate-500 border-b p-2">
          <span>{{ t('common.type') }}</span><span>{{ t('incident_settings.term') }}</span>
          <span>{{ t('incident_settings.warning_before') }}</span><span>{{ t('incident_settings.escalation_after') }}</span><span></span>
        </div>
        <div v-for="item in types" :key="item.id" class="grid grid-cols-[1fr,140px,100px,100px,60px] text-sm border-b p-2 items-center">
          <span class="font-semibold">{{ item.name }}</span>
          <span>{{ item.due_term != null ? `${item.due_term} ${unitLabel(item.due_unit)}` : '-' }}</span>
          <span>{{ item.warning_before ?? '-' }}</span>
          <span>{{ item.escalation_after ?? '-' }}</span>
          <button class="text-sky-500 underline" @click="editType(item)">{{ t('common.modify') }}</button>
        </div>
        <p class="text-xs text-slate-400 mt-2">{{ t('incident_settings.types_help') }}</p>
      </div>

      <div v-else class="grid grid-cols-2 gap-3">
        <h3 class="col-span-2 font-bold">{{ selectedType.name }}</h3>
        <div>
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.term') }}</label>
          <input type="number" min="0" v-model="selectedType.due_term" class="input" />
        </div>
        <div>
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.unit') }}</label>
          <v-select v-model="selectedType.due_unit" :options="unitOptions" :clearable="false" />
        </div>
        <div>
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.warning_before_long') }}</label>
          <input type="number" min="0" v-model="selectedType.warning_before" class="input" />
        </div>
        <div>
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.escalation_after_long') }}</label>
          <input type="number" min="0" v-model="selectedType.escalation_after" class="input" />
        </div>
        <div>
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.escalation_user') }}</label>
          <v-select v-model="selectedType.escalation_user" :options="users" />
        </div>
        <div>
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.escalation_group') }}</label>
          <v-select v-model="selectedType.escalation_group" :options="groups" />
        </div>
        <label class="flex items-center gap-2 text-sm"><input type="checkbox" v-model="selectedType.send_receipt" /> {{ t('incident_settings.send_receipt') }}</label>
        <label class="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" v-model="selectedType.blocks_commercial" /> {{ t('incident_settings.blocks_commercial') }}</label>
        <div class="col-span-2">
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.receipt_text') }}</label>
          <textarea v-model="selectedType.receipt_text" rows="3" class="w-full border border-slate-300 rounded-md p-2"></textarea>
        </div>
        <div class="col-span-2">
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.resolution_template') }}</label>
          <textarea v-model="selectedType.resolution_template" rows="4" class="w-full border border-slate-300 rounded-md p-2"></textarea>
          <p class="text-xs text-slate-400 mt-1">{{ t('incident_settings.placeholders') }}</p>
        </div>
        <div class="col-span-2 flex gap-2 justify-end">
          <button class="button-secondary" @click="selectedType = null">{{ t('common.cancel') }}</button>
          <button class="button-primary" :disabled="saving" @click="saveType">{{ t('common.save') }}</button>
        </div>
      </div>
    </section>

    <!-- Estats: fase, pausa del termini i transicions permeses -->
    <section v-else-if="tab === 'statuses'" class="mt-3">
      <div v-if="!selectedStatus">
        <div class="grid grid-cols-[1fr,140px,120px,1fr,60px] text-sm font-semibold text-slate-500 border-b p-2">
          <span>{{ t('common.status') }}</span><span>{{ t('incident_settings.phase') }}</span>
          <span>{{ t('incident_settings.pauses_due') }}</span><span>{{ t('incident_settings.allowed_next') }}</span><span></span>
        </div>
        <div v-for="item in statuses" :key="item.id" class="grid grid-cols-[1fr,140px,120px,1fr,60px] text-sm border-b p-2 items-center">
          <span class="font-semibold">{{ item.name }}</span>
          <span>{{ phaseLabel(item.phase) }}</span>
          <span>{{ item.pauses_due ? t('common.yes') : '-' }}</span>
          <span>{{ statuses.filter(s => (item.allowed_next || []).includes(s.id)).map(s => s.name).join(', ') || t('incident_settings.any') }}</span>
          <button class="text-sky-500 underline" @click="editStatus(item)">{{ t('common.modify') }}</button>
        </div>
      </div>

      <div v-else class="grid grid-cols-2 gap-3">
        <h3 class="col-span-2 font-bold">{{ selectedStatus.name }}</h3>
        <div>
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.phase') }}</label>
          <v-select v-model="selectedStatus.phase" :options="phaseOptions" />
        </div>
        <div>
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.max_pause_days') }}</label>
          <input type="number" min="0" v-model="selectedStatus.max_pause_days" class="input" :disabled="!selectedStatus.pauses_due" />
        </div>
        <label class="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" v-model="selectedStatus.pauses_due" /> {{ t('incident_settings.pauses_due_long') }}</label>
        <div class="col-span-2">
          <label class="block text-sm text-slate-500 mb-1">{{ t('incident_settings.allowed_next') }}</label>
          <v-select v-model="selectedStatus.allowed_next" multiple
            :options="statuses.filter(s => s.id !== selectedStatus.id).map(s => ({ code: s.id, label: s.name }))" />
          <p class="text-xs text-slate-400 mt-1">{{ t('incident_settings.allowed_next_help') }}</p>
        </div>
        <div class="col-span-2 flex gap-2 justify-end">
          <button class="button-secondary" @click="selectedStatus = null">{{ t('common.cancel') }}</button>
          <button class="button-primary" :disabled="saving" @click="saveStatus">{{ t('common.save') }}</button>
        </div>
      </div>
    </section>


    <!-- Festius per al càlcul de dies hàbils -->
    <section v-else-if="tab === 'holidays'" class="mt-3">
      <div class="flex items-center gap-2 mb-3">
        <button class="button-default-xs" @click="holidayYear--">&lt;</button>
        <span class="font-semibold">{{ holidayYear }}</span>
        <button class="button-default-xs" @click="holidayYear++">&gt;</button>
      </div>
      <div v-for="holiday in holidays" :key="holiday.id" class="grid grid-cols-[120px,1fr,200px,40px] text-sm border-b p-2 items-center">
        <span>{{ formatDate(holiday.date) }}</span>
        <span>{{ holiday.name }}</span>
        <span class="text-slate-500">{{ holiday.exploitation_name || t('incident_settings.all_exploitations') }}</span>
        <button @click="deleteHoliday(holiday)" class="px-2 py-1 hover:bg-slate-200 rounded">
          <Icon name="fa6-solid:trash-can" class="text-slate-500" />
        </button>
      </div>
      <div class="grid grid-cols-[160px,1fr,200px,80px] gap-2 mt-3 items-center">
        <input type="date" v-model="newHoliday.date" class="input" />
        <input type="text" v-model="newHoliday.name" class="input" :placeholder="t('common.name')" />
        <v-select v-model="newHoliday.exploitation" :options="exploitations" :placeholder="t('incident_settings.all_exploitations')" />
        <button class="button-primary" @click="addHoliday">{{ t('common.add') }}</button>
      </div>
      <p class="text-xs text-slate-400 mt-2">{{ t('incident_settings.holidays_help') }}</p>
    </section>
  </div>
</template>
