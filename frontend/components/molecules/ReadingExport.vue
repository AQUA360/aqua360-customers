<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import H1Region from '../atoms/H1Region.vue';
import { useI18n } from 'vue-i18n';
import { useServerExport } from '~/composables/useServerExport';

const { t } = useI18n();
const { exporting, runExport } = useServerExport();

const props = defineProps({
    batch_id: {
        type: Number,
        default: null
    }
});

const { $ConfiglistApiService, $ReadingApiService } = useNuxtApp();

const filtering = ref(false);

const select_remote = ref(true);
const select_reader = ref(true);
const select_estimated = ref(false);
const filter_reading_start_date = ref(null);
const filter_reading_end_date = ref(null);
const selected_reader_alerts = ref([]);
const selected_remote_alerts = ref([]);
const selected_reading_alert_types = ref([]);
const selected_min_consumption = ref(null);
const selected_max_consumption = ref(null);
const found_readings = ref([]);

const alerts = ref([]);
const remote_alerts = ref([]);
const reading_alert_types = ref([]);

const hasActiveFilters = computed(() => {
    return (
        !select_remote.value ||
        !select_reader.value ||
        !!filter_reading_start_date.value ||
        !!filter_reading_end_date.value ||
        selected_reading_alert_types.value.length > 0 ||
        selected_reader_alerts.value.length > 0 ||
        selected_remote_alerts.value.length > 0 ||
        selected_min_consumption.value !== null ||
        selected_max_consumption.value !== null
    );
});

const filterData = async () => {
    if (!selected_min_consumption.value && !selected_max_consumption.value && selected_reader_alerts.value.length === 0 && selected_remote_alerts.value.length === 0 && selected_reading_alert_types.value.length === 0) return;
    filtering.value = true;
    try {
        let filter_data = {
            batch_id: props.batch_id || null,
            select_remote: select_remote.value,
            select_reader: select_reader.value,
            select_estimated: select_estimated.value,
            selected_reader_alerts: selected_reader_alerts.value,
            selected_remote_alerts: selected_remote_alerts.value,
            selected_reading_alert_types: selected_reading_alert_types.value,
            selected_min_consumption: selected_min_consumption.value,
            selected_max_consumption: selected_max_consumption.value,
        }
        const response = await $ReadingApiService.filterExportReadings(filter_data);
        if (response) {
            console.log('response::', response);
            found_readings.value = response.reading_ids;
        }
    } catch (error) {
        console.error(error);
    }
    finally {
        filtering.value = false;
    }
};

const exportReadings = async () => {
    if (!confirm(t('confirmation_text_block.confirm_export_readings'))) return;
    try {
        await runExport({
            rows: [],
            columns: [],
            fileName: 'readings',
            totalPages: 2,
            serverExportFn: () => $ReadingApiService.exportReadings({ reading_ids: found_readings.value }),
        });
    } catch (error) {
        console.error(error);
    }
};

const resetFilters = () => {
    select_remote.value = true;
    select_reader.value = true;
    filter_reading_start_date.value = null;
    filter_reading_end_date.value = null;
    selected_reader_alerts.value = [];
    selected_remote_alerts.value = [];
    selected_reading_alert_types.value = [];
    selected_min_consumption.value = null;
    selected_max_consumption.value = null;
    found_readings.value = [];
};

const loadConfigData = async (entity, target, translate = false) => {
    try {
        const data = await $ConfiglistApiService.getAll(entity);

        target.value = (data?.results || []).map((item) => ({
            id: item.id,
            name: item.name,
            label: translate ? t(`billing_block.${item.name}`) : item.name,
            value: item.id
        }));
    } catch (error) {
        console.error(error);
    }
};

const loadData = async () => {
    await loadConfigData('billing/reader-alert', alerts);
    await loadConfigData('billing/remote-reading-alert', remote_alerts);
    await loadConfigData('billing/reading-alert-type', reading_alert_types, true);
};

watch([
    filter_reading_start_date,
    filter_reading_end_date,
    selected_reader_alerts,
    selected_remote_alerts,
    selected_reading_alert_types,
    selected_min_consumption,
    selected_max_consumption,
    select_estimated,
    select_remote,
    select_reader
], () => {
    filterData();
});

onMounted(async () => {
    await loadData();
});
</script>

<template>
    <div class="space-y-5 region__content">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
                <H1Region>{{ $t('billing_block.export_check_readings') }}</H1Region>
                <div class="mt-2 py-1 px-3 bg-sky-50 border-l border-sky-500 text-sky-500 max-w-2xl">
                    {{ $t('informative_block.info_export_readings') }}
                </div>
            </div>
        </div>

        <div class="py-4 px-1 space-y-6">
            <div class="grid gap-6 md:grid-cols-2">
                <div class="space-y-4">
                    <p class="text-xs uppercase tracking-wide text-slate-500">
                        {{ $t('common.origin') }}
                    </p>
                    <div class="flex flex-col gap-2">
                        <label
                            class="flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 hover:border-slate-400 transition">
                            <div>
                                <p>{{ $t('service_block.telecontrol') }}</p>
                            </div>
                            <input type="checkbox" class="toggle toggle-primary" v-model="select_remote">
                        </label>
                        <label
                            class="flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 hover:border-slate-400 transition">
                            <div>
                                <p>{{ $t('billing_block.manual_reading') }}</p>
                            </div>
                            <input type="checkbox" class="toggle toggle-primary" v-model="select_reader">
                        </label>
                        <label
                            class="flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 hover:border-slate-400 transition">
                            <div>
                                <p>{{ $t('billing_block.estimated_reading') }}</p>
                            </div>
                            <input type="checkbox" class="toggle toggle-primary" v-model="select_estimated">
                        </label>
                    </div>
                </div>

                <div>
                    <p class="text-xs uppercase tracking-wide text-slate-500 mb-3">
                        {{ $t('billing_block.consumption') }}
                    </p>
                    <div class="grid gap-3 sm:grid-cols-2">
                        <div>
                            <label for="selected_min_consumption"
                                class="block text-xs font-semibold text-slate-500 mb-1">
                                {{ $t('common.from') }}
                            </label>
                            <input id="selected_min_consumption" type="number" class="input w-full"
                                v-model.number="selected_min_consumption" placeholder="0">
                        </div>
                        <div>
                            <label for="selected_max_consumption"
                                class="block text-xs font-semibold text-slate-500 mb-1">
                                {{ $t('common.to') }}
                            </label>
                            <input id="selected_max_consumption" type="number" class="input w-full"
                                v-model.number="selected_max_consumption" placeholder="9999">
                        </div>
                    </div>
                </div>
            </div>

            <div class="grid gap-6 md:grid-cols-2">
                <div>
                    <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">
                        {{ $t('billing_block.reader_alerts') }}
                    </p>
                    <v-select multiple :options="alerts" label="label" track-by="id" :reduce="option => option.value"
                        class="w-full custom-select" v-model="selected_reader_alerts" :close-on-select="false" />
                </div>

                <div>
                    <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">
                        {{ $t('billing_block.remote_alerts') }}
                    </p>
                    <v-select multiple :options="remote_alerts" label="label" track-by="id"
                        :reduce="option => option.value" class="w-full custom-select" v-model="selected_remote_alerts"
                        :close-on-select="false" />
                </div>

                <div>
                    <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">
                        {{ $t('common.warnings') }}
                    </p>
                    <v-select multiple :options="reading_alert_types" label="label" track-by="id"
                        :reduce="option => option.value" class="w-full custom-select" v-model="selected_reading_alert_types"
                        :close-on-select="false" />
                </div>

            </div>

            <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p class="text-sm text-slate-500">
                    {{ $t('common.total_filtered') }}: {{ found_readings.length || 0 }}
                </p>
                <div class="flex gap-2">
                    <button type="button" class="button-default" :disabled="!hasActiveFilters" @click="resetFilters">
                        {{ $t('common.reset') }}
                    </button>
                    <!-- <button type="button" class="button-secondary flex items-center gap-2" @click="filterData"
                        :disabled="filtering">
                        <span>{{ filtering ? $t('common.loading') : $t('common.filter') }}</span>
                        <Icon :name="filtering ? 'fa6-solid:spinner' : 'fa6-solid:magnifying-glass'"
                            :class="filtering ? 'animate-spin' : ''" class="text-white" />
                    </button> -->
                    <button type="button" class="button-primary flex items-center gap-2" @click="exportReadings"
                        :disabled="filtering || found_readings.length === 0 || exporting">
                        <span>{{ filtering || exporting ? $t('common.loading') : $t('common.export') }}</span>
                        <Icon :name="filtering || exporting ? 'fa6-solid:spinner' : 'fa6-solid:file-excel'"
                            :class="filtering || exporting ? 'animate-spin' : ''" class="text-white" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>