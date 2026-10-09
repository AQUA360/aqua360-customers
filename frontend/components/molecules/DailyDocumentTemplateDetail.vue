<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';

const { $DailyDocumentTemplateApiService } = useNuxtApp();
const { t, te } = useI18n();

const FILE_ICONS = {
  XML: 'fa6-solid:file-code',
  CSV: 'fa6-solid:file-csv',
  XLS: 'fa6-solid:file-excel',
  XLSX: 'fa6-solid:file-excel',
  PDF: 'fa6-solid:file-pdf',
  JSON: 'fa6-solid:file-code',
};

const FIELD_I18N_KEYS = {
  start_date: 'common.start_date',
  end_date: 'common.end_date',
  exploitation_id: 'exploitation',
};

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  data: {
    type: Object,
    required: false
  },
  isSubRegion: {
    type: Boolean,
    default: false,
  }
});

const emit = defineEmits(['show-detail', 'edit']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $DailyDocumentTemplateApiService.getDetail(props.id);
    localData.value = detail;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }

};

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}


onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});

watch(() => props.data, (newData) => {
  if (newData) {
    localData.value = { ...newData };
  }
}, { deep: true });

const availableReport = computed(() => localData.value?.available_report || null);

const reportDescription = computed(() => {
  const report = availableReport.value;
  if (!report?.description) return '';
  if (report.description === report.name) return '';
  return report.description;
});

const fileFormat = computed(() => {
  const label = availableReport.value?.download_button_name || '';
  const match = label.match(/\b(XML|CSV|XLSX?|PDF|JSON)\b/i);
  return match ? match[1].toUpperCase() : null;
});

const fileIcon = computed(() => FILE_ICONS[fileFormat.value] || 'fa6-solid:file-lines');

const parseRequiredFields = (raw) => {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw.map(String).filter(Boolean);
  if (typeof raw !== 'string') return [];

  try {
    const parsed = JSON.parse(raw.replace(/'/g, '"'));
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
  } catch {
    return raw
      .replace(/^\[|\]$/g, '')
      .split(',')
      .map((item) => item.replace(/['"]/g, '').trim())
      .filter(Boolean);
  }
};

const requiredFields = computed(() => parseRequiredFields(availableReport.value?.required_fields));

const fieldLabel = (field) => {
  const mappedKey = FIELD_I18N_KEYS[field];
  if (mappedKey && te(mappedKey)) return t(mappedKey);
  if (te(`common.${field}`)) return t(`common.${field}`);
  if (te(field)) return t(field);
  return field.replace(/_id$/, '').replace(/_/g, ' ');
};
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
    }}</span>
  </div>

  <div v-else-if="localData">

    <div v-if="!localData.is_active" class="flex gap-x-2 items-center p-3 bg-amber-50 rounded border border-amber-300 mb-3">
      <Icon name="fa6-solid:circle-exclamation" class="text-amber-500" />
      <span class="text-amber-500">{{ t('warning_block.warning_inactive_template') }}</span>
    </div>

    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.name")' :value=localData.name />

      <FieldDetail :label="$t('common.expires_in')">
        {{ localData.days_to_complete }} {{ t('common.days') }}
      </FieldDetail>

      <FieldDetail class="col-span-2" :label='$t("common.description")' :value="localData.description || '-'" />
    </div>

    <section v-if="availableReport" id="daily_report__box"
      class="mb-3 overflow-hidden rounded-md border border-slate-200 bg-white">
      <div class="flex">
        <div class="w-1 shrink-0 bg-slate-800" aria-hidden="true" />
        <div class="flex min-w-0 flex-1 items-start gap-3 px-3 py-2.5">
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-slate-800 text-white"
            :title="fileFormat || t('common.file')">
            <Icon :name="fileIcon" class="text-sm" />
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {{ t('statistics_block.daily_file_generated') }}
              </span>
              <span v-if="fileFormat"
                class="rounded border border-slate-200 bg-slate-50 px-1.5 py-px text-[10px] font-semibold tracking-wide text-slate-700">
                {{ fileFormat }}
              </span>
              <span v-if="availableReport.section_name"
                class="rounded bg-slate-100 px-1.5 py-px text-[10px] font-medium text-slate-600">
                {{ availableReport.section_name }}
              </span>
            </div>

            <p class="mt-0.5 truncate text-sm font-semibold text-slate-900" :title="availableReport.name">
              {{ availableReport.name }}
            </p>
            <p v-if="reportDescription" class="mt-0.5 truncate text-xs text-slate-500" :title="reportDescription">
              {{ reportDescription }}
            </p>
            <p class="mt-0.5 text-xs text-slate-500">
              {{ t('statistics_block.daily_file_help') }}
            </p>

            <div v-if="requiredFields.length" class="mt-2 flex flex-wrap items-center gap-1.5">
              <span class="text-[10px] font-medium uppercase tracking-wide text-slate-400">
                {{ t('statistics_block.required_parameters') }}
              </span>
              <span v-for="field in requiredFields" :key="field"
                class="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-700">
                {{ fieldLabel(field) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <p v-else class="mb-3 text-sm text-slate-500">
      {{ t('statistics_block.no_available_report') }}
    </p>
  </div>
</template>
