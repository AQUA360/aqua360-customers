<script setup>
// Anomalies de la persona: llistat, resolució i baixa (l'alta es fa des de la subregió AddPersonAnomaly)
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

const props = defineProps({
  personId: { type: Number, required: true },
  canChange: { type: Boolean, default: false },
  reload: { type: Number, default: 0 },
});

const emit = defineEmits(['update:count', 'changed']);

const { t, te } = useI18n();
const { $PersonAnomalyApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const anomalies = ref([]);

const typeLabel = (type) => {
  if (!type) return '-';
  const key = `person_anomaly.types.${type.token}`;
  return te(key) ? t(key) : type.name;
};

const userName = (user) => {
  if (!user) return '-';
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username;
};

// Primer les vigents
const sortedAnomalies = computed(() =>
  [...anomalies.value].sort((a, b) => Number(b.is_current) - Number(a.is_current)),
);

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const res = await $PersonAnomalyApiService.getAll(props.personId);
    anomalies.value = res.results || res || [];
    emit('update:count', anomalies.value.length);
  } catch (err) {
    console.error(err);
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const resolve = async (item) => {
  if (!confirm(t('person_anomaly.confirm_resolve'))) return;
  try {
    await $PersonAnomalyApiService.resolve(item.id);
    await getData();
    emit('changed');
  } catch (err) {
    console.error(err);
  }
};

const remove = async (item) => {
  if (!confirm(t('person_anomaly.confirm_delete'))) return;
  try {
    await $PersonAnomalyApiService.remove(item.id);
    await getData();
    emit('changed');
  } catch (err) {
    console.error(err);
  }
};

onMounted(getData);
watch(() => [props.personId, props.reload], getData);
</script>

<template>
  <div v-if="pending" class="footering text-slate-500 p-2">{{ t('common.loading') }}...</div>
  <div v-else-if="error" class="footering text-red-600 p-2">{{ t('common.error_load') }}</div>
  <div v-else-if="anomalies.length" class="m-4 rounded-md border border-gray-300 divide-y bg-white">
    <div class="group grid grid-cols-[1.5fr,1fr,1fr,2fr,1fr,100px,70px] divide-x text-sm leading-4">
      <span class="p-2 pl-3 text-slate-600">{{ t('person_anomaly.anomaly_type') }}</span>
      <span class="p-2 pl-3 text-slate-600">{{ t('person_anomaly.start_date') }}</span>
      <span class="p-2 pl-3 text-slate-600">{{ t('person_anomaly.end_date') }}</span>
      <span class="p-2 pl-3 text-slate-600">{{ t('person_anomaly.observation') }}</span>
      <span class="p-2 pl-3 text-slate-600">{{ t('person_anomaly.user') }}</span>
      <span class="p-2 pl-3 text-slate-600">{{ t('person_anomaly.status') }}</span>
      <span class="p-2"></span>
    </div>
    <div v-for="item in sortedAnomalies" :key="item.id"
      class="group grid grid-cols-[1.5fr,1fr,1fr,2fr,1fr,100px,70px] divide-x text-sm leading-4 transition-all duration-100"
      :class="{ 'opacity-50': !item.is_current }">
      <div class="footering text-slate-800 p-2">{{ typeLabel(item.anomaly_type) }}</div>
      <div class="footering text-slate-500 p-2">{{ formatDate(item.start_date) }}</div>
      <div class="footering text-slate-500 p-2">{{ item.end_date ? formatDate(item.end_date) : '-' }}</div>
      <div class="footering text-slate-500 p-2 whitespace-pre-line break-words">{{ item.observation || '-' }}</div>
      <div class="footering text-slate-500 p-2 truncate" :title="userName(item.user)">{{ userName(item.user) }}</div>
      <div class="p-2">
        <span class="inline-block rounded px-2 py-0.5 text-xs"
          :class="item.is_current ? 'badge-amber' : 'badge-gray'">
          {{ item.is_current ? t('person_anomaly.current') : t('person_anomaly.resolved') }}
        </span>
      </div>
      <div class="p-1 flex items-center justify-center gap-1">
        <Icon v-if="item.in_open_process" name="fa6-solid:scale-balanced" class="text-red-500"
          :title="t('person_anomaly.managed_by_process')" />
        <button v-if="canChange && item.is_current && !item.in_open_process" type="button" @click="resolve(item)"
          :title="t('person_anomaly.resolve')" class="px-1.5 py-1 text-gray-400 hover:text-emerald-600">
          <Icon name="fa6-solid:check" />
        </button>
        <button v-if="canChange && !item.in_open_process" type="button" @click="remove(item)" :title="t('person_anomaly.delete')"
          class="px-1.5 py-1 text-gray-400 hover:text-red-500">
          <Icon name="fa6-solid:trash" />
        </button>
      </div>
    </div>
  </div>
  <div v-else class="footering text-slate-500 p-2">{{ t('person_anomaly.no_records') }}</div>
</template>
