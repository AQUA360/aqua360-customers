<script setup>
import { useI18n } from 'vue-i18n';
import AppLoading from '../atoms/AppLoading.vue';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';
import AddNewCommunicationClientData from '~/components/organisms/AddNewCommunicationClientData.vue';
import AddNewCommunicationMessageEdit from '~/components/organisms/AddNewCommunicationMessageEdit.vue';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const { $CommunicationApiService } = useNuxtApp();

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
        };
        const result = await $CommunicationApiService.save(save_data);
        if (result) {
            await navigateTo('/communication/communications/');
        }
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
    }
};

onMounted(() => {
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

        <div v-else>
            <WizardStatusNav :steps="wizardSteps" :current-step="currentStep" :max-step="maxStep" disabled
                :show-description="false" />

            <div class="border border-gray-300 rounded-b bg-white">
                <AddNewCommunicationClientData v-show="currentStep === 0" ref="clientDataRef"
                    @change="onClientDataChange" @ready="onClientDataReady" />

                <AddNewCommunicationMessageEdit v-show="currentStep === 1" ref="messageEditRef"
                    :selected-communication-types="clientForm.selectedCommunicationTypes ?? []"
                    :persons-no-contracts="personsNoContracts" @change="onMessageChange" :client-form="clientForm" />
            </div>
        </div>

        <div v-if="!loading"
            class="fixed right-0 bottom-0 z-[9999] border-t border-gray-200 py-4 px-4 shadow-lg bg-[#FAE2DA] z-40"
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
