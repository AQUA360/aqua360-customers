<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import H1 from '~/components/atoms/H1.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import { formatDate } from '~/utils/date';

const { t } = useI18n();
const toast = useToast();
const {
  $ReadingDocumentApiService,
  $ReadingApiService,
  $ReadingBatchImportTemplateApiService,
  $ReadingBatchImportColumnApiService,
  $apiManager,
} = useNuxtApp();

const PREVIEW_PAGE_SIZE = 25;
const TASK_POLL_INTERVAL_MS = 1500;

const METER_IDENTIFIER_CLASS = 'bg-blue-100 text-blue-800';

const DEFAULT_IMPORT_COLUMNS = [
  {
    labelKey: 'service_block.meter_code',
    original_name: 'meter',
    codeClass: METER_IDENTIFIER_CLASS,
    optional: false,
    identifierGroup: true,
  },
  {
    labelKey: 'contract',
    original_name: 'contract',
    codeClass: METER_IDENTIFIER_CLASS,
    optional: false,
    identifierGroup: true,
    customTemplateOnly: true,
  },
  {
    labelKey: 'service_block.comm_module',
    original_name: 'comm_module',
    codeClass: METER_IDENTIFIER_CLASS,
    optional: false,
    identifierGroup: true,
    customTemplateOnly: true,
  },
  {
    labelKey: 'reading',
    original_name: 'reading_value',
    codeClass: 'bg-green-100 text-green-800',
    optional: false,
    readingUnitSelect: true,
  },
  { labelKey: 'billing_block.reading_date', original_name: 'reading_date', codeClass: 'bg-purple-100 text-purple-800', optional: false },
  { labelKey: 'common.origin', original_name: 'origin', codeClass: 'bg-orange-100 text-orange-800', optional: true },
  { labelKey: 'informative_block.is_control', original_name: 'is_control', codeClass: 'bg-red-100 text-red-800', optional: true },
  { labelKey: 'billing_block.leak', original_name: 'leak_value', codeClass: 'bg-yellow-100 text-yellow-800', optional: true },
  {
    labelKey: 'common.observation',
    labelSuffixKey: 'service_block.telecontrol',
    original_name: 'observation',
    codeClass: 'bg-cyan-100 text-cyan-800',
    optional: true,
  },
];

const emit = defineEmits(['on-processed', 'close']);

const props = defineProps({
  /** Si false, el títol el gestiona la pàgina contenidora (pantalla completa). */
  showTitle: {
    type: Boolean,
    default: true,
  },
});

const step = ref('upload');
const saving = ref(false);
const validating = ref(false);
const processing = ref(false);
const file = ref(null);
const documentId = ref(null);
const previewData = ref(null);
const previewFilter = ref('all');
const previewPage = ref(1);
const processPollAbort = ref(null);
const objectPermissions = ref(null);
const importTemplates = ref([]);
const selectedTemplateKey = ref('default');
const creatingTemplate = ref(false);
const newTemplateName = ref('');
const creatingTemplateSaving = ref(false);
const deletingTemplate = ref(false);
const formatDetailsRef = ref(null);
const templateColumnRows = ref([]);
const columnsLoading = ref(false);
const columnsDirty = ref(false);
const columnsSaving = ref(false);
const readingVolumeUnit = ref('m3');
const readingVolumeUnitOptions = [
  { value: 'm3', label: 'm³' },
  { value: 'liter', label: 'L' },
];

const taskId = ref(null);

const isCustomTemplate = computed(() => selectedTemplateKey.value !== 'default');

const filterColumnsForDisplay = (cols) =>
  cols.filter((col) => !col.customTemplateOnly || isCustomTemplate.value);

const displayColumns = computed(() => {
  if (!isCustomTemplate.value) {
    return filterColumnsForDisplay(DEFAULT_IMPORT_COLUMNS);
  }
  const rows = templateColumnRows.value.length
    ? templateColumnRows.value
    : DEFAULT_IMPORT_COLUMNS.map((col) => ({ ...col, id: null, mapped_name: '' }));
  return filterColumnsForDisplay(rows);
});

const defaultColumnRows = () =>
  DEFAULT_IMPORT_COLUMNS.map((col) => ({
    ...col,
    id: null,
    mapped_name: '',
  }));

const isLitersFromUnit = (unit) => unit === 'liter';
const unitFromIsLiters = (isLiters) => (isLiters ? 'liter' : 'm3');

const applyTemplateVolumeUnit = (template) => {
  readingVolumeUnit.value = unitFromIsLiters(template?.is_liters === true);
};

const mergeDefaultColumnsWithApi = (apiRows) =>
  DEFAULT_IMPORT_COLUMNS.map((def) => {
    const apiCol = apiRows.find((row) => row.original_name === def.original_name);
    return {
      ...def,
      id: apiCol?.id ?? null,
      mapped_name: apiCol?.mapped_name ?? '',
    };
  });

const patchImportTemplateInList = (updated) => {
  if (!updated?.id) return;
  const index = importTemplates.value.findIndex((tpl) => String(tpl.id) === String(updated.id));
  if (index !== -1) {
    importTemplates.value[index] = { ...importTemplates.value[index], ...updated };
  }
};

const buildSelectedTemplatePayload = () => {
  const id = Number(selectedTemplateKey.value);
  const existing = importTemplates.value.find((tpl) => String(tpl.id) === String(id));
  return {
    id,
    name: existing?.name ?? '',
    is_liters: isLitersFromUnit(readingVolumeUnit.value),
  };
};

const persistSelectedTemplate = async () => {
  const updated = await $ReadingBatchImportTemplateApiService.update(buildSelectedTemplatePayload());
  patchImportTemplateInList(updated);
  applyTemplateVolumeUnit(updated);
  return updated;
};

const onReadingVolumeUnitChange = () => {
  if (isCustomTemplate.value) {
    markColumnsDirty();
  }
};

const openFormatDetails = () => {
  if (formatDetailsRef.value) {
    formatDetailsRef.value.open = true;
  }
};

const selectedTemplateLabel = computed(() => {
  if (!isCustomTemplate.value) return t('default');
  const tpl = importTemplates.value.find((item) => String(item.id) === String(selectedTemplateKey.value));
  return tpl?.name || t('common.template');
});

const mappedColumnsCount = computed(() => {
  if (!isCustomTemplate.value) return displayColumns.value.length;
  return templateColumnRows.value.filter((col) => String(col.mapped_name || '').trim()).length;
});

const selectedTemplateSummary = computed(() => {
  const unitLabel = readingVolumeUnit.value === 'liter' ? 'L' : 'm³';
  return t('statistics_block.reading_document_template_summary', {
    name: selectedTemplateLabel.value,
    unit: unitLabel,
    mapped: mappedColumnsCount.value,
  });
});

const normalizeListResponse = (data) => {
  if (Array.isArray(data)) return data;
  if (data?.results && Array.isArray(data.results)) return data.results;
  return [];
};

const loadImportTemplates = async () => {
  try {
    const data = await $ReadingBatchImportTemplateApiService.getAll();
    importTemplates.value = normalizeListResponse(data);
  } catch (err) {
    console.error(err);
  }
};

const initializeTemplateColumns = async (templateId) => {
  const response = await $ReadingBatchImportColumnApiService.sync({
    template: templateId,
    columns: DEFAULT_IMPORT_COLUMNS.map((col, index) => ({
      original_name: col.original_name,
      mapped_name: '',
      position: index + 1,
    })),
  });
  templateColumnRows.value = mergeDefaultColumnsWithApi(normalizeListResponse(response));
  columnsDirty.value = false;
};

const columnsToSyncPayload = () =>
  templateColumnRows.value.map((col, index) => ({
    original_name: col.original_name,
    mapped_name: col.mapped_name?.trim() ?? '',
    position: index + 1,
  }));

const loadTemplateColumns = async () => {
  if (!isCustomTemplate.value) {
    templateColumnRows.value = [];
    columnsDirty.value = false;
    readingVolumeUnit.value = 'm3';
    return;
  }

  columnsLoading.value = true;
  try {
    const [templateDetail, data] = await Promise.all([
      $ReadingBatchImportTemplateApiService.getDetail(selectedTemplateKey.value),
      $ReadingBatchImportColumnApiService.getAll({
        template: selectedTemplateKey.value,
      }),
    ]);
    applyTemplateVolumeUnit(templateDetail);
    const apiRows = normalizeListResponse(data);
    if (apiRows.length === 0) {
      await initializeTemplateColumns(selectedTemplateKey.value);
    } else {
      templateColumnRows.value = mergeDefaultColumnsWithApi(apiRows);
      columnsDirty.value = false;
    }
  } catch (err) {
    console.error(err);
    templateColumnRows.value = defaultColumnRows();
    columnsDirty.value = false;
  } finally {
    columnsLoading.value = false;
  }
};

const markColumnsDirty = () => {
  columnsDirty.value = true;
};

const saveTemplateColumns = async () => {
  if (!isCustomTemplate.value || columnsSaving.value) return;

  columnsSaving.value = true;
  try {
    const [columnResponse] = await Promise.all([
      $ReadingBatchImportColumnApiService.sync({
        template: Number(selectedTemplateKey.value),
        columns: columnsToSyncPayload(),
      }),
      persistSelectedTemplate(),
    ]);
    templateColumnRows.value = mergeDefaultColumnsWithApi(normalizeListResponse(columnResponse));
    columnsDirty.value = false;
    toast.success(t('common.correct_save'));
  } catch (err) {
    console.error(err);
  } finally {
    columnsSaving.value = false;
  }
};

const handleDocumentUpdate = (f) => {
  file.value = f
};

const downloadTemplate = async (fileUrl) => {
  try {
    const authToken = localStorage.getItem('auth_token') || '';
    const res = await fetch(fileUrl, {
      headers: { Authorization: `Token ${authToken}` },
    });

    if (!res.ok) {
      throw new Error(t('common.error'));
    }

    const blob = await res.blob();
    const filename = decodeURIComponent(fileUrl.split('/').pop()) || 'template.csv';
    const link = document.createElement('a');
    const blobUrl = URL.createObjectURL(blob);
    link.href = blobUrl;
    link.download = filename;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(blobUrl);
    }, 250);
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  }
};

const generateTemplate = async () => {
  let fileUrl = null;
  if (selectedTemplateKey.value === 'default') {
    const response = await $ReadingDocumentApiService.getTemplate();
    fileUrl = response?.file_url;
  } else {
    const response = await $ReadingBatchImportTemplateApiService.getDetail(selectedTemplateKey.value);
    fileUrl = response?.file_url;
  }

  if (fileUrl) {
    await downloadTemplate(fileUrl);
  }
};

const openCreateTemplate = () => {
  openFormatDetails();
  creatingTemplate.value = true;
  newTemplateName.value = '';
};

const cancelCreateTemplate = () => {
  creatingTemplate.value = false;
  newTemplateName.value = '';
};

const saveNewTemplate = async () => {
  const name = newTemplateName.value.trim();
  if (!name) return;

  creatingTemplateSaving.value = true;
  try {
    const created = await $ReadingBatchImportTemplateApiService.create({
      name,
      is_liters: isLitersFromUnit(readingVolumeUnit.value),
    });
    await loadImportTemplates();
    if (created?.id != null) {
      selectedTemplateKey.value = String(created.id);
      applyTemplateVolumeUnit(created);
      await initializeTemplateColumns(created.id);
    }
    cancelCreateTemplate();
    toast.success(t('common.correct_save'));
  } catch (err) {
    console.error(err);
  } finally {
    creatingTemplateSaving.value = false;
  }
};

const deleteSelectedTemplate = async () => {
  if (!isCustomTemplate.value || deletingTemplate.value) return;
  if (!window.confirm(t('confirmation_text_block.confirm_delete'))) return;

  const templateId = selectedTemplateKey.value;
  deletingTemplate.value = true;
  try {
    await $ReadingBatchImportTemplateApiService.remove(templateId);
    selectedTemplateKey.value = 'default';
    templateColumnRows.value = [];
    readingVolumeUnit.value = 'm3';
    columnsDirty.value = false;
    cancelCreateTemplate();
    await loadImportTemplates();
    toast.success(t('common.deleted_successfully'));
  } catch (err) {
    console.error(err);
  } finally {
    deletingTemplate.value = false;
  }
};

const handleDocumentDelete = () => {
  file.value = null;
};

const previewStatCards = computed(() => {
  const stats = previewData.value?.stats;
  if (!stats) return [];
  return [
    { key: 'all', filter: 'all', labelKey: 'statistics_block.reading_document_preview_filter_all', value: stats.rows, class: 'bg-slate-100 text-slate-800'},
    { key: 'would_create', filter: 'would_create', labelKey: 'statistics_block.reading_document_stat_would_create', value: stats.would_create, class: 'bg-green-100 text-green-800'},
    { key: 'would_update', filter: 'would_update', labelKey: 'statistics_block.reading_document_stat_would_update', value: stats.would_update, class: 'bg-orange-100 text-orange-800'},
    { key: 'not_found_meter', filter: 'not_found', labelKey: 'statistics_block.reading_document_stat_not_found_meter', value: stats.not_found_meter, class: 'bg-red-100 text-red-800'},
    { key: 'skipped_existing', filter: 'skipped_existing', labelKey: 'statistics_block.reading_document_stat_skipped_existing', value: stats.skipped_existing, class: 'bg-yellow-100 text-yellow-800'},
    { key: 'skipped_no_date', filter: 'skipped_no_date', labelKey: 'statistics_block.reading_document_stat_skipped_no_date', value: stats.skipped_no_date, class: 'bg-red-100 text-red-800'},
    { key: 'no_supply_points', filter: 'no_supply_points', labelKey: 'statistics_block.reading_document_stat_no_supply_points', value: stats.no_supply_points, class: 'bg-orange-100 text-orange-800'},
    { key: 'no_contracts', filter: 'no_contracts', labelKey: 'statistics_block.reading_document_stat_no_contracts', value: stats.no_contracts, class: 'bg-orange-100 text-orange-800'},
  ];
});

const previewFilterOptions = computed(() =>
  previewStatCards.value
    .filter((card) => card.filter === 'all' || (card.value ?? 0) > 0)
    .map((card) => ({
      value: card.filter,
      label: t(card.labelKey),
      count: card.value ?? 0,
    })),
);

const previewRows = computed(() => previewData.value?.rows ?? []);

const previewPagination = computed(() => {
  const total = previewData.value?.filtered_total
    ?? previewData.value?.total_rows
    ?? previewData.value?.stats?.rows
    ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PREVIEW_PAGE_SIZE) || 1);
  const page = Math.min(Math.max(previewPage.value, 1), totalPages);

  return {
    page,
    perPage: PREVIEW_PAGE_SIZE,
    total,
    totalPages,
    previous: page > 1 ? page - 1 : null,
    next: page < totalPages ? page + 1 : null,
    isFiltered: previewFilter.value !== 'all',
  };
});

const resetPreviewTableState = () => {
  previewFilter.value = 'all';
  previewPage.value = 1;
};

/** Params de validate segons filtre + pàgina (cache last_preview al backend). */
const buildValidateParams = () => {
  const params = {
    page: previewPage.value,
    page_size: PREVIEW_PAGE_SIZE,
  };
  const filter = previewFilter.value;
  if (filter && filter !== 'all') {
    if (filter === 'would_create' || filter === 'would_update' || filter === 'not_found') {
      params.action = filter;
    } else {
      params.action = 'skip';
      params.reason = filter;
    }
  }
  return params;
};

const loadPreview = async ({ refresh = false, id = documentId.value } = {}) => {
  if (!id || processing.value) return;

  validating.value = true;
  try {
    const params = buildValidateParams();
    if (refresh) {
      params.refresh = true;
    }
    const response = await $ReadingDocumentApiService.validate(id, params);

    taskId.value = response?.task_id;
    if (taskId.value) {
      return;
    }

    previewData.value = response;
    step.value = 'preview';

    // Si el backend retorna menys pàgines (filtre), ajustem la pàgina local
    const total = previewData.value?.filtered_total ?? 0;
    const totalPages = Math.max(1, Math.ceil(total / PREVIEW_PAGE_SIZE) || 1);
    if (previewPage.value > totalPages) {
      previewPage.value = totalPages;
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    validating.value = false;
  }
};

const getTaskData = async (task_data_id) => {
  try {
    const taskResponse = await $apiManager.checkTask(task_data_id);
    console.log("taskResponse", taskResponse);
    if (taskResponse?.state === 'SUCCESS') {
      step.value = 'preview';
    }
    previewData.value = taskResponse?.result;
    const total = taskResponse?.result?.filtered_total ?? 0;
    const totalPages = Math.max(1, Math.ceil(total / PREVIEW_PAGE_SIZE) || 1);
    if (previewPage.value > totalPages) {
      previewPage.value = totalPages;
    }

  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    validating.value = false;
    taskId.value = null;
  }
};

const setPreviewFilter = async (filter) => {
  if (isPreviewBusy.value) return;
  const next = previewFilter.value === filter ? 'all' : filter;
  if (next === previewFilter.value) return;
  previewFilter.value = next;
  previewPage.value = 1;
  await loadPreview();
};

const onPreviewFilterSelect = async () => {
  if (isPreviewBusy.value) return;
  previewPage.value = 1;
  await loadPreview();
};

const handlePreviewPageChange = async (newPage) => {
  if (isPreviewBusy.value || newPage === previewPage.value) return;
  previewPage.value = newPage;
  await loadPreview();
};

const getPreviewActionLabel = (row) => {
  if (row.action === 'would_create') return t('statistics_block.reading_document_action_would_create');
  if (row.action === 'would_update') return t('statistics_block.reading_document_action_would_update');
  if (row.action === 'not_found') return t('statistics_block.reading_document_action_not_found');
  if (row.action === 'skip') {
    const reasonKey = {
      skipped_existing: 'statistics_block.reading_document_action_skipped_existing',
      skipped_no_date: 'statistics_block.reading_document_action_skipped_no_date',
      no_supply_points: 'statistics_block.reading_document_action_no_supply_points',
      no_contracts: 'statistics_block.reading_document_action_no_contracts',
    }[row.reason];
    return reasonKey ? t(reasonKey) : row.reason || '—';
  }
  return row.action || '—';
};

const getPreviewActionClass = (row) => {
  if (row.action === 'would_create') return 'bg-green-100 text-green-800';
  if (row.action === 'would_update') return 'bg-orange-100 text-orange-800';
  if (row.action === 'not_found') return 'bg-red-100 text-red-800';
  if (row.action === 'skip') {
    if (row.reason === 'skipped_existing') return 'bg-yellow-100 text-yellow-800';
    if (row.reason === 'skipped_no_date') return 'bg-red-100 text-red-800';
    return 'bg-orange-100 text-orange-800';
  }
  return 'bg-slate-100 text-slate-700';
};

const formatPreviewCell = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  return value;
};

const formatPreviewBoolean = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  return value === true || value === 'true' || value === 1 || value === '1'
    ? t('common.yes')
    : t('common.no');
};

const buildUploadPayload = () => {
  const data = {
    token: _.random(10000, 99999),
    file: file.value,
    auto_process: false,
  };
  if (isCustomTemplate.value) {
    data.template = selectedTemplateKey.value;
  }
  data.is_liters = isLitersFromUnit(readingVolumeUnit.value);
  return data;
};

const runValidate = async (id, { refresh = false } = {}) => {
  resetPreviewTableState();
  await loadPreview({ refresh, id });
};

const uploadAndValidate = async () => {
  if (!file.value || saving.value || validating.value || taskId.value) return;

  if (isCustomTemplate.value && columnsDirty.value) {
    await saveTemplateColumns();
  }

  saving.value = true;
  try {
    const payload = buildUploadPayload();
    const res = documentId.value
      ? await $ReadingDocumentApiService.update(documentId.value, payload)
      : await $ReadingDocumentApiService.save(payload);

    documentId.value = res.id;
    // PATCH/POST invalida last_preview; primera validació reconstrueix la cache
    await runValidate(res.id, { refresh: true });
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
};

const goToUpload = () => {
  if (processing.value) return;
  step.value = 'upload';
  file.value = null;
  previewData.value = null;
  resetPreviewTableState();
};

const revalidate = async () => {
  if (!documentId.value || validating.value || processing.value) return;
  await runValidate(documentId.value, { refresh: true });
};

const sleep = (ms, signal) =>
  new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timeoutId = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timeoutId);
      signal?.removeEventListener('abort', onAbort);
      reject(new DOMException('Aborted', 'AbortError'));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });

const pollProcessingTask = async (taskId) => {
  processPollAbort.value?.abort();
  const abortController = new AbortController();
  processPollAbort.value = abortController;
  const signal = abortController.signal;

  while (!signal.aborted) {
    const taskResponse = await $apiManager.checkTask(taskId);
    if (signal.aborted) return null;

    const state = taskResponse?.state != null ? String(taskResponse.state).toUpperCase() : '';
    if (state === 'FAILURE') {
      const backendMsg =
        taskResponse?.error ||
        taskResponse?.message ||
        taskResponse?.result?.error ||
        taskResponse?.result?.message;
      throw new Error(backendMsg || t('common.error'));
    }

    if (state === 'SUCCESS') {
      return taskResponse;
    }

    await sleep(TASK_POLL_INTERVAL_MS, signal);
  }

  return null;
};

const confirmProcess = async () => {
  if (!documentId.value || processing.value) return;

  processing.value = true;
  step.value = 'processing';
  try {
    const processResponse = await $ReadingDocumentApiService.process(documentId.value);
    if (!processResponse?.task_id) {
      throw new Error(t('common.error'));
    }

    // 409: la tasca ja s'havia engegat (doble clic o status processing); continuem el polling
    await pollProcessingTask(processResponse.task_id);
    const finalDocument = await $ReadingDocumentApiService.getDetail(documentId.value);
    toast.success(t('statistics_block.reading_document_process_success'));
    emit('on-processed', finalDocument);
  } catch (err) {
    console.error(err);
    toast.error(err?.message || t('common.error'));
    step.value = 'preview';
  } finally {
    processing.value = false;
  }
};

const isUploadBusy = computed(() => saving.value || validating.value || !!taskId.value);
const isPreviewBusy = computed(() => validating.value || processing.value || !!taskId.value);

watch(selectedTemplateKey, () => {
  loadTemplateColumns();
});

onMounted(async () => {
  objectPermissions.value = await $ReadingApiService.getPermissions();
  if (!objectPermissions.value?.can_change) {
    toast.error(t('common.no_permissions'));
    emit('close');
    return;
  }
  await loadImportTemplates();
});

onBeforeUnmount(() => {
  processPollAbort.value?.abort();
  processPollAbort.value = null;
});

</script>

<template>
  <div id="add-readings" class="text-base max-w-full">

    <div>
      <div v-if="showTitle" class="flex justify-between items-center mb-6">
        <H1>{{ t('common.add') }} {{ t('readings') }}</H1>
      </div>
      <!-- <ReadingBatchEdit/> -->
      <div>
        <div v-if="step === 'upload'" class="space-y-4">
          <section class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-4">
              {{ t('statistics_block.reading_document_import_card_title') }}
            </h2>

            <div class="flex flex-col gap-4 xl:flex-row xl:items-start">
              <div class="flex-1 min-w-0">
                <label class="block text-sm font-medium text-slate-600 mb-1.5">
                  {{ t('statistics_block.reading_document_file_label') }}
                </label>
                <AtomsInputFile @update="handleDocumentUpdate" @delete="handleDocumentDelete" :name="'Fitxer'"
                  :uploaded="file" class="w-full" full-width />
              </div>

              <div class="xl:w-72 shrink-0">
                <label class="block text-sm font-medium text-slate-600 mb-1.5">
                  {{ t('common.template') }}
                </label>
                <div class="flex items-stretch gap-1.5">
                  <select v-model="selectedTemplateKey" class="input text-sm py-2 flex-1 min-w-0"
                    :aria-label="t('common.template')">
                    <option value="default">{{ t('default') }}</option>
                    <option v-for="tpl in importTemplates" :key="tpl.id" :value="String(tpl.id)">
                      {{ tpl.name }}
                    </option>
                  </select>
                  <button type="button"
                    class="inline-flex items-center justify-center px-2.5 rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
                    :title="t('statistics_block.reading_document_template_info')"
                    :aria-label="t('statistics_block.reading_document_template_info')" @click="openFormatDetails">
                    <Icon name="fa6-solid:circle-info" class="text-sm" />
                  </button>
                  <button type="button"
                    class="inline-flex items-center justify-center px-2.5 rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
                    :title="t('statistics_block.reading_document_configure_template')"
                    :aria-label="t('statistics_block.reading_document_configure_template')" @click="openFormatDetails">
                    <Icon name="fa6-solid:pen-to-square" class="text-sm" />
                  </button>
                </div>
                <p class="mt-1.5 text-xs text-slate-500 truncate" :title="selectedTemplateSummary">
                  {{ selectedTemplateSummary }}
                </p>
              </div>

              <div class="xl:shrink-0" style="padding-top: 1.5rem;">
                <button v-if="!taskId" type="button" class="button-secondary w-full xl:w-auto whitespace-nowrap"
                  :disabled="!file || isUploadBusy" @click="uploadAndValidate">
                  <Icon :name="isUploadBusy ? 'fa6-solid:spinner' : 'fa6-solid:file-circle-check'"
                    :class="{ 'animate-spin': isUploadBusy }" />
                  &nbsp;
                  {{
                    isUploadBusy
                      ? t('common.loading')
                      : t('statistics_block.reading_document_upload_validate')
                  }}
                </button>
                <AtomsProcessColorBadge class="w-fit py-2" v-else @refresh="getTaskData(taskId)"
                  :value="`${t('common.loading')}`" :color="'green'" :taskId="taskId"></AtomsProcessColorBadge>
              </div>
            </div>
          </section>

          <details ref="formatDetailsRef" class="rounded-lg border border-slate-200 bg-slate-50 group">
            <summary class="flex flex-wrap items-center justify-between gap-3 cursor-pointer list-none p-4">
              <div class="flex items-center gap-2 min-w-0">
                <Icon name="fa6-solid:angle-down"
                  class="group-open:rotate-180 text-lg transition-all duration-300 shrink-0" />
                <Icon name="fa6-solid:file-circle-question" class="text-sky-500 text-lg shrink-0" />
                <div class="min-w-0">
                  <span class="font-semibold text-slate-800 block">
                    {{ t('statistics_block.reading_document_template_panel_title') }}
                  </span>
                  <span class="text-xs text-slate-500 truncate block">
                    {{ selectedTemplateSummary }}
                  </span>
                </div>
              </div>
              <div class="flex items-center gap-2 shrink-0" @click.stop>
                <button type="button"
                  class="inline-flex items-center justify-center px-2 py-1.5 rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                  :title="t('common.new_template')" :aria-label="t('common.new_template')" :disabled="deletingTemplate"
                  @click="openCreateTemplate">
                  <Icon name="fa6-solid:plus" class="text-sm" />
                </button>
                <button type="button"
                  class="inline-flex items-center justify-center px-2 py-1.5 rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                  :title="t('common.delete')" :aria-label="t('common.delete')"
                  :disabled="!isCustomTemplate || deletingTemplate" @click="deleteSelectedTemplate">
                  <Icon :name="deletingTemplate ? 'fa6-solid:spinner' : 'fa6-solid:trash-can'" class="text-sm"
                    :class="{ 'animate-spin': deletingTemplate }" />
                </button>
                <button v-if="!isCustomTemplate" type="button" class="button-default whitespace-nowrap"
                  @click="generateTemplate">
                  <Icon name="fa6-solid:download" />
                  {{ t('common.template') }}
                </button>
              </div>
            </summary>

            <div class="px-4 pb-4 border-t border-slate-200/80">
              <div v-if="creatingTemplate"
                class="mt-4 flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4" @click.stop>
                <div class="flex-1 min-w-[12rem]">
                  <label class="block text-sm font-medium text-slate-500 mb-1">{{ t('common.name') }} *</label>
                  <input v-model="newTemplateName" type="text" class="input w-full" :placeholder="t('common.name')"
                    :disabled="creatingTemplateSaving" @keyup.enter="saveNewTemplate" />
                </div>
                <div class="flex gap-2">
                  <button type="button" class="button-default"
                    :disabled="creatingTemplateSaving || !newTemplateName.trim()" @click="saveNewTemplate">
                    <Icon :name="creatingTemplateSaving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                      :class="{ 'animate-spin': creatingTemplateSaving }" />
                    {{ creatingTemplateSaving ? t('common.loading') : t('common.save') }}
                  </button>
                  <button type="button" class="button-secondary" :disabled="creatingTemplateSaving"
                    @click="cancelCreateTemplate">
                    {{ t('common.cancel') }}
                  </button>
                </div>
              </div>

              <div class="mt-5">
                <p class="text-sm text-slate-600 mb-4 leading-relaxed">
                  {{ t('informative_block.format_cols') }}:
                </p>

                <div class="space-y-2 mb-6">
                  <p v-if="isCustomTemplate" class="px-4 mb-1 text-xs text-slate-600 leading-relaxed">
                    {{ t('statistics_block.reading_batch_import_identifier_hint_prefix') }}
                    <span class="text-red-500 font-semibold">*</span>
                    {{ t('statistics_block.reading_batch_import_identifier_hint_suffix') }}
                  </p>
                  <div v-if="isCustomTemplate" class="flex items-center justify-between gap-3 px-4 pb-0.5">
                    <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {{ t('statistics_block.reading_batch_import_col_field') }}
                    </span>
                    <div class="flex items-center gap-2 shrink-0">
                      <span
                        class="text-xs font-semibold uppercase tracking-wide text-slate-500 text-center min-w-[5.5rem]">
                        {{ t('statistics_block.reading_batch_import_col_original_name') }}
                      </span>
                      <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 w-36">
                        {{ t('statistics_block.reading_batch_import_col_mapped_name') }}
                      </span>
                    </div>
                  </div>
                  <div v-for="col in displayColumns" :key="col.original_name"
                    class="flex items-center justify-between gap-3 py-2 px-4 bg-white border border-slate-200 rounded-md">
                    <span class="text-sm font-medium text-slate-700 inline-flex items-center gap-1.5 flex-wrap"
                      :class="{ italic: col.optional }">
                      <template v-if="col.readingUnitSelect">
                        <span
                          class="inline-flex items-stretch rounded-md border border-slate-300 bg-white shadow-sm overflow-hidden focus-within:ring-2 focus-within:ring-sky-500 focus-within:ring-offset-0"
                          role="group" :aria-label="t('statistics_block.reading_batch_import_reading_unit')">
                          <span
                            class="inline-flex items-center px-2.5 py-1 text-sm font-medium text-slate-700 border-r border-slate-300 bg-slate-50">
                            {{ t(col.labelKey) }}
                          </span>
                          <span class="relative inline-flex items-center min-w-0">
                            <select v-model="readingVolumeUnit"
                              class="h-full min-w-[4.25rem] cursor-pointer appearance-none border-0 rounded-none bg-transparent py-1 pl-2 pr-7 text-sm font-medium text-slate-700 shadow-none focus:outline-none focus:ring-0 disabled:cursor-not-allowed disabled:opacity-60"
                              :disabled="columnsLoading || columnsSaving"
                              :aria-label="t('statistics_block.reading_batch_import_reading_unit')"
                              @change="onReadingVolumeUnitChange">
                              <option v-for="opt in readingVolumeUnitOptions" :key="opt.value" :value="opt.value">
                                {{ opt.label }}
                              </option>
                            </select>
                            <Icon name="fa6-solid:chevron-down"
                              class="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-xs text-slate-400"
                              aria-hidden="true" />
                          </span>
                        </span>
                      </template>
                      <template v-else>
                        {{ t(col.labelKey) }}{{ col.labelSuffix ?? '' }}
                      </template>
                      <template v-if="col.labelSuffixKey">
                        ({{ t(col.labelSuffixKey) }})
                      </template>
                      <span v-if="isCustomTemplate && col.identifierGroup" class="text-red-500" aria-hidden="true">
                        *</span>
                      <template v-if="col.optional">
                        ({{ t('common.optional') }})
                      </template>
                    </span>
                    <div class="flex items-center gap-2 shrink-0">
                      <code class="text-xs px-2 py-1 rounded font-bold font-mono" :class="col.codeClass">
    {{ col.original_name }}
  </code>
                      <input v-if="isCustomTemplate" v-model="col.mapped_name" type="text"
                        class="input text-sm py-1 px-2 w-36" :placeholder="col.original_name"
                        :disabled="columnsLoading || columnsSaving"
                        :aria-label="`${t('statistics_block.reading_batch_import_col_mapped_name')} (${col.original_name})`"
                        @input="markColumnsDirty" />
                    </div>
                  </div>
                </div>

                <div v-if="isCustomTemplate && columnsDirty" class="mb-6 flex justify-end">
                  <button type="button"
                    class="inline-flex items-center gap-1.5 rounded-md border border-sky-400/60 bg-sky-500 px-3 py-2 text-sm font-medium text-white shadow-none transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="columnsSaving || columnsLoading" @click="saveTemplateColumns">
                    <Icon :name="columnsSaving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                      class="size-4 shrink-0 opacity-95" :class="{ 'animate-spin': columnsSaving }" />
                    {{ columnsSaving ? t('common.loading') : t('common.save') }}
                  </button>
                </div>

                <div class="bg-white border border-slate-200 rounded-lg p-4">
                  <h4 class="font-semibold text-slate-800 mb-3">{{ t('informative_block.csv_example') }}</h4>
                  <div class="bg-slate-100 p-3 rounded overflow-x-auto">
                    <div class="text-xs font-mono">
                      <div class="flex mb-2">
                        <div class="w-16 text-blue-600 font-bold">meter</div>
                        <div class="w-24 text-green-600 font-bold">reading_value</div>
                        <div class="w-28 text-purple-600 font-bold">reading_date</div>
                        <div class="w-20 text-orange-600 font-bold">origin</div>
                        <div class="w-20 text-red-600 font-bold">is_control</div>
                        <div class="w-20 text-yellow-600 font-bold">leak_value</div>
                        <div class="w-20 text-teal-600 font-bold">observation</div>
                      </div>
                      <div class="flex mb-1">
                        <div class="w-16 text-blue-700">M001</div>
                        <div class="w-24 text-green-700">1234</div>
                        <div class="w-28 text-purple-700">30-09-2025</div>
                        <div class="w-20 text-orange-700">manual</div>
                        <div class="w-20 text-red-700">false</div>
                        <div class="w-20 text-yellow-700">0</div>
                        <div class="w-20 text-teal-700"></div>
                      </div>
                      <div class="flex mb-1">
                        <div class="w-16 text-blue-700">M002</div>
                        <div class="w-24 text-green-700">987</div>
                        <div class="w-28 text-purple-700">30-09-2025</div>
                        <div class="w-20 text-orange-700">pda</div>
                        <div class="w-20 text-red-700">true</div>
                        <div class="w-20 text-yellow-700">0</div>
                        <div class="w-20 text-teal-700">BG</div>
                      </div>
                      <div class="flex mb-1">
                        <div class="w-16 text-blue-700">M003</div>
                        <div class="w-24 text-green-700">2156</div>
                        <div class="w-28 text-purple-700">30-09-2025</div>
                        <div class="w-20 text-orange-700">manual</div>
                        <div class="w-20 text-red-700">false</div>
                        <div class="w-20 text-yellow-700">12</div>
                        <div class="w-20 text-teal-700"></div>
                      </div>
                      <div class="flex mb-1">
                        <div class="w-16 text-blue-700">M004</div>
                        <div class="w-24 text-green-700">543</div>
                        <div class="w-28 text-purple-700">30-09-2025</div>
                        <div class="w-20 text-orange-700">pda</div>
                        <div class="w-20 text-red-700">false</div>
                        <div class="w-20 text-yellow-700">0</div>
                        <div class="w-20 text-teal-700">BG</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </details>
        </div>

        <div v-if="step === 'preview' || step === 'processing'"
          class="mb-6 rounded-lg border border-slate-200 bg-white p-4">
          <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 class="text-lg font-semibold text-slate-800">
              {{ t('statistics_block.reading_document_preview_title') }}
            </h2>
            <!-- <div v-if="processing" class="inline-flex items-center gap-2 text-sm text-slate-600">
              <Icon name="fa6-solid:spinner" class="animate-spin" />
              {{ t('statistics_block.reading_document_processing') }}
            </div> -->
          </div>

          <div v-if="previewData?.stats" class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <button v-for="card in previewStatCards" :key="card.key" type="button"
              class="rounded-lg px-3 py-2 text-center transition-all relative min-h-[4.25rem]" :class="[
                card.class,
                (card.value ?? 0) > 0 || card.filter === 'all'
                  ? 'cursor-pointer hover:ring-2 hover:ring-sky-400/60'
                  : 'opacity-60 cursor-default',
                previewFilter === card.filter ? 'ring-2 ring-sky-500 shadow-sm' : '',
                (taskId || validating) && previewFilter !== card.filter ? 'opacity-40 pointer-events-none' : '',
              ]"
              :disabled="isPreviewBusy || ((card.value ?? 0) === 0 && card.filter !== 'all')"
              :title="t('statistics_block.reading_document_preview_filter_hint')"
              @click="setPreviewFilter(card.filter)">
              <div v-if="taskId && previewFilter === card.filter" class="flex items-center justify-center py-0.5"
                @click.stop>
                <AtomsProcessColorBadge class="w-fit py-1 text-xs" :value="`${t('common.loading')}`"
                  :taskId="taskId" :noBackground="true" @refresh="getTaskData(taskId)" />
              </div>
              <div v-else-if="validating && previewFilter === card.filter"
                class="flex items-center justify-center py-2 text-slate-600">
                <Icon name="fa6-solid:spinner" class="animate-spin text-lg" />
              </div>
              <template v-else>
                <div class="text-xl font-bold">{{ card.value ?? 0 }}</div>
                <div class="text-xs font-medium mt-0.5">{{ t(card.labelKey) }}</div>
              </template>
            </button>
          </div>

          <div class="transition-opacity"
            :class="(taskId || validating) ? 'opacity-40 pointer-events-none select-none' : ''"
            :aria-busy="!!(taskId || validating)">
            <div v-if="previewData" class="flex flex-wrap items-center justify-between gap-3 mb-3">
              <label class="inline-flex items-center gap-2 text-sm text-slate-600">
                <span class="font-medium">{{ t('statistics_block.reading_document_preview_filter') }}:</span>
                <select v-model="previewFilter" class="input text-sm py-1.5 min-w-[12rem]" :disabled="isPreviewBusy"
                  @change="onPreviewFilterSelect">
                  <option v-for="option in previewFilterOptions" :key="option.value" :value="option.value">
                    {{ option.label }} ({{ option.count }})
                  </option>
                </select>
              </label>
              <span class="text-xs text-slate-500">
                {{ t('statistics_block.reading_document_preview_showing_rows', {
                  shown: previewData.filtered_total ?? previewRows.length,
                  total: previewData.total_rows ?? previewData.stats?.rows ?? 0,
                }) }}
              </span>
            </div>

            <div v-if="previewRows.length"
              class="overflow-x-auto border border-slate-200 rounded-lg mb-3 max-h-[45vh] overflow-y-auto">
              <table class="w-full text-sm min-w-[72rem]">
                <thead class="bg-slate-100 text-slate-600 sticky top-0 z-10">
                  <tr>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">#</th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">{{ t('service_block.meter_code') }}</th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">{{ t('service_block.comm_module') }}
                    </th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">{{ t('contract') }}</th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">{{ t('billing_block.reading_date') }}
                    </th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">{{ t('reading') }}</th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">
                      {{ t('statistics_block.reading_document_preview_col_raw_value') }}
                    </th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">
                      {{ t('billing_block.previous_reading') }}
                    </th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">{{ t('common.origin') }}</th>
                    <th class="px-3 py-2 text-center font-medium whitespace-nowrap">
                      {{ t('billing_block.short_control_reading') }}
                    </th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">{{ t('billing_block.leak') }}</th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">{{ t('common.observation') }}</th>
                    <th class="px-3 py-2 text-left font-medium whitespace-nowrap">
                      {{ t('statistics_block.reading_document_preview_col_action') }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="(row, index) in previewRows" :key="`${row.row_index}-${index}`">
                    <td class="px-3 py-2 text-slate-600">{{ row.row_index }}</td>
                    <td class="px-3 py-2 text-slate-800 whitespace-nowrap">{{ formatPreviewCell(row.meter_code) }}</td>
                    <td class="px-3 py-2 text-slate-700 whitespace-nowrap">{{ formatPreviewCell(row.comm_module) }}</td>
                    <td class="px-3 py-2 text-slate-700 whitespace-nowrap">{{ formatPreviewCell(row.contract_token) }}
                    </td>
                    <td class="px-3 py-2 text-slate-700 whitespace-nowrap">
                      {{ row.reading_date ? formatDate(row.reading_date) : formatPreviewCell(row.reading_date_raw) }}
                    </td>
                    <td class="px-3 py-2 text-slate-700">{{ formatPreviewCell(row.reading_value) }}</td>
                    <td class="px-3 py-2 text-slate-500">{{ formatPreviewCell(row.raw_reading_value) }}</td>
                    <td class="px-3 py-2 text-slate-700">{{ formatPreviewCell(row.previous_reading_value) }}</td>
                    <td class="px-3 py-2 text-slate-700">{{ formatPreviewCell(row.origin) }}</td>
                    <td class="px-3 py-2 text-center">
                      <span
                        v-if="row.is_control === true || row.is_control === false || row.is_control === 'true' || row.is_control === 'false'"
                        class="inline-flex rounded px-2 py-0.5 text-xs font-semibold"
                        :class="(row.is_control === true || row.is_control === 'true') ? 'bg-sky-100 text-sky-800' : 'bg-slate-100 text-slate-500'">
                        {{ formatPreviewBoolean(row.is_control) }}
                      </span>
                      <span v-else class="text-slate-400">—</span>
                    </td>
                    <td class="px-3 py-2 text-slate-700">{{ formatPreviewCell(row.leak_value) }}</td>
                    <td class="px-3 py-2 text-slate-700 max-w-[10rem] truncate" :title="row.observation || ''">
                      {{ formatPreviewCell(row.observation) }}
                    </td>
                    <td class="px-3 py-2">
                      <span class="inline-flex rounded px-2 py-0.5 text-xs font-semibold whitespace-nowrap"
                        :class="getPreviewActionClass(row)">
                        {{ getPreviewActionLabel(row) }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-else-if="previewData"
              class="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 mb-3">
              {{ t('statistics_block.reading_document_preview_no_rows_for_filter') }}
            </div>

            <Pagination v-if="previewPagination.totalPages > 1" class="mb-3" :pagination="previewPagination"
              @update:page="handlePreviewPageChange" />

            <p v-if="previewData?.rows_truncated" class="text-xs text-slate-500 mb-4">
              {{
                t('statistics_block.reading_document_preview_page_hint', {
                  shown: previewRows.length,
                  total: previewData.filtered_total ?? previewData.total_rows ?? 0,
                })
              }}
            </p>

            <div
              class="sticky bottom-0 z-10 -mx-4 px-4 pt-3 pb-1 bg-white border-t border-slate-200 flex flex-wrap justify-end gap-3">
              <button v-if="!processing" type="button" class="button-secondary" :disabled="isPreviewBusy" @click="goToUpload">
                {{ t('statistics_block.reading_document_change_file') }}
              </button>
              <button v-if="!processing" type="button" class="button-secondary" :disabled="isPreviewBusy" @click="revalidate">
                <Icon :name="validating ? 'fa6-solid:spinner' : 'fa6-solid:rotate-right'"
                  :class="{ 'animate-spin': validating }" />
                &nbsp;{{ t('statistics_block.reading_document_revalidate') }}
              </button>
              <div class="flex flex-col items-end gap-2">
                <button type="button" class="button-primary" :disabled="isPreviewBusy" @click="confirmProcess">
                  <Icon :name="processing ? 'fa6-solid:spinner' : 'fa6-solid:check'"
                    :class="{ 'animate-spin': processing }" />
                  &nbsp;{{ t('statistics_block.reading_document_confirm_entry') }}
                </button>
                <p v-if="processing" class="text-xs font-bold text-orange-400">
                  {{ t('informative_block.info_celery_you_can_exit') }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>