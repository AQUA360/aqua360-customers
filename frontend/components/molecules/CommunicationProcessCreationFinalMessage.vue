<script setup>
import { useDebounceFn } from '@vueuse/core'
import CommunicationMessageEdit from './CommunicationMessageEdit.vue';

const props = defineProps({
    message: Object,
    fixed_data: Object,
    persons: Array,
    final_data: Object,
    is_region: {
        type: Boolean,
        default: false
    },
})

const { $ConfiglistApiService, $CommunicationProcessApiService, $MessageTemplateApiService } = useNuxtApp();
const { t } = useI18n();
const emit = defineEmits(['change'])

const subject = ref('')
const body = ref('')

const finalData = ref({})
const messages_data = ref([])
const types = ref([])

const messages = ref([])

const loadingMessageTypeTemplates = ref(false)
const selectedMessageTypeTemplate = ref(null)
const message_type_templates = ref([])

const persons_no_contracts = computed(() => {
    if (props.persons) {
        return props.persons.some(person => !person?.contracts)
    }
    return true
})

const typeIcons = {
    'default': 'fa6-solid:envelope',
    // 'sms': 'fa6-solid:phone',
    'email': 'fa6-solid:at',
    'letter': 'fa6-solid:envelope',
    // 'whatsapp': 'fa6-brands:whatsapp',
}

const getMessageTemplate = async () => {
    loadingMessageTypeTemplates.value = true
    try {
        const response = await $ConfiglistApiService.getAll('communication/message-type-template')
        response.results.forEach(data => {
            if (
                props.message.message_types.map(mt => mt.id).includes(data.id) ||
                props.message.message_template == data.message_template_id ||
                (props.message.message_types.map(mt => mt.id).includes('default') && props.message.message_template == data.message_template_id)) {
                message_type_templates.value.push({
                    label: data.subject,
                    code: data.id,
                    message: data.body,
                    type_id: data.type.id
                })
            }
        })
    } catch (error) {
        console.error(error)
    } finally {
        loadingMessageTypeTemplates.value = false
    }
}

const getTypes = async () => {
    try {
        const response = await $ConfiglistApiService.getAll('communication/message-type')
        types.value = response.results
    } catch (error) {
        console.error(error)
    }
}

const loadData = async () => {
    if (props.final_data) {
        finalData.value = props.final_data
        let isSameData = props?.final_data?.messages_data?.length == props?.message?.message_types?.length
        if (props?.final_data?.messages_data) {
            for (const message of props?.final_data?.messages_data) {
                if (!props.message.message_types.map(mt => mt.id).includes(message.type.id)) {
                    isSameData = false
                }
            }
        }
        if (props?.final_data?.messages_data?.length > 0 && isSameData) {
            messages.value = props?.final_data?.messages_data
        } else {
            if (props.message.message_types[0].id == 'default') {
                for (const type of types.value) {
                    if (message_type_templates.value.map(mt => mt.type_id).includes(type.id)) {
                        messages.value.push({
                            message_type: message_type_templates.value.find(template => template.type_id == type.id),
                            msg_data: {
                                subject: message_type_templates.value.find(template => template.type_id == type.id).label,
                                body: message_type_templates.value.find(template => template.type_id == type.id).message
                            },
                            type: type,
                            isOpen: false,
                        })
                    }
                }
            } else {
                for (const message_type of props.message.message_types) {
                    messages.value.push({
                        msg_data: {
                            subject: message_type.subject,
                            body: message_type.body
                        },
                        message_type: message_type_templates.value.find(template => template.type_id == message_type.type.id),
                        type: message_type.type,
                        isOpen: false,
                    })
                }
            }
        }
        emitChange()
    }
}

const getMessageTypeTemplate = async (id) => {
    try {
        let response = await $MessageTemplateApiService.getMessageTypeTemplateDetail(id)
        const newData = {
            subject: response.subject || '',
            body: response.body || ''
        }
        subject.value = newData.subject
        body.value = newData.body
        nextTick(() => {
            messageTextData.value = { ...newData }
        })
        emitChange()
    } catch (error) {
        console.error(error)
    }
}

const getMessageTextData = (data, message) => {
    message.msg_data = {
        subject: data.subject,
        body: data.body
    }
    debouncedEmitChange()
}

const emitChange = () => {
    finalData.value = {
        company: props.final_data?.company,
        due_date: props.final_data?.due_date,
        description: props.final_data?.description,
        messages_data: messages.value,
        attach_letter: props.final_data?.attach_letter || false,
        attach_invoices: props.final_data?.attach_invoices || false,
        use_type: props.final_data?.use_type,
    }
    emit('change', finalData.value)
}

const debouncedEmitChange = useDebounceFn(() => {
    emitChange()
}, 500)

const newMessageSelected = async (newVal, message) => {
    message.message_type = newVal
    message.msg_data = {
        subject: newVal.label,
        body: newVal.message
    }
    debouncedEmitChange()
}

watch(selectedMessageTypeTemplate, async (newVal) => {
    if (newVal) {
        await getMessageTypeTemplate(newVal.code)
    }
}, { immediate: false })

onMounted(async () => {
    await getTypes()
    await getMessageTemplate()
    await loadData()
})

</script>
<template>
    <div class="">
        <div v-if="fixed_data?.entity" class="m-2 p-3 border-l-2 border-orange-500 bg-orange-50 text-orange-500">
            <div class="flex items-center gap-2">
                <Icon name="fa6-solid:circle-exclamation" class="text-orange-500" />
                <p class="text-sm flex gap-2 items-center">
                    {{ $t('informative_block.info_fixed_data_comms') }}
                </p>
            </div>
        </div>

        <div v-for="message in messages" :key="message.message_type_id" class="mb-6">
            <div class="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">

                <div class="bg-gradient-to-r from-slate-50 to-slate-50 border-b border-slate-200">
                    <button @click="message.isOpen = !message.isOpen"
                        class="w-full px-6 py-4 text-left flex items-center justify-between hover:bg-slate-50 transition-colors duration-200 focus:outline-none"
                        :aria-expanded="message.isOpen" :aria-controls="`message-content-${message.message_type_id}`">
                        <div class="flex items-center space-x-3">
                            <div class="flex-shrink-0">
                                <Icon :name="message.type.token ? typeIcons[message.type.token] : 'fa6-solid:envelope'"
                                    class="w-5 h-5 text-sky-500" />
                            </div>
                            <div>
                                <h3 class="text-sm font-semibold text-slate-800">
                                    {{ message.type.name }}
                                </h3>
                                <p class="text-xs text-slate-500 mt-0.5">
                                    {{ $t('customer_service_block.msg_config') }}
                                </p>
                            </div>
                        </div>
                        <div class="flex-shrink-0">
                            <Icon :name="'fa6-solid:chevron-down'"
                                class="w-4 h-4 text-slate-500 transition-transform duration-200"
                                :class="{ 'rotate-180': message.isOpen }" />
                        </div>
                    </button>
                </div>


                <div v-show="message.isOpen" :id="`message-content-${message.message_type_id}`"
                    class="px-6 py-4 bg-white">
                    <div class="border-l-4 border-sky-500 pl-4 mb-4">
                        <p class="text-sm text-slate-600">
                            {{ $t('customer_service_block.msg_body_modify') }}
                        </p>
                    </div>
                    <v-select class="block w-full mr-2 required mb-3"
                        :disabled="loadingMessageTypeTemplates || message_type_templates.length == 0"
                        :model-value="message.message_type" @update:modelValue="newMessageSelected($event, message)"
                        :options="message_type_templates"></v-select>

                    <CommunicationMessageEdit :message_data="message.msg_data" :no_contracts="persons_no_contracts"
                        @change="getMessageTextData($event, message)" />
                </div>
            </div>
        </div>


        <div>
        </div>
    </div>

</template>