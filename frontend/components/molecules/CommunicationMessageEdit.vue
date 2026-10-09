<script setup>
import { useDebounceFn } from '@vueuse/core'
import CommunicationMessageVariables from './CommunicationMessageVariables.vue'
import CommunicationMessageFormatTags from './CommunicationMessageFormatTags.vue'
import { applyMessageFormatTagToTextarea } from '~/utils/messages'

const { t } = useI18n();
const props = defineProps({
    message_data: {
        type: Object,
        required: true
    },
    is_process: {
        type: Boolean,
        default: false
    },
    no_contracts: {
        type: Boolean,
        default: false
    },
    variables_details_open: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits(['change'])

const subject = ref('')
const body = ref('')

const insertPlaceholder = (value) => {
    const textarea = document.getElementById('messageTextarea');

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;

    body.value = body.value.substring(0, start) + value + body.value.substring(end);

    textarea.value = body.value;

    textarea.selectionStart = textarea.selectionEnd = start + value.length;
    textarea.focus();
    if (!props.is_process) {
        debouncedEmitChange()
    }
};

const applyFormatTag = (token) => {
    applyMessageFormatTagToTextarea(body, token);
    if (!props.is_process) {
        debouncedEmitChange()
    }
};

const saveMessage = async () => {
    if (props.is_process) {
        if (!confirm(t('confirmation_text_block.confirm_modify'))) return
    }
    emit('change', {
        id: props?.message_data?.id || null,
        subject: subject.value,
        body: body.value,
        type_id: props?.message_data?.type?.id || null
    })
}

const debouncedEmitChange = useDebounceFn(() => {
    saveMessage()
}, 500)

onMounted(() => {
    if (props.message_data) {
        subject.value = props.message_data.subject || ''
        body.value = props.message_data.body || ''
    }
})

watch(() => props.message_data, (newVal) => {
    if (newVal) {
        subject.value = newVal.subject || ''
        body.value = newVal.body || ''
    }
}, { deep: true, immediate: true })

</script>

<template>
    <div class="space-y-2">
        <div v-if="is_process"
            class="flex items-center p-3 bg-amber-50 text-amber-800 border border-amber-200 rounded-lg">
            <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500 flex-shrink-0" />
            <p class="ml-3 text-sm">
                {{ t('informative_block.info_msg_change_comms') }}</p>
        </div>

        <div v-if="message_data?.type"
            class="p-1 border border-sky-300 italic rounded text-sky-300 text-sm font-medium w-fit ml-auto">
            {{ message_data.type.name }}
        </div>

        <div class="space-y-4">
            <div>
                <label class="block text-sm font-semibold text-slate-700 mb-2">
                    {{ $t('customer_service_block.subject') }}
                    <span class="text-red-500">*</span>
                </label>
                <input type="text" v-model="subject"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors duration-200"
                    @input="!is_process ? debouncedEmitChange() : null"
                    :placeholder="$t('customer_service_block.add_subject')" />
            </div>

            <div>
                <label class="block text-sm font-semibold text-slate-700 mb-2">
                    {{ $t('customer_service_block.body') }}
                    <span class="text-red-500">*</span>
                </label>
                <textarea id="messageTextarea" v-model="body"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors duration-200"
                    :placeholder="$t('customer_service_block.add_body')" rows="7"
                    @input="!is_process ? debouncedEmitChange() : null" />
            </div>
        </div>

        <CommunicationMessageVariables :no_contracts="no_contracts" :open="variables_details_open"
            @insert="insertPlaceholder" />
        <CommunicationMessageFormatTags @apply="applyFormatTag" />

        <div v-if="props.is_process" class="flex flex-row-reverse">
            <button class="button-primary" @click="saveMessage">
                {{ t('common.save') }}
            </button>
        </div>
    </div>
</template>