<script setup>
import { useI18n } from 'vue-i18n';

// Fitxers locals que s'adjuntaran a una comunicació nova. No es pugen fins que
// la comunicació s'ha desat (cal el seu id); el pare els rep amb v-model.
const props = defineProps({
    modelValue: {
        type: Array,
        default: () => [],
    },
    disabled: {
        type: Boolean,
        default: false,
    },
});

const emit = defineEmits(['update:modelValue']);
const { t } = useI18n();

const fileInput = ref(null);

const formatSize = (bytes) => {
    if (!bytes && bytes !== 0) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const isSameFile = (a, b) => a.name === b.name && a.size === b.size && a.lastModified === b.lastModified;

const chooseFiles = () => {
    if (props.disabled) return;
    fileInput.value?.click();
};

const onFilesSelected = (event) => {
    const selected = Array.from(event.target.files || []);
    const current = [...props.modelValue];
    selected.forEach((file) => {
        if (!current.some((existing) => isSameFile(existing, file))) {
            current.push(file);
        }
    });
    emit('update:modelValue', current);
    // Permet tornar a triar el mateix fitxer després d'haver-lo tret.
    event.target.value = '';
};

const removeFile = (index) => {
    const current = [...props.modelValue];
    current.splice(index, 1);
    emit('update:modelValue', current);
};
</script>

<template>
    <section class="space-y-2 rounded-lg border border-slate-200 bg-slate-50/60 p-4">
        <div class="flex items-center justify-between gap-2">
            <div>
                <p class="text-sm font-medium text-slate-700">
                    <Icon name="fa6-solid:paperclip" class="mr-1 text-slate-500" />
                    {{ t('customer_service_block.attached_files') }} ({{ modelValue.length }})
                </p>
                <p class="text-xs text-slate-500">{{ t('customer_service_block.attachments_help') }}</p>
            </div>
            <button type="button" class="button-secondary !px-2.5 !py-1 text-xs flex items-center gap-1"
                :disabled="disabled" @click="chooseFiles">
                <Icon name="fa6-solid:plus" />
                {{ t('customer_service_block.add_attachments') }}
            </button>
            <input ref="fileInput" type="file" multiple class="hidden" @change="onFilesSelected" />
        </div>

        <ul v-if="modelValue.length > 0" class="divide-y divide-slate-200 rounded-md border border-slate-200 bg-white">
            <li v-for="(file, index) in modelValue" :key="`${file.name}-${file.size}-${file.lastModified}`"
                class="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                <span class="flex min-w-0 items-center gap-2">
                    <Icon name="fa6-regular:file" class="shrink-0 text-slate-500" />
                    <span class="truncate text-slate-700">{{ file.name }}</span>
                    <span class="shrink-0 text-xs text-slate-400">{{ formatSize(file.size) }}</span>
                </span>
                <button type="button" class="rounded px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-red-600"
                    :disabled="disabled" :title="t('common.delete')" @click="removeFile(index)">
                    <Icon name="fa6-solid:trash" />
                </button>
            </li>
        </ul>
        <p v-else class="text-xs italic text-slate-400">{{ t('customer_service_block.no_attachments') }}</p>
    </section>
</template>
