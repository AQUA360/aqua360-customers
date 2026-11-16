<script setup>
import { useI18n } from 'vue-i18n';
import AppLoading from '../atoms/AppLoading.vue';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';
import AddNewCommunicationClientData from '~/components/organisms/AddNewCommunicationClientData.vue';
import AddNewCommunicationMessageEdit from '~/components/organisms/AddNewCommunicationMessageEdit.vue';
import CommunicationAttachments from '~/components/molecules/CommunicationAttachments.vue';
import CommunicationRegion from '~/components/organisms/CommunicationRegion.vue';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const { $CommunicationApiService, $IncidentApiService } = useNuxtApp();
const toast = useToast();

// Si s'arriba des d'una incidència, la comunicació hi queda vinculada i en desar es torna a la incidència.
const incidentId = computed(() => {
    const id = parseInt(route.query.incident_id, 10);
    return Number.isNaN(id) ? null : id;
});
const incident = ref(null);

const attachments = ref([]);

// Un cop desada, es mostra el detall de la comunicació i es pot enviar al moment.
const savedCommunicationId = ref(null);
const savedCommunication = ref(null);
const communicationPermissions = ref(null);
const sending = ref(false);
const uploadingAttachments = ref(false);
const sendRequested = ref(false);
const regionKey = ref(0);

const canSendNow = computed(() =>
    !uploadingAttachments.value
    && !!savedCommunication.value?.status?.is_default
    && !!communicationPermissions.value?.can_change
    && !sendRequested.value
);

const loadSavedCommunication = async () => {
    if (!savedCommunicationId.value) return;
    try {
        savedCommunication.value = await $CommunicationApiService.getDetail(savedCommunicationId.value);
    } catch (error) {
        console.error(error);
    }
};

const sendNow = async () => {
    if (!savedCommunicationId.value || !confirm(t('customer_service_block.confirm_send_now'))) return;
    sending.value = true;
    try {
        const response = await $CommunicationApiService.sendCommunications({ communication_ids: [savedCommunicationId.value] });
        if (response) {
            sendRequested.value = true;
            toast.success(t('informative_block.info_process_msgs'));
            await loadSavedCommunication();
            regionKey.value++;
        }
    } catch (error) {
        console.error(error);
    } finally {
        sending.value = false;
    }
};

const goToList = () => navigateTo({ path: '/communication/communications/', query: { id: savedCommunicationId.value } });
const goToIncident = () => navigateTo({ path: '/incident/incidents', query: { id: incidentId.value } });
// Torna a obrir l'assistent buit (conservant la incidència, si n'hi ha) per crear-ne una altra.
const newCommunication = () => {
    const query = incidentId.value ? { incident_id: incidentId.value } : {};
    if (route.query.contract_id) query.contract_id = route.query.contract_id;
    return navigateTo({ path: '/communication/communications/add', query }, { replace: true }).then(() => window.location.reload());
};

const ELECTRONIC_INVOICE_TOKEN = 'electronic_inv';

const saving = ref(false);
const loading = ref(false);

const steps = ref(['1', '2']);
const currentStep = ref(0);
const maxStep = ref(0);

const clientDataRef = ref(null);
const messageEditRef = ref(null);
const clientForm = ref({});
const messageForm = ref({});

const wizardSteps = computed(() => [
    {
        index: 0,
        label: `${t('billing_block.step')} 1`,
        title: t('customer_service_block.step_select_data_info'),
        description: t('customer_service_block.step_select_data_info'),
        icon: 'fa6-solid:address-card',
    },
    {
        index: 1,
        label: `${t('billing_block.step')} 2`,
        title: t('customer_service_block.step_edit_preview_message'),
        description: t('customer_service_block.step_edit_preview_message'),
        icon: 'fa6-solid:envelope-open-text',
    },
]);

const hasElectronicInvoiceType = computed(() =>
    (clientForm.value?.selectedCommunicationTypes ?? []).some(t => t.token === ELECTRONIC_INVOICE_TOKEN)
);

const isOnlyElectronicInvoice = computed(() => {
    const types = clientForm.value?.selectedCommunicationTypes ?? [];
    return types.length === 1 && types[0]?.token === ELECTRONIC_INVOICE_TOKEN;
});

const messageCommunicationTypes = computed(() =>
    (clientForm.value?.selectedCommunicationTypes ?? []).filter(t => t.token !== ELECTRONIC_INVOICE_TOKEN)
);

const hasRequiredInvoices = computed(() => {
    if (!hasElectronicInvoiceType.value) return true;
    return (clientForm.value?.selectedInvoices ?? []).length > 0;
});

const canGoToStep2 = computed(() =>
    clientForm.value?.clientData != null
    && (clientForm.value?.selectedCommunicationTypes?.length ?? 0) > 0
    && (!!clientForm.value?.selectedCompanyConfig)
    && (!!clientForm.value?.dueDate)
    && (!!clientForm.value?.selectedCompanyConfigEmail)
    && hasRequiredInvoices.value
);

const canSaveFromStep1 = computed(() =>
    isOnlyElectronicInvoice.value
    && canGoToStep2.value
    && !!clientForm.value?.selectedPerson
);

const personsNoContracts = computed(() => !clientForm.value?.selectedContract);

const onClientDataChange = (data) => {
    clientForm.value = data;
};

const onMessageChange = (data) => {
    messageForm.value = data;
};

const onClientDataReady = () => {
    loading.value = false;
    if (currentStep.value > 0 && !canGoToStep2.value) {
        currentStep.value = 0;
        maxStep.value = 0;
        setUrlStep();
    }
};

const setUrlStep = () => {
    if (savedCommunicationId.value) return;
    router.replace({
        query: {
            ...route.query,
            step: currentStep.value + 1,
        },
    });
};

const nextStep = () => {
    if (!canGoToStep2.value || messageCommunicationTypes.value.length === 0) return;
    if (currentStep.value < steps.value.length - 1) {
        currentStep.value++;
        if (currentStep.value > maxStep.value) {
            maxStep.value = currentStep.value;
        }
        setUrlStep();
    }
};

const previousStep = () => {
    if (currentStep.value > 0) {
        currentStep.value--;
        setUrlStep();
    }
};

// Els fitxers es pugen un cop creada la comunicació (cal el seu id). Si en falla algun,
// la comunicació ja existeix: s'avisa i es poden afegir des del detall de la comunicació.
const uploadAttachments = async (communicationId) => {
    if (!communicationId || attachments.value.length === 0) return;
    let failed = false;
    for (const file of attachments.value) {
        try {
            await $CommunicationApiService.saveDocumentationFile({ document: file, communication: communicationId });
        } catch (error) {
            console.error(error);
            failed = true;
        }
    }
    if (failed) {
        toast.warning(t('customer_service_block.attachments_upload_error'));
    }
};

const loadIncident = async () => {
    if (!incidentId.value) return;
    try {
        incident.value = await $IncidentApiService.getDetail(incidentId.value);
    } catch (error) {
        console.error(error);
        incident.value = null;
    }
};

const save = async () => {
    if (!confirm(t('confirmation_text_block.confirm_create'))) return;
    saving.value = true;
    try {
        const client = clientForm.value;
        const messages = messageForm.value?.messagesData ?? [];
        const save_data = {
            person: client.selectedPerson?.id,
            contract_id: client.selectedContract?.id ?? null,
            company_config: client.selectedCompanyConfig?.code,
            company_config_email: client.selectedCompanyConfigEmail?.id,
            used_address: client.selectedAddress,
            used_phones: client.selectedPhone,
            used_email: client.selectedEmail,
            message_types: (client.selectedCommunicationTypes ?? []).map(type => type.value),
            message_type_names: (client.selectedCommunicationTypes ?? []).map(type => type.label),
            messages_data: messages,
            due_date: client.dueDate,
            use_type_id: client.selectedCommunicationUseType?.value ?? null,
            accounting_office: client.accountingOffice,
            managing_body: client.managingBody,
            processing_unit: client.processingUnit,
            selected_invoices: client.selectedInvoices.map(invoice => invoice.id),
            selected_readings: client.selectedReadings.map(reading => reading.id),
            incident: incidentId.value,
        };
        const result = await $CommunicationApiService.save(save_data);
        if (result) {
            // Primer es fixa la comunicació desada (també a la URL) perquè una recàrrega la recuperi
            // encara que els adjunts no hagin acabat de pujar.
            savedCommunicationId.value = result.id;
            await router.replace({ query: { ...route.query, step: undefined, saved: result.id } });
            uploadingAttachments.value = attachments.value.length > 0;
            try {
                await uploadAttachments(result.id);
            } finally {
                uploadingAttachments.value = false;
            }
            toast.success(incidentId.value ? t('incident_block.comm_saved_from_incident') : t('customer_service_block.comm_saved'));
            await loadSavedCommunication();
            regionKey.value++;
        }
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
    }
};

onMounted(() => {
    loadIncident();
    $CommunicationApiService.getPermissions().then(result => {
        communicationPermissions.value = result;
    }).catch(() => {
        communicationPermissions.value = null;
    });
    // En recarregar la pàgina després de desar, es torna a mostrar el detall de la comunicació desada.
    const savedFromUrl = parseInt(route.query.saved, 10);
    if (!Number.isNaN(savedFromUrl)) {
        savedCommunicationId.value = savedFromUrl;
        loadSavedCommunication();
        return;
    }
    if (route.query.step) {
        const stepFromUrl = parseInt(route.query.step, 10) - 1;
        if (stepFromUrl >= 0 && stepFromUrl < steps.value.length) {
            currentStep.value = stepFromUrl;
            maxStep.value = stepFromUrl;
        }
    }
    setUrlStep();
});

watch(canGoToStep2, (valid) => {
    if (!valid && currentStep.value > 0) {
        currentStep.value = 0;
        maxStep.value = 0;
        setUrlStep();
    }
});

watch(isOnlyElectronicInvoice, (onlyElectronic) => {
    if (onlyElectronic && currentStep.value > 0) {
        currentStep.value = 0;
        maxStep.value = 0;
        setUrlStep();
    }
});
</script>

<template>
    <div class="overflow-hidden mb-20">
        <AppLoading v-if="loading" />

        <div v-else-if="savedCommunicationId" class="space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
                <div class="flex items-center gap-2 text-sm text-emerald-800">
                    <Icon name="fa6-solid:circle-check" class="text-emerald-600" />
                    <span class="font-medium">{{ $t('customer_service_block.comm_saved') }}</span>
                    <span v-if="savedCommunication?.token" class="text-emerald-700">· {{ savedCommunication.token }}</span>
                    <span v-if="uploadingAttachments" class="flex items-center gap-1 text-emerald-700">
                        · <Icon name="fa6-solid:spinner" class="animate-spin" /> {{ $t('customer_service_block.uploading_attachments') }}
                    </span>
                    <span v-if="sendRequested" class="text-emerald-700">· {{ $t('informative_block.info_process_msgs') }}</span>
                </div>
                <div class="flex flex-wrap items-center gap-2">
                    <button v-if="canSendNow" type="button" @click="sendNow" :disabled="sending"
                        class="button-primary flex items-center gap-2">
                        <Icon :name="sending ? 'fa6-solid:spinner' : 'fa6-solid:paper-plane'" :class="{ 'animate-spin': sending }" />
                        {{ $t('customer_service_block.send_now') }}
                    </button>
                    <button v-if="incidentId" type="button" @click="goToIncident" class="button-secondary flex items-center gap-2">
                        <Icon name="fa6-solid:triangle-exclamation" />
                        {{ $t('customer_service_block.back_to_incident') }}
                    </button>
                    <button type="button" @click="goToList" class="button-secondary flex items-center gap-2">
                        <Icon name="fa6-solid:list" />
                        {{ $t('customer_service_block.go_to_comms_list') }}
                    </button>
                    <button type="button" @click="newCommunication" class="button-secondary flex items-center gap-2">
                        <Icon name="fa6-solid:plus" />
                        {{ $t('customer_service_block.new_comm') }}
                    </button>
                </div>
            </div>
            <div class="rounded border border-gray-300 bg-white p-4">
                <CommunicationRegion :key="regionKey" :id="savedCommunicationId" :isSubRegion="true"
                    @changed="loadSavedCommunication" />
            </div>
        </div>

        <div v-else>
            <WizardStatusNav :steps="wizardSteps" :current-step="currentStep" :max-step="maxStep" disabled
                :show-description="false" />

            <div v-if="incidentId"
                class="flex items-center gap-2 border-x border-gray-300 bg-amber-50 px-4 py-2 text-sm text-slate-700">
                <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500" />
                <span class="font-medium">{{ $t('customer_service_block.linked_incident') }}:</span>
                <span>{{ incident?.token || `#${incidentId}` }}</span>
                <span v-if="incident?.name" class="truncate text-slate-500">· {{ incident.name }}</span>
            </div>

            <div class="border border-gray-300 rounded-b bg-white">
                <AddNewCommunicationClientData v-show="currentStep === 0" ref="clientDataRef"
                    @change="onClientDataChange" @ready="onClientDataReady" />

                <AddNewCommunicationMessageEdit v-show="currentStep === 1" ref="messageEditRef"
                    :selected-communication-types="clientForm.selectedCommunicationTypes ?? []"
                    :persons-no-contracts="personsNoContracts" @change="onMessageChange" :client-form="clientForm" />

                <div v-show="currentStep === 1" class="px-4 pb-4">
                    <CommunicationAttachments v-model="attachments" :disabled="saving" />
                </div>
            </div>
        </div>

        <div v-if="!loading && !savedCommunicationId"
            class="fixed right-0 bottom-0 z-[90] border-t border-gray-200 py-4 px-4 shadow-lg bg-[#FAE2DA]"
            style="width: calc(100% - 250px)">
            <div class="flex justify-between items-center">
                <button v-if="currentStep > 0" type="button" @click="previousStep"
                    class="button-secondary flex items-center gap-2">
                    <Icon name="fa6-solid:chevron-left" />
                    {{ $t('common.previous') }}
                </button>
                <div v-else></div>
                <div class="flex gap-3 ml-auto">
                    <button v-if="currentStep === 0 && !isOnlyElectronicInvoice" type="button"
                        @click="nextStep"
                        :disabled="!canGoToStep2 || clientForm.loadingClientData || messageCommunicationTypes.length === 0"
                        class="button-primary flex items-center gap-2">
                        {{ $t('common.next') }}
                        <Icon name="fa6-solid:chevron-right" />
                    </button>
                    <button v-if="currentStep === 0 && isOnlyElectronicInvoice" type="button" @click="save"
                        :disabled="saving || !canSaveFromStep1 || clientForm.loadingClientData"
                        class="button-primary flex items-center gap-2">
                        <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                            :class="{ 'animate-spin': saving }" />
                        {{ $t('common.save') }}
                    </button>
                    <button v-if="currentStep === 1" type="button" @click="save"
                        :disabled="saving || !clientForm.selectedPerson || !canGoToStep2"
                        class="button-primary flex items-center gap-2">
                        <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                            :class="{ 'animate-spin': saving }" />
                        {{ $t('common.save') }}
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
