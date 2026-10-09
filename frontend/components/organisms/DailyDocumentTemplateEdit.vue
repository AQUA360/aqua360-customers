<script setup>
import H1Region from '../atoms/H1Region.vue';
import { useToast } from 'vue-toastification';

const toast = useToast();
const { t } = useI18n();
const props = defineProps({
    id: {
        type: Number,
        default: null
    }
});

const { $ReportsApiService, $DailyDocumentTemplateApiService } = useNuxtApp();
const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);

const loading = ref(false);
const loadingAvailableReports = ref(false);
const saving = ref(false);
const error = ref(null);
const attemptedSave = ref(false);

const availableReports = ref([]);
const selectedSection = ref(null);
const selectedAvailableReport = ref(null);
const searchQuery = ref('');

const normalizedSearch = computed(() => searchQuery.value.trim().toLowerCase());

const reportMatchesSearch = (report) => {
    const query = normalizedSearch.value;
    if (!query) return true;
    return [report.name, report.description, report.sectionName]
        .some((value) => String(value || '').toLowerCase().includes(query));
};

const name = ref('');
const description = ref('');
const daysToComplete = ref(2);

const normalizeReport = (report) => ({
    id: report.id,
    name: report.name || '',
    description: report.description && report.description !== report.name ? report.description : '',
    section: report.section_token || 'other',
    sectionName: report.section_name || t('common.other'),
    position: report.position ?? 0
});

const sectionOptions = computed(() => {
    const map = new Map();
    availableReports.value.forEach((report) => {
        if (!map.has(report.section)) {
            map.set(report.section, {
                value: report.section,
                label: report.sectionName,
                count: 0
            });
        }
        if (reportMatchesSearch(report)) {
            map.get(report.section).count += 1;
        }
    });
    const options = Array.from(map.values());
    return normalizedSearch.value ? options.filter((section) => section.count > 0) : options;
});

const reportsInSection = computed(() => {
    if (!selectedSection.value) return [];
    return availableReports.value
        .filter((report) => report.section === selectedSection.value)
        .filter(reportMatchesSearch)
        .sort((a, b) => a.position - b.position || a.name.localeCompare(b.name));
});

const missingReport = computed(() => attemptedSave.value && !selectedAvailableReport.value);

const getData = async () => {
    if (!props.id) return;
    loading.value = true;
    try {
        const response = await $DailyDocumentTemplateApiService.getDetail(props.id);
        name.value = response.name;
        description.value = response.description;
        daysToComplete.value = response.days_to_complete;
        const report = response.available_report;
        if (report) {
            const normalized = normalizeReport(report);
            selectedSection.value = normalized.section;
            selectedAvailableReport.value = availableReports.value.find((item) => item.id === normalized.id) || normalized;
        }
    } catch (err) {
        console.error(err);
        error.value = err;
    } finally {
        loading.value = false;
    }
};

const getAvailableReports = async () => {
    loadingAvailableReports.value = true;
    try {
        const response = await $ReportsApiService.getActiveReports();
        const list = Array.isArray(response) ? response : (response?.results || []);
        availableReports.value = list.map(normalizeReport);
        if (!selectedSection.value && sectionOptions.value.length) {
            selectedSection.value = sectionOptions.value[0].value;
        }
    } catch (err) {
        console.error(err);
    } finally {
        loadingAvailableReports.value = false;
    }
};

const selectSection = (token) => {
    if (selectedSection.value === token) return;
    selectedSection.value = token;
};

const selectReport = (report) => {
    selectedAvailableReport.value = report;
    console.log(report);
};

watch(normalizedSearch, () => {
    if (!normalizedSearch.value) return;
    if (reportsInSection.value.length) return;
    const firstMatch = sectionOptions.value[0];
    if (firstMatch) selectedSection.value = firstMatch.value;
});

const showSelectedReport = async () => {
    const report = selectedAvailableReport.value;
    if (!report) return;
    searchQuery.value = '';
    if (selectedSection.value !== report.section) {
        selectedSection.value = report.section;
        await nextTick();
    }
    document.getElementById(`daily-report-option-${report.id}`)?.scrollIntoView({
        block: 'nearest',
        behavior: 'smooth'
    });
};

const save = async () => {
    attemptedSave.value = true;
    if (!isValid()) return;
    saving.value = true;
    try {
        const payload = {
            id: props.id || null,
            name: name.value,
            description: description.value,
            days_to_complete: daysToComplete.value,
            available_report_id: selectedAvailableReport.value?.id
        }
        const response = await $DailyDocumentTemplateApiService.save(payload);
        if (response) {
            toast.success(t('common.saved_successfully'));
            emit('changed');
            emit('close-subregion');
        }
    } catch (err) {
        console.error(err);
        error.value = err;
    } finally {
        saving.value = false;
    }
}

const isValid = () => {
    if (!name.value) return false;
    if (daysToComplete.value < 0) return false;
    if (!selectedAvailableReport.value) return false;
    return true
}

onMounted(async () => {
    await getAvailableReports();
    await getData();
});
</script>

<template>
    <div>
        <H1Region class="mb-4">{{ $t('statistics_block.edit_daily_document_template') }}</H1Region>

        <div v-if="loading" class="space-y-3 py-6">
            <div class="h-10 animate-pulse rounded-md bg-slate-100" />
            <div class="h-20 animate-pulse rounded-md bg-slate-100" />
            <div class="h-48 animate-pulse rounded-md bg-slate-100" />
        </div>

        <div v-else class="space-y-5">
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
                    <input type="text" v-model="name" class="input"
                        :class="{ 'invalid': attemptedSave && (name == '' || name == null) }" />
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.expires_in') }}</label>
                    <div class="relative">
                        <input type="number" min="1" v-model="daysToComplete" class="input pr-14"
                            :class="{ 'invalid': attemptedSave && (daysToComplete == '' || daysToComplete == null) }" />
                        <span
                            class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-400">
                            {{ t('common.days') }}
                        </span>
                    </div>
                </div>
                <div class="col-span-2">
                    <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.description') }}</label>
                    <textarea name="description" id="description" rows="3" v-model="description"
                        class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
                </div>
            </div>

            <section class="overflow-hidden rounded-md border bg-white"
                :class="missingReport ? 'border-red-300' : 'border-slate-200'">
                <div class="flex items-start gap-3 border-b border-slate-100 px-3 py-3">
                    <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-sky-700 text-white">
                        <Icon name="fa6-solid:file-lines" class="text-sm" />
                    </div>
                    <div class="min-w-0">
                        <p class="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {{ t('statistics_block.daily_file_generated') }}
                        </p>
                        <p class="mt-0.5 text-sm font-semibold text-slate-900">
                            {{ t('statistics_block.choose_daily_report') }}
                        </p>
                        <p class="mt-0.5 text-xs text-slate-500">
                            {{ t('statistics_block.choose_daily_report_help') }}
                        </p>
                    </div>
                </div>

                <div class="space-y-3 p-3">

                    <div class="relative">
                        <Icon name="fa6-solid:magnifying-glass"
                            class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400" />
                        <input v-model="searchQuery" type="text" :placeholder="t('dashboard.search')"
                            class="block w-full rounded-md border border-gray-300 bg-white py-2 pl-9 pr-8 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-indigo-500"
                            autocomplete="off" />
                        <button v-if="searchQuery" type="button"
                            class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                            @click="searchQuery = ''">
                            <Icon name="fa6-solid:xmark" class="text-sm" />
                        </button>
                    </div>

                    <div v-if="sectionOptions.length" class="flex flex-wrap gap-1.5">
                        <button v-for="section in sectionOptions" :key="section.value" type="button"
                            class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
                            :class="selectedSection === section.value
                                ? 'border-sky-700 bg-sky-700 text-white'
                                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'"
                            @click="selectSection(section.value)">
                            <Icon v-if="selectedAvailableReport?.section === section.value"
                                name="fa6-solid:circle-check" class="text-[10px]" />
                            <span>{{ section.label }}</span>
                            <span class="rounded-full px-1.5 py-px text-[10px] font-semibold tabular-nums"
                                :class="selectedSection === section.value ? 'bg-white/15 text-white' : 'bg-slate-100 text-slate-500'">
                                {{ section.count }}
                            </span>
                        </button>
                    </div>

                    <div v-if="loadingAvailableReports" class="space-y-2">
                        <div v-for="n in 3" :key="n" class="h-16 animate-pulse rounded-md bg-slate-100" />
                    </div>

                    <div v-else-if="!selectedSection"
                        class="rounded-md bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
                        {{ t('statistics_block.report_section') }}
                    </div>

                    <div v-else-if="reportsInSection.length === 0"
                        class="rounded-md bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
                        {{ normalizedSearch ? `${t('common.no_search_results')}: "${searchQuery}"` :
                            t('common.no_records') }}
                    </div>

                    <div v-else class="max-h-80 space-y-2 overflow-y-auto pr-0.5">
                        <button v-for="report in reportsInSection" :key="report.id" type="button"
                            :id="`daily-report-option-${report.id}`"
                            class="flex w-full overflow-hidden rounded-md border text-left transition-all" :class="selectedAvailableReport?.id === report.id
                                ? 'border-sky-700 bg-white ring-1 ring-sky-700'
                                : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'"
                            @click="selectReport(report)">
                            <div class="w-1 shrink-0"
                                :class="selectedAvailableReport?.id === report.id ? 'bg-sky-700' : 'bg-transparent'"
                                aria-hidden="true" />
                            <div class="flex min-w-0 flex-1 items-start gap-3 px-3 py-2.5">
                                <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded text-white"
                                    :class="selectedAvailableReport?.id === report.id ? 'bg-sky-700' : 'bg-sky-500'">
                                    <Icon name="fa6-solid:file-lines" class="text-sm" />
                                </div>
                                <div class="min-w-0 flex-1">
                                    <p class="truncate text-sm font-semibold text-slate-900" :title="report.name">
                                        {{ report.name }}
                                    </p>
                                    <p v-if="report.description" class="mt-0.5 line-clamp-2 text-xs text-slate-500"
                                        :title="report.description">
                                        {{ report.description }}
                                    </p>
                                </div>
                                <Icon v-if="selectedAvailableReport?.id === report.id" name="fa6-solid:circle-check"
                                    class="mt-1 shrink-0 text-sky-700" />
                            </div>
                        </button>
                    </div>

                    <div v-if="selectedAvailableReport"
                        class="flex items-start gap-2.5 rounded-md border border-sky-200 bg-sky-50 px-3 py-2">
                        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-sky-700 text-white">
                            <Icon name="fa6-solid:circle-check" class="text-sm" />
                        </div>
                        <div class="min-w-0 flex-1">
                            <p class="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-800">
                                {{ t('statistics_block.selected_daily_report') }}
                            </p>
                            <p class="truncate text-sm font-semibold text-slate-900"
                                :title="selectedAvailableReport.name">
                                {{ selectedAvailableReport.name }}
                            </p>
                            <p class="mt-0.5 truncate text-xs text-slate-500">
                                <span>{{ selectedAvailableReport.sectionName }}</span>
                                <span v-if="selectedAvailableReport.description">
                                    · {{ selectedAvailableReport.description }}
                                </span>
                            </p>
                        </div>
                        <button type="button"
                            class="shrink-0 self-center rounded-md px-2 py-1 text-xs font-medium text-sky-800 hover:bg-sky-100"
                            @click="showSelectedReport">
                            {{ t('common.show') }}
                        </button>
                    </div>
                </div>
            </section>

            <div class="flex flex-row-reverse border-t border-slate-100 pt-4">
                <button @click="save" :disabled="saving" class="button-primary">
                    <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
                </button>
            </div>
        </div>
    </div>
</template>
