<script setup>
import { format } from 'date-fns';
import { useI18n } from 'vue-i18n';
import CommunicationMessageEdit from '../molecules/CommunicationMessageEdit.vue';
import MessagesVisualization from '../molecules/MessagesVisualization.vue';

const { t } = useI18n();
const { $ConfiglistApiService, $MessageTemplateApiService, $CommunicationApiService } = useNuxtApp();

const ELECTRONIC_INVOICE_TOKEN = 'electronic_inv';

const props = defineProps({
    selectedCommunicationTypes: {
        type: Array,
        default: () => [],
    },
    personsNoContracts: {
        type: Boolean,
        default: false,
    },
    clientForm: {
        type: Object,
        default: () => ({}),
    },
});

const emit = defineEmits(['change']);

const messageActiveTab = ref('message');
const messagesData = ref([]);
const useSameMessageForAllTypes = ref(false);
const sharedMessageData = ref({ subject: '', body: '', id: null });
const localClientForm = ref(props.clientForm);

const emailPreview = ref(null)

const loadingOrigins = ref(false);
const loadingTemplates = ref(false);
const origins = ref([]);
const templates = ref([]);
const selectedOrigin = ref(null);
const selectedTemplate = ref(null);
const messageTypeTemplates = ref([]);

const typeIcons = {
    default: 'fa6-solid:envelope',
    digital: 'fa6-solid:envelope',
    email: 'fa6-solid:at',
    letter: 'fa6-solid:envelope',
    sms: 'fa6-solid:phone',
    whatsapp: 'fa6-brands:whatsapp',
};

const activeMessageTypeId = ref(null);

const messageCommunicationTypes = computed(() =>
    props.selectedCommunicationTypes.filter(type => type.token !== ELECTRONIC_INVOICE_TOKEN)
);

const activeMessage = computed(() =>
    messagesData.value.find(m => m.type.id === activeMessageTypeId.value) ?? messagesData.value[0] ?? null
);

const formatMessages = (messages) => {
    try {
        if (!localClientForm.value || !localClientForm.value.selectedPerson || !localClientForm.value.selectedCompanyConfig) return messages;
        for (const message of messages) {
            message.body = message.body.replaceAll('%person.name', localClientForm.value.selectedPerson.full_name);
            message.body = message.body.replaceAll('%person.token', localClientForm.value.selectedPerson.token);
            message.body = message.body.replaceAll('%person.address_complete', localClientForm.value.selectedPerson.address);
            
            message.body = message.body.replaceAll('%company.name', localClientForm.value.selectedCompanyConfig.company.name);
            message.body = message.body.replaceAll('%company.phone', localClientForm.value.selectedCompanyConfig.company.phone);
            message.body = message.body.replaceAll('%company.email', localClientForm.value.selectedCompanyConfig.company.email);
            message.body = message.body.replaceAll('%company.address_complete', localClientForm.value.selectedCompanyConfig.company.address_complete);

            const today = format(new Date(), 'yyyy-MM-dd').toString();
            message.body = message.body.replaceAll('%date.today', today);
            message.body = message.body.replaceAll('%communication.due_date', formatDate(localClientForm.value.dueDate));
            if (localClientForm.value.selectedContract) {
                message.body = message.body.replaceAll('%contract.token', localClientForm.value.selectedContract?.token);
                message.body = message.body.replaceAll('%contract.persons', localClientForm.value.selectedContract?.persons?.length);
                message.body = message.body.replaceAll('%contract.supply_address', localClientForm.value.selectedContract?.supply_point);
                message.body = message.body.replaceAll('%contract.previous_daily_consumption', localClientForm.value.selectedContract?.previous_daily_consumption || t('warning_block.warning_no_previous_avg_found'));
                message.body = message.body.replaceAll('%contract.previous_period_consumption', localClientForm.value.selectedContract?.previous_period_consumption || t('warning_block.warning_no_previous_avg_found'));
            }

            if (localClientForm.value.selectedInvoices.length > 0) {
                message.body = message.body.replaceAll('%invoice.serie_final', localClientForm.value.selectedInvoices.map(invoice => invoice.serie_final).join(', '));
                message.body = message.body.replaceAll('%invoice.consumption', localClientForm.value.selectedInvoices.reduce((sum, invoice) => sum + (Number(invoice.consumption) || 0), 0).toString() + 'm3');
                message.body = message.body.replaceAll('%invoice.total', formatMoneyWithCurrency(localClientForm.value.selectedInvoices.reduce((sum, invoice) => sum + (Number(invoice.total_final) || 0), 0).toString()));
                message.body = message.body.replaceAll('%invoice.issue_date', localClientForm.value.selectedInvoices[0].issue_date ? formatDate(localClientForm.value.selectedInvoices[0].issue_date) : '');
                message.body = message.body.replaceAll('%invoice.due_date', localClientForm.value.selectedInvoices[0].due_date ? formatDate(localClientForm.value.selectedInvoices[0].due_date) : '');
            }
            if (localClientForm.value.selectedReadings.length > 0) {
                message.body = message.body.replaceAll('%reading.data', `${localClientForm.value.selectedReadings.map(
                    reading => `${t('meter')} ${reading.meter_code} - ${t('reading')} ${parseInt(reading.reading_value)} ${t('billing_block.reading_date').toLowerCase()}: ${formatDate(reading.reading_date)} . ${t('billing_block.consumption')}: ${parseInt(reading.calculated_value)} m3 ${reading.leak_value ? `- ${t('billing_block.leak')}: ${parseInt(reading.leak_value)} m3` : ''}`
                ).join('\n')}`);
                message.body = message.body.replaceAll('%reading.meter_code', localClientForm.value.selectedReadings[0]?.meter_code);
                message.body = message.body.replaceAll('%reading.reading_value', localClientForm.value.selectedReadings[0]?.reading_value);
                message.body = message.body.replaceAll('%reading.reading_date', localClientForm.value.selectedReadings[0]?.reading_date ? formatDate(localClientForm.value.selectedReadings[0].reading_date) : '');
                message.body = message.body.replaceAll('%reading.calculated_value', localClientForm.value.selectedReadings[0]?.calculated_value ? parseInt(localClientForm.value.selectedReadings[0]?.calculated_value) : 0);
                message.body = message.body.replaceAll('%reading.leak_value', localClientForm.value.selectedReadings[0]?.leak_value ? parseInt(localClientForm.value.selectedReadings[0]?.leak_value) : 0);
                message.body = message.body.replaceAll('%reading.previous_reading_value', localClientForm.value.selectedReadings[0]?.previous_reading_value ? parseInt(localClientForm.value.selectedReadings[0]?.previous_reading_value) : 0);
                message.body = message.body.replaceAll('%reading.previous_reading_date', localClientForm.value.selectedReadings[0]?.previous_reading_date ? formatDate(localClientForm.value.selectedReadings[0]?.previous_reading_date) : '');
            }
        }

    } catch (error) {
        console.error(error);
    } finally {
        return messages;
    }
}

const previewMessages = computed(() =>
    formatMessages(messagesData.value.map(message => ({
        subject: message.msg_data.subject,
        body: message.msg_data.body,
        type: message.type,
        person_id: localClientForm.value?.selectedPerson?.id,
        company_config_id: localClientForm.value?.selectedCompanyConfig?.code,
    })))
);

const emitChange = () => {
    emit('change', {
        messagesData: messagesData.value,
        selectedOrigin: selectedOrigin.value,
        selectedTemplate: selectedTemplate.value,
        useSameMessageForAllTypes: useSameMessageForAllTypes.value,
        sharedMessageData: sharedMessageData.value,
    });
};

const getTemplateContentForType = (type) => {
    const template = messageTypeTemplates.value.find(mt => mt.type?.id === type.value);
    if (!template) return { subject: '', body: '' };
    return {
        subject: template.subject || '',
        body: template.body || '',
        template,
    };
};

const createMessageEntry = (type, existingMsgData = null) => {
    const templateContent = getTemplateContentForType(type);
    const msgData = existingMsgData || {
        subject: templateContent.subject,
        body: templateContent.body,
        id: null,
    };
    return {
        type: { id: type.value, name: type.label, token: type.token },
        msg_data: { ...msgData },
        message_type_template: templateContent.template || null,
    };
};

const syncMessagesWithSelectedTypes = () => {
    const selectedIds = messageCommunicationTypes.value.map(t => t.value);
    const kept = messagesData.value.filter(m => selectedIds.includes(m.type.id));
    const added = [];
    for (const type of messageCommunicationTypes.value) {
        const existing = kept.find(m => m.type.id === type.value);
        if (existing) {
            added.push(existing);
        } else {
            added.push(createMessageEntry(type));
        }
    }
    messagesData.value = added;
    const activeStillValid = added.some(m => m.type.id === activeMessageTypeId.value);
    if (!activeStillValid) {
        activeMessageTypeId.value = added[0]?.type.id ?? null;
    }
    if (useSameMessageForAllTypes.value && messagesData.value.length > 0) {
        propagateSharedMessageToAll();
    }
    emitChange();
};

const propagateSharedMessageToAll = () => {
    messagesData.value.forEach(message => {
        message.msg_data = {
            ...message.msg_data,
            subject: sharedMessageData.value.subject,
            body: sharedMessageData.value.body,
        };
    });
    emitChange();
};

const onSharedMessageChange = (data) => {
    sharedMessageData.value = {
        ...sharedMessageData.value,
        subject: data.subject,
        body: data.body,
        id: data.id ?? null,
    };
    propagateSharedMessageToAll();
};

const onMessageChange = (data, message) => {
    message.msg_data = {
        ...message.msg_data,
        subject: data.subject,
        body: data.body,
        id: data.id ?? null,
    };
    emitChange();
};

const loadTemplateConfig = async () => {
    loadingOrigins.value = true;
    try {
        const data = await $ConfiglistApiService.getAll('communication/message-origin');
        origins.value = (data.results || []).map(item => ({
            label: item.name || item.token,
            code: item.id,
        }));
    } catch (error) {
        console.error('Error fetching message origins:', error);
    } finally {
        loadingOrigins.value = false;
    }
};

const getMessageTemplates = async () => {
    loadingTemplates.value = true;
    try {
        templates.value = [];
        const originId = selectedOrigin.value?.code ?? null;
        const response = await $MessageTemplateApiService.getAll('', [], 1, null, false, originId);
        templates.value = (response.results || []).map(data => ({
            label: data.name || data.token,
            code: data.id,
        }));
    } catch (error) {
        console.error(error);
    } finally {
        loadingTemplates.value = false;
    }
};

const getMessageTypeTemplates = async () => {
    try {
        if (!selectedTemplate.value) {
            messageTypeTemplates.value = [];
            return;
        }
        const response = await $MessageTemplateApiService.getMessageTypeTemplates(selectedTemplate.value.code);
        messageTypeTemplates.value = response.results || [];
        applyTemplateToMessages();
    } catch (error) {
        console.error(error);
    }
};

const applyTemplateToMessages = () => {
    if (messageCommunicationTypes.value.length === 0) return;
    if (useSameMessageForAllTypes.value) {
        const firstType = messageCommunicationTypes.value[0];
        const content = getTemplateContentForType(firstType);
        sharedMessageData.value = {
            subject: content.subject,
            body: content.body,
            id: null,
        };
        syncMessagesWithSelectedTypes();
        propagateSharedMessageToAll();
        return;
    }
    messagesData.value = messageCommunicationTypes.value.map(type => createMessageEntry(type));
    if (!activeMessageTypeId.value && messagesData.value.length > 0) {
        activeMessageTypeId.value = messagesData.value[0].type.id;
    }
    emitChange();
};

const reset = () => {
    messagesData.value = [];
    activeMessageTypeId.value = null;
    useSameMessageForAllTypes.value = false;
    sharedMessageData.value = { subject: '', body: '', id: null };
    selectedOrigin.value = null;
    selectedTemplate.value = null;
    messageTypeTemplates.value = [];
    messageActiveTab.value = 'message';
    emitChange();
};

defineExpose({ reset });

watch(useSameMessageForAllTypes, (useSame) => {
    if (!useSame || messagesData.value.length === 0) return;
    const first = messagesData.value[0];
    sharedMessageData.value = {
        subject: first.msg_data.subject,
        body: first.msg_data.body,
        id: first.msg_data.id ?? null,
    };
    propagateSharedMessageToAll();
});

watch(selectedOrigin, async () => {
    selectedTemplate.value = null;
    messageTypeTemplates.value = [];
    await getMessageTemplates();
    emitChange();
});

watch(selectedTemplate, async () => {
    await getMessageTypeTemplates();
});

watch(messageCommunicationTypes, () => {
    syncMessagesWithSelectedTypes();
}, { deep: true });

watch(() => props.clientForm, () => {
    localClientForm.value = props.clientForm;
}, { deep: true });

onMounted(async () => {
    await loadTemplateConfig();
    syncMessagesWithSelectedTypes();
});
</script>

<template>
    <div class="p-2">
        <div v-if="messageCommunicationTypes.length > 0">
            <AtomsTabs>
                <li class="me-2">
                    <a href="#tab_message" @click.prevent="messageActiveTab = 'message'"
                        :class="{ 'text-sky-600 border-sky-600': messageActiveTab === 'message', 'hover:text-gray-600 hover:border-gray-300': messageActiveTab !== 'message' }">
                        {{ $t('common.message') }}
                    </a>
                </li>
                <li class="me-2">
                    <a href="#tab_preview" @click.prevent="messageActiveTab = 'preview'"
                        :class="{ 'text-sky-600 border-sky-600': messageActiveTab === 'preview', 'hover:text-gray-600 hover:border-gray-300': messageActiveTab !== 'preview' }">
                        {{ $t('common.preview') }}
                    </a>
                </li>
            </AtomsTabs>

            <section v-show="messageActiveTab === 'message'" role="tabpanel" id="tab_message"
                class="bg-white antialiased p-2 space-y-4">
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.origin') }}</label>
                        <v-select class="block w-full mr-2 required" :disabled="loadingOrigins || origins.length === 0"
                            :model-value="selectedOrigin" @update:modelValue="selectedOrigin = $event"
                            :options="origins" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.template') }}</label>
                        <v-select class="block w-full mr-2 required" :options="templates"
                            :disabled="loadingTemplates || templates.length === 0 || selectedOrigin == null"
                            :model-value="selectedTemplate" @update:modelValue="selectedTemplate = $event" />
                    </div>
                </div>

                <template v-if="messageCommunicationTypes.length > 0">
                    <label v-if="messageCommunicationTypes.length > 1"
                        class="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                        <input v-model="useSameMessageForAllTypes" type="checkbox"
                            class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500" />
                        <span>{{ t('customer_service_block.use_same_message_all_types') }}</span>
                    </label>

                    <CommunicationMessageEdit
                        v-if="useSameMessageForAllTypes || messageCommunicationTypes.length === 1"
                        :message_data="useSameMessageForAllTypes ? sharedMessageData : { ...messagesData[0]?.msg_data, type: messagesData[0]?.type }"
                        :no_contracts="personsNoContracts"
                        @change="useSameMessageForAllTypes ? onSharedMessageChange($event) : onMessageChange($event, messagesData[0])" />

                    <div v-else class="space-y-3">
                        <div class="flex flex-wrap items-center gap-1.5" role="tablist">
                            <button v-for="message in messagesData" :key="message.type.id" type="button" role="tab"
                                :aria-selected="activeMessageTypeId === message.type.id"
                                @click="activeMessageTypeId = message.type.id"
                                class="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-all duration-300"
                                :class="activeMessageTypeId === message.type.id
                                    ? 'border-sky-500 bg-sky-500 text-white hover:bg-sky-800 hover:border-sky-800'
                                    : 'border-slate-300 bg-white text-slate-600 hover:border-sky-100 hover:bg-sky-100'">
                                <Icon
                                    :name="message.type.token ? (typeIcons[message.type.token] || 'fa6-solid:envelope') : 'fa6-solid:envelope'"
                                    class="text-sm" />
                                {{ message.type.name }}
                            </button>
                        </div>

                        <div v-if="activeMessage" class="rounded-lg border border-slate-200 bg-white p-4">
                            <CommunicationMessageEdit :key="activeMessage.type.id"
                                :message_data="{ ...activeMessage.msg_data, type: activeMessage.type }"
                                :no_contracts="personsNoContracts" @change="onMessageChange($event, activeMessage)" />
                        </div>
                    </div>
                </template>
            </section>

            <section v-show="messageActiveTab === 'preview'" role="tabpanel" id="tab_preview"
                class="bg-white antialiased p-2">
                <MessagesVisualization :messages="previewMessages" :modify="false" />
            </section>
        </div>

        <div v-else
            class="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
            {{ t('customer_service_block.select_communication_channel') }}
        </div>
    </div>
</template>
