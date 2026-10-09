<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import { DocumentSignStatus, DocumentSignStatusLabels, documentSignStatusColor, documentSignStatusCode } from '~/utils/document-sign';

const props = defineProps({
    contractId: {
        type: [Number, String],
        default: null
    },
    /** Id de la ContractRequest, usat mentre encara no existeix un contracte (flux d'alta). */
    contractRequestId: {
        type: [Number, String],
        default: null
    },
    contractFileId: {
        type: [Number, String],
        default: null
    },
    defaultName: {
        type: String,
        default: ''
    },
    defaultEmail: {
        type: String,
        default: ''
    },
    defaultPhone: {
        type: String,
        default: ''
    },
});

const { t } = useI18n();
const toast = useToast();
const { $DocumentSignApiService } = useNuxtApp();

const loading = ref(true);
const sending = ref(false);
const requesting = ref(false);
const resetting = ref(false);
const documentSigns = ref([]);
const showForm = ref(false);

const otp_name = ref('');
const otp_email = ref('');
const otp_phone = ref('');

/** Sempre agafem l'últim DocumentSign creat per aquest contracte. */
const currentSign = computed(() => {
    if (!documentSigns.value.length) return null;
    return [...documentSigns.value].sort((a, b) => b.id - a.id)[0];
});

const STATUS_PENDING = DocumentSignStatus.PENDING;
const STATUS_SENDED = DocumentSignStatus.SENDED;
const STATUS_SIGNED = DocumentSignStatus.SIGNED;
const STATUS_EXPIRED = DocumentSignStatus.EXPIRED;
const STATUS_ERROR = DocumentSignStatus.ERROR;

const currentStatus = computed(() => documentSignStatusCode(currentSign.value?.status));

/** Un cop `/send/` ha anat bé, el pas següent és sol·licitar el PDF, no tornar a enviar. */
const hasBeenSent = ref(false);

/** `status_display` arriba en anglès des de Django; l'etiqueta es tradueix pel codi. */
const statusLabel = (status) => {
    const code = documentSignStatusCode(status);
    return DocumentSignStatusLabels[code] ? t(DocumentSignStatusLabels[code]) : '';
};

const isBusy = computed(() => sending.value || requesting.value || resetting.value);

/** Només el document ja signat: l'URL del contracte original no compta. */
const signedDownloadUrl = computed(() => {
    if (!currentSign.value || currentStatus.value !== STATUS_SIGNED) return null;
    return currentSign.value.contract_file_signed_url
        || $DocumentSignApiService.getDownloadUrl(currentSign.value.id);
});

const canDownloadSigned = computed(() => currentStatus.value === STATUS_SIGNED && !!signedDownloadUrl.value);

/** Pas 2: demanar a Sign el PDF. Mai `/send/`. */
const canRequestSigned = computed(() => {
    if (!currentSign.value || canDownloadSigned.value) return false;
    const status = currentStatus.value;
    if (status === STATUS_ERROR) return false;
    return status === STATUS_SENDED || status === STATUS_EXPIRED || hasBeenSent.value;
});

const canSendFirstTime = computed(() => currentStatus.value === STATUS_PENDING && !hasBeenSent.value);

const downloadDocument = async () => {
    if (!signedDownloadUrl.value) return;
    await openAuthenticatedFileUrl(signedDownloadUrl.value, false);
};

const requestSigned = async () => {
    if (!currentSign.value) return;
    requesting.value = true;
    try {
        const result = await $DocumentSignApiService.requestSignedDocument(currentSign.value.id);
        await loadSigns();
        const status = currentStatus.value ?? documentSignStatusCode(result?.status);
        if (status === STATUS_SIGNED) {
            toast.success(t('contract_block.document_sign_retrieved'));
        } else {
            toast.info(t('contract_block.document_sign_not_ready'));
        }
    } catch (error) {
        console.error('Error sol·licitant el document signat:', error);
        await loadSigns();
    } finally {
        requesting.value = false;
    }
};

const resetSign = async () => {
    if (!currentSign.value) return;
    if (!confirm(t(currentStatus.value === STATUS_SIGNED
        ? 'confirmation_text_block.confirm_reset_document_sign_signed'
        : 'confirmation_text_block.confirm_reset_document_sign'))) return;
    resetting.value = true;
    try {
        await $DocumentSignApiService.doDelete({ id: currentSign.value.id });
        showForm.value = false;
        hasBeenSent.value = false;
        await loadSigns();
    } catch (error) {
        console.error('Error reiniciant la signatura OTP:', error);
    } finally {
        resetting.value = false;
    }
};

const loadSigns = async () => {
    if (!props.contractId && !props.contractRequestId) {
        loading.value = false;
        return;
    }
    loading.value = true;
    try {
        const res = props.contractId
            ? await $DocumentSignApiService.getByContract(props.contractId)
            : await $DocumentSignApiService.getByContractRequest(props.contractRequestId);
        documentSigns.value = res?.document_signs || [];
        const loaded = documentSignStatusCode(documentSigns.value.length
            ? [...documentSigns.value].sort((a, b) => b.id - a.id)[0]?.status
            : null);
        if (loaded === STATUS_SENDED || loaded === STATUS_SIGNED || loaded === STATUS_EXPIRED) {
            hasBeenSent.value = true;
        }
    } catch (error) {
        console.error('Error carregant DocumentSign:', error);
    } finally {
        loading.value = false;
    }
};

const resetForm = () => {
    otp_name.value = props.defaultName || '';
    otp_email.value = props.defaultEmail || '';
    otp_phone.value = props.defaultPhone || '';
};

const openForm = () => {
    resetForm();
    showForm.value = true;
};

const createAndSend = async () => {
    if (!otp_name.value || !otp_email.value) {
        toast.error(t('common.required_fields'));
        return;
    }
    sending.value = true;
    try {
        const created = await $DocumentSignApiService.save({
            ...(props.contractId ? { contract: props.contractId } : { contract_request: props.contractRequestId }),
            contract_file: props.contractFileId,
            otp_name: otp_name.value,
            otp_email: otp_email.value,
            otp_phone: otp_phone.value,
        });
        await $DocumentSignApiService.send(created.id);
        hasBeenSent.value = true;
        toast.success(t('contract_block.document_sign_sent'));
        showForm.value = false;
        await loadSigns();
    } catch (error) {
        console.error('Error enviant document a firmar:', error);
    } finally {
        sending.value = false;
    }
};

const retrySend = async (force = false) => {
    if (!currentSign.value) return;
    sending.value = true;
    try {
        await $DocumentSignApiService.send(currentSign.value.id, force);
        hasBeenSent.value = true;
        toast.success(t('contract_block.document_sign_sent'));
        await loadSigns();
    } catch (error) {
        console.error('Error reenviant document a firmar:', error);
    } finally {
        sending.value = false;
    }
};

watch([() => props.contractId, () => props.contractRequestId], () => {
    loadSigns();
});

onMounted(() => {
    loadSigns();
});

defineExpose({ refresh: loadSigns });
</script>

<template>
    <div v-if="!loading" class="mb-3">
        <div v-if="!contractId && !contractRequestId" class="text-xs text-slate-400 italic">
            {{ t('contract_block.document_sign_needs_contract') }}
        </div>

        <template v-else>
            <!-- Encara no s'ha iniciat cap petició de signatura -->
            <div v-if="!currentSign && !showForm" class="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-3">
                <p class="text-sm text-slate-600 flex items-start gap-2 min-w-0">
                    <Icon name="fa6-solid:signature" class="text-slate-400 mt-0.5 shrink-0" />
                    <span>{{ t('contract_block.document_sign_not_requested') }}</span>
                </p>
                <button @click="openForm" class="button-default-xs w-full justify-center">
                    <Icon name="fa6-solid:pen-nib" class="mr-1" />
                    {{ t('contract_block.document_sign_otp') }}
                </button>
            </div>

            <!-- Formulari per iniciar la signatura OTP -->
            <div v-else-if="showForm" class="bg-sky-50 border border-sky-200 rounded-lg p-3 space-y-2">
                <div class="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                    {{ t('contract_block.document_sign_otp') }}
                </div>
                <input v-model="otp_name" type="text" :placeholder="t('common.name')"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2" />
                <input v-model="otp_email" type="email" :placeholder="t('common.email')"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2" />
                <input v-model="otp_phone" type="text" :placeholder="t('common.tlf')"
                    class="w-full text-sm border border-slate-300 rounded-md px-3 py-2" />
                <div class="flex justify-end gap-2 pt-1">
                    <button @click="showForm = false" :disabled="isBusy" class="button-default-xs">
                        {{ t('common.cancel') }}
                    </button>
                    <button @click="createAndSend" :disabled="isBusy" class="button-secondary flex items-center gap-2">
                        <Icon :name="sending ? 'fa6-solid:spinner' : 'fa6-solid:paper-plane'" :class="{ 'animate-spin': sending }" />
                        {{ t('common.send') }}
                    </button>
                </div>
            </div>

            <!-- Caixa d'estat de la signatura OTP ja iniciada -->
            <div v-else class="rounded-lg border p-3 space-y-3" :class="{
                'bg-amber-50 border-amber-200': currentStatus === STATUS_SENDED,
                'bg-emerald-50 border-emerald-200': currentStatus === STATUS_SIGNED,
                'bg-rose-50 border-rose-200': currentStatus === STATUS_ERROR,
                'bg-yellow-50 border-yellow-200': currentStatus === STATUS_EXPIRED,
                'bg-slate-50 border-slate-200': currentStatus === STATUS_PENDING,
            }">
                <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0">
                        <div class="flex items-center gap-2 flex-wrap">
                            <Icon name="fa6-solid:signature" class="shrink-0" :class="{
                                'text-amber-500': currentStatus === STATUS_SENDED,
                                'text-emerald-500': currentStatus === STATUS_SIGNED,
                                'text-rose-500': currentStatus === STATUS_ERROR,
                                'text-yellow-500': currentStatus === STATUS_EXPIRED,
                                'text-slate-400': currentStatus === STATUS_PENDING,
                            }" />
                            <span class="text-xs font-semibold text-slate-600 uppercase tracking-wide">
                                {{ t('contract_block.document_sign_otp') }}
                            </span>
                            <AtomsColorBadge :value="statusLabel(currentSign.status)" :color="documentSignStatusColor(currentSign.status)" />
                        </div>
                        <p class="mt-2 text-sm text-slate-800 truncate" :title="currentSign.otp_name">
                            {{ currentSign.otp_name }}
                        </p>
                        <p class="text-xs text-slate-500 truncate" :title="currentSign.otp_email">
                            {{ currentSign.otp_email }}
                        </p>
                    </div>
                    <button @click="loadSigns" :title="t('common.refresh')" :disabled="isBusy"
                        class="text-slate-400 hover:text-slate-600 disabled:opacity-50 shrink-0 p-1">
                        <Icon name="fa6-solid:rotate" />
                    </button>
                </div>

                <div v-if="currentStatus === STATUS_ERROR && currentSign.error_report"
                    class="text-xs text-rose-700 bg-rose-100 rounded px-2 py-1 break-words">
                    {{ currentSign.error_report }}
                </div>

                <div class="flex flex-col gap-2">
                    <button v-if="canRequestSigned" @click="requestSigned" :disabled="isBusy"
                        class="button-default-xs w-full justify-center">
                        <Icon :name="requesting ? 'fa6-solid:spinner' : 'fa6-solid:cloud-arrow-down'"
                            :class="{ 'animate-spin': requesting }" class="mr-1" />
                        {{ t('contract_block.document_sign_request_signed') }}
                    </button>
                    <button v-if="canDownloadSigned" @click="downloadDocument"
                        class="button-default-xs w-full justify-center">
                        <Icon name="fa6-solid:download" class="mr-1" />
                        {{ t('common.download') }}
                    </button>
                    <button v-if="canSendFirstTime" @click="retrySend(false)" :disabled="isBusy"
                        class="button-default-xs w-full justify-center">
                        <Icon :name="sending ? 'fa6-solid:spinner' : 'fa6-solid:paper-plane'"
                            :class="{ 'animate-spin': sending }" class="mr-1" />
                        {{ t('common.send') }}
                    </button>
                    <button v-if="currentStatus === STATUS_ERROR" @click="retrySend(true)" :disabled="isBusy"
                        class="button-default-xs w-full justify-center">
                        <Icon :name="sending ? 'fa6-solid:spinner' : 'fa6-solid:rotate-right'"
                            :class="{ 'animate-spin': sending }" class="mr-1" />
                        {{ t('common.retry') }}
                    </button>
                    <button @click="resetSign" :disabled="isBusy"
                        class="button-default-xs w-full justify-center"
                        :title="t('common.reset')">
                        <Icon :name="resetting ? 'fa6-solid:spinner' : 'fa6-solid:rotate-left'"
                            :class="{ 'animate-spin': resetting }" class="mr-1" />
                        {{ t('common.reset') }}
                    </button>
                </div>
            </div>
        </template>
    </div>
</template>
