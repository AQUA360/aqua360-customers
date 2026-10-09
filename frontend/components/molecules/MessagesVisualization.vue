<script setup>
import AppLoading from '../atoms/AppLoading.vue';
import { formatMessageTextForPreview } from '~/utils/messages';

const { t } = useI18n()

const props = defineProps({
    messages: {
        type: Array,
        required: true
    },
    communication: Object,
    modify: {
        type: Boolean,
        default: true
    }
})

const { $DocumentManagerApiService, $apiManager, $CommunicationApiService } = useNuxtApp();
const emit = defineEmits(['show-detail', 'changed'])

const local_messages = ref(props.messages)
const showEmailPreview = ref(false)
const emailPreview = ref(null)
const loadingEmailPreview = ref(false)

const emailPreviewSrc = computed(() => {
    const preview = emailPreview.value;
    if (!preview) return null;

    const data = typeof preview === 'string'
        ? preview
        : preview.image_base64;

    if (!data) return null;
    if (data.startsWith('data:') || data.startsWith('http')) return data;
    return `data:image/png;base64,${data}`;
});

const getEmailPreview = async (message) => {
    if (showEmailPreview.value && !props.communication) {
        showEmailPreview.value = false;
        return;
    };
    showEmailPreview.value = true;
    loadingEmailPreview.value = true;
    if (!message.body || message.body.trim() === '') return;
    try {
        const payload = {
            comm_id: props.communication?.id || null,
            message: message,
        }
        const response = await $CommunicationApiService.getEmailPreview(payload);
        emailPreview.value = response;
    } catch (error) {
        console.error(error);
    } finally {
        loadingEmailPreview.value = false;
    }
}

const downloadLetter = async () => {
    try {
        const letter_file = props.communication.files.find(file => file.is_letter)
        if (!letter_file?.file) return

        if (!props.communication.sent_at) {
            if (confirm(t('confirmation_text_block.confirm_sent_postal'))) {
                await $CommunicationApiService.markAsSent({
                    communication_ids: [props.communication.id]
                })
            }
        }

        const document_file = await $DocumentManagerApiService.getDetail(letter_file.file.id)
        const file = await $DocumentManagerApiService.viewDocument(letter_file.file.id)

        const link = document.createElement('a')
        const file_url = URL.createObjectURL(file)
        link.href = file_url
        link.download = document_file.document_name
        link.click()

        setTimeout(() => {
            window.URL.revokeObjectURL(file_url)
        }, 250)

        emit('changed')
    } catch (error) {
        console.error(error)
    }
}

const personalizeText = (text) => {
    let personalizedText = text;
    if (props.communication) {
        personalizedText = personalizedText.replace('%person.name', props.communication.person.full_name);
        personalizedText = personalizedText.replace('%person.address', props.communication.used_address);
        personalizedText = personalizedText.replace('%company.name', props.communication.config_company.name);
    }
    return personalizedText;
}

const highlightMessageText = (text) => formatMessageTextForPreview(text)

const getPersonalizedTextWithHighlighting = (text) => {
    return highlightMessageText(personalizeText(text ?? ''))
}

const getOriginalTextWithHighlighting = (text) => {
    return highlightMessageText(text ?? '')
}

const editMessage = (message) => {
    emit('show-detail', 'CommunicationMessageEdit', message)
}

onMounted(() => {
    if (props.communication) {
        if (props.messages.find(message => message.type.token === 'email')) {
            getEmailPreview(props.messages.find(message => message.type.token === 'email'));
        }
    }
})

watch(() => props.messages, () => {
    local_messages.value = props.messages
    if (props.communication) {
        if (props.messages.find(message => message.type.token === 'email')) {
            getEmailPreview(props.messages.find(message => message.type.token === 'email'));
        }
    }
}, { deep: true, immediate: true })


</script>

<template>
    <div>
        <div v-for="message in local_messages" class="mt-2">

            <div v-if="message.type.token === 'letter'" class="relative group">
                <div v-if="props.communication"
                    class="relative mb-4 overflow-hidden bg-gradient-to-br from-sky-50 to-white rounded-lg py-2 px-4">
                    <div class="absolute top-0 left-0 w-0.5 h-full bg-sky-500"></div>
                    <div class="cursor-pointer flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <Icon name="fa6-solid:envelope" class="text-sky-500" />
                            <h3 class="text-sky-800 font-medium text-sm">{{ t('customer_service_block.letter') }}</h3>
                        </div>
                        <button
                            :disabled="!communication.files.find(file => file.is_letter) || !communication.files?.find(file => file.is_letter)?.file"
                            @click="downloadLetter()"
                            class="bg-white border border-sky-400 flex items-center gap-1 rounded p-1 text-sky-400 font-semibold enabled:hover:bg-sky-400 enabled:hover:text-white disabled:opacity-50 disabled:cursor-not-allowed">
                            <Icon name="fa6-solid:download" />
                            {{ t('common.download') }} {{ t('customer_service_block.letter') }}
                        </button>
                    </div>
                </div>
                <div v-else>
                    <details open
                        class="border-l-2  border-sky-500 w-full bg-gradient-to-br from-sky-50 to-white rounded-lg p-3">
                        <summary class="cursor-pointer flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <Icon name="fa6-solid:envelope" class="text-sky-500" />
                                <h3 class="text-sky-800 font-medium text-sm">
                                    {{ t('customer_service_block.letter') }}
                                    <span v-if="!props.communication">
                                        ({{ t('customer_service_block.body') }})
                                    </span>
                                </h3>

                            </div>
                        </summary>

                        <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden mt-3">
                            <div class="p-3">
                                <div class="mb-3">
                                    <h2 class="text-base font-medium text-slate-800 mb-1"
                                        v-html="props.communication ? getPersonalizedTextWithHighlighting(message.subject) : getOriginalTextWithHighlighting(message.subject)">
                                    </h2>
                                </div>
                                <div class="mb-3">
                                    <h3 class="text-base font-medium text-slate-800 mb-1"
                                        v-html="props.communication ? getPersonalizedTextWithHighlighting(message.body) : getOriginalTextWithHighlighting(message.body)">
                                    </h3>
                                </div>
                            </div>
                        </div>
                    </details>
                </div>
                <button v-if="modify" @click="editMessage(message)"
                    class="absolute top-1 right-1 bg-white border border-sky-500 flex items-center gap-1 rounded p-1 text-sky-500 font-semibold hover:bg-sky-500 hover:text-white opacity-0 group-hover:opacity-100 transition-all duration-300 ease">
                    <Icon name="fa6-solid:pencil" />
                </button>
            </div>

            <div v-if="message.type.token === 'email'" class="relative group">
                <details :open="!props.communication"
                    class="border-l-2 relative group border-sky-500 w-full bg-gradient-to-br from-sky-50 to-white rounded-lg p-3">
                    <summary class="cursor-pointer flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <Icon name="fa6-solid:envelope" class="text-sky-500" />
                            <h3 class="text-sky-800 font-medium text-sm">
                                {{ t('common.email_long') }}
                                <span v-if="!props.communication">
                                    ({{ t('customer_service_block.body') }})
                                </span>
                            </h3>
                        </div>
                        <div v-if="props.communication" class="text-xs text-slate-500">
                            <Icon name="fa6-solid:clock" class="mr-1" />
                            {{ new Date().toLocaleDateString() }}
                        </div>
                    </summary>

                    <div v-if="!loadingEmailPreview" class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden mt-3">
                        <div class="border-b border-slate-200 p-3">
                            <div class="flex items-start gap-3">
                                <div class="w-8 h-8 rounded-full bg-sky-100 flex items-center justify-center">
                                    <Icon name="fa6-solid:user" class="text-sky-500 text-sm" />
                                </div>
                                <div class="flex-1">
                                    <div class="flex items-center justify-between">
                                        <div>
                                            <h4 class="font-medium text-slate-800 text-sm">
                                                {{ props.communication ? communication.config_company.name : t('customer_service_block.sender_company') }}</h4>
                                            <p class="text-xs text-slate-500">{{ props.communication ? communication.config_company.email : t('common.email_long') }}
                                            </p>
                                        </div>

                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="p-3">
                            <div class="mb-3">
                                <h2 class="text-base font-semibold text-slate-600 mb-1"
                                    v-html="getOriginalTextWithHighlighting(message.subject)">
                                </h2>
                                <div v-if="props.communication" class="text-xs text-slate-500">
                                    {{ t('customer_service_block.recipient') }}: {{ communication.person.full_name }}
                                </div>
                            </div>
                            <div class="mb-3">
                                <h3 v-if="!showEmailPreview || !emailPreview"
                                    class="text-base font-medium text-slate-800 mb-1"
                                    v-html="props.communication ? getPersonalizedTextWithHighlighting(message.body) : getOriginalTextWithHighlighting(message.body)">
                                </h3>
                                <img
                                    v-else-if="emailPreviewSrc"
                                    :src="emailPreviewSrc"
                                    :alt="t('common.email_long')"
                                    class="w-full max-w-3xl h-auto"
                                />
                            </div>
                        </div>
                    </div>
                    <AppLoading v-else />
                </details>
                <button v-if="modify" @click="editMessage(message)"
                    class="absolute top-1 right-1 bg-white border border-sky-500 flex items-center gap-1 rounded p-1 text-sky-500 font-semibold hover:bg-sky-500 hover:text-white opacity-0 group-hover:opacity-100 transition-all duration-300 ease">
                    <Icon name="fa6-solid:pencil" />
                </button>
                <button v-if="!props.communication && !modify" @click="getEmailPreview(message)"
                    class="absolute top-1 right-8 bg-white border border-sky-500 flex items-center gap-1 rounded p-1 text-sky-500 font-semibold hover:bg-sky-500 hover:text-white opacity-0 group-hover:opacity-100 transition-all duration-300 ease">
                    <Icon name="fa6-solid:eye-slash" />
                    {{ t('common.preview') }}
                </button>
            </div>

        </div>
    </div>
</template>