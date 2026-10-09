<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { exportToXlsx } from '~/utils/xlsx-export';
import { useServerExport } from '~/composables/useServerExport';

const { t } = useI18n();
const { exporting, runExport } = useServerExport();

const props = defineProps({
    // Rows to export — already filtered/sorted as shown in the table.
    rows: {
        type: Array,
        default: () => [],
    },
    // Column definitions: [{ header: 'Data', value: row => ... }]
    columns: {
        type: Array,
        required: true,
    },
    // File name without extension.
    fileName: {
        type: String,
        default: 'export',
    },
    // Worksheet name (optional).
    sheetName: {
        type: String,
        default: 'Sheet1',
    },
    // Kept for existing callers. The export no longer depends on the page count:
    // whenever serverExportFn is set, the file is built on the backend.
    totalPages: {
        type: Number,
        default: 1,
    },
    // Called to trigger the server-side export. Should hit the backend export
    // endpoint with the active filters/search and return `{ task_id, export_job_id }`
    // (the file then goes to the user's downloads queue).
    serverExportFn: {
        type: Function,
        default: null,
    },
    // Show only the icon, no label.
    iconOnly: {
        type: Boolean,
        default: false,
    },
    // Force-disable the button.
    disabled: {
        type: Boolean,
        default: false,
    },
    label: {
        type: String,
        default: '',
    },
    // Name shown in the downloads queue (optional; defaults to the page title).
    exportName: {
        type: String,
        default: '',
    },
});

const emit = defineEmits(['download', 'error']);

const isDisabled = computed(() => props.disabled || exporting.value || (!props.rows?.length && !props.serverExportFn));

const buttonLabel = computed(() => {
    if (exporting.value) return `${t('common.loading')}...`;
    return props.label || `${t('common.download')} XLSX`;
});

const download = async () => {
    if (isDisabled.value) return;
    try {
        await runExport({
            rows: props.rows,
            columns: props.columns,
            fileName: props.fileName,
            sheetName: props.sheetName,
            totalPages: props.totalPages,
            serverExportFn: props.serverExportFn,
            exportName: props.exportName || undefined,
        });
        emit('download');
    } catch (err) {
        console.error('XLSX export error:', err);
        emit('error', err);
    }
};
</script>

<template>
    <button type="button" class="button-secondary" :disabled="isDisabled"
        :class="{ 'opacity-60 cursor-not-allowed': isDisabled }" :title="buttonLabel" @click="download">
        <Icon :name="exporting ? 'fa6-solid:spinner' : 'fa6-solid:file-excel'" :class="{ 'animate-spin': exporting }" />
        <span v-if="!iconOnly" class="ml-1">{{ buttonLabel }}</span>
    </button>
</template>
