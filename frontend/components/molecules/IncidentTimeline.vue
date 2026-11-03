<script setup>
import { useI18n } from 'vue-i18n';
import { formatDateTime } from '~/utils/date';
import AppLoading from '~/components/atoms/AppLoading.vue';

// Cronologia unificada de la incidència (estats, canvis, trucades, informes, observacions...)
const props = defineProps({
  id: Number,
  reload: Boolean,
});
const emit = defineEmits(['update:count']);

const { t } = useI18n();
const { $IncidentApiService } = useNuxtApp();

const loading = ref(true);
const events = ref([]);

const icons = {
  created: 'fa6-solid:flag',
  status: 'fa6-solid:arrows-rotate',
  change: 'fa6-solid:pencil',
  call: 'fa6-solid:phone',
  report: 'fa6-solid:newspaper',
  report_deleted: 'fa6-solid:trash-can',
  observation: 'fa6-solid:note-sticky',
  task: 'fa6-solid:calendar-check',
  receipt: 'fa6-solid:file-pdf',
  closed: 'fa6-solid:circle-check',
  deleted: 'fa6-solid:trash-can',
};

const getData = async () => {
  loading.value = true;
  try {
    events.value = await $IncidentApiService.getTimeline(props.id);
    emit('update:count', events.value.length);
  } catch (err) {
    console.error('Error obtenint la cronologia:', err);
  } finally {
    loading.value = false;
  }
};

onMounted(getData);
watch(() => [props.id, props.reload], getData);
</script>

<template>
  <div class="mt-2">
    <AppLoading v-if="loading" :text="t('common.loading')" :size="40" />
    <div v-else-if="events.length === 0" class="p-2 text-slate-500">{{ t('common.no_records') }}</div>
    <ol v-else class="border-l border-slate-200 ml-3">
      <li v-for="(event, index) in events" :key="index" class="ml-4 mb-3 relative">
        <span class="absolute -left-[26px] top-0.5 w-5 h-5 rounded-full bg-white border border-slate-200 flex items-center justify-center">
          <Icon :name="icons[event.kind] || 'fa6-solid:circle'" class="text-[10px] text-slate-500" />
        </span>
        <div class="text-xs text-slate-400">
          {{ formatDateTime(event.date) }}<span v-if="event.user"> · {{ event.user }}</span>
        </div>
        <div class="text-sm font-semibold text-slate-700">{{ event.title }}</div>
        <div v-if="event.detail" class="text-sm text-slate-600 whitespace-pre-line">{{ event.detail }}</div>
      </li>
    </ol>
  </div>
</template>
