<script setup>
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import DailyDocumentTemplateDetail from '../molecules/DailyDocumentTemplateDetail.vue';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import { formatDate, formatDateTime } from '~/utils/date';
import { useSidebarStore } from '~/stores/useNavSideBar';

const { t } = useI18n();
const sidebarStore = useSidebarStore();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
    id: Number,
    isSubRegion: false,
    isSubRegionOpen: Boolean
});
const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);
const { $ReportsApiService, $DailyDocumentApiService, $DocumentManagerApiService } = useNuxtApp();

const pending = ref(false);
const regenerating_task_id = ref(null);
const error = ref(null);
const data = ref(null);
const cancelling = ref(false);
const openCancelModal = ref(false);
const cancelObservation = ref('');
const completedAt = ref(new Date(Date.now()).toISOString().split('T')[0]);

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);


const documentId = computed(() => {
    const doc = data.value?.document;
    if (!doc) return null;
    return typeof doc === 'object' ? doc.id : doc;
});

const documentName = computed(() => {
    const doc = data.value?.document;
    if (doc && typeof doc === 'object') return doc.document_name || data.value?.document_name || null;
    return data.value?.document_name || null;
});

const hasCreationError = computed(() => !documentId.value && Boolean(data.value?.creation_error));

const isCancelled = computed(() => Boolean(
    data.value?.cancelled_at || data.value?.cancelled_by || data.value?.cancelled_observation
));

const getData = async (load = true) => {
    pending.value = load;
    error.value = null;
    try {
        data.value = await $DailyDocumentApiService.getDetail(props.id);
        regenerating_task_id.value = data.value?.regenerating_task_id ?? null;
    } catch (err) {
        console.error(err);
        error.value = err;
        toast.error(t('error_block.daily_documents_not_found'));
    } finally {
        pending.value = false;
    }
};

const getTaskData = async () => {
    await getData(false);
    emit('changed');
};

const regenerateDocument = async () => {
    try {
        const response = await $DailyDocumentApiService.regenerate(props.id);
        if (response) {
            toast.success(t('success_block.daily_document_regenerated'));
            regenerating_task_id.value = response.regenerating_task_id ?? response.task_id ?? null;
        }
    } catch (err) {
        console.error(err);
        toast.error(t('error_block.remake_daily_document_failed'));
        regenerating_task_id.value = null;
    }
};

const canSubmitCancel = computed(() => Boolean(cancelObservation.value?.trim()) && !cancelling.value);

const cancelObject = () => {
    if (isCancelled.value || cancelling.value) return;
    cancelObservation.value = '';
    openCancelModal.value = true;
};

const closeCancelModal = () => {
    if (cancelling.value) return;
    openCancelModal.value = false;
    cancelObservation.value = '';
};

const confirmCancel = async () => {
    const observation = cancelObservation.value.trim();
    if (!observation) {
        toast.warning(t('warning_block.no_cancel_observation_warning'));
        return;
    }

    cancelling.value = true;
    try {
        const payload = {
            id: props.id,
            cancelled_observation: observation,
        }

        const response = await $DailyDocumentApiService.save(payload);
        if (response) {
            toast.success(t('success_block.daily_document_cancelled'));
            openCancelModal.value = false;
            cancelObservation.value = '';
            data.value = response;
            reloadSideBar();
            emit('changed');
        }
    } catch (err) {
        console.error(err);
        toast.error(t('error_block.cancel_daily_document_failed'));
    } finally {
        cancelling.value = false;
        openCancelModal.value = false;
        cancelObservation.value = '';
    }
};

const printDocument = async (doc_id) => {
    if (!doc_id) {
        toast.error(t('error_block.no_document_available'));
        return;
    }
    try {
        const document_file = await $DocumentManagerApiService.getDetail(doc_id);
        const file = await $DocumentManagerApiService.viewDocument(doc_id);
        const link = document.createElement('a');
        const file_url = URL.createObjectURL(file);
        link.href = file_url;
        link.download = document_file.document_name || documentName.value || 'document';

        link.click();

        setTimeout(() => {
            window.URL.revokeObjectURL(file_url);
        }, 250);
    } catch (err) {
        console.error(err);
        toast.error(t('error_block.download_failed'));
    }
};

const sendDocument = async () => {
    if (!completedAt.value) {
        toast.warning(t('warning_block.no_send_date_warning'));
        return;
    }
    if (!confirm(t('confirmation_text_block.confirm_send_daily_document'))) return;

    try {
        const payload = {
            id: props.id,
            is_completed: true,
            completed_at: completedAt.value,
        }
        const response = await $DailyDocumentApiService.save(payload);
        if (response) {
            toast.success(t('success_block.daily_document_sent'));
            data.value = response;
            reloadSideBar();
            emit('changed');
        }
    } catch (err) {
        console.error(err);
        toast.error(t('error_block.send_daily_document_failed'));
    }

};

const reloadSideBar = async () => {
    try {
        let newDailyDocuments = await $DailyDocumentApiService.checkNewDailyDocuments();
        sidebarStore.newDailyDocumentsFound(newDailyDocuments);
    } catch (err) {
        console.error(err);
    }
}

const closeSubRegion = function () {
    SubRegion.value = false;
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
    emit('show-subregion', false);
}
const showSubRegion = function () {
    SubRegion.value = true;
    emit('show-subregion', true);
}

const showDetail = function (component, id) {
    showRegionDetailComponent.value = component
    regionDetailId.value = id;
    showSubRegion();
}

onMounted(async () => {
    objectPermissions.value = await checkPermission($ReportsApiService);
    if (!objectPermissions.value.can_view) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
    await getData();
});

watch(() => props.id, () => {
    if (!objectPermissions.value?.can_view) {
        emit('close-subregion');
        return
    }
    getData();
});

</script>

<template>
    <div class="region__content h-full" @click.stop>
        <div v-if="pending">
            <p>{{ $t('common.loading') }}...</p>
        </div>
        <div v-else-if="error">
            <p>Error: {{ error.message }}</p>
            <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
                    }}</button></p>
        </div>
        <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
            :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48%]': SubRegion }">
            <div v-if="openCancelModal" class="fixed inset-0 z-40 flex items-center justify-center overflow-y-auto"
                @click="closeCancelModal">
                <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative" @click.stop>
                    <button type="button" @click="closeCancelModal"
                        class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
                        <Icon name="fa6-solid:xmark" class="text-xl" />
                    </button>
                    <div>
                        <label class="block font-medium text-slate-500">{{ $t('common.observation') }}</label>
                        <p class="text-sm text-slate-500 mt-1">{{
                            t('confirmation_text_block.confirm_cancel_daily_document') }}
                        </p>
                        <div class="py-4 px-1 rounded-lg text-left">
                            <textarea v-model="cancelObservation" rows="3" :placeholder="t('common.write_comment')"
                                class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
                        </div>
                    </div>
                    <div class="flex justify-end">
                        <button class="button-primary flex items-center justify-center gap-2" @click="confirmCancel"
                            :disabled="!canSubmitCancel">
                            <Icon v-if="cancelling" name="fa6-solid:spinner" class="animate-spin" />
                            <span v-if="!cancelling">{{ $t('common.save') }}</span>
                            <span v-else>{{ $t('common.processing') }}</span>
                        </button>
                    </div>
                </div>
            </div>
            <div v-if="openCancelModal"
                class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-20 flex items-center justify-center">
            </div>

            <div class="flex justify-between relative mb-3">
                <H1Region class="">{{ $t('statistics_block.daily_document') }}</H1Region>
                <OptionsDropdown v-if="objectPermissions?.can_change && !data.is_completed && !isCancelled"
                    id="CommunicationRegionOptions">
                    <DropdownOption v-if="!isCancelled" :disabled="hasCreationError || regenerating_task_id"
                        :name="`${t('common.cancel')}`" @click="cancelObject()">
                        <div class="flex items-center gap-x-2">
                            <Icon name="fa6-solid:x" class="display-inline" />
                            {{ t('common.cancel') }}
                        </div>
                    </DropdownOption>
                    <DropdownOption :name="`${t('common.regenerate')}`" @click="regenerateDocument()"
                        :disabled="regenerating_task_id">
                        <div class="flex items-center gap-x-2">
                            <Icon name="fa6-solid:rotate-right" class="display-inline" />
                            {{ t('common.regenerate') }}
                        </div>
                    </DropdownOption>
                </OptionsDropdown>
            </div>

            <div v-if="data" id="item_data" :data-rel=id>
                <div class="flex justify-between items-start gap-x-2 mb-3">
                    <label class="inline-block truncate text-slate-600">
                        {{ data.name }} ({{ formatDate(data.document_date) }})
                    </label>
                    <div>
                        <FieldDetail v-if="data.due_date" :label="t('common.due_date')" :value="formatDate(data.due_date)" />
                        <FieldDetail :label="t('common.status')">
                            <AtomsColorBadge :value="data.status?.name" :color="data.status?.color" />
                        </FieldDetail>
                    </div>
                </div>

                <div v-if="isCancelled"
                    class="flex items-start gap-2 p-3 pb-1 bg-slate-50 rounded border border-slate-300 mb-3">
                    <!-- <Icon name="fa6-solid:ban" class="text-slate-500 mt-0.5 shrink-0" /> -->
                    <div class="min-w-0 flex-1 flex items-center gap-x-2 grid grid-cols-2">
                        <!-- <p class="text-slate-700 font-medium text-sm mb-2 col-span-2">{{
                            t('statistics_block.daily_document_cancelled') }}</p> -->
                        <FieldDetail v-if="data.cancelled_at" :label="t('common.cancelled_at')"
                            :value="formatDateTime(data.cancelled_at)" />
                        <FieldDetail v-if="data.cancelled_by" :label="t('common.cancelled_by')"
                            :value="data.cancelled_by?.username || 'Admin'" />
                        <FieldDetail v-if="data.cancelled_observation" class="col-span-2"
                        :label="t('common.observation')"
                            :value="data.cancelled_observation" />
                    </div>
                </div>

                <div v-if="hasCreationError"
                    class="flex items-start gap-2 py-1 px-3 bg-red-50 rounded border border-red-500 mb-3">
                    <Icon name="fa6-solid:triangle-exclamation" class="text-red-500 mt-0.5 shrink-0" />
                    <div class="min-w-0 flex-1">
                        <p class="text-red-700 font-bold text-sm"> {{ t('common.error') }}: {{ data.creation_error }}
                        </p>
                        <p class="text-red-600 text-xs mt-1">{{ t('statistics_block.creation_error_help') }}</p>
                    </div>
                </div>

                <div v-if="documentId || regenerating_task_id"
                    class="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-3 py-2.5 mb-3">
                    <div class="min-w-0">
                        <span class="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {{ t('common.doc') }}
                        </span>
                        <p class="truncate text-sm font-semibold text-slate-900" :title="documentName">
                            {{ documentName || '-' }}
                        </p>
                    </div>
                    <AtomsProcessColorBadge v-if="regenerating_task_id" class="py-2 shrink-0" @refresh="getTaskData"
                        :value="`${t('common.loading')}`" :color="'blue'" :taskId="regenerating_task_id" />
                    <button v-else-if="documentId" type="button" @click="printDocument(documentId)"
                        class="w-8 h-8 rounded-full border border-orange-500 text-orange-500 bg-orange-50 hover:bg-orange-100 shrink-0"
                        :title="t('common.download')" :disabled="isCancelled">
                        <Icon name="fa6-solid:download" class="m-auto w-3.5 h-3.5" />
                    </button>
                </div>
                <div v-if="!hasCreationError">
                    <div v-if="!data.completed_at && !isCancelled" class="flex items-end justify-start gap-2 mb-3">
                        <AtomsInputDate v-model="completedAt" :label="t('common.send_date')" />
                        <button class="button-primary mb-4" :disabled="!completedAt || regenerating_task_id"
                            @click="sendDocument">
                            {{ t('common.send') }}
                        </button>
                    </div>

                    <section v-else-if="data.completed_at" class="grid grid-cols-2 mb-3">
                        <FieldDetail :label="t('common.completion_date')" :value="formatDate(data.completed_at)" />
                        <FieldDetail v-if="data.completed_by" :label="t('common.completed_by')"
                            :value="data.completed_by?.username || 'Admin'" />
                    </section>
                </div>


                <!-- <hr class="my-3"> -->
                <fieldset v-if="data.template" id="setup__box"
                    class="relative rounded-md border border-slate-200 p-3 mt-10">
                    <legend class="px-3 font-semibold bg-white shadow">{{ t('common.template') }}</legend>
                    <DailyDocumentTemplateDetail :id="data.template.id" :data="data.template"
                        @show-detail="showDetail" />
                </fieldset>
            </div>
        </div>

        <div v-if="SubRegion" role="region" id="subregion"
            class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48%] z-10"
            :class="{
                'translate-x-0': SubRegion,
                'translate-x-full': !SubRegion,
            }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">

            </div>
        </div>
    </div>

</template>
