<script setup>
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';
import AddNewCall from '~/components/molecules/AddNewCall.vue';

const { t } = useI18n();
const props = defineProps({
    contract_id: Number,
    person_id: Number,
    incident_id: Number,
    contract: {
        type: Object,
        default: null
    },
    incident: {
        type: Object,
        default: null
    },
    reload: Boolean,
    can_add: {
        type: Boolean,
        default: true
    },
    max_height: {
        type: String,
        default: '40vh'
    },
    exportable: {
        type: Boolean,
        default: true
    },
    exportFileName: {
        type: String,
        default: 'call_register'
    },
});

const emit = defineEmits(['update:count']);
const { $CallRegisterApiService } = useNuxtApp();

const loading = ref(true);

// Només s'enllacen adreces web (evita enllaços javascript: o similars)
const isWebUrl = (url) => /^https?:\/\//i.test(url || '');
const localData = ref([]);
const new_call = ref(null);

const formatDuration = (seconds) => {
    if (seconds == null || seconds < 0) return '';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
};

const exportColumns = computed(() => [
    { header: t('common.name'), value: (row) => row.person_name, key: 'person_name' },
    { header: t('common.identification'), value: (row) => row.person_token, key: 'person_token' },
    { header: t('contract'), value: (row) => row.contract_token, key: 'contract' },
    { header: t('incident'), value: (row) => row.incident_token, key: 'incident' },
    { header: t('common.tlf'), value: (row) => row.phone, key: 'phone' },
    { header: t('common.email'), value: (row) => row.email, key: 'email' },
    { header: t('contract_block.channel'), value: (row) => row.channel, key: 'channel' },
    { header: t('common.date'), value: (row) => row.time_call ? formatTime(row.time_call) : '', key: 'time_call' },
    { header: t('contract_block.call_duration'), value: (row) => formatDuration(row.call_duration_seconds), key: 'duration' },
    { header: t('user'), value: (row) => row.user?.username },
    { header: t('call_block.direction'), value: (row) => row.direction === 'inbound' ? t('call_block.inbound') : t('call_block.outbound'), key: 'direction' },
    { header: t('incident'), value: (row) => row.incident_token, key: 'incident_token' },
    { header: t('call_block.callback_requested'), value: (row) => row.callback_requested ? t('common.yes') : t('common.no'), key: 'callback_requested' },
    { header: t('contract_block.has_answered'), value: (row) => row.answered ? t('common.yes') : t('common.no'), key: 'answered' },
    { header: t('contract_block.abandoned_call'), value: (row) => row.abandoned_call ? t('common.yes') : t('common.no'), key: 'abandoned_call' },
    { header: t('contract_block.contacted_by_client'), value: (row) => row.contacted_by_client ? t('common.yes') : t('common.no'), key: 'contacted_by_client' },
    { header: t('common.comment'), value: (row) => row.comment, key: 'comment' },
]);

const getData = async () => {
    try {
        const response = await $CallRegisterApiService.getAll(
            '',
            1,
            props.contract_id || props.contract?.id || null,
            props.person_id || null,
            props.incident_id || props.incident?.id || null
        );
        localData.value = response.results;
        emit('update:count', localData.value.length);
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
    }
};

const openAddCall = () => {
    new_call.value = {
        mode: 'manual',
        contract: props.contract || (props.contract_id ? { id: props.contract_id } : null),
        incident: props.incident || (props.incident_id ? { id: props.incident_id } : null),
        contact: null,
    };
};

const handleNewCall = async () => {
    new_call.value = null;
    loading.value = true;
    await getData();
};

onMounted(async () => {
    await getData();
});

watch(() => props.reload, () => {
    getData();
});

</script>

<template>
    <div class="mt-2 overflow-y-auto" :style="{ maxHeight: props.max_height }">
        <!-- <div v-if="can_add" class="flex justify-end mb-2">
            <button type="button" @click="openAddCall" class="button-primary !px-2.5 !py-1 text-xs">
                <Icon name="fa6-solid:phone" class="display-inline mr-1" />
                {{ t('contract_block.add_call') }}
            </button>
        </div> -->

        <div v-if="loading" class="py-4">
            <AppLoading :text="$t('common.loading')" :size="40" />
        </div>

        <div v-else class="space-y-2">
            <div class="flex justify-end mb-1 gap-x-2">
                <button v-if="can_add" type="button" @click="openAddCall"
                    class="button-primary flex items-center gap-x-1">
                    <Icon name="fa6-solid:phone" class="display-inline mr-1" />
                    {{ t('contract_block.add_call') }}
                </button>
                <AtomsDownloadXlsxButton v-if="exportable && localData?.length > 0" :rows="localData"
                    :columns="exportColumns" :file-name="exportFileName" />
            </div>
            <div v-for="item in localData" :key="item.id"
                class="bg-white border-b border-slate-200 rounded-lg hover:bg-slate-50 transition-all duration-200 overflow-hidden">

                <div class="px-4 py-2">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1 flex-wrap">
                                <h3 v-if="item.person_name" class="font-semibold text-slate-900 text-sm truncate">
                                    {{ item.person_name }}
                                </h3>
                                <span v-if="item.person_token"
                                    class="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                                    {{ item.person_token }}
                                </span>
                                <span v-if="item.channel"
                                    class="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                                    {{ item.channel === 'EMAIL' ? t('contract_block.channel_email') :
                                        t('contract_block.channel_phone') }}
                                </span>
                                <span v-if="item.contacted_by_client"
                                    class="text-xs text-sky-700 bg-sky-100 px-2 py-0.5 rounded-full">
                                    {{ t('contract_block.contacted_by_client') }}
                                </span>
                            </div>
                            <div v-if="item.contract_token && !props.contract_id && !props.contract?.id"
                                class="flex items-center gap-2 text-slate-600">
                                <span class="text-sm font-mono">
                                    {{ t('contract') }}: {{ item.contract_token }}</span>
                            </div>
                            <div v-if="item.incident && !props.incident_id && !props.incident?.id"
                                class="flex items-center gap-2 text-slate-600">
                                <span class="text-sm font-mono">{{ t('incident') }}:</span>
                                <AtomsRedirectButton :id="item.incident" :path="'/incident/incidents/'">
                                    <template #text>
                                        <span class="text-sm font-mono">
                                            {{ item.incident_token }}{{ item.incident_name ? ` - ${item.incident_name}`
                                                : '' }}
                                        </span>
                                    </template>
                                </AtomsRedirectButton>
                            </div>
                            <div v-if="item.phone" class="flex items-center gap-2 text-slate-600">
                                <Icon name="fa6-solid:phone" class="text-xs" />
                                <span class="text-sm font-mono">{{ item.phone }}</span>
                            </div>
                            <div v-if="item.email" class="flex items-center gap-2 text-slate-600">
                                <Icon name="fa6-solid:envelope" class="text-xs" />
                                <span class="text-sm font-mono">{{ item.email }}</span>
                            </div>
                            <div v-if="item.transfered_to || item.transfered_to_name"
                                class="text-xs text-slate-500 mt-1">
                                {{ t('contract_block.transfered_to') }}:
                                {{ item.transfered_to?.username || item.transfered_to_name }}
                            </div>
                            <div v-if="item.transfered_from || item.transfered_from_name"
                                class="text-xs text-slate-500">
                                {{ t('contract_block.transfered_from') }}:
                                {{ item.transfered_from?.username || item.transfered_from_name }}
                            </div>
                        </div>

                        <div class="flex flex-col items-end gap-2 flex-shrink-0">
                            <div class="flex items-center gap-1.5 text-slate-600">
                                <Icon name="fa6-solid:clock" class="text-xs" />
                                <span class="text-xs font-medium">{{ formatTime(item.time_call) }}</span>
                                <template v-if="item.user">
                                    -
                                    <span class="text-xs font-medium">{{ item.user.username }}</span>
                                </template>
                            </div>
                            <div v-if="item.call_duration_seconds != null" class="text-xs text-slate-500">
                                {{ t('contract_block.call_duration') }}: {{ formatDuration(item.call_duration_seconds)
                                }}
                            </div>
                            <div v-if="item.wait_time != null" class="text-xs text-slate-500">
                                {{ t('contract_block.wait_time') }}: {{ item.wait_time }} {{ t('contract_block.minutes')
                                }}
                            </div>
                            <div class="flex items-center gap-3">
                                <div class="relative">
                                    <input v-model="item.answered" type="checkbox" :id="`answered-${item.id}`"
                                        class="sr-only cursor-default" :disabled="true" />
                                    <label :for="`answered-${item.id}`"
                                        class="flex items-center gap-1.5 cursor-default">
                                        <div class="w-4 h-4 border rounded-sm flex items-center justify-center text-slate-500"
                                            :class="item.answered ? 'bg-green-500 border-green-500' : 'bg-white border-slate-300 '">
                                            <Icon v-if="item.answered" name="fa6-solid:check"
                                                class="text-white text-xs" />
                                        </div>
                                        <span class="text-xs text-slate-400 font-medium">
                                            {{ t('contract_block.has_answered') }}
                                        </span>
                                    </label>
                                </div>
                                <div v-if="item.abandoned_call" class="text-xs text-amber-600 font-medium">
                                    {{ t('contract_block.abandoned_call') }}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-wrap gap-1 mt-1">
                        <span v-if="item.direction === 'inbound'" class="text-xs bg-sky-100 text-sky-700 px-2 py-0.5 rounded-full">{{ t('call_block.inbound') }}</span>
                        <span v-if="item.incident_token && !props.incident_id" class="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full">{{ t('incident') }}: {{ item.incident_token }}</span>
                        <span v-if="item.callback_requested" class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{{ t('call_block.callback_requested') }}</span>
                        <span v-if="item.supervisor_requested" class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{{ t('call_block.supervisor_requested') }}</span>
                        <span v-if="item.transferred_to" class="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full">{{ t('call_block.transferred_to') }}: {{ item.transferred_to }}</span>
                        <a v-if="isWebUrl(item.recording_url)" :href="item.recording_url" target="_blank" class="text-xs text-sky-500 underline">{{ t('call_block.recording') }}</a>
                    </div>
                    <div v-if="item.comment" class="mt-2 px-2 py-1 bg-slate-50 rounded-md">
                        <div class="flex items-center gap-2">
                            <Icon name="fa6-solid:comment" class="text-slate-400 text-xs" />
                            <span class="text-sm text-slate-700 leading-relaxed">{{ item.comment }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="localData.length === 0">
                <div class="footering text-slate-500 p-2">
                    {{ t('common.no_records') }}
                </div>
            </div>
        </div>

        <div v-if="new_call" class="fixed inset-0 z-50 flex items-center justify-center">
            <div class="relative z-10 bg-white rounded-lg shadow-xl p-4 w-full max-w-3xl mx-4">
                <AddNewCall :data="new_call" @exit="handleNewCall" />
            </div>
            <div class="fixed inset-0 bg-black/40" @click="handleNewCall"></div>
        </div>
    </div>
</template>
