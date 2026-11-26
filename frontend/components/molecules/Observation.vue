<script setup>
import { ref, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

import { formatDateTime } from '~/utils/date';
import TimeRelative from '~/components/atoms/TimeRelative.vue';

const { t } = useI18n();

const props = defineProps({
    id: Number,
    object: Object,
    user: String,
    datetime: String,
    observation: String,
    status_name: String,
    allow_mark: Boolean,
    allow_edit: Boolean
});

const emit = defineEmits(['delete:observation', 'mark:observation', 'edit:observation']);

const editing = ref(false);
const draft = ref('');
const editTextarea = ref(null);
const saving = ref(false);

const deleteObservation = () => {
    emit('delete:observation', props.id)
}

const markObservation = () => {
    emit('mark:observation', props.object);
}

const startEdit = async () => {
    draft.value = props.observation || '';
    editing.value = true;
    await nextTick();
    editTextarea.value?.focus();
}

const cancelEdit = () => {
    editing.value = false;
    draft.value = '';
}

const saveEdit = () => {
    const text = draft.value?.trim();
    if (!text || saving.value) {
        return;
    }
    if (text === (props.observation || '').trim()) {
        cancelEdit();
        return;
    }
    // L'editor només es tanca si el desament va bé; si falla, es conserva l'esborrany.
    saving.value = true;
    emit('edit:observation', {
        id: props.id,
        observation: text,
        done: (ok) => {
            saving.value = false;
            if (ok) {
                cancelEdit();
            }
        }
    });
}

</script>
<template>
    <article class="p-2 text-base bg-white rounded-lg group hover:bg-black hover:bg-opacity-10 relative"
    :class="{ 'bg-yellow-50': props?.object?.is_important }">
        <footer class="flex justify-between items-center relative pt-1">
            <div class="flex items-center mb-1">
                <p v-if="props.user?.trim() != ''" class="text-sm text-gray-700 mr-3">{{ props.user }}</p>
                <p v-else class="text-sm text-gray-700 mr-3">{{ t('common.automatic_process') }}</p>
                <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
                    <TimeRelative :datetime=props.datetime></TimeRelative>
                </p>
                <Icon v-if="props?.object?.is_important" name="fa6-solid:circle-exclamation" class="ml-2 w-3 h-3 text-orange-500" />
            </div>
            <div>
                <span class="text-slate-400 text-sm">{{ formatDateTime(props.datetime) }}</span>
            </div>
        </footer>
        <div v-if="!editing"
            :class="{ 'top-[40px]': props.object.status_name, 'top-4': !props.object.status_name }"
            class="absolute right-2 flex gap-1 opacity-0 transition-all duration-300 group-hover:opacity-100">
            <button v-if="props.allow_mark" type="button"
                :title="props.object.is_important ? t('common.unmark_important') : t('common.mark_important')"
                :aria-label="props.object.is_important ? t('common.unmark_important') : t('common.mark_important')"
                class="cursor-pointer shadow-md border text-sm w-8 h-8 bg-white rounded-md text-slate-600 hover:text-red-700 focus:border-none focus:outline-none"
                @click="markObservation">
                <Icon name="fa6-solid:exclamation" />
            </button>
            <button v-if="props.allow_edit && props.object.editable" type="button"
                :title="t('common.edit')" :aria-label="t('common.edit')"
                class="cursor-pointer shadow-md border text-sm w-8 h-8 bg-white rounded-md text-slate-600 hover:text-sky-700 focus:border-none focus:outline-none"
                @click="startEdit">
                <Icon name="fa6-solid:pen" />
            </button>
            <button type="button"
                :title="t('common.delete')" :aria-label="t('common.delete')"
                class="cursor-pointer shadow-md border text-sm w-8 h-8 bg-white rounded-md text-slate-600 hover:text-red-700 focus:border-none focus:outline-none"
                @click="deleteObservation">
                <Icon name="fa6-solid:trash" />
            </button>
        </div>

        <div v-if="props.object.status_name" class="text-base mb-1 text-gray-500 flex items-center gap-2 font-semibold">
            <span>&rarr;</span>
            <span>{{ props.object.status_name }}</span>
        </div>
        <div v-if="editing" class="mt-1">
            <textarea ref="editTextarea" v-model="draft" rows="3"
                class="w-full text-base text-gray-700 border border-gray-300 rounded-md p-2 focus:outline-none focus:border-sky-500"
                :disabled="saving"
                @keydown.esc.prevent="cancelEdit"
                @keydown.enter.ctrl.prevent="saveEdit"></textarea>
            <div class="flex justify-end gap-2 mt-1">
                <button type="button" class="button-secondary !px-2.5 !py-1 text-xs" :disabled="saving" @click="cancelEdit">
                    {{ t('common.cancel') }}
                </button>
                <button type="button" class="button-primary !px-2.5 !py-1 text-xs" :disabled="saving || !draft?.trim()" @click="saveEdit">
                    {{ t('common.save') }}
                </button>
            </div>
        </div>
        <p v-else class="text-base text-gray-700 break-words whitespace-pre-wrap">{{ props.observation }}</p>
    </article>
</template>
