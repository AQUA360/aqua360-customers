<script setup>
// Informes personalitzats: consultes SQL desades (django-sql-explorer) que es poden crear,
// desar, tornar a executar amb paràmetres, analitzar en taula dinàmica i exportar.
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import CustomReportSchema from '~/components/molecules/CustomReportSchema.vue';
import CustomReportResultTable from '~/components/molecules/CustomReportResultTable.vue';
import CustomReportPivot from '~/components/molecules/CustomReportPivot.vue';

const { t, locale } = useI18n();
const toast = useToast();
const route = useRoute();
const router = useRouter();
const { $CustomReportApiService: api } = useNuxtApp();

const PARAM_REGEX = /\$\$([a-z0-9_]+)(?:\|([^$:]+))?(?::([^$]+))?\$\$/gi;
const PARAM_EXAMPLE = '$$date_from|From:2026-01-01$$';

const status = ref(null);
const reports = ref([]);
const search = ref('');
const loadingList = ref(true);

const emptyForm = () => ({ id: null, title: '', description: '', sql: '' });
const form = reactive(emptyForm());
const savedSnapshot = ref(JSON.stringify(emptyForm()));
const selected = ref(null);
const paramValues = reactive({});

const result = ref(null);
const runError = ref('');
const running = ref(false);
const saving = ref(false);
const exporting = ref(false);
const resultView = ref('table');

const showSchema = ref(false);
const schema = ref([]);
const schemaLoading = ref(false);
const showSqlForViewer = ref(false);
const sqlInput = ref(null);

const canChange = computed(() => !!status.value?.can_change);
const enabled = computed(() => !!status.value?.enabled);
const snapshotOf = (f) => JSON.stringify({ id: f.id, title: f.title, description: f.description, sql: f.sql });
const dirty = computed(() => canChange.value && snapshotOf(form) !== savedSnapshot.value);
const isNew = computed(() => !form.id);

const filteredReports = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return reports.value;
  return reports.value.filter((r) => `${r.title} ${r.description}`.toLowerCase().includes(q));
});

const detectedParams = computed(() => {
  const seen = new Map();
  for (const match of (form.sql || '').matchAll(PARAM_REGEX)) {
    const name = match[1].toLowerCase();
    if (!seen.has(name)) seen.set(name, { name, label: match[2] || name, default: match[3] || '' });
  }
  return [...seen.values()];
});

watch(detectedParams, (params) => {
  for (const p of params) {
    if (!(p.name in paramValues)) paramValues[p.name] = p.default;
  }
}, { immediate: true });

const paramsPayload = () => Object.fromEntries(detectedParams.value.map((p) => [p.name, paramValues[p.name] ?? '']));

const dateTimeFormat = computed(() => new Intl.DateTimeFormat(locale.value, { dateStyle: 'short', timeStyle: 'short' }));
const formatDate = (value) => (value ? dateTimeFormat.value.format(new Date(value)) : '');

// --- llista ----------------------------------------------------------------------------------

const loadReports = async () => {
  loadingList.value = true;
  try {
    reports.value = await api.getAll();
  } catch (e) {
    console.error(e);
  } finally {
    loadingList.value = false;
  }
};

const confirmDiscard = () => !dirty.value || window.confirm(t('custom_report_block.confirm_discard'));

const resetParams = () => {
  Object.keys(paramValues).forEach((k) => delete paramValues[k]);
  for (const p of detectedParams.value) paramValues[p.name] = p.default;
};

const applyReport = (report) => {
  selected.value = report;
  Object.assign(form, { id: report?.id ?? null, title: report?.title ?? '', description: report?.description ?? '', sql: report?.sql ?? '' });
  savedSnapshot.value = snapshotOf(form);
  resetParams();
  result.value = null;
  runError.value = '';
  showSqlForViewer.value = false;
};

const selectReport = (report) => {
  if (report.id === form.id || !confirmDiscard()) return;
  applyReport(report);
  router.replace({ query: { ...route.query, id: report.id } });
};

const newReport = () => {
  if (!confirmDiscard()) return;
  applyReport(null);
  const { id, ...query } = route.query;
  router.replace({ query });
  nextTick(() => sqlInput.value?.focus());
};

// --- edició ----------------------------------------------------------------------------------

const save = async (asNew = false) => {
  if (!form.title.trim()) {
    toast.warning(t('custom_report_block.title_required'));
    return;
  }
  saving.value = true;
  try {
    const saved = await api.save({ ...form, id: asNew ? null : form.id });
    toast.success(t('custom_report_block.saved'));
    await loadReports();
    const fresh = reports.value.find((r) => r.id === saved.id) || saved;
    selected.value = fresh;
    Object.assign(form, { id: saved.id, title: saved.title, description: saved.description, sql: saved.sql });
    savedSnapshot.value = snapshotOf(form);
    router.replace({ query: { ...route.query, id: saved.id } });
  } catch (e) {
    console.error(e);
  } finally {
    saving.value = false;
  }
};

const removeReport = async () => {
  if (!form.id || !window.confirm(t('custom_report_block.confirm_delete'))) return;
  try {
    await api.remove(form.id);
    toast.success(t('custom_report_block.deleted'));
    savedSnapshot.value = snapshotOf(form); // evita la pregunta de canvis sense desar
    applyReport(null);
    const { id, ...query } = route.query;
    router.replace({ query });
    await loadReports();
  } catch (e) {
    console.error(e);
  }
};

const insertAtCursor = (text) => {
  const el = sqlInput.value;
  if (!el) {
    form.sql += text;
    return;
  }
  const start = el.selectionStart ?? form.sql.length;
  const end = el.selectionEnd ?? start;
  form.sql = form.sql.slice(0, start) + text + form.sql.slice(end);
  nextTick(() => {
    el.focus();
    el.selectionStart = el.selectionEnd = start + text.length;
  });
};

const toggleSchema = async () => {
  showSchema.value = !showSchema.value;
  if (showSchema.value && !schema.value.length && enabled.value) {
    schemaLoading.value = true;
    try {
      schema.value = await api.getSchema();
    } catch (e) {
      console.error(e);
    } finally {
      schemaLoading.value = false;
    }
  }
};

const onSqlKeydown = (event) => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    run();
  } else if (event.key === 'Tab') {
    event.preventDefault();
    insertAtCursor('  ');
  }
};

// --- execució i exportació -----------------------------------------------------------------

// Un informe desat i sense canvis s'executa pel seu id (n'hi ha prou amb permís de lectura);
// el SQL en edició s'envia sencer (cal permís d'edició).
const useSavedReport = computed(() => !!form.id && !dirty.value);

const errorMessage = (e) =>
  e?.response?._data?.error || e?.response?._data?.detail || e?.data?.error || e?.message || t('custom_report_block.error');

const run = async () => {
  if (running.value || !form.sql.trim() || !enabled.value) return;
  running.value = true;
  runError.value = '';
  try {
    result.value = useSavedReport.value
      ? await api.run(form.id, paramsPayload())
      : await api.runSql(form.sql, paramsPayload());
    if (form.id) {
      const item = reports.value.find((r) => r.id === form.id);
      if (item && useSavedReport.value) {
        item.run_count = (item.run_count || 0) + 1;
        item.last_run_at = new Date().toISOString();
      }
    }
  } catch (e) {
    result.value = null;
    runError.value = errorMessage(e);
  } finally {
    running.value = false;
  }
};

const exportAs = async (format) => {
  if (exporting.value || !form.sql.trim() || !enabled.value) return;
  exporting.value = true;
  try {
    const { truncated } = useSavedReport.value
      ? await api.exportReport(form.id, paramsPayload(), format)
      : await api.exportSql(form.sql, paramsPayload(), format, form.title || t('custom_report_block.untitled'));
    if (truncated) toast.warning(t('custom_report_block.export_truncated', { max: status.value.export_max_rows }));
  } catch (e) {
    toast.error(e?.message || t('custom_report_block.error'));
  } finally {
    exporting.value = false;
  }
};

// --- cicle de vida ---------------------------------------------------------------------------

onBeforeRouteLeave(() => confirmDiscard());

onMounted(async () => {
  try {
    status.value = await api.getStatus();
  } catch (e) {
    console.error(e);
    loadingList.value = false;
    return;
  }
  await loadReports();
  const id = Number(route.query.id);
  if (id) {
    const report = reports.value.find((r) => r.id === id);
    if (report) applyReport(report);
  }
});
</script>

<template>
  <div class="px-4 pb-6">
    <div class="mb-4">
      <H1>{{ t('custom_report_block.title') }}</H1>
      <p class="mt-1 text-sm text-slate-500">{{ t('custom_report_block.subtitle') }}</p>
    </div>

    <div v-if="status && !enabled" class="mb-4 flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
      <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5 shrink-0" />
      <span>{{ t('custom_report_block.not_configured') }}</span>
    </div>

    <div v-if="!status && loadingList" class="rounded-md border border-slate-200 bg-white p-8">
      <AppLoading :text="t('common.loading')" />
    </div>

    <div v-else-if="status" class="flex flex-col gap-4 lg:flex-row lg:items-start">
      <!-- Llista d'informes desats -->
      <aside class="w-full shrink-0 rounded-md border border-slate-300 bg-white p-3 shadow-sm lg:sticky lg:top-4 lg:w-72">
        <button
          v-if="canChange"
          type="button"
          class="mb-3 flex w-full items-center justify-center gap-2 rounded-md bg-sky-700 px-3 py-2 text-sm font-medium text-white hover:bg-sky-800"
          @click="newReport"
        >
          <Icon name="fa6-solid:plus" /> {{ t('custom_report_block.new_report') }}
        </button>
        <input
          v-model="search"
          type="search"
          class="mb-2 w-full rounded border border-slate-300 px-2 py-1.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          :placeholder="t('custom_report_block.search_reports')"
        />
        <div v-if="loadingList" class="py-4"><AppLoading :text="t('common.loading')" /></div>
        <p v-else-if="!filteredReports.length" class="py-4 text-center text-sm text-slate-500">{{ t('custom_report_block.no_reports') }}</p>
        <ul v-else class="max-h-[65vh] space-y-1 overflow-y-auto">
          <li v-for="report in filteredReports" :key="report.id">
            <button
              type="button"
              class="w-full rounded-md border px-2.5 py-2 text-left transition-colors"
              :class="report.id === form.id ? 'border-sky-300 bg-sky-50' : 'border-transparent hover:bg-slate-50'"
              @click="selectReport(report)"
            >
              <div class="truncate text-sm font-medium text-slate-800">{{ report.title }}</div>
              <div v-if="report.description" class="truncate text-xs text-slate-500">{{ report.description }}</div>
              <div class="mt-0.5 text-[11px] text-slate-400">
                <template v-if="report.last_run_at">{{ t('custom_report_block.runs', { n: report.run_count }) }} · {{ formatDate(report.last_run_at) }}</template>
                <template v-else>{{ t('custom_report_block.never_run') }}</template>
              </div>
            </button>
          </li>
        </ul>
      </aside>

      <!-- Editor i resultats -->
      <section class="min-w-0 flex-1 space-y-4">
        <div v-if="!canChange && !form.id" class="rounded-md border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          {{ reports.length ? t('custom_report_block.select_report') : t('custom_report_block.no_reports') }}
        </div>

        <div v-else class="rounded-md border border-slate-300 bg-white p-4 shadow-sm">
          <!-- Capçalera: títol, descripció i accions -->
          <div class="flex flex-col gap-3 xl:flex-row xl:items-start">
            <div class="min-w-0 flex-1 space-y-2">
              <template v-if="canChange">
                <input
                  v-model="form.title"
                  type="text"
                  class="w-full rounded border border-slate-300 px-2 py-1.5 text-lg font-semibold text-slate-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  :placeholder="t('custom_report_block.report_title')"
                />
                <textarea
                  v-model="form.description"
                  rows="1"
                  class="w-full resize-y rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-700 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  :placeholder="t('custom_report_block.report_description')"
                />
              </template>
              <template v-else>
                <h2 class="text-lg font-semibold text-slate-900">{{ form.title }}</h2>
                <p v-if="form.description" class="whitespace-pre-line text-sm text-slate-600">{{ form.description }}</p>
                <p class="text-xs text-slate-500">{{ t('custom_report_block.read_only_notice') }}</p>
              </template>
              <p v-if="selected?.created_by" class="text-xs text-slate-400">
                {{ t('custom_report_block.created_by') }}: {{ selected.created_by }} · {{ formatDate(selected.created_at) }}
              </p>
            </div>
            <div v-if="canChange" class="flex shrink-0 flex-wrap items-center gap-2">
              <span v-if="dirty" class="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">{{ t('custom_report_block.unsaved') }}</span>
              <button
                type="button"
                class="rounded-md bg-sky-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50"
                :disabled="saving || !form.sql.trim() || (!dirty && !isNew)"
                @click="save(false)"
              >
                <Icon name="fa6-solid:floppy-disk" class="mr-1" />{{ t('custom_report_block.save') }}
              </button>
              <button
                v-if="!isNew"
                type="button"
                class="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                :disabled="saving || !form.sql.trim()"
                @click="save(true)"
              >
                {{ t('custom_report_block.save_as_new') }}
              </button>
              <button
                v-if="!isNew"
                type="button"
                class="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50"
                @click="removeReport"
              >
                <Icon name="fa6-solid:trash-can" class="mr-1" />{{ t('custom_report_block.delete') }}
              </button>
            </div>
          </div>

          <!-- SQL -->
          <div class="mt-4">
            <div class="mb-1 flex items-center justify-between gap-2">
              <label class="text-sm font-medium text-slate-700">{{ t('custom_report_block.sql') }}</label>
              <button v-if="canChange" type="button" class="text-xs font-medium text-sky-700 hover:underline" @click="toggleSchema">
                <Icon name="fa6-solid:table-columns" class="mr-1" />{{ t('custom_report_block.schema') }}
              </button>
              <button v-else type="button" class="text-xs font-medium text-sky-700 hover:underline" @click="showSqlForViewer = !showSqlForViewer">
                {{ showSqlForViewer ? t('custom_report_block.hide_sql') : t('custom_report_block.show_sql') }}
              </button>
            </div>
            <div v-if="canChange || showSqlForViewer" class="flex flex-col gap-3 md:flex-row">
              <div class="min-w-0 flex-1">
                <textarea
                  ref="sqlInput"
                  v-model="form.sql"
                  :readonly="!canChange"
                  spellcheck="false"
                  rows="12"
                  class="w-full resize-y rounded border border-slate-300 bg-slate-900 p-3 font-mono text-[13px] leading-relaxed text-slate-100 caret-sky-300 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  placeholder="SELECT ..."
                  @keydown="onSqlKeydown"
                />
                <p v-if="canChange" class="mt-1 text-xs text-slate-500">
                  {{ t('custom_report_block.sql_help') }}
                  <code class="rounded bg-slate-100 px-1 font-mono text-slate-700">{{ PARAM_EXAMPLE }}</code>
                  {{ t('custom_report_block.sql_help_end') }}
                </p>
              </div>
              <div v-if="showSchema && canChange" class="h-80 w-full shrink-0 rounded border border-slate-200 bg-slate-50 p-2 md:h-auto md:max-h-[22rem] md:w-72">
                <CustomReportSchema v-if="enabled" :schema="schema" :loading="schemaLoading" @insert="insertAtCursor" />
                <div v-else class="flex h-full items-start gap-2 p-2 text-xs text-amber-900">
                  <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5 shrink-0" />
                  <span>{{ t('custom_report_block.not_configured') }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Paràmetres i execució -->
          <div class="mt-4 flex flex-col gap-3 border-t border-slate-200 pt-4 md:flex-row md:items-end md:justify-between">
            <div v-if="detectedParams.length" class="flex flex-wrap gap-3">
              <label v-for="p in detectedParams" :key="p.name" class="text-xs font-medium text-slate-600">
                {{ p.label }}
                <input
                  v-model="paramValues[p.name]"
                  type="text"
                  class="mt-1 block w-44 rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  :placeholder="p.default"
                  @keydown.enter.prevent="run"
                />
              </label>
            </div>
            <div v-else />
            <div class="flex flex-wrap items-center gap-2">
              <button
                type="button"
                class="flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                :disabled="running || !form.sql.trim() || !enabled"
                @click="run"
              >
                <Icon :name="running ? 'fa6-solid:spinner' : 'fa6-solid:play'" :class="{ 'animate-spin': running }" />
                {{ running ? t('custom_report_block.running') : t('custom_report_block.run') }}
              </button>
              <div class="flex overflow-hidden rounded-md border border-slate-300">
                <span class="flex items-center bg-slate-50 px-2 text-xs font-medium text-slate-600">
                  <Icon name="fa6-solid:download" class="mr-1" />{{ t('custom_report_block.export') }}
                </span>
                <button
                  type="button"
                  class="border-l border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  :disabled="exporting || !form.sql.trim() || !enabled"
                  @click="exportAs('xlsx')"
                >
                  Excel
                </button>
                <button
                  type="button"
                  class="border-l border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  :disabled="exporting || !form.sql.trim() || !enabled"
                  @click="exportAs('csv')"
                >
                  CSV
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Resultats -->
        <div v-if="canChange || form.id" class="rounded-md border border-slate-300 bg-white p-4 shadow-sm">
          <div v-if="runError" class="rounded-md border border-red-200 bg-red-50 p-3">
            <div class="mb-1 text-sm font-semibold text-red-800">{{ t('custom_report_block.error') }}</div>
            <pre class="whitespace-pre-wrap break-words font-mono text-xs text-red-700">{{ runError }}</pre>
          </div>
          <div v-else-if="running && !result" class="py-6"><AppLoading :text="t('custom_report_block.running')" /></div>
          <p v-else-if="!result" class="py-6 text-center text-sm text-slate-500">{{ t('custom_report_block.run_to_see') }}</p>
          <template v-else>
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div class="flex rounded-md border border-slate-300 p-0.5 text-sm">
                <button
                  v-for="view in ['table', 'pivot']"
                  :key="view"
                  type="button"
                  class="rounded px-3 py-1 font-medium"
                  :class="resultView === view ? 'bg-sky-700 text-white' : 'text-slate-600 hover:bg-slate-50'"
                  @click="resultView = view"
                >
                  {{ t(`custom_report_block.${view}_view`) }}
                </button>
              </div>
              <div class="text-xs text-slate-500">
                {{ t('custom_report_block.rows', { n: result.row_count }) }} · {{ result.duration_ms }} ms
              </div>
            </div>
            <div v-if="result.truncated" class="mb-3 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
              {{ t('custom_report_block.truncated', { n: result.max_rows, max: status.export_max_rows }) }}
            </div>
            <p v-if="!result.row_count" class="py-6 text-center text-sm text-slate-500">{{ t('custom_report_block.no_results') }}</p>
            <CustomReportResultTable v-else-if="resultView === 'table'" :columns="result.columns" :rows="result.rows" />
            <CustomReportPivot v-else :columns="result.columns" :rows="result.rows" />
          </template>
        </div>
      </section>
    </div>
  </div>
</template>
